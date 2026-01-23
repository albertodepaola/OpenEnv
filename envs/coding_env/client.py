"""
CodingEnv
---------
Client-side wrapper for the Coding environment server.

This client maintains a persistent WebSocket connection to the environment
server, enabling efficient multi-step interactions with lower latency.

- users instantiate CodingEnv with a base_url provided by the higher-level
  vector/orchestration layer.
- Environment authors ship the Docker image that serves the API.

(Seeds, episode IDs, request IDs, capabilities can be added later in the payloads.)
"""

from __future__ import annotations

from typing import Any, List, Optional, Type, TYPE_CHECKING

from openenv.core.client_types import StepResult
from openenv.core.env_client import EnvClient

from .models import CodeAction, CodeObservation, CodeState

if TYPE_CHECKING:
    from openenv.core.containers.runtime import ContainerProvider


class CodingEnv(EnvClient[CodeAction, CodeObservation, CodeState]):
    # --- EnvClient abstract hooks ---

    def _step_payload(self, action: CodeAction) -> dict:
        # Shape expected by the server's /step endpoint under "action"
        return {
            "code": action.code,
            "capture_screenshot": action.capture_screenshot,
            "capture_frames": action.capture_frames,
            "capture_interval_ms": action.capture_interval_ms,
            "max_frames": action.max_frames,
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
        provider: Optional["ContainerProvider"] = None,
        additional_imports: Optional[List[str]] = None,
        executor_backend: str = "subprocess",
        **kwargs: Any,
    ) -> "CodingEnv":
        """
        Create a CodingEnv client by spinning up a Docker container.

        This method extends the base EnvClient.from_docker_image() with
        CodingEnv-specific configuration for authorizing additional Python imports
        and selecting the executor backend.

        Args:
            image: Docker image name (e.g., "coding-env:latest")
            provider: Container provider to use (defaults to LocalDockerProvider)
            additional_imports: List of additional Python modules to authorize in executor.
                              Both stdlib and PyPI packages can be specified.
                              - Stdlib modules (e.g., "dataclasses", "typing") are always available
                              - PyPI packages (e.g., "numpy", "scipy") are installed dynamically
                                at container startup via pip install
            executor_backend: Backend to use for code execution.
                            Options: "subprocess" (default), "smolagents"
                            - subprocess: Full Python semantics with resource limits
                            - smolagents: Fast but doesn't support decorators
            **kwargs: Additional arguments passed to provider.start_container()

        Returns:
            CodingEnv client connected to the running container

        Example:
            >>> # Basic usage with subprocess (default)
            >>> env = CodingEnv.from_docker_image("coding-env:latest")
            >>>
            >>> # With smolagents backend
            >>> env = CodingEnv.from_docker_image(
            ...     "coding-env:latest",
            ...     executor_backend="smolagents",
            ...     additional_imports=["numpy"],
            ... )

        Note:
            PyPI packages are installed at container startup, which adds 5-30 seconds
            depending on package size. Stdlib modules are filtered out and not installed.
        """
        # Get existing env_vars or create new dict
        env_vars = kwargs.get("env_vars", {})

        # Convert additional_imports list to ADDITIONAL_IMPORTS env var
        if additional_imports:
            env_vars["ADDITIONAL_IMPORTS"] = ",".join(additional_imports)

        # Set executor backend
        env_vars["EXECUTOR_BACKEND"] = executor_backend

        # Update kwargs with the env_vars
        kwargs["env_vars"] = env_vars

        # Call parent class method with updated kwargs
        return super().from_docker_image(image, provider, **kwargs)
