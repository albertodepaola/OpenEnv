# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
FastAPI application for the Coding Environment.

This module creates an HTTP server that exposes the PythonCodeActEnv
over HTTP and WebSocket endpoints, compatible with EnvClient.

Usage:
    # Development (with auto-reload):
    uvicorn envs.coding_env.server.app:app --reload --host 0.0.0.0 --port 8000

    # Production:
    uvicorn envs.coding_env.server.app:app --host 0.0.0.0 --port 8000 --workers 4

    # With custom authorized imports (comma-separated):
    ADDITIONAL_IMPORTS=numpy,pandas,scipy uvicorn envs.coding_env.server.app:app --host 0.0.0.0 --port 8000

    # With RestrictedPython backend (supports @dataclass decorators):
    EXECUTOR_BACKEND=restrictedpython uvicorn envs.coding_env.server.app:app --host 0.0.0.0 --port 8000

    # Or run directly:
    python -m envs.coding_env.server.app
"""

import os
from functools import partial

from openenv.core.env_server import create_app

from coding_env.models import CodeAction, CodeObservation
from coding_env.server.python_codeact_env import PythonCodeActEnv


def _get_additional_imports() -> list[str]:
    """Parse ADDITIONAL_IMPORTS environment variable.

    Returns:
        List of additional module names to authorize for import.
    """
    additional_imports_env = os.environ.get("ADDITIONAL_IMPORTS", "")
    additional_imports = []

    if additional_imports_env:
        # Parse comma-separated list and strip whitespace
        additional_imports = [
            imp.strip() for imp in additional_imports_env.split(",") if imp.strip()
        ]
        print(
            f"[app.py] Loading with additional imports from ADDITIONAL_IMPORTS: {additional_imports}"
        )

    # Always include tkinter for UI/canvas examples
    if "tkinter" not in additional_imports:
        additional_imports.append("tkinter")

    return additional_imports


def _get_executor_backend() -> str:
    """Get executor backend from environment variable.

    Returns:
        Backend name ("smolagents" or "restrictedpython")
    """
    backend = os.environ.get("EXECUTOR_BACKEND", "smolagents")
    print(f"[app.py] Using executor backend: {backend}")
    return backend


def create_configured_env() -> PythonCodeActEnv:
    """Factory function to create a configured PythonCodeActEnv.

    This function is used as a factory by create_app to instantiate
    fresh environments for each WebSocket session.

    Returns:
        Configured PythonCodeActEnv instance
    """
    additional_imports = _get_additional_imports()
    executor_backend = _get_executor_backend()

    print(f"[app.py] Creating environment with authorized imports: {additional_imports}")

    return PythonCodeActEnv(
        additional_imports=additional_imports,
        executor_backend=executor_backend,
    )


# Create the app with web interface and README integration
# Pass the factory function instead of a class for configurable environments
app = create_app(
    create_configured_env,
    CodeAction,
    CodeObservation,
    env_name="coding_env",
)


def main():
    """Main entry point for running the server."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
