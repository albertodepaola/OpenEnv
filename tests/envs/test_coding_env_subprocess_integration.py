# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Integration tests for CodingEnv with Subprocess Executor Docker image.

These tests require Docker to be running and the coding-env-subprocess image to be built:
    docker build -t coding-env-subprocess:latest -f envs/coding_env/server/Dockerfile.subprocess .

Run with:
    PYTHONPATH=src:envs SKIP_DOCKER_TESTS=0 uv run pytest tests/envs/test_coding_env_subprocess_integration.py -v

These tests verify that the subprocess executor backend produces the same results
as the default smolagents backend, ensuring compatibility.
"""

import os
import sys
from pathlib import Path

import pytest

# Add paths for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "envs"))

# Skip if Docker is not available or image not built
docker_available = pytest.mark.skipif(
    os.environ.get("SKIP_DOCKER_TESTS", "1") == "1",
    reason="Docker tests disabled. Set SKIP_DOCKER_TESTS=0 to enable.",
)

from coding_env import CodeAction, CodingEnv


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def subprocess_env_client():
    """Create a CodingEnv client from subprocess Docker image.

    This fixture is module-scoped to avoid starting/stopping containers
    for each test, which is slow.
    """
    client = CodingEnv.from_docker_image(
        "coding-env-subprocess:latest",
        executor_backend="subprocess",
    )
    yield client
    client.close()


# ============================================================================
# Integration Tests - Same as test_coding_env_integration.py
# ============================================================================


@docker_available
class TestSubprocessEnvDocker:
    """Integration tests that run against the subprocess Docker container."""

    def test_reset(self, subprocess_env_client):
        """Test that reset returns a valid observation."""
        result = subprocess_env_client.reset()

        assert result.observation is not None
        assert result.observation.exit_code == 0
        assert result.observation.stderr == ""

    def test_step_simple_print(self, subprocess_env_client):
        """Test executing a simple print statement."""
        subprocess_env_client.reset()

        result = subprocess_env_client.step(CodeAction(code="print('Hello, World!')"))

        assert result.observation.exit_code == 0
        assert "Hello, World!" in result.observation.stdout
        assert result.reward is not None

    def test_step_calculation(self, subprocess_env_client):
        """Test executing a calculation."""
        subprocess_env_client.reset()

        result = subprocess_env_client.step(
            CodeAction(code="x = 5 + 3\nprint(f'Result: {x}')")
        )

        assert result.observation.exit_code == 0
        assert "Result: 8" in result.observation.stdout

    def test_step_import_math(self, subprocess_env_client):
        """Test importing and using the math module."""
        subprocess_env_client.reset()

        result = subprocess_env_client.step(
            CodeAction(code="import math\nprint(f'Pi: {math.pi:.4f}')")
        )

        assert result.observation.exit_code == 0
        assert "Pi: 3.1416" in result.observation.stdout

    def test_step_multiline(self, subprocess_env_client):
        """Test executing multi-line code."""
        subprocess_env_client.reset()

        code = """
for i in range(1, 4):
    print(f'{i} squared is {i**2}')
"""
        result = subprocess_env_client.step(CodeAction(code=code))

        assert result.observation.exit_code == 0
        assert "1 squared is 1" in result.observation.stdout
        assert "2 squared is 4" in result.observation.stdout
        assert "3 squared is 9" in result.observation.stdout

    def test_error_division_by_zero(self, subprocess_env_client):
        """Test that division by zero returns an error."""
        subprocess_env_client.reset()

        result = subprocess_env_client.step(CodeAction(code="x = 1 / 0"))

        assert result.observation.exit_code == 1
        assert (
            "ZeroDivisionError" in result.observation.stderr
            or result.observation.stderr != ""
        )

    def test_error_undefined_variable(self, subprocess_env_client):
        """Test that undefined variable returns an error."""
        subprocess_env_client.reset()

        result = subprocess_env_client.step(CodeAction(code="print(undefined_variable)"))

        assert result.observation.exit_code == 1

    def test_error_syntax_error(self, subprocess_env_client):
        """Test that syntax error returns an error."""
        subprocess_env_client.reset()

        result = subprocess_env_client.step(CodeAction(code="print('Hello'"))

        assert result.observation.exit_code == 1

    def test_state_tracking(self, subprocess_env_client):
        """Test that state is properly tracked."""
        subprocess_env_client.reset()

        state = subprocess_env_client.state()
        assert state.episode_id is not None
        assert state.step_count == 0

        subprocess_env_client.step(CodeAction(code="x = 1"))
        state = subprocess_env_client.state()
        assert state.step_count == 1

        subprocess_env_client.step(CodeAction(code="y = 2"))
        state = subprocess_env_client.state()
        assert state.step_count == 2

    def test_reward_safe_code(self, subprocess_env_client):
        """Test that safe code receives a positive or zero reward."""
        subprocess_env_client.reset()

        result = subprocess_env_client.step(CodeAction(code="x = 5"))

        assert result.reward is not None
        assert result.reward >= 0  # Safe code should not be penalized

    def test_reward_dangerous_code(self, subprocess_env_client):
        """Test that dangerous code receives a negative reward."""
        subprocess_env_client.reset()

        result = subprocess_env_client.step(CodeAction(code="import os"))

        assert result.reward is not None
        assert result.reward < 0  # Dangerous code should be penalized

    # ========================================================================
    # Subprocess-specific tests: Features that work better with subprocess
    # ========================================================================

    def test_dataclass_support(self, subprocess_env_client):
        """Test that @dataclass decorators work (advantage over RestrictedPython)."""
        subprocess_env_client.reset()

        code = """
