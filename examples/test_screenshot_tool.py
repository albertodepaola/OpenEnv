#!/usr/bin/env python3
"""
Simple test to verify the _internal_capture_screenshot tool works.
"""

import base64
import logging
import sys
from pathlib import Path

# Enable logging to see debug output
logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from envs.coding_env import CodeAction, CodingEnv


def test_screenshot_tool():
    """Test that the screenshot tool works via the injected code."""
    print("=" * 70)
    print("Testing Screenshot Capture Tool")
    print("=" * 70)

    client = CodingEnv.from_docker_image(
        "coding-env:latest", env_vars={"ADDITIONAL_IMPORTS": "dataclass, typing, numpy"}
    )

    # Test 1: Simple tkinter with screenshot flag
    print("\n[Test 1] Tkinter with capture_screenshot=True")
    #     code = """
    # import tkinter as tk

    # root = tk.Tk()
    # root.geometry("200x200")
    # canvas = tk.Canvas(root, width=200, height=200, bg='white')
    # canvas.pack()
    # canvas.create_rectangle(50, 50, 150, 150, fill='blue')

    # print('Tkinter window created')
    # """

    code = """
import math
import tkinter as tk
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

# Global simulation parameters
WIDTH, HEIGHT = 800, 600  # Canvas size
DT = 0.016  # Time step (in seconds)
GRAVITY = np.array([0, 500])  # Gravity acceleration (pixels/s^2)
VELOCITY_DAMPING = 0.999  # Air friction damping factor per frame
ANGULAR_DAMPING = 0.98  # Angular velocity damping per frame
WALL_RESTITUTION = 0.8  # Bounce reduction factor for wall collisions
BALL_RESTITUTION = 0.9  # Bounce reduction factor for ball-ball collisions

# Heptagon parameters
HEPTAGON_RADIUS = 300  # radius of circumscribed circle
HEPTAGON_CENTER = np.array([WIDTH / 2, HEIGHT / 2])
HEPTAGON_SIDES = 7
# Heptagon rotates at 360 degrees per 5 seconds -> 72 degrees/s in rad/s:
HEPTAGON_ANGULAR_VELOCITY = 2 * math.pi / 5

# Ball parameters
BALL_RADIUS = 15

# Colors list for balls (20 balls)
BALL_COLORS = [
    "#f8b862",
    "#f6ad49",
    "#f39800",
    "#f08300",
    "#ec6d51",
    "#ee7948",
    "#ed6d3d",
    "#ec6800",
    "#ec6800",
    "#ee7800",
    "#eb6238",
    "#ea5506",
    "#ea5506",
    "#eb6101",
    "#e49e61",
    "#e45e32",
    "#e17b34",
    "#dd7a56",
    "#db8449",
    "#d66a35",
]


@dataclass
class Ball:
    number: int
    color: str
    pos: np.ndarray  # Position vector [x, y]
    vel: np.ndarray  # Velocity vector [vx, vy]
    radius: float
    angle: float  # spin angle in radians (for drawing the number indicator)
    angular_velocity: float  # spin angular velocity


class Simulation:
    def __init__(self, master: tk.Tk):
        self.master = master
        self.canvas = tk.Canvas(master, width=WIDTH, height=HEIGHT, bg="black")
        self.canvas.pack()
        self.start_time = None
        self.time_elapsed = 0.0  # keeps simulation time in seconds

        # Create balls dropping from center inside heptagon
        self.balls: List[Ball] = []
        for i in range(20):
            ball = Ball(
                number=i + 1,
                color=BALL_COLORS[i],
                pos=HEPTAGON_CENTER.copy(),
                vel=np.array([0.0, 0.0]),
                radius=BALL_RADIUS,
                angle=0.0,
                angular_velocity=0.0,
            )
            self.balls.append(ball)

        # Heptagon rotation angle (in radians)
        self.heptagon_angle = 0.0

        # For tracking drawing items
        self.ball_items = {}
        self.text_items = {}
        self.spin_lines = {}

        # Start simulation loop
        self.last_update = None
        self.update_loop()

    def get_heptagon_vertices(self) -> List[np.ndarray]:
        vertices = []
        for i in range(HEPTAGON_SIDES):
            angle = (
                self.heptagon_angle + i * (2 * math.pi / HEPTAGON_SIDES) - math.pi / 2
            )
            # Subtract pi/2 to have one vertex at the top
            vertex = HEPTAGON_CENTER + np.array(
                [HEPTAGON_RADIUS * math.cos(angle), HEPTAGON_RADIUS * math.sin(angle)]
            )
            vertices.append(vertex)
        return vertices

    def update_loop(self):
        # Compute time step
        current_time = self.master.tk.call("after", "info")
        if self.last_update is None:
            dt = DT
        else:
            dt = DT  # use fixed dt for stability
        self.time_elapsed += dt

        # Update heptagon rotation
        self.heptagon_angle += HEPTAGON_ANGULAR_VELOCITY * dt
        self.heptagon_angle %= 2 * math.pi

        # Update ball physics
        self.update_balls(dt)

        # Clear canvas and redraw everything
        self.canvas.delete("all")
        self.draw_heptagon()
        self.draw_balls()

        # Schedule next frame
        self.master.after(int(DT * 1000), self.update_loop)

    def update_balls(self, dt: float):
        vertices = self.get_heptagon_vertices()
        # Precompute heptagon edges (each as a tuple of (A, B) points)
        edges = []
        for i in range(len(vertices)):
            A = vertices[i]
            B = vertices[(i + 1) % len(vertices)]
            # Compute inward normal: for edge from A to B, the inward normal is chosen such that
            # dot(normal, (center - A)) > 0.
            edge_vec = B - A
            normal = np.array([-edge_vec[1], edge_vec[0]])
            if np.dot(normal, HEPTAGON_CENTER - A) < 0:
                normal = -normal
            normal_length = np.linalg.norm(normal)
            if normal_length != 0:
                normal = normal / normal_length
            edges.append((A, B, normal))

        # Update each ball
        for ball in self.balls:
            # Apply gravity
            ball.vel += GRAVITY * dt

            # Apply air friction
            ball.vel *= VELOCITY_DAMPING
            ball.angular_velocity *= ANGULAR_DAMPING

            # Update position and rotation
            ball.pos += ball.vel * dt
            ball.angle += ball.angular_velocity * dt

            # Collision with heptagon walls
            for A, B, normal in edges:
                # Find closest point on edge segment to ball center
                edge_vec = B - A
                edge_length_sq = np.dot(edge_vec, edge_vec)
                if edge_length_sq == 0:
                    continue
                t = np.dot(ball.pos - A, edge_vec) / edge_length_sq
                t = max(0, min(1, t))
                closest = A + t * edge_vec
                dist_vec = ball.pos - closest
                distance = np.linalg.norm(dist_vec)
                if distance < ball.radius:
                    # Collision detected; push ball out by penetration depth
                    penetration = ball.radius - distance
                    if distance == 0:
                        # If exactly overlapping, use edge normal
                        push_dir = normal
                    else:
                        push_dir = dist_vec / distance
                    ball.pos += push_dir * penetration

                    # Compute relative velocity in normal direction. For a moving wall, account for wall motion.
                    # Wall’s velocity at collision point due to rotation: v_wall = angular_velocity x (r)
                    r = closest - HEPTAGON_CENTER
                    # In 2D, perpendicular velocity: v_wall = omega * (-r_y, r_x)
                    v_wall = HEPTAGON_ANGULAR_VELOCITY * np.array([-r[1], r[0]])
                    relative_vel = ball.vel - v_wall

                    # Reflect the relative velocity on collision with restitution
                    vn = np.dot(relative_vel, normal)
                    if vn < 0:
                        ball.vel -= (1 + WALL_RESTITUTION) * vn * normal
                        # Impart some angular velocity from collision impulse (using ball number as spin indicator visually)
                        ball.angular_velocity += vn * 0.01

            # Collision with other balls (simple pair-wise collision)
        n = len(self.balls)
        for i in range(n):
            for j in range(i + 1, n):
                ball1 = self.balls[i]
                ball2 = self.balls[j]
                diff = ball2.pos - ball1.pos
                dist = np.linalg.norm(diff)
                min_dist = ball1.radius + ball2.radius
                if dist < min_dist and dist > 0:
                    # Overlap detected, compute normal
                    normal = diff / dist
                    penetration = min_dist - dist
                    # Separate balls equally
                    ball1.pos -= normal * (penetration / 2)
                    ball2.pos += normal * (penetration / 2)
                    # Relative velocity along normal (elastic collision with restitution)
                    rel_vel = np.dot(ball2.vel - ball1.vel, normal)
                    if rel_vel < 0:
                        impulse = (
                            -(1 + BALL_RESTITUTION) * rel_vel
                        ) / 2  # divide by 2 for equal mass
                        ball1.vel -= impulse * normal
                        ball2.vel += impulse * normal
                        # Impart small angular velocity change on collision based on impulse
                        ball1.angular_velocity -= impulse * 0.005
                        ball2.angular_velocity += impulse * 0.005

            # Keep balls inside the heptagon if something goes wrong (fallback: if ball center wanders too far, push back)
            offset = ball.pos - HEPTAGON_CENTER
            dist_center = np.linalg.norm(offset)
            if dist_center > HEPTAGON_RADIUS - ball.radius:
                # Project onto boundary
                ball.pos = HEPTAGON_CENTER + offset / dist_center * (
                    HEPTAGON_RADIUS - ball.radius
                )
                # Reflect velocity
                nvec = offset / dist_center
                vn = np.dot(ball.vel, nvec)
                if vn > 0:
                    ball.vel -= (1 + WALL_RESTITUTION) * vn * nvec

    def draw_heptagon(self):
        vertices = self.get_heptagon_vertices()
        points = []
        for vertex in vertices:
            points.extend(vertex.tolist())
        self.canvas.create_polygon(points, outline="white", fill="", width=3)

    def draw_balls(self):
        for ball in self.balls:
            x, y = ball.pos
            r = ball.radius
            # Draw ball circle
            self.canvas.create_oval(
                x - r, y - r, x + r, y + r, fill=ball.color, outline="white", width=2
            )
            # Draw ball number (centered); cannot rotate text easily so we add a line indicating spin
            self.canvas.create_text(
                x,
                y,
                text=str(ball.number),
                fill="black",
                font=("Helvetica", 12, "bold"),
            )
            # Draw a line from center to circumference indicating spin direction
            line_len = r
            x_end = x + line_len * math.cos(ball.angle)
            y_end = y + line_len * math.sin(ball.angle)
            self.canvas.create_line(x, y, x_end, y_end, fill="black", width=2)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Bouncing Balls inside a Spinning Heptagon")
    sim = Simulation(root)
    root.mainloop()
"""

    result = client.step(
        CodeAction(
            code=code,
            capture_screenshot=True,
        )
    )

    print("\n--- FULL OUTPUT ---")
    print(result.observation.stdout)
    if result.observation.stderr:
        print("\n--- STDERR ---")
        print(result.observation.stderr)

    print(f"\nExit code: {result.observation.exit_code}")
    print(f"Screenshot present: {result.observation.screenshot is not None}")

    if result.observation.screenshot:
        screenshot_bytes = base64.b64decode(result.observation.screenshot)
        output_path = Path(__file__).parent / "test_screenshot.png"
        output_path.write_bytes(screenshot_bytes)
        print(f"\n✅ SUCCESS! Screenshot saved to: {output_path}")
        print(f"   Size: {len(screenshot_bytes)} bytes PNG")
    else:
        print("\n❌ FAILED! No screenshot captured")
        print("   See debug output above for details")

    client.close()


if __name__ == "__main__":
    try:
        test_screenshot_tool()
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback

        traceback.print_exc()
