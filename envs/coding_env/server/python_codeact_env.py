# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Python Code Action Environment.

This module provides a server-side environment implementation for executing
Python code actions using various executor backends.
"""

import uuid

from openenv.core.env_server.interfaces import Action, Environment, Observation

from ..models import CodeAction, CodeObservation, CodeState
from .executor_backend import ExecutorBackend
from .python_executor import PyExecutor
from .subprocess_executor import SubprocessExecutor
from .transforms import create_safe_coding_transform


class PythonCodeActEnv(Environment):
    """
    Python Code Action Environment for executing code and tracking state.

    This environment executes Python code submitted as CodeAction during step,
    maintains the last exit code in its state, and returns results wrapped
    in CodeObservation.

    Args:
        transform: Optional transform to apply to observations
        additional_imports: List of additional module imports to authorize
                          (e.g., ["numpy", "pandas", "matplotlib"])
        executor_backend: Backend to use for code execution. Options:
                         - "subprocess" (default): Use subprocess isolation with resource limits
                             (requires hardened container for security)
                         - "smolagents": Use smolagents LocalPythonExecutor

    Example:
        >>> env = PythonCodeActEnv()
        >>> obs = env.reset()
        >>> action = CodeAction(code="print('Hello, World!')")
        >>> obs = env.step(action)
        >>> print(obs.stdout)  # "Hello, World!\n"
        >>> print(obs.exit_code)  # 0
        >>> print(env.state.last_exit_code)  # 0
    """

    def __init__(
        self,
        additional_imports: list[str] | None = None,
        executor_backend: str = "subprocess",
    ):
        self.transform = create_safe_coding_transform()
        self._additional_imports = additional_imports or []
        self._executor_backend = executor_backend
        self._executor: ExecutorBackend = self._create_executor(executor_backend)
        self._state = CodeState()

    def _create_executor(self, backend: str) -> ExecutorBackend:
        """Create the appropriate executor backend based on configuration.

        Args:
            backend: Name of the backend. Options:
                - "subprocess": Subprocess isolation with resource limits
                    (requires hardened container for security)
                - "smolagents": AST-based executor from smolagents library

        Returns:
            ExecutorBackend instance

        Raises:
            ValueError: If backend name is not recognized
        """
        if backend == "subprocess":
            # Subprocess executor with resource limits
            # Security relies on container hardening (--cap-drop=ALL, etc.)
            return SubprocessExecutor()
        elif backend == "smolagents":
            return PyExecutor(additional_imports=self._additional_imports)
        else:
            raise ValueError(
                f"Unknown executor backend: {backend}. "
                f"Valid options: 'subprocess', 'smolagents'"
            )

    def reset(self) -> Observation:
        """
        Reset environment and start fresh execution session.

        Returns:
            Initial observation with empty stdout/stderr and exit_code=0
        """
        # Initialize fresh state
        self._state = CodeState(episode_id=str(uuid.uuid4()), step_count=0)
        # Add last_exit_code to state
        self._state.last_exit_code = 0

        # Reset executor to clear any previously defined variables/functions
        self._executor = self._create_executor(self._executor_backend)

        # Reset transform to clear any accumulated state
        self.transform = create_safe_coding_transform()

        # Return initial observation
        observation = CodeObservation(
            stdout="",
            stderr="",
            exit_code=0,
        )

        return self._apply_transform(observation)

    def step(self, action: Action) -> Observation:
        """
        Execute code action and return observation.

        Args:
            action: CodeAction containing the code to execute

        Returns:
            CodeObservation with execution results (stdout, stderr, exit_code, screenshot, frames)

        Raises:
            ValueError: If action is not a CodeAction instance
        """
        if not isinstance(action, CodeAction):
            raise ValueError(f"Expected CodeAction, got {type(action)}")

        # Execute the code using the executor backend
        # Pass capture flags to enable screenshot/frame capture
        result = self._executor.run(
            action.code,
            capture_screenshot=action.capture_screenshot,
            capture_frames=action.capture_frames,
            capture_interval_ms=action.capture_interval_ms,
            max_frames=action.max_frames,
        )

        # Update state
        self._state.step_count += 1
        self._state.last_exit_code = result.exit_code

        # Retrieve screenshot and frames captured during execution
        screenshot = None
        frames = []

        if action.capture_frames:
            # Frame capture mode - get all frames
            frames = self._executor.get_captured_frames()
            # Use last frame as screenshot for backward compatibility
            screenshot = self._executor.get_captured_screenshot()
            if not frames:
                import logging

                logging.warning(
                    "Frame capture was requested but no frames were captured. "
                    "This may occur if UI elements were not rendered or Xvfb is not running."
                )
        elif action.capture_screenshot:
            # Single screenshot mode
            screenshot = self._executor.get_captured_screenshot()
            if screenshot is None:
                import logging

                logging.warning(
                    "Screenshot capture was requested but no screenshot was captured. "
                    "This may occur if UI elements were not rendered or Xvfb is not running."
                )

        # Create observation from execution result
        # Include code in metadata for transform reward calculation
        observation = CodeObservation(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            metadata={"last_code": action.code},  # Add code to metadata for transforms
            screenshot=screenshot,
            frames=frames,
            frame_count=len(frames),
        )

        return self._apply_transform(observation)

    @property
    def state(self) -> CodeState:
        """Get current environment state including last exit code."""
        return self._state