from dataclasses import dataclass

@dataclass
class Point:
    x: float
    y: float

p = Point(3.0, 4.0)
print(f'Point: ({p.x}, {p.y})')
"""
        result = subprocess_env_client.step(CodeAction(code=code))

        assert result.observation.exit_code == 0
        assert "Point: (3.0, 4.0)" in result.observation.stdout

    def test_class_definition(self, subprocess_env_client):
        """Test that class definitions work correctly."""
        subprocess_env_client.reset()

        code = """
class Counter:
    def __init__(self, start=0):
        self.value = start

    def increment(self):
        self.value += 1
        return self.value

counter = Counter()
print(counter.increment())
print(counter.increment())
"""
        result = subprocess_env_client.step(CodeAction(code=code))

        assert result.observation.exit_code == 0
        assert "1" in result.observation.stdout
        assert "2" in result.observation.stdout

    def test_list_comprehension(self, subprocess_env_client):
        """Test that list comprehensions work."""
        subprocess_env_client.reset()

        code = "squares = [x**2 for x in range(5)]\nprint(squares)"
        result = subprocess_env_client.step(CodeAction(code=code))

        assert result.observation.exit_code == 0
        assert "[0, 1, 4, 9, 16]" in result.observation.stdout

    # ========================================================================
    # Subprocess-specific tests: State is NOT persisted between steps
    # This is a key difference from smolagents executor
    # ========================================================================

    def test_no_variable_persistence_within_episode(self, subprocess_env_client):
        """Test that variables do NOT persist within an episode for subprocess executor.

        Note: Unlike smolagents executor, subprocess executor runs each step in a
        fresh process, so variables don't persist. This is a known tradeoff for
        the increased security of process isolation.
        """
        subprocess_env_client.reset()

        # Define a variable
        subprocess_env_client.step(CodeAction(code="my_var = 42"))

        # Use the variable in a subsequent step - should FAIL for subprocess
        result = subprocess_env_client.step(CodeAction(code="print(my_var)"))

        # Subprocess executor doesn't persist state, so this should fail
        assert result.observation.exit_code == 1

    def test_reset_has_no_effect_on_isolation(self, subprocess_env_client):
        """Test that reset doesn't change behavior for subprocess executor.

        Since each step already runs in isolation, reset just affects server-side
        state tracking (episode_id, step_count) but not execution behavior.
        """
        # Define a variable
        subprocess_env_client.reset()
        subprocess_env_client.step(CodeAction(code="my_var = 42"))

        # Reset and try to use the variable
        subprocess_env_client.reset()
        result = subprocess_env_client.step(CodeAction(code="print(my_var)"))

        # Should fail because subprocess doesn't persist state anyway
        assert result.observation.exit_code == 1

    # ========================================================================
    # Screenshot capture tests with tkinter GUI rendering
    # ========================================================================

    def test_screenshot_capture_basic(self, subprocess_env_client):
        """Test that screenshot capture flag is accepted and returns data."""
        import base64

        subprocess_env_client.reset()

        # Simple code that doesn't require GUI - just test the screenshot mechanism
        code = """
