#!/usr/bin/env python3
"""
Diagnostic script to test screenshot capture directly in the container.
This helps identify if the issue is with Xvfb, ImageMagick, or the capture code.
"""

import sys
from pathlib import Path
import subprocess

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from envs.coding_env import CodeAction, CodingEnv


def test_container_environment():
    """Test the container environment for screenshot prerequisites."""
    print("=" * 70)
    print("Container Environment Diagnostics")
    print("=" * 70)

    client = CodingEnv.from_docker_image("coding-env:latest")

    # Test 1: Check if Xvfb is running
    print("\n[Test 1] Checking if Xvfb is running...")
    code = """
import subprocess
import os

print("[INFO] Checking for Xvfb process...")
try:
    result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
    if 'Xvfb' in result.stdout:
        print("[✓] Xvfb is running")
        for line in result.stdout.split('\\n'):
            if 'Xvfb' in line:
                print(f"    {line}")
    else:
        print("[✗] Xvfb is NOT running")
        print("    This is the problem! Xvfb must be running for screenshots.")
except Exception as e:
    print(f"[✗] Error checking processes: {e}")

print("[INFO] Checking DISPLAY environment variable...")
display = os.environ.get('DISPLAY')
if display:
    print(f"[✓] DISPLAY is set to: {display}")
else:
    print("[✗] DISPLAY is not set")
    print("    This is a problem! DISPLAY must be set for X11 applications.")
"""

    result = client.step(CodeAction(code=code))
    print(result.observation.stdout)
    if result.observation.stderr:
        print(f"STDERR: {result.observation.stderr}")

    # Test 2: Check if ImageMagick 'import' command is available
    print("\n[Test 2] Checking if ImageMagick 'import' command is available...")
    code = """
import subprocess
import shutil

print("[INFO] Checking for ImageMagick 'import' command...")
import_path = shutil.which('import')
if import_path:
    print(f"[✓] 'import' command found at: {import_path}")

    # Try to get version
    try:
        result = subprocess.run(['import', '-version'], capture_output=True, text=True, timeout=2)
        print("[INFO] ImageMagick version:")
        for line in result.stdout.split('\\n')[:3]:
            if line.strip():
                print(f"    {line}")
    except Exception as e:
        print(f"[!] Could not get version: {e}")
else:
    print("[✗] 'import' command NOT found")
    print("    This is the problem! ImageMagick must be installed.")
    print("    Install with: apt-get install imagemagick")
"""

    result = client.step(CodeAction(code=code))
    print(result.observation.stdout)
    if result.observation.stderr:
        print(f"STDERR: {result.observation.stderr}")

    # Test 3: Test screenshot_utils directly
    print("\n[Test 3] Testing screenshot_utils.capture_screenshot_base64() directly...")
    code = """
print("[INFO] Attempting direct screenshot capture...")

try:
    from envs.coding_env.server.screenshot_utils import capture_screenshot_base64

    print("[INFO] Imported capture_screenshot_base64 successfully")
    print("[INFO] Calling capture_screenshot_base64(verbose=True)...")

    screenshot = capture_screenshot_base64(display=":99", verbose=True)

    if screenshot:
        print(f"[✓] Screenshot captured successfully!")
        print(f"    Base64 length: {len(screenshot)} characters")
        print(f"    Estimated PNG size: ~{len(screenshot) * 3 // 4} bytes")
    else:
        print("[✗] Screenshot capture returned None")

except Exception as e:
    print(f"[✗] Error during screenshot capture: {e}")
    import traceback
    print(traceback.format_exc())
"""

    result = client.step(CodeAction(code=code))
    print(result.observation.stdout)
    if result.observation.stderr:
        print(f"STDERR: {result.observation.stderr}")

    # Test 4: Test with actual tkinter window
    print("\n[Test 4] Testing with actual tkinter window...")
    code = """
import tkinter as tk

print("[INFO] Creating tkinter window...")
root = tk.Tk()
root.geometry("200x200")
canvas = tk.Canvas(root, width=200, height=200, bg='white')
canvas.pack()
canvas.create_rectangle(50, 50, 150, 150, fill='blue')
print("[✓] Tkinter window created")

print("[INFO] Updating tkinter display...")
root.update_idletasks()
root.update()
print("[✓] Tkinter display updated")

print("[INFO] Waiting for render...")
import time
time.sleep(0.5)

print("[INFO] Attempting screenshot capture...")
try:
    from envs.coding_env.server.screenshot_utils import capture_screenshot_base64
    screenshot = capture_screenshot_base64(display=":99", verbose=True)

    if screenshot:
        print(f"[✓] Screenshot captured with tkinter window!")
        print(f"    Base64 length: {len(screenshot)} characters")
    else:
        print("[✗] Screenshot capture failed even with tkinter window")
except Exception as e:
    print(f"[✗] Error: {e}")
    import traceback
    print(traceback.format_exc())
"""

    result = client.step(CodeAction(code=code))
    print(result.observation.stdout)
    if result.observation.stderr:
        print(f"STDERR: {result.observation.stderr}")

    client.close()

    print("\n" + "=" * 70)
    print("Diagnostics Complete")
    print("=" * 70)


if __name__ == "__main__":
    try:
        test_container_environment()
    except Exception as e:
        print(f"\n❌ Diagnostic test failed: {e}")
        import traceback
        traceback.print_exc()
