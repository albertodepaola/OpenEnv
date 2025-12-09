#!/bin/bash
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

set -e

echo "=== Coding Environment Startup ==="

# Step 1: Install additional packages dynamically if specified
if [ -n "$ADDITIONAL_IMPORTS" ]; then
    echo "Processing ADDITIONAL_IMPORTS: $ADDITIONAL_IMPORTS"

    # Use Python to filter out stdlib modules and install only PyPI packages
    # This also updates ADDITIONAL_IMPORTS to the filtered list for smolagents
    FILTERED_RESULT=$(python3 << 'EOF'
import sys
import subprocess
import os

# Get the imports list from environment
imports_str = os.environ.get("ADDITIONAL_IMPORTS", "")
if not imports_str:
    sys.exit(0)

# Parse comma-separated list
requested_imports = [imp.strip() for imp in imports_str.split(",") if imp.strip()]

# Standard library modules that should NOT be pip installed
# This is a curated list of common stdlib modules that people might try to authorize
STDLIB_MODULES = {
    # Built-in types and core
    "dataclasses", "dataclass",  # dataclass is common typo for dataclasses
    "typing", "types",
    "collections", "functools", "itertools",
    "operator", "copy", "pickle", "json", "csv", "xml", "html",

    # System/OS
    "os", "sys", "pathlib", "subprocess", "shutil", "tempfile",
    "glob", "fnmatch", "io", "time", "datetime", "calendar",

    # Math/Numbers
    "math", "cmath", "decimal", "fractions", "random", "statistics",

    # Text/String
    "string", "re", "textwrap", "unicodedata", "codecs",

    # Data structures
    "array", "queue", "heapq", "bisect", "weakref", "enum",

    # Networking/Web
    "urllib", "http", "httplib", "email", "mimetypes", "base64", "binascii",

    # Threading/Concurrency
    "threading", "multiprocessing", "concurrent", "asyncio",

    # Testing/Debugging
    "unittest", "doctest", "pdb", "trace", "traceback", "warnings",

    # Misc
    "argparse", "logging", "abc", "contextlib", "importlib",

    # GUI (built-in or system-provided)
    "tkinter", "turtle",

    # Common stdlib submodules that people might list separately
    "typing_extensions",  # Note: this is actually a PyPI package but backports stdlib
}

# Map common typos to their correct stdlib names
TYPO_TO_CORRECT = {
    "dataclass": "dataclasses",
}

# Filter to only PyPI packages (not stdlib)
pypi_packages = []
corrected_imports = []

for imp in requested_imports:
    # Remove submodule paths (e.g., "matplotlib.pyplot" -> "matplotlib")
    base_module = imp.split(".")[0]

    if base_module in STDLIB_MODULES:
        print(f"  - Skipping stdlib module from installation: {base_module}", file=sys.stderr)
        # If it's a typo, add the corrected version to the imports list
        if base_module in TYPO_TO_CORRECT:
            corrected = TYPO_TO_CORRECT[base_module]
            if corrected not in corrected_imports:
                corrected_imports.append(corrected)
                print(f"    → Corrected to: {corrected}", file=sys.stderr)
        else:
            # Keep the original stdlib module in the imports list
            # (smolagents needs to know it's authorized, even if not installed)
            corrected_imports.append(imp)
    else:
        # PyPI package - needs installation
        if base_module not in pypi_packages:
            pypi_packages.append(base_module)
        # Keep original import spec (might include submodules)
        corrected_imports.append(imp)

if pypi_packages:
    print(f"  - Installing PyPI packages: {', '.join(pypi_packages)}", file=sys.stderr)
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-cache-dir", "--quiet"] + pypi_packages,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"  ✓ Successfully installed: {', '.join(pypi_packages)}", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"  ✗ Failed to install packages: {e}", file=sys.stderr)
        print(f"    stdout: {e.stdout}", file=sys.stderr)
        print(f"    stderr: {e.stderr}", file=sys.stderr)
        sys.exit(1)
else:
    print(f"  - No PyPI packages to install (all stdlib)", file=sys.stderr)

# Output the corrected imports list for the environment variable
# This will be picked up by the shell script
print(",".join(corrected_imports))
EOF
)

    if [ $? -ne 0 ]; then
        echo "ERROR: Package installation failed"
        exit 1
    fi

    # Update ADDITIONAL_IMPORTS with the filtered/corrected list
    export ADDITIONAL_IMPORTS="$FILTERED_RESULT"
    echo "  - Updated ADDITIONAL_IMPORTS to: $ADDITIONAL_IMPORTS"
else
    echo "No ADDITIONAL_IMPORTS specified, skipping package installation"
fi

# Step 2: Start Xvfb virtual display
echo ""
echo "Starting Xvfb virtual display on DISPLAY=:99..."
Xvfb :99 -screen 0 1024x768x24 -nolisten tcp -nolisten unix &
XVFB_PID=$!

# Wait for Xvfb to be ready
echo "Waiting for Xvfb to be ready..."
for i in {1..10}; do
    if xdpyinfo -display :99 >/dev/null 2>&1; then
        echo "✓ Xvfb is ready!"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "✗ ERROR: Xvfb failed to start"
        exit 1
    fi
    sleep 0.5
done

# Step 3: Start the application
echo ""
echo "Starting uvicorn server..."
echo "=== Ready to accept requests ==="
echo ""

# Execute the main command passed to the entrypoint
exec "$@"