print("Testing screenshot capture")
x = 1 + 1
print(f"Result: {x}")
"""
        result = subprocess_env_client.step(
            CodeAction(code=code, capture_screenshot=True)
        )

        assert result.observation.exit_code == 0
        assert "Result: 2" in result.observation.stdout

        # Screenshot may or may not be captured depending on Xvfb setup
        # The key test is that the flag doesn't cause errors
        if result.observation.screenshot is not None:
            # If screenshot was captured, verify it's valid PNG
            screenshot_bytes = base64.b64decode(result.observation.screenshot)
            png_signature = b"\x89PNG\r\n\x1a\n"
            assert screenshot_bytes[:8] == png_signature, "Screenshot should be valid PNG"

            # Save to file for viewing
            output_path = Path(__file__).parent / "screenshot_basic.png"
            output_path.write_bytes(screenshot_bytes)
            print(f"Screenshot saved to: {output_path}")

    def test_tkinter_screenshot_capture(self, subprocess_env_client):
        """Test screenshot capture with actual tkinter GUI rendering."""
        import base64

        subprocess_env_client.reset()

        # Tkinter code that creates a visible window
        code = """
import tkinter as tk

# Create window
root = tk.Tk()
root.title("Subprocess Executor Test")
root.geometry("400x300")

# Create canvas with colored rectangles
canvas = tk.Canvas(root, width=400, height=300, bg="white")
canvas.pack()

# Draw some shapes
canvas.create_rectangle(50, 50, 150, 150, fill="red", outline="black")
canvas.create_rectangle(200, 50, 300, 150, fill="blue", outline="black")
canvas.create_oval(100, 180, 300, 280, fill="green", outline="black")

# Force rendering
root.update_idletasks()
root.update()

print("Tkinter window created with shapes")
print("Window size: 400x300")

# Keep window for screenshot - DO NOT destroy window!
# The screenshot capture code is injected AFTER this code runs,
# so the window must remain visible when this code ends.
import time
time.sleep(0.3)

print("Window ready for screenshot capture")
"""
        result = subprocess_env_client.step(
            CodeAction(code=code, capture_screenshot=True)
        )

        assert result.observation.exit_code == 0
        assert "Tkinter window created" in result.observation.stdout
        assert "Window ready for screenshot capture" in result.observation.stdout

        # Verify screenshot was captured and save to file
        if result.observation.screenshot is not None:
            screenshot_bytes = base64.b64decode(result.observation.screenshot)
            png_signature = b"\x89PNG\r\n\x1a\n"
            assert screenshot_bytes[:8] == png_signature, "Screenshot should be valid PNG"
            assert len(screenshot_bytes) > 200, "Screenshot should have substantial content"

            # Save to file for viewing
            output_path = Path(__file__).parent / "screenshot_tkinter_shapes.png"
            output_path.write_bytes(screenshot_bytes)
            print(f"Screenshot saved to: {output_path} ({len(screenshot_bytes)} bytes)")

    def test_tkinter_animation_screenshot(self, subprocess_env_client):
        """Test screenshot capture during tkinter animation rendering."""
        import base64

        subprocess_env_client.reset()

        # Tkinter code with simple animation
        code = """
import tkinter as tk
import time

# Create window
root = tk.Tk()
root.title("Animation Test")
root.geometry("400x300")

canvas = tk.Canvas(root, width=400, height=300, bg="lightblue")
canvas.pack()

# Create a ball that moves
ball = canvas.create_oval(10, 140, 50, 180, fill="yellow", outline="orange", width=2)

# Simple animation - move ball across screen
for i in range(10):
    canvas.move(ball, 30, 0)
    root.update_idletasks()
    root.update()
    time.sleep(0.05)

print("Animation complete")
print(f"Ball moved to final position")

# Keep window for screenshot - DO NOT destroy window!
# The screenshot capture code is injected AFTER this code runs.
time.sleep(0.2)

