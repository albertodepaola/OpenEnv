"""Executor backend abstractions for the coding environment.

This module defines the minimal contract that executor implementations must
satisfy so that the environment can swap between different backends (e.g.,
smolagents LocalPythonExecutor, RestrictedPython) without impacting higher
level features such as screenshot capture or observation transforms.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

# Support both standalone and in-repo imports
try:
    # Standalone imports (when installed from pip)
    from openenv_core.env_server.types import CodeExecResult
except ImportError:  # pragma: no cover - executed in repo mode
    # In-repo imports (when running from OpenEnv repository)
    from core.env_server.types import CodeExecResult


class ExecutorBackend(ABC):
    """Abstract base class for executor backends.

    Implementations are responsible for executing Python code within a sandbox
    and returning results using the shared ``CodeExecResult`` record. Backends
    that support screenshot capture can optionally implement the screenshot
    helper methods; the default implementations operate as no-ops so callers can
    interact with the backend uniformly.
    """

    @abstractmethod
    def run(
        self,
        code: str,
        *,
        capture_screenshot: bool = False,
        render_timeout: float = 0.5,
    ) -> CodeExecResult:
        """Execute user code and return a ``CodeExecResult`` instance."""

    def get_captured_screenshot(self) -> Optional[str]:
        """Return the last captured screenshot as a base64 string if available."""

        return None

    def clear_screenshot(self) -> None:
        """Clear any stored screenshot state for the backend."""

        return None
