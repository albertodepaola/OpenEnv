# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

#!/usr/bin/env python3
"""
Simple test showing how users will use CodingEnv.from_docker_image().

This is the simplest possible usage
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from envs.coding_env import CodeAction, CodingEnv


def main():
    """Test CodingEnv.from_docker_image()."""
    print("=" * 60)
    print("CodingEnv.from_docker_image() Test")
    print("=" * 60)
    print()

    try:
        # This is what users will do - just one line!
        print("Creating client from Docker image...")
        print("  CodingEnv.from_docker_image('coding-env:latest')")
        print()

        client = CodingEnv.from_docker_image("coding-env:latest")

        print("✓ Client created and container started!\n")

        # Now use it like any other client
        print("Testing the environment:")
        print("-" * 60)

        # Reset
        print("\n1. Reset:")
        result = client.reset()
        print(f"   stdout: {result.observation.stdout}")
        print(f"   stderr: {result.observation.stderr}")
        print(f"   exit_code: {result.observation.exit_code}")

        # Get initial state
        state = client.state()
        print(f"   State: episode_id={state.episode_id}, step_count={state.step_count}")

        # Execute some Python code
        print("\n2. Execute Python code:")

        code_samples = [
            "print('Hello, World!')",
            "x = 5 + 3\nprint(f'Result: {x}')",
            "import math\nprint(f'Pi is approximately {math.pi:.4f}')",
            "# Multi-line calculation\nfor i in range(1, 4):\n    print(f'{i} squared is {i**2}')",
        ]

        for i, code in enumerate(code_samples, 1):
            result = client.step(CodeAction(code=code))
            print(f"   {i}. Code: {code.replace(chr(10), '\\n')[:50]}...")
            print(f"      → stdout: {result.observation.stdout.strip()}")
            print(f"      → exit_code: {result.observation.exit_code}")
            print(f"      → reward: {result.reward}")
            if result.observation.stderr:
                print(f"      → stderr: {result.observation.stderr}")

        # Test UI code with tkinter
        print("\n3. Test UI code (tkinter - may fail without display):")

        tkinter_code = """import tkinter as tk

# Create main window
root = tk.Tk()
root.title("Test Canvas")
root.geometry("400x300")

# Create canvas
canvas = tk.Canvas(root, width=400, height=300, bg='white')
canvas.pack()

# Draw some elements
# Rectangle
canvas.create_rectangle(50, 50, 150, 150, fill='blue', outline='black')

# Circle (oval)
canvas.create_oval(200, 50, 300, 150, fill='red', outline='black')

# Line
canvas.create_line(50, 200, 300, 200, fill='green', width=3)

# Text
canvas.create_text(200, 250, text='Hello from Tkinter!', font=('Arial', 14))

print('Canvas created with rectangle, circle, line, and text')
print('Window size: 400x300')
print('Elements: 1 blue rectangle, 1 red circle, 1 green line, 1 text label')

# Note: In a headless environment, mainloop() would block forever
# So we just print success and exit instead
# root.mainloop()
"""

        result = client.step(CodeAction(code=tkinter_code))
        print("   Code: Tkinter canvas with shapes")
        print(f"      → stdout: {result.observation.stdout.strip()}")
        print(f"      → exit_code: {result.observation.exit_code}")
        if result.observation.stderr:
            # Truncate long error messages
            error_msg = result.observation.stderr
            # if len(result.observation.stderr) > 200:
            #     error_msg += "..."
            print(f"      → stderr: {error_msg}")

        # Test screenshot capture
        print("\n4. Test screenshot capture (NEW: captures DURING execution):")
        print("   The screenshot is now captured while UI elements are still alive,")
        print("   with automatic rendering timeout to ensure proper display.")

        result = client.step(CodeAction(code=tkinter_code, capture_screenshot=True))
        print("   Code: Tkinter canvas with shapes (with screenshot)")
        print(f"      → stdout: {result.observation.stdout.strip()}")
        print(f"      → exit_code: {result.observation.exit_code}")

        if result.observation.screenshot:
            import base64

            screenshot_bytes = base64.b64decode(result.observation.screenshot)
            print(f"      → ✅ screenshot captured: {len(screenshot_bytes)} bytes PNG")
            print(f"      → base64 length: {len(result.observation.screenshot)} chars")

            # Optionally save to file for inspection
            screenshot_path = Path(__file__).parent / "screenshot_test.png"
            screenshot_path.write_bytes(screenshot_bytes)
            print(f"      → saved to: {screenshot_path}")
            print(
                "      → Screenshot should show blue rectangle, red circle, green line, and text!"
            )
        else:
            print("      → ❌ screenshot: None (capture failed - check Xvfb)")

        # Test advanced screenshot with matplotlib
        print("\n5. Test matplotlib screenshot:")

        matplotlib_code = """import matplotlib
matplotlib.use('TkAgg')  # Use Tk backend for Xvfb
import matplotlib.pyplot as plt
import numpy as np

# Create a simple plot
x = np.linspace(0, 2 * np.pi, 100)
y = np.sin(x)

plt.figure(figsize=(8, 6))
plt.plot(x, y, 'b-', linewidth=2, label='sin(x)')
plt.plot(x, np.cos(x), 'r--', linewidth=2, label='cos(x)')
plt.title('Sine and Cosine Waves', fontsize=16)
plt.xlabel('x (radians)')
plt.ylabel('y')
plt.legend()
plt.grid(True, alpha=0.3)

print('Plot created successfully')
"""

        result = client.step(CodeAction(code=matplotlib_code, capture_screenshot=True))
        print("   Code: Matplotlib sine/cosine plot")
        print(f"      → stdout: {result.observation.stdout.strip()}")
        print(f"      → exit_code: {result.observation.exit_code}")

        if result.observation.screenshot:
            import base64

            screenshot_bytes = base64.b64decode(result.observation.screenshot)
            print(f"      → ✅ screenshot captured: {len(screenshot_bytes)} bytes PNG")

            # Save matplotlib screenshot
            screenshot_path = Path(__file__).parent / "matplotlib_plot.png"
            screenshot_path.write_bytes(screenshot_bytes)
            print(f"      → saved to: {screenshot_path}")
        else:
            print("      → ❌ screenshot: None (capture may have failed)")

        # Test error scenarios
        print("\n6. Test error scenarios:")

        error_samples = [
            ("Division by zero", "x = 1 / 0\nprint('Should not reach here')"),
            ("Undefined variable", "print(undefined_variable)"),
            ("Syntax error", "print('Hello'"),
        ]

        for i, (description, code) in enumerate(error_samples, 1):
            result = client.step(CodeAction(code=code))
            print(f"   {i}. {description}")
            print(f"      Code: {code.replace(chr(10), '\\n')[:40]}...")
            print(f"      → exit_code: {result.observation.exit_code}")
            print(f"      → reward: {result.reward}")

            if result.observation.stderr:
                # Truncate long error messages
                error_msg = result.observation.stderr[:100]
                if len(result.observation.stderr) > 100:
                    error_msg += "..."
                print(f"      → stderr: {error_msg}")

        # Check final state
        print("\n7. Check final state:")
        state = client.state()
        print(f"   episode_id: {state.episode_id}")
        print(f"   step_count: {state.step_count}")
        print(f"   last_exit_code: {state.last_exit_code}")

        print("\n" + "-" * 60)
        print("\n✓ All operations successful!")
        print()

        print("Cleaning up...")
        client.close()
        print("✓ Container stopped and removed")
        print()

        print("=" * 60)
        print("Test completed successfully! 🎉")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