print("Ready for screenshot")
"""
        result = subprocess_env_client.step(
            CodeAction(code=code, capture_screenshot=True)
        )

        assert result.observation.exit_code == 0
        assert "Animation complete" in result.observation.stdout
        assert "Ready for screenshot" in result.observation.stdout

        # Verify screenshot captured the animation frame and save to file
        if result.observation.screenshot is not None:
            screenshot_bytes = base64.b64decode(result.observation.screenshot)
            png_signature = b"\x89PNG\r\n\x1a\n"
            assert screenshot_bytes[:8] == png_signature, "Screenshot should be valid PNG"

            # Save to file for viewing
            output_path = Path(__file__).parent / "screenshot_animation.png"
            output_path.write_bytes(screenshot_bytes)
            print(f"Animation screenshot saved to: {output_path} ({len(screenshot_bytes)} bytes)")

    def test_multiframe_capture_animation(self, subprocess_env_client):
        """Test multi-frame capture during tkinter animation (2 FPS for 2 seconds)."""
        import base64

        subprocess_env_client.reset()

        # Tkinter code with animation that runs for ~2 seconds
        code = """
import tkinter as tk
import time

# Create window
root = tk.Tk()
root.title("Multi-Frame Test")
root.geometry("400x300")

canvas = tk.Canvas(root, width=400, height=300, bg="white")
canvas.pack()

# Create a ball that moves across screen
ball = canvas.create_oval(10, 140, 50, 180, fill="red", outline="darkred", width=3)

# Add a frame counter label
frame_label = canvas.create_text(200, 20, text="Frame 0", font=("Arial", 16))

# Animation - move ball across screen over ~2 seconds
# 40 frames at 50ms each = 2 seconds
for i in range(40):
    canvas.move(ball, 9, 0)  # Move 9 pixels per frame
    canvas.itemconfig(frame_label, text=f"Frame {i+1}")
    root.update_idletasks()
    root.update()
    time.sleep(0.05)  # 50ms per frame = 20 FPS

print("Animation complete - 2 seconds of movement")
print("Ball moved from left to right")

# Keep window open for final frame capture
time.sleep(0.3)

