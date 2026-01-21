#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Test screenshot capture with RestrictedPython backend.

This script tests that screenshot capture works correctly with the
RestrictedPython executor backend, which is the final validation for
Milestone M1.

Tests:
1. Basic tkinter GUI with screenshot capture
2. Matplotlib figure with screenshot capture
3. Verify screenshot data is returned correctly
"""

import base64
import sys
from pathlib import Path

# Add src to path for openenv core
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# Add envs/coding_env to path for coding_env package
sys.path.insert(0, str(Path(__file__).parent.parent / "envs" / "coding_env"))

from coding_env import CodingEnv, CodeAction


def test_tkinter_screenshot_with_restrictedpython():
    """Test tkinter GUI screenshot capture with RestrictedPython backend."""
    print("=" * 70)
    print("TEST: Tkinter Screenshot Capture with RestrictedPython")
    print("=" * 70)

    print("\n[1/4] Creating CodingEnv with RestrictedPython backend...")
    env = CodingEnv.from_docker_image(
        image="coding-env:latest",  # Docker image name
        additional_imports=["tkinter"],
        executor_backend="restrictedpython",  # Use RestrictedPython backend
        timeout_s=120.0,  # Allow time for container startup
    )

    print("Environment created")

    try:
        print("\n[2/4] Executing code that creates a tkinter window...")
        code = """
import tkinter as tk

# Create a simple window
root = tk.Tk()
root.title("RestrictedPython Test")
root.geometry("400x300")

# Add a label
label = tk.Label(root, text="Hello from RestrictedPython!", font=("Arial", 20))
label.pack(pady=50)

# Add a button
button = tk.Button(root, text="Click Me!", bg="blue", fg="white", font=("Arial", 14))
button.pack(pady=20)

# CRITICAL: Update the window to render it to the display
root.update_idletasks()
root.update()

print("Tkinter window created and rendered successfully")
"""

        result = env.step(CodeAction(code=code, capture_screenshot=True))
        obs = result.observation

        print("\n[3/4] Analyzing results...")
        print(f"Exit Code: {obs.exit_code}")
        print(f"Stdout:\n{obs.stdout}")
        if obs.stderr:
            print(f"Stderr:\n{obs.stderr}")

        # Check if screenshot was captured
        print("\n[4/4] Checking screenshot...")
        if obs.screenshot:
            screenshot_size = len(obs.screenshot)
            print(f"Screenshot captured: {screenshot_size} bytes (base64)")

            # Try to decode to verify it's valid base64
            try:
                png_bytes = base64.b64decode(obs.screenshot)
                print(f"Valid base64 encoding: {len(png_bytes)} bytes PNG")

                # Check PNG signature (first 8 bytes)
                png_signature = b"\x89PNG\r\n\x1a\n"
                if png_bytes[:8] == png_signature:
                    print("Valid PNG file signature")

                    # Save screenshot to file
                    screenshot_path = (
                        Path(__file__).parent
                        / "restrictedpython_tkinter_screenshot.png"
                    )
                    screenshot_path.write_bytes(png_bytes)
                    print(f"Screenshot saved to: {screenshot_path}")
                else:
                    print(f"Warning: PNG signature not found. Got: {png_bytes[:8]}")
            except Exception as e:
                print(f"Failed to decode screenshot: {e}")
                return False
        else:
            print("No screenshot was captured")
            return False

        print("\n" + "=" * 70)
        print("TEST PASSED - Screenshot capture works with RestrictedPython!")
        print("=" * 70)

        return True

    finally:
        # Always cleanup - stop and remove container
        print("\n[Cleanup] Stopping and removing container...")
        env.close()
        print("Container cleaned up")


def test_matplotlib_screenshot_with_restrictedpython():
    """Test matplotlib figure screenshot capture with RestrictedPython backend."""
    print("\n" + "=" * 70)
    print("TEST: Matplotlib Screenshot Capture with RestrictedPython")
    print("=" * 70)

    print("\n[1/4] Creating CodingEnv with RestrictedPython backend...")
    env = CodingEnv.from_docker_image(
        image="coding-env:latest",  # Docker image name
        additional_imports=["matplotlib", "numpy"],
        executor_backend="restrictedpython",  # Use RestrictedPython backend
        timeout_s=120.0,
    )

    print("Environment created")

    try:
        print("\n[2/4] Executing code that creates a matplotlib figure...")
        code = """
