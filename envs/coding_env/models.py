"""
envs/coding_env/models.py
--------------------------------
Action/Observation types for the Coding environment.
"""

from __future__ import annotations

from typing import Optional

from openenv.core.env_server.interfaces import Action, Observation, State


class CodeAction(Action):
    """
    Represents a single code execution request.
    """

    code: str
    capture_screenshot: bool = False
    """If True, capture screenshot of Xvfb display during code execution.

    The screenshot is captured DURING execution (after a 0.5s rendering timeout)
    to ensure UI elements are still alive. This works correctly for GUI frameworks
    like tkinter, matplotlib, pygame, etc.

    The rendering timeout allows UI elements time to render before the screenshot
    is captured. The screenshot happens before the code completes, so GUI windows
    are not destroyed yet.
    """


class CodeObservation(Observation):
    """
    Result of executing code in the environment.
    """

    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    screenshot: Optional[str] = None
    """Base64-encoded PNG screenshot captured during code execution.

    This screenshot is captured while UI elements are still alive (not after
    execution completes), ensuring GUI windows and plots are properly captured.
    A 0.5s rendering timeout is applied to allow UI elements to fully render.

    Returns None if:
    - capture_screenshot was False in the CodeAction
    - Screenshot capture failed (e.g., Xvfb not running)
    - No UI elements were rendered
    """


class CodeState(State):
    """State for CodeAct environment with persistent execution context."""

    last_exit_code: int = 0
