#!/usr/bin/env python3
"""
Example demonstrating the improved screenshot capture API.

The screenshot is now captured DURING code execution (not after),
ensuring UI elements are still alive when the screenshot is taken.
A 0.5s rendering timeout is automatically applied.
"""

import sys
from pathlib import Path
import base64

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from envs.coding_env import CodeAction, CodingEnv


def example_1_basic_tkinter():
    """Example 1: Basic tkinter screenshot."""
    print("=" * 70)
    print("Example 1: Basic Tkinter Screenshot")
    print("=" * 70)

    client = CodingEnv.from_docker_image("coding-env:latest")

    code = """
import tkinter as tk

# Create window
root = tk.Tk()
root.title("My Drawing")
root.geometry("400x300")

# Create canvas
canvas = tk.Canvas(root, width=400, height=300, bg='white')
canvas.pack()

# Draw shapes
canvas.create_rectangle(50, 50, 150, 150, fill='blue', outline='black', width=2)
canvas.create_oval(200, 50, 300, 150, fill='red', outline='black', width=2)
canvas.create_line(50, 200, 300, 200, fill='green', width=3)
canvas.create_text(200, 250, text='Hello from Tkinter!', font=('Arial', 16, 'bold'))

print('Created: blue rectangle, red circle, green line, and text')
"""

    # Simple! Just set capture_screenshot=True
    result = client.step(CodeAction(code=code, capture_screenshot=True))

    print(f"\n--- Full Execution Output ---")
    print(f"STDOUT:\n{result.observation.stdout}")
    if result.observation.stderr:
        print(f"\nSTDERR:\n{result.observation.stderr}")
    print(f"\nExit code: {result.observation.exit_code}")
    print(f"Screenshot present: {result.observation.screenshot is not None}")

    if result.observation.screenshot:
        screenshot_bytes = base64.b64decode(result.observation.screenshot)
        output_path = Path(__file__).parent / "tkinter_screenshot.png"
        output_path.write_bytes(screenshot_bytes)
        print(f"\n✅ Screenshot saved to: {output_path}")
        print(f"   Size: {len(screenshot_bytes)} bytes")
    else:
        print("\n❌ Screenshot capture failed")
        print("   Check the debug output above for details")

    client.close()
    print()


def example_2_matplotlib():
    """Example 2: Matplotlib plot screenshot."""
    print("=" * 70)
    print("Example 2: Matplotlib Plot Screenshot")
    print("=" * 70)

    client = CodingEnv.from_docker_image("coding-env:latest")

    code = """
import matplotlib
matplotlib.use('TkAgg')  # Required for Xvfb
import matplotlib.pyplot as plt
import numpy as np

# Create plot
x = np.linspace(0, 2 * np.pi, 100)

plt.figure(figsize=(8, 6))
plt.plot(x, np.sin(x), 'b-', linewidth=2, label='sin(x)')
plt.plot(x, np.cos(x), 'r--', linewidth=2, label='cos(x)')
plt.title('Trigonometric Functions', fontsize=16)
plt.xlabel('x (radians)')
plt.ylabel('y')
plt.legend()
plt.grid(True, alpha=0.3)

print('Matplotlib plot created')
"""

    # Automatic screenshot with rendering timeout
    result = client.step(CodeAction(code=code, capture_screenshot=True))

    print(f"Execution output:\n{result.observation.stdout}")

    if result.observation.screenshot:
        screenshot_bytes = base64.b64decode(result.observation.screenshot)
        output_path = Path(__file__).parent / "matplotlib_screenshot.png"
        output_path.write_bytes(screenshot_bytes)
        print(f"\n✅ Screenshot saved to: {output_path}")
        print(f"   Size: {len(screenshot_bytes)} bytes")
    else:
        print("\n❌ Screenshot capture failed")

    client.close()
    print()


def example_3_no_screenshot():
    """Example 3: Normal execution without screenshot."""
    print("=" * 70)
    print("Example 3: Normal Execution (No Screenshot)")
    print("=" * 70)

    client = CodingEnv.from_docker_image("coding-env:latest")

    code = """
# No UI code, just computation
result = sum(range(100))
print(f'Sum of 0-99: {result}')
"""

    # Don't capture screenshot for non-UI code
    result = client.step(CodeAction(code=code, capture_screenshot=False))

    print(f"Execution output:\n{result.observation.stdout}")
    print(f"Screenshot: {result.observation.screenshot}")

    client.close()
    print()


if __name__ == "__main__":
    print("\n")
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║       Screenshot Capture API - Usage Examples                     ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    print()
    print("The screenshot is captured DURING code execution with automatic")
    print("rendering timeout, ensuring UI elements are still alive.")
    print()

    try:
        example_1_basic_tkinter()
        example_2_matplotlib()
        example_3_no_screenshot()

        print("=" * 70)
        print("✅ All examples completed successfully!")
        print("=" * 70)
        print()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
