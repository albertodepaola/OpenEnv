# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Subprocess-based executor with resource limits and screenshot support.

This module provides a subprocess-based executor backend that executes Python
code in isolated subprocesses with resource limits. Security relies on:
1. Subprocess resource limits (CPU, memory, processes)
2. Container hardening (when running in Docker)

This is an alternative to RestrictedPython that provides full Python
compatibility - all Python syntax works naturally without transformation.

Key features:
- Implements ExecutorBackend interface
- Resource limits via setrlimit (CPU, memory, processes)
- Screenshot capture support via ImageMagick
- Minimal environment variable exposure
- Timeout enforcement
"""

from __future__ import annotations

import base64
import logging
import os
import resource
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional

from openenv.core.env_server.types import CodeExecResult

from .executor_backend import ExecutorBackend

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


@dataclass
class ResourceLimits:
    """Resource limits for subprocess execution.

    These limits are applied via setrlimit in the subprocess.
    They provide defense-in-depth alongside container restrictions.
    """

    cpu_seconds: int = 30
    """Max CPU time in seconds."""

    memory_bytes: int = 512 * 1024 * 1024  # 512MB
    """Max virtual memory (address space) in bytes."""

    max_processes: int = 50
    """Max number of subprocesses/threads. Allows tkinter threading while limiting fork bombs."""

    max_file_size: int = 10 * 1024 * 1024  # 10MB
    """Max file size that can be created."""

    max_open_files: int = 64
    """Max number of open file descriptors."""


@dataclass
class ExecutionConfig:
    """Configuration for secure code execution."""

    limits: ResourceLimits = field(default_factory=ResourceLimits)
    """Resource limits to apply."""

    timeout: int = 15
    """Timeout in seconds for subprocess execution (wall clock time).

    This is the maximum wall clock time for code execution. Set lower than
    the WebSocket client timeout (60s) to ensure responses are returned.

    For UI animations that run forever (e.g., tkinter mainloop), this determines
    how long frame capture continues before the process is terminated.

    Note: This is different from RLIMIT_CPU which limits actual CPU time consumed.
    Event-driven code (like tkinter) may use little CPU time but run for long
    wall clock duration, so this timeout ensures termination.
    """

    render_timeout: float = 0.5
    """Time to wait for UI rendering before screenshot capture."""

    allowed_env_vars: list[str] = field(
        default_factory=lambda: ["DISPLAY", "HOME", "PATH"]
    )
    """Environment variables to pass through to subprocess."""


def _set_resource_limits(limits: ResourceLimits) -> None:
    """Apply resource limits to current process.

    This function is called via preexec_fn in the subprocess,
    so it runs in the child process before exec().

    Args:
        limits: ResourceLimits configuration to apply
    """
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (limits.cpu_seconds, limits.cpu_seconds))
    except (ValueError, resource.error) as e:
        logger.warning(f"Failed to set RLIMIT_CPU: {e}")

    try:
        resource.setrlimit(resource.RLIMIT_AS, (limits.memory_bytes, limits.memory_bytes))
    except (ValueError, resource.error) as e:
        logger.warning(f"Failed to set RLIMIT_AS: {e}")

    try:
        resource.setrlimit(
            resource.RLIMIT_NPROC, (limits.max_processes, limits.max_processes)
        )
    except (ValueError, resource.error) as e:
        logger.warning(f"Failed to set RLIMIT_NPROC: {e}")

    try:
        resource.setrlimit(
            resource.RLIMIT_FSIZE, (limits.max_file_size, limits.max_file_size)
        )
    except (ValueError, resource.error) as e:
        logger.warning(f"Failed to set RLIMIT_FSIZE: {e}")

    try:
        resource.setrlimit(
            resource.RLIMIT_NOFILE, (limits.max_open_files, limits.max_open_files)
        )
    except (ValueError, resource.error) as e:
        logger.warning(f"Failed to set RLIMIT_NOFILE: {e}")


class SubprocessExecutor(ExecutorBackend):
    """Subprocess-based executor with resource limits and screenshot support.

    This executor runs Python code in isolated subprocesses with resource
    limits applied. It provides full Python compatibility since code runs
    in a standard Python interpreter without AST transformation.

    Security Model:
    - Subprocess resource limits (CPU, memory, processes, files)
    - Timeout enforcement
    - Minimal environment variables
    - Container hardening (external to this class)

    The container running this executor should be hardened with:
    - --cap-drop=ALL
    - --security-opt=no-new-privileges
    - --network=none (or restricted)
    - --read-only with tmpfs for /tmp
    - --user=1000:1000 (non-root)
    - --memory and --pids-limit

    Example:
        >>> executor = SubprocessExecutor()
        >>> result = executor.run("print('Hello, World!')")
        >>> print(result.stdout)
        Hello, World!
    """

    def __init__(self, config: Optional[ExecutionConfig] = None):
        """Initialize the subprocess executor.

        Args:
            config: Execution configuration. If None, uses defaults.
        """
        self._config = config or ExecutionConfig()
        self._captured_screenshot: Optional[str] = None
        self._captured_frames: List[str] = []

    def _create_safe_env(self) -> dict[str, str]:
        """Create minimal environment for subprocess.

        Only passes through explicitly allowed environment variables
        to reduce information leakage.

        Returns:
            Dictionary of environment variables for subprocess
        """
        env = {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
        }

        for var in self._config.allowed_env_vars:
            if var in os.environ:
                env[var] = os.environ[var]

        return env

    def _write_temp_file(self, code: str) -> str:
        """Write code to temporary file.

        Using a temp file avoids shell injection risks that could occur
        with python -c "...".

        Args:
            code: Python code to write

        Returns:
            Path to temporary file
        """
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            dir="/tmp",
        ) as f:
            f.write(code)
            return f.name

    def _execute_subprocess(self, script_path: str) -> CodeExecResult:
        """Execute script in resource-limited subprocess.

        Args:
            script_path: Path to Python script to execute

        Returns:
            CodeExecResult with stdout, stderr, and exit code.

        Exit Code Semantics:
            - 0: Success
            - 1-127: Code error (exception, syntax error, etc.)
            - 124: Python subprocess timeout (configurable)
            - 137: OOM killer (128 + SIGKILL)
            - -9: Process killed by SIGKILL (often RLIMIT_CPU exceeded)
            - -24: SIGXCPU (CPU time soft limit exceeded)

        Note:
            Negative exit codes indicate the process was killed by a signal.
            The absolute value is the signal number. Common cases:
            - -9 (SIGKILL): Hard kill, often from RLIMIT_CPU
            - -24 (SIGXCPU): CPU time limit exceeded
            - -25 (SIGXFSZ): File size limit exceeded

            When these occur, captured frames are still returned - the
            frame capture runs in a separate thread and is not affected
            by the subprocess termination.
        """
        limits = self._config.limits

        def apply_limits() -> None:
            _set_resource_limits(limits)

        try:
            result = subprocess.run(
                ["python", script_path],
                capture_output=True,
                timeout=self._config.timeout,
                env=self._create_safe_env(),
                cwd="/tmp",
                preexec_fn=apply_limits,
            )

            stdout = result.stdout.decode("utf-8", errors="replace")
            stderr = result.stderr.decode("utf-8", errors="replace")
            exit_code = result.returncode

            # Detect and annotate resource limit signals
            if exit_code < 0:
                signal_num = abs(exit_code)
                signal_messages = {
                    9: f"Process killed by SIGKILL (signal 9). "
                       f"This typically means CPU time limit ({limits.cpu_seconds}s) was exceeded. "
                       f"Consider reducing execution time or requesting higher limits.",
                    24: f"Process killed by SIGXCPU (signal 24). "
                        f"CPU time limit ({limits.cpu_seconds}s) exceeded.",
                    25: f"Process killed by SIGXFSZ (signal 25). "
                        f"File size limit ({limits.max_file_size} bytes) exceeded.",
                    11: "Process killed by SIGSEGV (signal 11). Segmentation fault.",
                    6: "Process killed by SIGABRT (signal 6). Aborted.",
                }

                if signal_num in signal_messages:
                    resource_msg = signal_messages[signal_num]
                else:
                    resource_msg = f"Process killed by signal {signal_num}."

                # Append resource limit message to stderr
                if stderr:
                    stderr = f"{stderr}\n[Resource Limit] {resource_msg}"
                else:
                    stderr = f"[Resource Limit] {resource_msg}"

                logger.info(f"Process terminated by signal {signal_num}: {resource_msg}")

            return CodeExecResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
            )

        except subprocess.TimeoutExpired as e:
            # Get any partial output before timeout
            stdout = e.stdout.decode("utf-8", errors="replace") if e.stdout else ""
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""

            timeout_msg = (
                f"[Timeout] Execution timeout after {self._config.timeout} seconds. "
                f"The code did not complete within the allowed time. "
                f"Consider adding exit logic (e.g., root.after(N, root.quit) for tkinter)."
            )

            if stderr:
                stderr = f"{stderr}\n{timeout_msg}"
            else:
                stderr = timeout_msg

            return CodeExecResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=124,  # Standard timeout exit code
            )

        except MemoryError:
            return CodeExecResult(
                stdout="",
                stderr=f"[Resource Limit] Memory limit exceeded ({limits.memory_bytes // (1024*1024)}MB limit)",
                exit_code=137,  # Killed by OOM
            )

    def _cleanup(self, script_path: str) -> None:
        """Clean up temporary files.

        Args:
            script_path: Path to script file to remove
        """
        files_to_remove = [
            script_path,
            "/tmp/_screenshot.png",
            "/tmp/_screenshot_b64.txt",
        ]

        for path in files_to_remove:
            try:
                os.unlink(path)
            except OSError:
                pass

    def _capture_single_frame(self, frame_path: str) -> Optional[str]:
        """Capture a single frame from the X11 display.

        Args:
            frame_path: Path to save the screenshot PNG

        Returns:
            Base64-encoded PNG string, or None if capture failed
        """
        try:
            result = subprocess.run(
                ["import", "-window", "root", "-display", ":99", frame_path],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0 and os.path.exists(frame_path):
                with open(frame_path, "rb") as f:
                    frame_b64 = base64.b64encode(f.read()).decode()
                # Clean up immediately
                try:
                    os.unlink(frame_path)
                except OSError:
                    pass
                return frame_b64
        except subprocess.TimeoutExpired:
            logger.warning("Frame capture timed out")
        except Exception as e:
            logger.warning(f"Frame capture failed: {e}")
        return None

    def _background_capture_loop(
        self,
        stop_event: threading.Event,
        frames: List[str],
        interval_ms: int,
        max_frames: int,
    ) -> None:
        """Background thread loop that captures frames at fixed intervals.

        Args:
            stop_event: Event signaling when to stop capturing
            frames: List to append captured frames to (shared with main thread)
            interval_ms: Interval between captures in milliseconds
            max_frames: Maximum number of frames to capture
        """
        frame_idx = 0
        interval_s = interval_ms / 1000.0

        # Wait a bit for the window to appear
        time.sleep(0.2)

        while not stop_event.is_set() and frame_idx < max_frames:
            frame_path = f"/tmp/_frame_{frame_idx}.png"
            frame_b64 = self._capture_single_frame(frame_path)
            if frame_b64:
                frames.append(frame_b64)
                logger.debug(f"Captured frame {frame_idx}")
            frame_idx += 1

            # Wait for next capture interval
            stop_event.wait(interval_s)

    def run(
        self,
        code: str,
        *,
        capture_screenshot: bool = False,
        capture_frames: bool = False,
        capture_interval_ms: int = 500,
        max_frames: int = 100,
        max_capture_duration_s: float = 10.0,
        render_timeout: float = 0.5,
    ) -> CodeExecResult:
        """Execute Python code in isolated subprocess.

        Args:
            code: Python code to execute
            capture_screenshot: If True, capture a single screenshot after execution
            capture_frames: If True, capture frames during execution using background thread
            capture_interval_ms: Interval between frame captures in milliseconds
            max_frames: Maximum number of frames to capture
            max_capture_duration_s: Maximum duration to capture frames (seconds)
            render_timeout: Time to wait for rendering before final screenshot

        Returns:
            CodeExecResult with stdout, stderr, and exit code
        """
        self.clear_screenshot()
        self.clear_frames()

        script_path = self._write_temp_file(code)

        try:
            if capture_frames:
                # Background capture mode
                stop_event = threading.Event()
                frames: List[str] = []

                capture_thread = threading.Thread(
                    target=self._background_capture_loop,
                    args=(stop_event, frames, capture_interval_ms, max_frames),
                    daemon=True,
                )
                capture_thread.start()

                try:
                    result = self._execute_subprocess(script_path)
                finally:
                    # Signal capture thread to stop
                    stop_event.set()
                    # Wait for capture thread to finish (with timeout)
                    capture_thread.join(timeout=2.0)

                self._captured_frames = frames
                # Use the last frame as the screenshot for backward compatibility
                if frames:
                    self._captured_screenshot = frames[-1]

            elif capture_screenshot:
                # Single screenshot mode - capture after execution completes
                result = self._execute_subprocess(script_path)

                # Wait for rendering to complete
                time.sleep(render_timeout)

                # Capture single screenshot
                frame_b64 = self._capture_single_frame("/tmp/_screenshot.png")
                if frame_b64:
                    self._captured_screenshot = frame_b64

            else:
                # No capture mode
                result = self._execute_subprocess(script_path)

            return result

        finally:
            self._cleanup(script_path)

    def get_captured_screenshot(self) -> Optional[str]:
        """Get the screenshot captured during the last execution.

        Returns:
            Base64-encoded PNG string, or None if no screenshot was captured
        """
        return self._captured_screenshot

    def get_captured_frames(self) -> List[str]:
        """Get all frames captured during the last execution.

        Returns:
            List of base64-encoded PNG strings
        """
        return self._captured_frames

    def clear_screenshot(self) -> None:
        """Clear the stored screenshot."""
        self._captured_screenshot = None

    def clear_frames(self) -> None:
        """Clear the stored frames."""
        self._captured_frames = []