print("Ready for capture completion")
"""
        result = subprocess_env_client.step(
            CodeAction(
                code=code,
                capture_frames=True,
                capture_interval_ms=500,  # 2 FPS
                max_frames=10,  # Cap at 10 frames
            )
        )

        assert result.observation.exit_code == 0
        assert "Animation complete" in result.observation.stdout

        # Check that frames were captured
        print(f"Captured {result.observation.frame_count} frames")
        assert result.observation.frame_count >= 1, "Should capture at least 1 frame"

        # With 2 FPS over ~2.3 seconds, expect 4-5 frames
        # (0.2s initial delay + 2s animation + 0.3s sleep)
        print(f"Expected ~4 frames, got {result.observation.frame_count}")

        # Verify each frame is valid PNG and save to files
        tmp_dir = Path(__file__).parent / "tmp"
        tmp_dir.mkdir(exist_ok=True)
        for i, frame_b64 in enumerate(result.observation.frames):
            frame_bytes = base64.b64decode(frame_b64)
            png_signature = b"\x89PNG\r\n\x1a\n"
            assert frame_bytes[:8] == png_signature, f"Frame {i} should be valid PNG"

            # Save frame to file for viewing
            output_path = tmp_dir / f"multiframe_{i:02d}.png"
            output_path.write_bytes(frame_bytes)
            print(f"Frame {i} saved to: {output_path} ({len(frame_bytes)} bytes)")

        # Check that the last frame is also available as screenshot (backward compatibility)
        if result.observation.screenshot is not None:
            assert result.observation.screenshot == result.observation.frames[-1]
            print("Backward compatibility: screenshot == last frame ✓")

    def test_custom_animation_capture(self, subprocess_env_client):
        """Test custom animation with 10 screenshots over 5 seconds (2 FPS)."""
        import base64

        subprocess_env_client.reset()

        # User-provided animation code goes here
        code = '''
import tkinter as tk
import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import sys

# Constants
WIDTH, HEIGHT = 800, 800
CENTER_X, CENTER_Y = WIDTH // 2, HEIGHT // 2
NUM_BALLS = 20
BALL_RADIUS = 20
HEPTAGON_RADIUS = 300  # Large enough to contain all balls
HEPTAGON_SIDES = 7
GRAVITY = 500  # pixels/s^2
FRICTION = 0.99  # Linear velocity damping
ANGULAR_FRICTION = 0.98  # Rotational velocity damping
RESTITUTION = 0.7  # Bounce coefficient (controls bounce height)
WALL_RESTITUTION = 0.6  # Wall bounce coefficient
SPIN_RATE = 2 * math.pi / 5  # 360 degrees per 5 seconds

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
    vx: float = 0.0
    vy: float = 0.0
    radius: float = BALL_RADIUS
    mass: float = 1.0
    angle: float = 0.0  # Current rotation angle of the ball
    angular_velocity: float = 0.0  # Rotational speed
    color: str = "#ffffff"
    number: int = 1
    canvas_id: Optional[int] = None
    text_id: Optional[int] = None


def get_heptagon_vertices(cx: float, cy: float, radius: float, rotation: float) -> List[Tuple[float, float]]:
    """Calculate heptagon vertices given center, radius, and rotation angle."""
    vertices = []
    for i in range(HEPTAGON_SIDES):
        angle = rotation + (2 * math.pi * i / HEPTAGON_SIDES) - math.pi / 2
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        vertices.append((x, y))
    return vertices


def point_to_line_segment_distance(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> Tuple[float, float, float, float]:
    """
    Calculate distance from point to line segment and the closest point on segment.
    Returns: (distance, closest_x, closest_y, t_parameter)
    """
    dx = x2 - x1
    dy = y2 - y1
    length_sq = dx * dx + dy * dy

    if length_sq == 0:
        return math.sqrt((px - x1)**2 + (py - y1)**2), x1, y1, 0.0

    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy
    distance = math.sqrt((px - closest_x)**2 + (py - closest_y)**2)

    return distance, closest_x, closest_y, t


def get_wall_velocity(cx: float, cy: float, point_x: float, point_y: float, angular_velocity: float) -> Tuple[float, float]:
    """Calculate the velocity of a point on the rotating wall."""
    rx = point_x - cx
    ry = point_y - cy
    # Velocity perpendicular to radius: v = omega × r
    vx = -angular_velocity * ry
    vy = angular_velocity * rx
    return vx, vy


def normalize(vx: float, vy: float) -> Tuple[float, float]:
    """Normalize a 2D vector."""
    length = math.sqrt(vx * vx + vy * vy)
    if length == 0:
        return 0.0, 0.0
    return vx / length, vy / length


def dot(ax: float, ay: float, bx: float, by: float) -> float:
    """Dot product of two 2D vectors."""
    return ax * bx + ay * by


class Simulation:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Bouncing Balls in Spinning Heptagon")

        self.canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg="#1a1a2e")
        self.canvas.pack()

        self.heptagon_rotation = 0.0
        self.balls: List[Ball] = []
        self.last_time = None
        self.heptagon_id = None

        self.create_balls()
        self.create_heptagon()

        self.running = True
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.update()

    def on_close(self):
        self.running = False
        self.root.destroy()

    def create_balls(self):
        """Create all balls at the center with slight random offsets."""
        for i in range(NUM_BALLS):
            # Small offset to prevent all balls stacking exactly
            offset_x = (i % 5 - 2) * 3
            offset_y = (i // 5 - 2) * 3
            ball = Ball(
                x=CENTER_X + offset_x,
                y=CENTER_Y + offset_y,
                color=COLORS[i],
                number=i + 1,
                # Small initial velocities to spread them out
                vx=(i % 5 - 2) * 20,
                vy=(i // 5 - 2) * 15
            )
            self.balls.append(ball)

    def create_heptagon(self):
        """Create the heptagon on the canvas."""
        vertices = get_heptagon_vertices(CENTER_X, CENTER_Y, HEPTAGON_RADIUS, self.heptagon_rotation)
        flat_vertices = [coord for vertex in vertices for coord in vertex]
        self.heptagon_id = self.canvas.create_polygon(
            flat_vertices, outline="#4cc9f0", fill="", width=3
        )

    def draw_ball(self, ball: Ball):
        """Draw or update a ball on the canvas."""
        x1 = ball.x - ball.radius
        y1 = ball.y - ball.radius
        x2 = ball.x + ball.radius
        y2 = ball.y + ball.radius

        if ball.canvas_id is None:
            ball.canvas_id = self.canvas.create_oval(x1, y1, x2, y2, fill=ball.color, outline="#ffffff", width=1)
            ball.text_id = self.canvas.create_text(ball.x, ball.y, text=str(ball.number), fill="#000000", font=("Arial", 10, "bold"))
        else:
            self.canvas.coords(ball.canvas_id, x1, y1, x2, y2)
            self.canvas.coords(ball.text_id, ball.x, ball.y)

        # Rotate the number to show ball spin
        # We'll use a simple approach: offset the text position based on angle
        text_offset_x = 0.3 * ball.radius * math.sin(ball.angle)
        text_offset_y = -0.3 * ball.radius * math.cos(ball.angle)
        self.canvas.coords(ball.text_id, ball.x + text_offset_x, ball.y + text_offset_y)

    def update_heptagon(self):
        """Update the heptagon's position based on rotation."""
        vertices = get_heptagon_vertices(CENTER_X, CENTER_Y, HEPTAGON_RADIUS, self.heptagon_rotation)
        flat_vertices = [coord for vertex in vertices for coord in vertex]
        self.canvas.coords(self.heptagon_id, *flat_vertices)

    def check_wall_collision(self, ball: Ball, dt: float):
        """Check and respond to collision between ball and heptagon walls."""
        vertices = get_heptagon_vertices(CENTER_X, CENTER_Y, HEPTAGON_RADIUS, self.heptagon_rotation)

        for i in range(HEPTAGON_SIDES):
            x1, y1 = vertices[i]
            x2, y2 = vertices[(i + 1) % HEPTAGON_SIDES]

            distance, closest_x, closest_y, t = point_to_line_segment_distance(
                ball.x, ball.y, x1, y1, x2, y2
            )

            if distance < ball.radius:
                # Collision detected
                # Calculate normal pointing inward (toward center)
                nx = ball.x - closest_x
                ny = ball.y - closest_y
                nl = math.sqrt(nx * nx + ny * ny)
                if nl > 0:
                    nx /= nl
                    ny /= nl
                else:
                    # Ball exactly on wall, use perpendicular to wall
                    wx = x2 - x1
                    wy = y2 - y1
                    nx, ny = normalize(-wy, wx)
                    # Make sure normal points inward
                    to_center_x = CENTER_X - ball.x
                    to_center_y = CENTER_Y - ball.y
                    if dot(nx, ny, to_center_x, to_center_y) < 0:
                        nx, ny = -nx, -ny

                # Get wall velocity at contact point
                wall_vx, wall_vy = get_wall_velocity(CENTER_X, CENTER_Y, closest_x, closest_y, SPIN_RATE)

                # Relative velocity of ball with respect to wall
                rel_vx = ball.vx - wall_vx
                rel_vy = ball.vy - wall_vy

                # Velocity component along normal
                vn = dot(rel_vx, rel_vy, nx, ny)

                # Only respond if moving toward the wall
                if vn < 0:
                    # Tangent direction
                    tx, ty = -ny, nx

                    # Tangent velocity (for friction/spin)
                    vt = dot(rel_vx, rel_vy, tx, ty)

                    # Apply restitution for normal component
                    new_vn = -vn * WALL_RESTITUTION

                    # Apply friction to tangent component
                    friction_coef = 0.3
                    new_vt = vt * (1 - friction_coef)

                    # Update ball angular velocity based on friction
                    # Friction causes the ball to spin
                    ball.angular_velocity += (vt - new_vt) / ball.radius * 0.5

                    # Reconstruct velocity
                    ball.vx = wall_vx + new_vn * nx + new_vt * tx
                    ball.vy = wall_vy + new_vn * ny + new_vt * ty

                    # Limit bounce height by clamping velocity
                    # Max height h = v^2 / (2g), so v = sqrt(2gh)
                    max_bounce_height = min(HEPTAGON_RADIUS * 0.9, HEPTAGON_RADIUS - ball.radius)
                    max_bounce_height = max(max_bounce_height, ball.radius * 2)
                    max_velocity = math.sqrt(2 * GRAVITY * max_bounce_height)

                    speed = math.sqrt(ball.vx**2 + ball.vy**2)
                    if speed > max_velocity:
                        scale = max_velocity / speed
                        ball.vx *= scale
                        ball.vy *= scale

                # Push ball out of wall
                penetration = ball.radius - distance
                ball.x += nx * penetration * 1.01
                ball.y += ny * penetration * 1.01

    def check_ball_collision(self, ball1: Ball, ball2: Ball):
        """Check and respond to collision between two balls."""
        dx = ball2.x - ball1.x
        dy = ball2.y - ball1.y
        distance = math.sqrt(dx * dx + dy * dy)
        min_dist = ball1.radius + ball2.radius

        if distance < min_dist and distance > 0:
            # Collision detected
            nx = dx / distance
            ny = dy / distance

            # Relative velocity
            dvx = ball1.vx - ball2.vx
            dvy = ball1.vy - ball2.vy
            dvn = dot(dvx, dvy, nx, ny)

            # Only respond if balls are approaching
            if dvn > 0:
                # Elastic collision with restitution
                m1, m2 = ball1.mass, ball2.mass

                # Impulse magnitude
                j = (1 + RESTITUTION) * dvn / (1/m1 + 1/m2)

                # Apply impulse
                ball1.vx -= j * nx / m1
                ball1.vy -= j * ny / m1
                ball2.vx += j * nx / m2
                ball2.vy += j * ny / m2

                # Tangential friction affects spin
                tx, ty = -ny, nx
                dvt = dot(dvx, dvy, tx, ty)

                friction_coef = 0.2
                impulse_t = friction_coef * abs(j)

                if abs(dvt) > 0.1:
                    sign = 1 if dvt > 0 else -1
                    ball1.angular_velocity -= sign * impulse_t / ball1.radius * 0.3
                    ball2.angular_velocity += sign * impulse_t / ball2.radius * 0.3

            # Separate balls
            overlap = min_dist - distance
            ball1.x -= nx * overlap * 0.5
            ball1.y -= ny * overlap * 0.5
            ball2.x += nx * overlap * 0.5
            ball2.y += ny * overlap * 0.5

    def update(self):
        if not self.running:
            return

        import time
        current_time = time.perf_counter()

        if self.last_time is None:
            dt = 1/60
        else:
            dt = min(current_time - self.last_time, 1/30)

        self.last_time = current_time

        # Update heptagon rotation
        self.heptagon_rotation += SPIN_RATE * dt

        # Physics substeps for stability
        substeps = 4
        sub_dt = dt / substeps

        for _ in range(substeps):
            # Apply gravity and friction to each ball
            for ball in self.balls:
                ball.vy += GRAVITY * sub_dt
                ball.vx *= FRICTION
                ball.vy *= FRICTION
                ball.angular_velocity *= ANGULAR_FRICTION

                # Update position
                ball.x += ball.vx * sub_dt
                ball.y += ball.vy * sub_dt

                # Update rotation angle
                ball.angle += ball.angular_velocity * sub_dt

            # Check wall collisions
            for ball in self.balls:
                self.check_wall_collision(ball, sub_dt)

            # Check ball-ball collisions
            for i in range(len(self.balls)):
                for j in range(i + 1, len(self.balls)):
                    self.check_ball_collision(self.balls[i], self.balls[j])

        # Update visuals
        self.update_heptagon()
        for ball in self.balls:
            self.draw_ball(ball)

        # Schedule next update
        self.root.after(16, self.update)


