#!/usr/bin/env python3
"""
Simple example showing how to configure imports directly in the code.
No need for environment variables - just specify what you need!
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from envs.coding_env import CodeAction, CodingEnv


def main():
    print("=" * 70)
    print("Dynamic Import Configuration Example")
    print("=" * 70)
    print()

    # Configure imports right here in your code!
    # The imports you specify are what your code execution can use
    client = CodingEnv.from_docker_image(
        "coding-env:latest",
        additional_imports=["numpy", "scipy"]  # ← Simply list what you need!
    )

    # Now use numpy in your code
    code = """
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class Ball:
    number: int
    pos: np.ndarray  # Position vector [x, y]
    vel: np.ndarray  # Velocity vector [vx, vy]
    radius: float

# Create some balls
balls: List[Ball] = []
for i in range(5):
    ball = Ball(
        number=i + 1,
        pos=np.array([100.0 + i * 50, 300.0]),
        vel=np.array([0.0, 0.0]),
        radius=15.0
    )
    balls.append(ball)

# Physics simulation step
GRAVITY = np.array([0, 500])
DT = 0.016

for ball in balls:
    ball.vel += GRAVITY * DT
    ball.pos += ball.vel * DT
    print(f"Ball {ball.number}: pos={ball.pos}, vel={ball.vel}")
"""

    result = client.step(CodeAction(code=code))

    print("Execution Output:")
    print(result.observation.stdout)
    print(f"\nExit code: {result.observation.exit_code}")

    if result.observation.stderr:
        print(f"\nErrors:")
        print(result.observation.stderr)

    client.close()

    print("\n" + "=" * 70)
    print("✅ Done! Notice how easy it was:")
    print("   1. Specify additional_imports when creating the environment")
    print("   2. Use those imports in your code")
    print("   3. No Docker rebuild, no environment variables needed!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
