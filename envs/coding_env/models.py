"""
envs/coding_env/models.py
--------------------------------
Action/Observation types for the Coding environment.
"""

from __future__ import annotations

from typing import List, Optional

from openenv.core.env_server.interfaces import Action, Observation, State


class CodeAction(Action):
    """
    Code execution request with optional frame capture.

    For simple code execution, only `code` is required. For capturing UI output
    (screenshots or animation frames), use the capture options.

    Frame Capture Mode:
        When `capture_frames=True`, frames are captured in a background thread
        DURING code execution. This is ideal for animations that run continuously
        (e.g., tkinter.mainloop()). The process will be terminated after the
        wall clock timeout (15s default), but all captured frames are returned.

    Screenshot Mode:
        When `capture_screenshot=True`, a single screenshot is captured AFTER
        code execution completes. This requires the UI to remain visible after
        the code finishes.

    Example:
        >>> # Simple code execution
        >>> action = CodeAction(code="print('Hello')")
        >>>
        >>> # Animation with frame capture
        >>> action = CodeAction(
        ...     code=animation_code,
        ...     capture_frames=True,
        ...     capture_interval_ms=500,  # 2 FPS
        ...     max_frames=10,
        ... )
    """

    code: str
    capture_screenshot: bool = False
    """If True, capture a single screenshot after code execution completes.

    The screenshot is captured AFTER execution with a configurable rendering timeout
    to ensure UI elements have time to render. This is simpler but means the window
    must remain open after user code finishes.
    """

    capture_frames: bool = False
    """If True, capture frames during code execution using background capture.

    This enables multi-frame capture mode where screenshots are taken at regular
    intervals DURING code execution. This is useful for capturing animations.
    The frames are captured in a background thread while user code runs.
    """

    capture_interval_ms: int = 500
    """Interval between frame captures in milliseconds (default: 500ms = 2 FPS).

    Only used when capture_frames=True.
    """

    max_frames: int = 100
    """Maximum number of frames to capture (default: 100).

    Only used when capture_frames=True. Prevents unbounded memory usage.
    """


class CodeObservation(Observation):
    """
    Result of executing code in the environment.

    Contains stdout/stderr from execution, exit code, and optional visual output
    (screenshots or animation frames).

    Exit Code Semantics:
        - 0: Success - code completed normally
        - 1-127: Code error (exception, syntax error, etc.)
        - 124: Timeout - wall clock time limit exceeded
        - 137: OOM killer (128 + SIGKILL)
        - -9: SIGKILL - often CPU time limit exceeded
        - -24: SIGXCPU - CPU time soft limit exceeded

    Important for Frame Capture:
        A non-zero exit code (e.g., 124 timeout) does NOT mean failure for
        animation capture scenarios. Frames are captured in a background thread
        during execution, so they are returned even if the process is terminated.
        Success should be measured by analyzing the captured frames, not by exit code.

    Example:
        >>> result = env.step(CodeAction(code=animation, capture_frames=True))
        >>> # Exit code may be 124 (timeout) - this is expected!
        >>> print(f"Frames: {result.observation.frame_count}")  # e.g., 10
        >>> for frame in result.observation.frames:
        ...     # Analyze frame content for reward calculation
        ...     pass
    """

    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    screenshot: Optional[str] = None
    """Base64-encoded PNG screenshot.

    In single screenshot mode (capture_screenshot=True): captured after execution.
    In frame capture mode (capture_frames=True): the last captured frame.

    Returns None if:
    - capture_screenshot and capture_frames were both False
    - Screenshot capture failed (e.g., Xvfb not running)
    - No UI elements were rendered
    """

    frames: List[str] = []
    """List of base64-encoded PNG frames captured during execution.

    Only populated when capture_frames=True in the CodeAction.
    Each frame is captured at the interval specified by capture_interval_ms.
    """

    frame_count: int = 0
    """Number of frames captured during execution."""


class CodeState(State):
    """State for CodeAct environment with persistent execution context."""

    last_exit_code: int = 0
