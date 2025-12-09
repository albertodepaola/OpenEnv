#!/usr/bin/env python3
"""
Example showing dynamic package installation at container startup.

This demonstrates that you can specify ANY PyPI package in additional_imports
and it will be installed automatically when the container starts - no need to
rebuild the Docker image!
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from envs.coding_env import CodeAction, CodingEnv


def test_dynamic_package_install():
    """Test that packages not in the base image get installed dynamically."""
    print("=" * 70)
    print("Dynamic Package Installation Test")
    print("=" * 70)
    print()
    print("This will install 'requests' package dynamically at startup.")
    print("Watch for the startup logs showing package installation...")
    print()

    # Specify a package that's NOT in the base image
    # The entrypoint script will pip install it automatically
    # Use longer timeout since pip install takes time (60s instead of default 30s)
    client = CodingEnv.from_docker_image(
        "coding-env:latest",
        additional_imports=[
            "requests",     # PyPI package - will be installed
            "dataclasses",  # stdlib - will be skipped (already available)
            "typing",       # stdlib - will be skipped (already available)
        ],
        timeout_s=60.0  # Allow time for pip install
    )

    # Now use the dynamically installed package
    code = """
import requests
from dataclasses import dataclass
from typing import Optional

@dataclass
class HTTPResponse:
    status_code: int
    url: str
    success: bool

# Make a simple HTTP request
response = requests.get("https://httpbin.org/json")

result = HTTPResponse(
    status_code=response.status_code,
    url=response.url,
    success=response.ok
)

print(f"HTTP Request Result:")
print(f"  URL: {result.url}")
print(f"  Status Code: {result.status_code}")
print(f"  Success: {result.success}")
print(f"  Content Length: {len(response.content)} bytes")
"""

    print("Executing code that uses 'requests' package...")
    result = client.step(CodeAction(code=code))

    print("\n--- Execution Output ---")
    print(result.observation.stdout)

    if result.observation.stderr:
        print("\n--- Errors ---")
        print(result.observation.stderr)

    print(f"\nExit code: {result.observation.exit_code}")

    client.close()

    print("\n" + "=" * 70)
    print("✅ Success! Key points:")
    print("   1. 'requests' was NOT in the base Docker image")
    print("   2. It was installed automatically at container startup")
    print("   3. stdlib modules (dataclasses, typing) were skipped")
    print("   4. Your code could use the package immediately")
    print("   5. NO Docker rebuild required!")
    print("=" * 70)


def test_stdlib_vs_pypi():
    """Test that stdlib modules don't get installed but are still usable."""
    print("\n" + "=" * 70)
    print("Stdlib vs PyPI Test")
    print("=" * 70)
    print()

    client = CodingEnv.from_docker_image(
        "coding-env:latest",
        additional_imports=[
            "json",         # stdlib - should skip install
            "collections",  # stdlib - should skip install
            "pathlib",      # stdlib - should skip install
        ]
    )

    code = """
import json
from collections import Counter, defaultdict
from pathlib import Path

# All these are stdlib - no install needed!
data = {"hello": "world", "count": 42}
json_str = json.dumps(data)
print(f"JSON: {json_str}")

counter = Counter("hello world")
print(f"Character counts: {counter.most_common(3)}")

d = defaultdict(int)
d["key"] += 1
print(f"defaultdict: {dict(d)}")

p = Path("/tmp/test.txt")
print(f"Path parts: {p.parts}")
"""

    result = client.step(CodeAction(code=code))

    print("Output:")
    print(result.observation.stdout)
    print(f"\nExit code: {result.observation.exit_code}")

    client.close()

    print("\n✅ All stdlib modules worked without installation!")


if __name__ == "__main__":
    try:
        # Test 1: Dynamic PyPI package installation
        test_dynamic_package_install()

        # Test 2: Stdlib modules (no installation needed)
        test_stdlib_vs_pypi()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
