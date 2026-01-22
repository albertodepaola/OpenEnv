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
import matplotlib
matplotlib.use('TkAgg')  # Use Tk backend for Xvfb
import matplotlib.pyplot as plt
import numpy as np

# Create a simple plot
x = np.linspace(0, 10, 100)
y = np.sin(x)

fig = plt.figure(figsize=(10, 6))
plt.plot(x, y, 'b-', linewidth=2, label='sin(x)')
plt.plot(x, np.cos(x), 'r--', linewidth=2, label='cos(x)')
plt.title('Sine and Cosine Functions - RestrictedPython Test', fontsize=16)
plt.xlabel('x', fontsize=12)
plt.ylabel('y', fontsize=12)
plt.legend()
plt.grid(True, alpha=0.3)

# CRITICAL: Actually display the figure to the X11 display
# show(block=False) opens the window without blocking
# pause() gives time for the window to render
plt.show(block=False)
plt.pause(0.5)

# Force the figure canvas to draw
fig.canvas.draw()
fig.canvas.flush_events()

print("Matplotlib figure created and displayed successfully")
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


def test_python_animation():
    """Test bouncing balls animation with screenshot capture."""
    print("\n" + "=" * 70)
    print("TEST: Bouncing Balls Animation with RestrictedPython")
    print("=" * 70)

    print("\n[1/7] Creating CodingEnv with RestrictedPython backend...")
    env = CodingEnv.from_docker_image(
        image="coding-env:latest",
        additional_imports=["tkinter", "math", "numpy", "dataclasses", "typing"],
        executor_backend="restrictedpython",
        timeout_s=120.0,
    )

    print("Environment created")

    try:
        print("\n[2/7] Executing animation code...")
        # This is the actual Python code for the bouncing balls animation
        # Note: Simplified to avoid RestrictedPython tuple unpacking issues
        code = '''
import tkinter as tk
import math
from dataclasses import dataclass

# Constants
WIDTH = 800
HEIGHT = 800
CENTER_X = WIDTH // 2
CENTER_Y = HEIGHT // 2
HEPTAGON_RADIUS = 300
BALL_RADIUS = 20
NUM_BALLS = 20
GRAVITY = 0.5
FRICTION = 0.98
BOUNCE_DAMPING = 0.7
ROTATION_SPEED = 2 * math.pi / 5  # 360 degrees per 5 seconds

# Ball colors
COLORS = [
    "#f8b862", "#f6ad49", "#f39800", "#f08300", "#ec6d51",
    "#ee7948", "#ed6d3d", "#ec6800", "#ec6800", "#ee7800",
    "#eb6238", "#ea5506", "#ea5506", "#eb6101", "#e49e61",
    "#e45e32", "#e17b34", "#dd7a56", "#db8449", "#d66a35"
]

@dataclass
class Ball:
    x: float
    y: float
    vx: float
    vy: float
    radius: float
    color: str
    number: int
    angle: float = 0.0
    angular_velocity: float = 0.0

def get_heptagon_vertices(cx, cy, radius, rotation):
    """Get the 7 vertices of the heptagon as list of [x, y] pairs."""
    vertices = []
    for i in range(7):
        angle = rotation + (2 * math.pi * i / 7) - math.pi / 2
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        vertices.append([x, y])
    return vertices

def point_to_line_distance(px, py, x1, y1, x2, y2):
    """Calculate distance from point to line segment and closest point."""
    dx = x2 - x1
    dy = y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        dist = math.sqrt((px - x1)**2 + (py - y1)**2)
        return [dist, x1, y1]
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy
    dist = math.sqrt((px - closest_x)**2 + (py - closest_y)**2)
    return [dist, closest_x, closest_y]

def check_ball_wall_collision(ball, vertices):
    """Check and handle ball-wall collision."""
    collided = False
    for i in range(len(vertices)):
        v1 = vertices[i]
        v2 = vertices[(i + 1) % len(vertices)]
        result = point_to_line_distance(ball.x, ball.y, v1[0], v1[1], v2[0], v2[1])
        dist = result[0]
        cx = result[1]
        cy = result[2]
        if dist < ball.radius:
            # Calculate normal vector (pointing inward)
            nx = ball.x - cx
            ny = ball.y - cy
            length = math.sqrt(nx**2 + ny**2)
            if length > 0:
                nx = nx / length
                ny = ny / length
                # Move ball out of wall
                overlap = ball.radius - dist
                ball.x = ball.x + nx * overlap
                ball.y = ball.y + ny * overlap
                # Reflect velocity
                dot = ball.vx * nx + ball.vy * ny
                ball.vx = (ball.vx - 2 * dot * nx) * BOUNCE_DAMPING
                ball.vy = (ball.vy - 2 * dot * ny) * BOUNCE_DAMPING
                # Add spin from friction
                tangent_vel = -ball.vx * ny + ball.vy * nx
                ball.angular_velocity = ball.angular_velocity + tangent_vel * 0.1
                collided = True
    return collided

def check_ball_ball_collision(ball1, ball2):
    """Check and handle ball-ball collision."""
    dx = ball2.x - ball1.x
    dy = ball2.y - ball1.y
    dist = math.sqrt(dx**2 + dy**2)
    min_dist = ball1.radius + ball2.radius
    if dist < min_dist and dist > 0:
        # Normalize collision vector
        nx = dx / dist
        ny = dy / dist
        # Separate balls
        overlap = (min_dist - dist) / 2
        ball1.x = ball1.x - nx * overlap
        ball1.y = ball1.y - ny * overlap
        ball2.x = ball2.x + nx * overlap
        ball2.y = ball2.y + ny * overlap
        # Calculate relative velocity
        dvx = ball1.vx - ball2.vx
        dvy = ball1.vy - ball2.vy
        dvn = dvx * nx + dvy * ny
        if dvn > 0:
            # Apply impulse
            ball1.vx = ball1.vx - dvn * nx * BOUNCE_DAMPING
            ball1.vy = ball1.vy - dvn * ny * BOUNCE_DAMPING
            ball2.vx = ball2.vx + dvn * nx * BOUNCE_DAMPING
            ball2.vy = ball2.vy + dvn * ny * BOUNCE_DAMPING
            # Add spin
            ball1.angular_velocity = ball1.angular_velocity - dvn * 0.05
            ball2.angular_velocity = ball2.angular_velocity + dvn * 0.05

# Create window
root = tk.Tk()
root.title("Bouncing Balls in Spinning Heptagon")
root.geometry(str(WIDTH) + "x" + str(HEIGHT))

canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg="white")
canvas.pack()

# Initialize balls at center
balls = []
for i in range(NUM_BALLS):
    ball = Ball(
        x=CENTER_X + (i % 5 - 2) * 5,
        y=CENTER_Y + (i // 5 - 2) * 5,
        vx=(i % 3 - 1) * 2,
        vy=0,
        radius=BALL_RADIUS,
        color=COLORS[i],
        number=i + 1
    )
    balls.append(ball)

# Animation state
rotation = 0.0
frame_count = 0

def update():
    global rotation, frame_count
    frame_count = frame_count + 1

    # Update rotation (60 fps assumed, so divide by 60)
    rotation = rotation + ROTATION_SPEED / 60

    # Get current heptagon vertices
    vertices = get_heptagon_vertices(CENTER_X, CENTER_Y, HEPTAGON_RADIUS, rotation)

    # Update balls
    for ball in balls:
        # Apply gravity
        ball.vy = ball.vy + GRAVITY
        # Apply friction
        ball.vx = ball.vx * FRICTION
        ball.vy = ball.vy * FRICTION
        ball.angular_velocity = ball.angular_velocity * FRICTION
        # Update position
        ball.x = ball.x + ball.vx
        ball.y = ball.y + ball.vy
        ball.angle = ball.angle + ball.angular_velocity
        # Check wall collisions
        check_ball_wall_collision(ball, vertices)

    # Check ball-ball collisions
    for i in range(len(balls)):
        for j in range(i + 1, len(balls)):
            check_ball_ball_collision(balls[i], balls[j])

    # Clear and redraw
    canvas.delete("all")

    # Draw heptagon
    heptagon_coords = []
    for v in vertices:
        heptagon_coords.append(v[0])
        heptagon_coords.append(v[1])
    canvas.create_polygon(heptagon_coords, outline="black", fill="", width=3)

    # Draw balls
    for ball in balls:
        x1 = ball.x - ball.radius
        y1 = ball.y - ball.radius
        x2 = ball.x + ball.radius
        y2 = ball.y + ball.radius
        canvas.create_oval(x1, y1, x2, y2, fill=ball.color, outline="black")
        # Draw number with rotation
        canvas.create_text(
            ball.x, ball.y,
            text=str(ball.number),
            font=("Arial", 12, "bold"),
            fill="white",
            angle=math.degrees(ball.angle)
        )

    # Continue animation for a few frames then stop
    if frame_count < 60:  # Run for ~1 second
        root.after(16, update)
    else:
        print("Animation completed: " + str(frame_count) + " frames rendered")

# Start animation
update()

# Update display
root.update_idletasks()
root.update()

# Run a few more update cycles to ensure rendering
for _ in range(10):
    root.update()

print("Bouncing balls animation created and rendered successfully")
'''

        result = env.step(CodeAction(code=code, capture_screenshot=True))
        obs = result.observation

        print("\n[3/7] Analyzing results...")
        print(f"Exit Code: {obs.exit_code}")
        print(f"Stdout:\n{obs.stdout}")
        if obs.stderr:
            print(f"Stderr:\n{obs.stderr}")

        # Check if screenshot was captured
        print("\n[4/7] Checking screenshot...")
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
                        / "restrictedpython_animation_screenshot.png"
                    )
                    screenshot_path.write_bytes(png_bytes)
                    print(f"Screenshot saved to: {screenshot_path}")

                    # Basic validation: animation screenshot should be reasonably large
                    # (contains colored balls and heptagon outline)
                    if len(png_bytes) > 5000:
                        print(f"Screenshot size ({len(png_bytes)} bytes) indicates content present")
                    else:
                        print(f"Warning: Screenshot may be mostly empty ({len(png_bytes)} bytes)")
                else:
                    print("Warning: PNG signature not found")
                    return False
            except Exception as e:
                print(f"Failed to decode screenshot: {e}")
                return False
        else:
            print("No screenshot was captured")
            return False

        print("\n" + "=" * 70)
        print("TEST PASSED - Animation screenshot captured with RestrictedPython!")
        print("=" * 70)

        return True

    finally:
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
    print("Tkinter, matplotlib, and animation screenshot capture will be tested.")

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

    # Test 3: Animation screenshot
    try:
        result = test_python_animation()
        results.append(("Animation Screenshot", result))
    except Exception as e:
        print(f"\nAnimation test failed with error: {e}")
        import traceback

        traceback.print_exc()
        results.append(("Animation Screenshot", False))

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
