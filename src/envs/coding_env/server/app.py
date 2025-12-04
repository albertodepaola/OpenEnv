# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
FastAPI application for the Coding Environment.

This module creates an HTTP server that exposes the PythonCodeActEnv
over HTTP endpoints, making it compatible with HTTPEnvClient.

Usage:
    # Development (with auto-reload):
    uvicorn envs.coding_env.server.app:app --reload --host 0.0.0.0 --port 8000

    # Production:
    uvicorn envs.coding_env.server.app:app --host 0.0.0.0 --port 8000 --workers 4

    # With custom authorized imports (comma-separated):
    ADDITIONAL_IMPORTS=numpy,pandas,scipy uvicorn envs.coding_env.server.app:app --host 0.0.0.0 --port 8000

    # Or run directly:
    python -m envs.coding_env.server.app
"""

import os

# Support both standalone and in-repo imports
try:
    # Standalone imports (when installed from pip)
    from openenv_core.env_server import create_app
except ImportError:
    # In-repo imports (when running from OpenEnv repository)
    from core.env_server import create_app

# Use relative/absolute imports that work in both modes
try:
    # Standalone mode
    from coding_env.models import CodeAction, CodeObservation
    from coding_env.server.python_codeact_env import PythonCodeActEnv
except ImportError:
    # In-repo mode
    from envs.coding_env.models import CodeAction, CodeObservation
    from envs.coding_env.server.python_codeact_env import PythonCodeActEnv

# Get additional imports from environment variable
# Format: comma-separated list, e.g., "numpy,pandas,scipy,PIL"
additional_imports_env = os.environ.get("ADDITIONAL_IMPORTS", "")
additional_imports = []

if additional_imports_env:
    # Parse comma-separated list and strip whitespace
    additional_imports = [imp.strip() for imp in additional_imports_env.split(",") if imp.strip()]
    print(f"[app.py] Loading with additional imports from ADDITIONAL_IMPORTS: {additional_imports}")

# Always include tkinter for UI/canvas examples
if "tkinter" not in additional_imports:
    additional_imports.append("tkinter")

print(f"[app.py] Creating environment with authorized imports: {additional_imports}")

# Create the environment instance with additional authorized imports
# Note: To use these libraries, they must be installed in the Docker image first
env = PythonCodeActEnv(additional_imports=additional_imports)

# Create the app with web interface and README integration
app = create_app(env, CodeAction, CodeObservation, env_name="coding_env")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


def main():
    """Main entry point for running the server."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
