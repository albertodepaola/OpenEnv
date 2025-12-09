#!/usr/bin/env python3
"""
Example showing how to configure additional imports dynamically
from the client without modifying the Docker image.

This uses the ADDITIONAL_IMPORTS environment variable to authorize
additional Python modules at container startup.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from envs.coding_env import CodeAction, CodingEnv


def example_with_numpy():
    """Example using numpy with dynamically authorized imports."""
    print("=" * 70)
    print("Example: Dynamic Import Authorization (numpy, scipy)")
    print("=" * 70)

    # Create environment with additional imports via environment variable
    # The ADDITIONAL_IMPORTS env var is passed to the Docker container
    client = CodingEnv.from_docker_image(
        "coding-env:latest",
        env_vars={
            "ADDITIONAL_IMPORTS": "numpy,scipy,pandas",  # Comma-separated list
        }
    )

    # Now you can use numpy in your code!
    code = """
import numpy as np

# Create array
arr = np.array([1, 2, 3, 4, 5])
print(f"Array: {arr}")
print(f"Mean: {np.mean(arr)}")
print(f"Std: {np.std(arr)}")

# Matrix operations
matrix = np.random.rand(3, 3)
print(f"\\nRandom 3x3 matrix:\\n{matrix}")
print(f"Determinant: {np.linalg.det(matrix):.4f}")
"""

    result = client.step(CodeAction(code=code))

    print("\nOutput:")
    print(result.observation.stdout)
    print(f"Exit code: {result.observation.exit_code}")

    client.close()
    print()


def example_without_additional_imports():
    """Example showing what happens without authorizing imports."""
    print("=" * 70)
    print("Example: Without Authorization (will fail)")
    print("=" * 70)

    # Create environment WITHOUT numpy authorization
    client = CodingEnv.from_docker_image("coding-env:latest")

    code = """
import numpy as np  # This will fail!
arr = np.array([1, 2, 3])
print(arr)
"""

    result = client.step(CodeAction(code=code))

    print("\nOutput:")
    print(result.observation.stdout)
    if result.observation.stderr:
        print("\nError (expected):")
        print(result.observation.stderr[:200] + "...")

    client.close()
    print()


def example_dataclass_with_imports():
    """Example using dataclasses with numpy (from the user's heptagon simulation)."""
    print("=" * 70)
    print("Example: Dataclasses + NumPy (Complex Simulation)")
    print("=" * 70)

    # Authorize numpy for the simulation code
    client = CodingEnv.from_docker_image(
        "coding-env:latest",
        env_vars={
            "ADDITIONAL_IMPORTS": "numpy",
        }
    )

    code = """
import numpy as np
from dataclasses import dataclass

@dataclass
class Vector2D:
    x: float
    y: float

    def as_array(self) -> np.ndarray:
        return np.array([self.x, self.y])

    def magnitude(self) -> float:
        return np.linalg.norm(self.as_array())

# Create vectors
v1 = Vector2D(3.0, 4.0)
v2 = Vector2D(1.0, 2.0)

print(f"v1: {v1}")
print(f"v1 magnitude: {v1.magnitude():.2f}")

# Vector math with numpy
arr1 = v1.as_array()
arr2 = v2.as_array()
dot_product = np.dot(arr1, arr2)
print(f"\\nDot product: {dot_product:.2f}")
"""

    result = client.step(CodeAction(code=code))

    print("\nOutput:")
    print(result.observation.stdout)
    print(f"Exit code: {result.observation.exit_code}")

    client.close()
    print()


if __name__ == "__main__":
    print("\n")
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║       Dynamic Import Authorization Examples                       ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    print()
    print("These examples show how to authorize additional Python imports")
    print("from the client WITHOUT rebuilding the Docker image.")
    print()
    print("Note: The libraries must still be installed in the Docker image!")
    print("      This only controls which imports are ALLOWED by smolagents.")
    print()

    try:
        # Example 1: With numpy authorized
        example_with_numpy()

        # Example 2: Without authorization (will fail)
        example_without_additional_imports()

        # Example 3: Complex dataclass example
        example_dataclass_with_imports()

        print("=" * 70)
        print("✅ All examples completed!")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
