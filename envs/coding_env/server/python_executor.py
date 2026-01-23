# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Local Python Executor (enhanced).

This module provides a safer wrapper around smolagents.LocalPythonExecutor
with improved exception handling and a few helpful tools registered with
the executor to make debugging executed code easier.

Key improvements:
- Register a few helper utilities via send_tools so user code can use
  them for reporting (e.g. `format_exc`).
- More robust extraction of stdout/stderr/exit codes from the executor
  result object, tolerant to different versions of smolagents.
- Detailed stderr on unexpected exceptions including full traceback.
- Structured logging for operational visibility.
"""

from __future__ import annotations

import json
import logging
import traceback
from typing import List, Optional

from smolagents import LocalPythonExecutor

from openenv.core.env_server.types import CodeExecResult

from .executor_backend import ExecutorBackend

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class PyExecutor(ExecutorBackend):
    """Wrapper around smolagents LocalPythonExecutor.

    The wrapper registers a few non-privileged helper tools to the
    LocalPythonExecutor that can be used by the executed code to
    format exceptions and to safely stringify results for improved
    error reporting.
    """

    def __init__(self, additional_imports: list[str] | None = None):
        if additional_imports is None:
            additional_imports = []

        self._executor = LocalPythonExecutor(
            additional_authorized_imports=additional_imports
        )
        self._captured_screenshot: Optional[str] = None
        self._captured_frames: List[str] = []

        # Register helpful utilities exposed to the execution environment.
        # These are intentionally small, read-only helpers.
        tools = {
            # Provide a small helper to format the current exception in the
            # executed context. This is a *string formatting* helper only.
            "format_exc": traceback.format_exc,
            # Safe JSON dumps with a fallback for non-serializable objects.
            "safe_json_dumps": lambda obj: json.dumps(obj, default=lambda o: repr(o)),
        }

        # `send_tools` is the public API on LocalPythonExecutor to make
        # helper callables available to the sandboxed runtime. We don't
        # provide any builtins that could change the environment.
        try:
            self._executor.send_tools(tools)
        except Exception:
            # If the LocalPythonExecutor implementation doesn't support
            # send_tools or fails, log and continue — the executor is still usable.
            logger.debug(
                "LocalPythonExecutor.send_tools failed; continuing without extra tools",
                exc_info=True,
            )

    def _create_screenshot_capture_tool(self):
        """Create the screenshot capture tool for the execution sandbox.

        This function is injected into the user's execution environment and
        captures screenshots from the Xvfb display.

        Returns a dictionary with screenshot data and debug info so the calling
        code can print the debug messages (which will be properly captured).
        """

        def capture_screenshot_internal(display: str = ":99") -> dict:
            """Capture screenshot from Xvfb display during code execution.

            Args:
                display: X11 display to capture (default :99)

            Returns:
                Dictionary with 'screenshot' (base64 string or None) and 'debug' (list of messages)
            """
            import base64
            import subprocess
            import tempfile
            from pathlib import Path

            debug_messages = []
            debug_messages.append(
                f"[DEBUG] Capture tool: Starting screenshot capture for display {display}"
            )

            tmp_path = None
            try:
                # Create temporary file for screenshot
                with tempfile.NamedTemporaryFile(
                    suffix=".png", delete=False
                ) as tmp_file:
                    tmp_path = tmp_file.name

                debug_messages.append(
                    f"[DEBUG] Capture tool: Temporary file created: {tmp_path}"
                )

                # Capture screenshot using ImageMagick import command
                cmd = ["import", "-window", "root", "-display", display, tmp_path]
                debug_messages.append(
                    f"[DEBUG] Capture tool: Running command: {' '.join(cmd)}"
                )

                result = subprocess.run(cmd, capture_output=True, timeout=5, check=True)

                debug_messages.append(
                    "[DEBUG] Capture tool: Command completed successfully"
                )
                if result.stdout:
                    debug_messages.append(
                        f"[DEBUG] Capture tool: stdout: {result.stdout.decode()}"
                    )
                if result.stderr:
                    debug_messages.append(
                        f"[DEBUG] Capture tool: stderr: {result.stderr.decode()}"
                    )

                # Check if file was created and has content
                if not Path(tmp_path).exists():
                    debug_messages.append(
                        "[DEBUG] Capture tool: ERROR - Screenshot file was not created"
                    )
                    return {
                        "screenshot": None,
                        "debug": debug_messages,
                        "success": False,
                    }

                file_size = Path(tmp_path).stat().st_size
                debug_messages.append(
                    f"[DEBUG] Capture tool: Screenshot file size: {file_size} bytes"
                )

                if file_size == 0:
                    debug_messages.append(
                        "[DEBUG] Capture tool: ERROR - Screenshot file is empty"
                    )
                    return {
                        "screenshot": None,
                        "debug": debug_messages,
                        "success": False,
                    }

                # Read PNG file and encode to base64
                with open(tmp_path, "rb") as f:
                    png_bytes = f.read()
                    base64_str = base64.b64encode(png_bytes).decode("utf-8")

                debug_messages.append(
                    "[DEBUG] Capture tool: Screenshot captured successfully!"
                )
                debug_messages.append(
                    f"[DEBUG] Capture tool: PNG size: {len(png_bytes)} bytes"
                )
                debug_messages.append(
                    f"[DEBUG] Capture tool: Base64 size: {len(base64_str)} characters"
                )

                # Store the screenshot in the executor instance
                self._captured_screenshot = base64_str

                return {
                    "screenshot": base64_str,
                    "debug": debug_messages,
                    "success": True,
                }

            except subprocess.TimeoutExpired:
                debug_messages.append(
                    "[DEBUG] Capture tool: ERROR - Screenshot capture timed out"
                )
                return {
                    "screenshot": None,
                    "debug": debug_messages,
                    "success": False,
                    "error": "Timeout",
                }

            except subprocess.CalledProcessError as e:
                stdout = e.stdout.decode() if e.stdout else "No stdout"
                stderr = e.stderr.decode() if e.stderr else "No stderr"
                debug_messages.append(
                    f"[DEBUG] Capture tool: ERROR - Command failed with exit code {e.returncode}"
                )
                debug_messages.append(f"[DEBUG] Capture tool: stdout: {stdout}")
                debug_messages.append(f"[DEBUG] Capture tool: stderr: {stderr}")
                return {
                    "screenshot": None,
                    "debug": debug_messages,
                    "success": False,
                    "error": f"Exit code {e.returncode}",
                }

            except FileNotFoundError as e:
                debug_messages.append(
                    f"[DEBUG] Capture tool: ERROR - Command not found: {e}"
                )
                debug_messages.append(
                    "[DEBUG] Capture tool: Make sure ImageMagick 'import' command is installed"
                )
                return {
                    "screenshot": None,
                    "debug": debug_messages,
                    "success": False,
                    "error": "Command not found",
                }

            except Exception as e:
                debug_messages.append(
                    f"[DEBUG] Capture tool: ERROR - Unexpected exception: {e}"
                )
                import traceback

                debug_messages.append(
                    f"[DEBUG] Capture tool: Traceback: {traceback.format_exc()}"
                )
                return {
                    "screenshot": None,
                    "debug": debug_messages,
                    "success": False,
                    "error": str(e),
                }

            finally:
                # Cleanup temporary file
                if tmp_path:
                    try:
                        Path(tmp_path).unlink(missing_ok=True)
                        debug_messages.append(
                            "[DEBUG] Capture tool: Cleaned up temporary file"
                        )
                    except Exception as e:
                        debug_messages.append(
                            f"[DEBUG] Capture tool: WARNING - Failed to cleanup: {e}"
                        )

        return capture_screenshot_internal

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

    def run(
        self,
        code: str,
        *,
        capture_screenshot: bool = False,
        capture_frames: bool = False,
        capture_interval_ms: int = 500,
        max_frames: int = 100,
        render_timeout: float = 0.5,
    ) -> CodeExecResult:
        """Execute Python code and return a CodeExecResult.

        This method is intentionally defensive: it attempts to extract
        meaningful stdout/stderr/exit_code information from a variety of
        possible return shapes that different versions of smolagents
        may provide.

        Args:
            code: Python code to execute
            capture_screenshot: If True, inject code to capture screenshot during execution
            capture_frames: Not supported by this backend (ignored)
            capture_interval_ms: Not supported by this backend (ignored)
            max_frames: Not supported by this backend (ignored)
            render_timeout: Time in seconds to wait for UI rendering before screenshot (default 0.5s)

        Returns:
            CodeExecResult containing stdout, stderr, and exit_code
        """
        # Clear previous screenshot
        self.clear_screenshot()
        self.clear_frames()

        try:
            exec_result = self._executor(code)

            # Default values
            stdout_parts: list[str] = []
            stderr_parts: list[str] = []
            exit_code = 0

            # Extract logs/prints
            try:
                logs = getattr(exec_result, "logs", None)
                if logs:
                    stdout_parts.append(str(logs))
            except Exception:
                logger.debug("Failed to read exec_result.logs", exc_info=True)

            # Extract the result / output value
            try:
                if hasattr(exec_result, "output"):
                    out_val = exec_result.output
                    # If the output is not None, stringify it in a safe way
                    if out_val is not None:
                        # Prefer JSON if possible, otherwise repr
                        try:
                            stdout_parts.append(json.dumps(out_val))
                        except Exception:
                            stdout_parts.append(repr(out_val))
            except Exception:
                logger.debug("Failed to read exec_result.output", exc_info=True)

            # Some runtime implementations may put errors on `error` or `exception`
            try:
                err = getattr(exec_result, "error", None)
                if err:
                    stderr_parts.append(str(err))
            except Exception:
                logger.debug("Failed to read exec_result.error", exc_info=True)

            try:
                ex = getattr(exec_result, "exception", None)
                if ex:
                    stderr_parts.append(str(ex))
            except Exception:
                logger.debug("Failed to read exec_result.exception", exc_info=True)

            # Determine exit code if provided
            try:
                if hasattr(exec_result, "exit_code"):
                    exit_code = (
                        int(exec_result.exit_code)
                        if exec_result.exit_code is not None
                        else 0
                    )
                elif hasattr(exec_result, "success"):
                    # Some versions use `success` boolean
                    exit_code = 0 if exec_result.success else 1
                else:
                    # Fallback: if there were any stderr parts, treat as non-zero
                    exit_code = 1 if stderr_parts else 0
            except Exception:
                logger.debug("Failed to determine exec_result exit code", exc_info=True)
                exit_code = 1 if stderr_parts else 0

            # Compose the final stdout/stderr strings
            stdout = "\n".join(part for part in stdout_parts if part is not None)
            stderr = "\n".join(part for part in stderr_parts if part is not None)

            return CodeExecResult(stdout=stdout, stderr=stderr, exit_code=exit_code)

        except Exception:
            # Any unexpected exception from the LocalPythonExecutor is
            # returned with a full traceback to make debugging easier.
            tb = traceback.format_exc()
            logger.exception("LocalPythonExecutor raised an exception during run")
            return CodeExecResult(stdout="", stderr=tb, exit_code=1)