def main():
    root = tk.Tk()
    root.resizable(False, False)
    sim = Simulation(root)
    root.mainloop()


if __name__ == "__main__":
    main()

'''
        result = subprocess_env_client.step(
            CodeAction(
                code=code,
                capture_frames=True,
                capture_interval_ms=500,  # 2 FPS
                max_frames=10,  # 10 frames over 5 seconds
            )
        )

        # Create tmp subfolder in envs directory - SAVE IMAGES FIRST before any assertions
        tmp_dir = Path(__file__).parent.parent.parent / "envs" / "tmp"
        tmp_dir.mkdir(exist_ok=True)

        print(f"Exit code: {result.observation.exit_code}")
        print(f"Captured {result.observation.frame_count} frames")
        print(f"Stdout: {result.observation.stdout[:500] if result.observation.stdout else 'empty'}")
        print(f"Stderr: {result.observation.stderr[:500] if result.observation.stderr else 'empty'}")

        # Save each frame to tmp folder BEFORE asserting exit code
        for i, frame_b64 in enumerate(result.observation.frames):
            frame_bytes = base64.b64decode(frame_b64)
            png_signature = b"\x89PNG\r\n\x1a\n"
            if frame_bytes[:8] == png_signature:
                output_path = tmp_dir / f"custom_animation_{i:02d}.png"
                output_path.write_bytes(frame_bytes)
                print(f"Frame {i} saved to: {output_path} ({len(frame_bytes)} bytes)")
            else:
                print(f"Frame {i} is not valid PNG, skipping")

        # Assert after saving - so we can see the images even if test fails
        # Note: exit_code -9 means SIGKILL (resource limit exceeded or timeout)
        # The animation runs forever (mainloop), so it will be killed
        # For now, just check we captured frames
        assert result.observation.frame_count > 0, "Should capture at least 1 frame"
        print(f"Successfully captured {result.observation.frame_count} frames!")
