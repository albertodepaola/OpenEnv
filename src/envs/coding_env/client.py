"""
CodingEnv
---------
Client-side wrapper for the Coding environment server.
Talks HTTP to a single base_url exposing: /reset and /step.

- users instantiate CodingEnv with a base_url provided by the higher-level
  vector/orchestration layer.
- Environment authors ship the Docker image that serves the HTTP API.

(Seeds, episode IDs, request IDs, capabilities can be added later in the payloads.)
"""

from __future__ import annotations

from typing import Any, List, Optional, Type

# Support both standalone and in-repo imports
try:
    # Standalone imports (when installed from pip)
    from openenv_core.client_types import StepResult
    from openenv_core.http_env_client import HTTPEnvClient
    from openenv_core.containers.runtime import ContainerProvider
except ImportError:
    # In-repo imports (when running from OpenEnv repository)
    from core.client_types import StepResult
    from core.http_env_client import HTTPEnvClient
    from core.containers.runtime import ContainerProvider

# Use relative imports for sibling modules - works in both modes
from .models import CodeAction, CodeObservation, CodeState


class CodingEnv(HTTPEnvClient[CodeAction, CodeObservation]):
    # --- HTTPEnvClient abstract hooks ---

    def _step_payload(self, action: CodeAction) -> dict:
        # Shape expected by the server's /step endpoint under "action"
        return {
            "code": action.code,
            "capture_screenshot": action.capture_screenshot,
        }

    def _parse_result(self, payload: dict) -> StepResult[CodeObservation]:
        # Expecting: { "observation": {...}, "reward": <float|null>, "done": <bool>, "info": {...} }
        obs = CodeObservation(**payload["observation"])
        return StepResult(
            observation=obs,
            reward=payload.get("reward"),
            done=bool(payload.get("done", False)),
        )

    def _parse_state(self, payload: dict) -> CodeState:
        """
        Parse server response into CodeState object.

        Args:
            payload: JSON response from /state endpoint

        Returns:
            CodeState object with episode_id, step_count, and last_exit_code
        """
        return CodeState(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
            last_exit_code=payload.get("last_exit_code", 0),
        )

    @classmethod
    def from_docker_image(
        cls: Type["CodingEnv"],
        image: str,
        provider: Optional[ContainerProvider] = None,
        additional_imports: Optional[List[str]] = None,
        timeout_s: float = 30.0,
        **kwargs: Any,
    ) -> "CodingEnv":
        """
        Create a CodingEnv client by spinning up a Docker container.

        This method extends the base HTTPEnvClient.from_docker_image() with
        CodingEnv-specific configuration for authorizing additional Python imports.

        Args:
            image: Docker image name (e.g., "coding-env:latest")
            provider: Container provider to use (defaults to LocalDockerProvider)
            additional_imports: List of additional Python modules to authorize in smolagents.
                              Both stdlib and PyPI packages can be specified.
                              - Stdlib modules (e.g., "dataclasses", "typing") are always available
                              - PyPI packages (e.g., "numpy", "scipy") are installed dynamically
                                at container startup via pip install
            **kwargs: Additional arguments passed to provider.start_container()

        Returns:
            CodingEnv client connected to the running container

        Example:
            >>> # Basic usage
            >>> env = CodingEnv.from_docker_image("coding-env:latest")
            >>>
            >>> # With additional imports (both stdlib and PyPI packages)
            >>> env = CodingEnv.from_docker_image(
            ...     "coding-env:latest",
            ...     additional_imports=[
            ...         "numpy",        # PyPI - installed dynamically
            ...         "scipy",        # PyPI - installed dynamically
            ...         "dataclasses",  # stdlib - always available (no install needed)
            ...         "typing",       # stdlib - always available (no install needed)
            ...     ]
            ... )
            >>>
            >>> # Use numpy in code
            >>> result = env.step(CodeAction(code='''
            ... import numpy as np
            ... arr = np.array([1, 2, 3, 4, 5])
            ... print(f"Mean: {np.mean(arr)}")
            ... '''))

        Note:
            PyPI packages are installed at container startup, which adds 5-30 seconds
            depending on package size. Stdlib modules are filtered out and not installed.
        """
        # Convert additional_imports list to ADDITIONAL_IMPORTS env var
        if additional_imports:
            # Get existing env_vars or create new dict
            env_vars = kwargs.get("env_vars", {})

            # Convert list to comma-separated string
            env_vars["ADDITIONAL_IMPORTS"] = ",".join(additional_imports)

            # Update kwargs with the env_vars
            kwargs["env_vars"] = env_vars

        # Call parent class method with updated kwargs
        return super().from_docker_image(image, provider, timeout_s=timeout_s, **kwargs)
