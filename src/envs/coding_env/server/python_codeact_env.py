# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Python Code Action Environment.

This module provides a server-side environment implementation for executing
Python code actions using PyExecutor.
"""

import uuid

# Support both standalone and in-repo imports
try:
    # Standalone imports (when installed from pip)
    from openenv_core.env_server.interfaces import Action, Environment, Observation
except ImportError:
    # In-repo imports (when running from OpenEnv repository)
    from core.env_server.interfaces import Action, Environment, Observation

# Use relative/absolute imports that work in both modes
try:
    from coding_env.models import CodeAction, CodeObservation, CodeState

    # Standalone mode
    from coding_env.server.executor_backend import ExecutorBackend
    from coding_env.server.python_executor import PyExecutor
    from coding_env.server.restricted_python_executor import RestrictedPythonExecutor
    from coding_env.server.transforms import create_safe_coding_transform
except ImportError:
    from envs.coding_env.models import CodeAction, CodeObservation, CodeState

    # In-repo mode
    from envs.coding_env.server.executor_backend import ExecutorBackend
    from envs.coding_env.server.python_executor import PyExecutor
    from envs.coding_env.server.restricted_python_executor import (
        RestrictedPythonExecutor,
    )
    from envs.coding_env.server.transforms import create_safe_coding_transform


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
                         - "smolagents" (default): Use smolagents LocalPythonExecutor
                         - "restrictedpython": Use RestrictedPython for full Python semantics

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
        executor_backend: str = "smolagents",
    ):
        self.transform = create_safe_coding_transform()
        self._additional_imports = (
            additional_imports if additional_imports is not None else []
        )
        self._backend_name = executor_backend
        self._executor = self._create_executor(executor_backend)
        self._state = CodeState()

    def _create_executor(self, backend: str) -> ExecutorBackend:
        """Create the appropriate executor backend based on configuration.

        Args:
            backend: Name of the backend ("smolagents" or "restrictedpython")

        Returns:
            ExecutorBackend instance

        Raises:
            ValueError: If backend name is not recognized
        """
        if backend == "smolagents":
            return PyExecutor(additional_imports=self._additional_imports)
        elif backend == "restrictedpython":
            return RestrictedPythonExecutor(additional_imports=self._additional_imports)
        else:
            raise ValueError(
                f"Unknown executor backend: {backend}. "
                f"Valid options: 'smolagents', 'restrictedpython'"
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
        self._executor = self._create_executor(self._backend_name)

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
            CodeObservation with execution results (stdout, stderr, exit_code, screenshot)

        Raises:
            ValueError: If action is not a CodeAction instance
        """
        if not isinstance(action, CodeAction):
            raise ValueError(f"Expected CodeAction, got {type(action)}")

        # Execute the code using PyExecutor
        # Pass the capture_screenshot flag to enable in-execution screenshot capture
        result = self._executor.run(
            action.code, capture_screenshot=action.capture_screenshot
        )

        # Update state
        self._state.step_count += 1
        self._state.last_exit_code = result.exit_code

        # Retrieve screenshot captured during execution (if any)
        screenshot = None
        if action.capture_screenshot:
            screenshot = self._executor.get_captured_screenshot()
            if screenshot is None:
                import logging

                logging.warning(
                    "Screenshot capture was requested but no screenshot was captured. "
                    "This may occur if UI elements were not rendered or Xvfb is not running."
                )

        # Create observation from execution result
        observation = CodeObservation(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            metadata={"last_code": action.code},  # Add code to metadata for transforms
            screenshot=screenshot,
        )

        return self._apply_transform(observation)

    @property
    def state(self) -> CodeState:
        """Get current environment state including last exit code."""
        return self._state
