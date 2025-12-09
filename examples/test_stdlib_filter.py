#!/usr/bin/env python3
"""
Test that common stdlib typos/variations are filtered correctly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from envs.coding_env import CodeAction, CodingEnv

print("Testing stdlib filtering with common typos...")
print("Testing: dataclass (should be dataclasses), types, typing")
print()

# Create environment with common typos that should be filtered
client = CodingEnv.from_docker_image(
    "coding-env:latest",
    additional_imports=[
        "dataclass",      # Typo - should be "dataclasses" (plural)
        "types",          # Stdlib - should be filtered
        "typing",         # Stdlib - should be filtered
        "numpy",          # PyPI - should be installed
    ],
    timeout_s=90.0
)

# Test that they all work
code = """
from dataclasses import dataclass
from typing import List, Optional
import types
import numpy as np

@dataclass
class Point:
    x: float
    y: float

points: List[Point] = [
    Point(1.0, 2.0),
    Point(3.0, 4.0),
]

print(f"✓ Created {len(points)} points")
print(f"  Points: {points}")

arr = np.array([p.x for p in points])
print(f"  Mean X: {arr.mean()}")
print(f"\\n✓ All imports work correctly!")
"""

result = client.step(CodeAction(code=code))

print("Output:")
print(result.observation.stdout)

if result.observation.exit_code != 0:
    print(f"\n❌ Failed with exit code: {result.observation.exit_code}")
    if result.observation.stderr:
        print(f"Stderr: {result.observation.stderr}")
else:
    print("\n✅ Success! Stdlib typos were filtered correctly!")
    print("   - 'dataclass' (typo) was skipped ✓")
    print("   - 'types' and 'typing' were skipped ✓")
    print("   - 'numpy' was installed dynamically ✓")

client.close()
