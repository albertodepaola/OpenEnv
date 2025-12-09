#!/usr/bin/env python3
"""Quick debug test to check reward computation."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from envs.coding_env import CodeAction, CodingEnv


def main():
    print("Testing reward computation...")
    print()

    # Create client
    print("Creating CodingEnv client...")
    client = CodingEnv.from_docker_image("coding-env:latest")
    print("✓ Client created")
    print()

    # Reset
    print("Resetting environment...")
    result = client.reset()
    print(f"  Reset reward: {result.observation.reward}")
    print()

    # Test 1: Simple safe code (should get 0.1 for concise + 0.0 for safe = 0.1)
    print("Test 1: Simple safe code")
    code1 = "print('Hello')"
    result1 = client.step(CodeAction(code=code1))
    print(f"  Code: {code1}")
    print(f"  Reward: {result1.observation.reward}")
    print(f"  Exit code: {result1.observation.exit_code}")
    print(f"  Metadata: {result1.observation.metadata}")
    print()

    # Test 2: Dangerous code (should get -1.0)
    print("Test 2: Dangerous code with import os")
    code2 = "import os\nprint(os.getcwd())"
    result2 = client.step(CodeAction(code=code2))
    print(f"  Code: {code2}")
    print(f"  Reward: {result2.observation.reward}")
    print(f"  Exit code: {result2.observation.exit_code}")
    print(f"  Metadata: {result2.observation.metadata}")
    print()

    # Test 3: Long code (should get 0.0 for safe, no concise bonus)
    print("Test 3: Long safe code")
    code3 = "x = " + " + ".join(str(i) for i in range(50)) + "\nprint(x)"
    result3 = client.step(CodeAction(code=code3))
    print(f"  Code length: {len(code3)} chars")
    print(f"  Reward: {result3.observation.reward}")
    print(f"  Exit code: {result3.observation.exit_code}")
    print()

    # Cleanup
    print("Cleaning up...")
    client.close()
    print("✓ Done")


if __name__ == "__main__":
    main()
