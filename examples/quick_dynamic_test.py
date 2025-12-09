#!/usr/bin/env python3
"""
Quick test to verify dynamic package installation is working.
Uses pandas (small package) instead of requests.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from envs.coding_env import CodeAction, CodingEnv

print("Testing dynamic package installation...")
print("This will install 'pandas' at container startup.")
print()

# Create environment with pandas (not in base image)
client = CodingEnv.from_docker_image(
    "coding-env:latest",
    additional_imports=["pandas", "dataclasses"],  # pandas will be installed, dataclasses skipped
    timeout_s=90.0  # Allow time for pip install
)

# Test pandas import
code = """
import pandas as pd
from dataclasses import dataclass

@dataclass
class DataPoint:
    x: float
    y: float

# Create a simple dataframe
df = pd.DataFrame({
    'x': [1, 2, 3, 4, 5],
    'y': [2, 4, 6, 8, 10]
})

print("✓ Pandas imported successfully!")
print(f"  Version: {pd.__version__}")
print(f"\\nDataFrame:\\n{df}")
print(f"\\nMean: x={df['x'].mean()}, y={df['y'].mean()}")
"""

result = client.step(CodeAction(code=code))

print("Output:")
print(result.observation.stdout)

if result.observation.exit_code != 0:
    print(f"\n❌ Failed with exit code: {result.observation.exit_code}")
    if result.observation.stderr:
        print(f"Errors: {result.observation.stderr}")
else:
    print("\n✅ Success! Pandas was dynamically installed and works!")

client.close()