import matplotlib.pyplot as plt
import numpy as np

# Create a simple plot
x = np.linspace(0, 10, 100)
y = np.sin(x)

plt.figure(figsize=(10, 6))
plt.plot(x, y, 'b-', linewidth=2, label='sin(x)')
plt.plot(x, np.cos(x), 'r--', linewidth=2, label='cos(x)')
plt.title('Sine and Cosine Functions - RestrictedPython Test', fontsize=16)
plt.xlabel('x', fontsize=12)
plt.ylabel('y', fontsize=12)
plt.legend()
plt.grid(True, alpha=0.3)

print("Matplotlib figure created successfully")
"""

        result = env.step(CodeAction(code=code, capture_screenshot=True))
        obs = result.observation

        print("\n[3/4] Analyzing results...")
        print(f"Exit Code: {obs.exit_code}")
        print(f"Stdout:\n{obs.stdout}")
        if obs.stderr:
            print(f"Stderr:\n{obs.stderr}")

        # Check if screenshot was captured
        print("\n[4/4] Checking screenshot...")
        if obs.screenshot:
            screenshot_size = len(obs.screenshot)
            print(f"Screenshot captured: {screenshot_size} bytes (base64)")

            try:
                png_bytes = base64.b64decode(obs.screenshot)
                print(f"Valid base64 encoding: {len(png_bytes)} bytes PNG")

                png_signature = b"\x89PNG\r\n\x1a\n"
                if png_bytes[:8] == png_signature:
                    print("Valid PNG file signature")

                    # Save screenshot to file
                    screenshot_path = (
                        Path(__file__).parent
                        / "restrictedpython_matplotlib_screenshot.png"
                    )
                    screenshot_path.write_bytes(png_bytes)
                    print(f"Screenshot saved to: {screenshot_path}")
                else:
                    print("Warning: PNG signature not found")
            except Exception as e:
                print(f"Failed to decode screenshot: {e}")
                return False
        else:
            print("No screenshot was captured")
            return False

        print("\n" + "=" * 70)
        print("TEST PASSED - Matplotlib screenshot works with RestrictedPython!")
        print("=" * 70)

        return True

    finally:
        # Always cleanup - stop and remove container
        print("\n[Cleanup] Stopping and removing container...")
        env.close()
        print("Container cleaned up")


def main():
    """Run all screenshot tests."""
    print("\n" + "=" * 70)
    print("TESTING SCREENSHOT CAPTURE WITH RESTRICTEDPYTHON BACKEND")
    print("=" * 70)

    print(
        "\nThis test uses the RestrictedPython backend via executor_backend parameter"
    )
    print("Both tkinter and matplotlib screenshot capture will be tested.")

    results = []

    # Test 1: Tkinter screenshot
    try:
        result = test_tkinter_screenshot_with_restrictedpython()
        results.append(("Tkinter Screenshot", result))
    except Exception as e:
        print(f"\nTkinter test failed with error: {e}")
        import traceback

        traceback.print_exc()
        results.append(("Tkinter Screenshot", False))

    # Test 2: Matplotlib screenshot
    try:
        result = test_matplotlib_screenshot_with_restrictedpython()
        results.append(("Matplotlib Screenshot", result))
    except Exception as e:
        print(f"\nMatplotlib test failed with error: {e}")
        import traceback

        traceback.print_exc()
        results.append(("Matplotlib Screenshot", False))

    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "PASSED" if result else "FAILED"
        print(f"{name}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\nALL SCREENSHOT TESTS PASSED!")
        print(
            "\nScreenshot capture is confirmed working with RestrictedPython backend!"
        )
        return 0
    else:
        print(f"\n{total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
