# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Executor backend abstractions for the coding environment.

This module defines the minimal contract that executor implementations must
satisfy so that the environment can swap between different backends (e.g.,
smolagents LocalPythonExecutor, subprocess isolation) without impacting higher
level features such as screenshot capture or observation transforms.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from openenv.core.env_server.types import CodeExecResult


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
        capture_frames: bool = False,
        capture_interval_ms: int = 500,
        max_frames: int = 100,
        render_timeout: float = 0.5,
    ) -> CodeExecResult:
        """Execute user code and return a ``CodeExecResult`` instance.

        Args:
            code: Python code to execute
            capture_screenshot: If True, capture a single screenshot after execution
            capture_frames: If True, capture frames during execution
            capture_interval_ms: Interval between frame captures in milliseconds
            max_frames: Maximum number of frames to capture
            render_timeout: Time to wait for rendering before screenshot
        """

    def get_captured_screenshot(self) -> Optional[str]:
        """Return the last captured screenshot as a base64 string if available."""

        return None

    def get_captured_frames(self) -> List[str]:
        """Return all captured frames as a list of base64 strings."""

        return []

    def clear_screenshot(self) -> None:
        """Clear any stored screenshot state for the backend."""

        return None

    def clear_frames(self) -> None:
        """Clear any stored frame state for the backend."""

        return None
