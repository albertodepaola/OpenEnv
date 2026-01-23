---
title: Coding Environment Server
emoji: 💻
colorFrom: blue
colorTo: blue
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
  - openenv
---

# Coding Environment

A Python code execution environment that runs arbitrary Python code and returns results. Perfect for testing code execution infrastructure and demonstrating environment usage patterns.

## Quick Start

The simplest way to use the Coding environment is through the `CodingEnv` class:

```python
from envs.coding_env import CodeAction, CodingEnv

try:
    # Create environment from Docker image
    coding_env = CodingEnv.from_docker_image("coding-env:latest")

    # Reset
    result = coding_env.reset()
    print(f"Reset complete: exit_code={result.observation.exit_code}")

    # Execute Python code
    code_samples = [
        "print('Hello, World!')",
        "x = 5 + 3\nprint(f'Result: {x}')",
        "import math\nprint(math.pi)"
    ]

    for code in code_samples:
        result = coding_env.step(CodeAction(code=code))
        print(f"Code: {code}")
        print(f"  → stdout: {result.observation.stdout.strip()}")
        print(f"  → exit_code: {result.observation.exit_code}")

finally:
    # Always clean up
    coding_env.close()
```

That's it! The `CodingEnv.from_docker_image()` method handles:
- Starting the Docker container
- Waiting for the server to be ready
- Connecting to the environment
- Container cleanup when you call `close()`

## Building the Docker Image

Before using the environment, you need to build the Docker image:

```bash
# From project root
docker build -t coding-env:latest -f envs/coding_env/server/Dockerfile .
```

## Environment Details

### Action
**CodeAction**: Code execution request with optional frame capture

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `code` | str | (required) | Python code to execute |
| `capture_screenshot` | bool | False | Capture single screenshot after execution |
| `capture_frames` | bool | False | Capture frames during execution (for animations) |
| `capture_interval_ms` | int | 500 | Interval between frame captures (2 FPS default) |
| `max_frames` | int | 100 | Maximum frames to capture |

### Observation
**CodeObservation**: Execution results with optional visual output

| Field | Type | Description |
|-------|------|-------------|
| `stdout` | str | Standard output from code execution |
| `stderr` | str | Standard error (includes timeout/resource limit messages) |
| `exit_code` | int | Exit code (see Exit Code Semantics below) |
| `screenshot` | str \| None | Base64-encoded PNG (last frame if capturing frames) |
| `frames` | List[str] | List of base64-encoded PNG frames |
| `frame_count` | int | Number of frames captured |

### Exit Code Semantics

The `exit_code` field indicates how the code execution terminated:

| Exit Code | Meaning |
|-----------|---------|
| 0 | Success - code completed normally |
| 1-127 | Code error (exception, syntax error, etc.) |
| 124 | Timeout - wall clock time limit exceeded |
| 137 | OOM killer (128 + SIGKILL) |
| -9 | SIGKILL - often CPU time limit exceeded |
| -24 | SIGXCPU - CPU time soft limit exceeded |

**Important for frame capture**: A non-zero exit code (e.g., 124 timeout or -9 SIGKILL) does NOT mean failure for animation capture scenarios. The frames are captured in a background thread during execution, so they are returned even if the process is terminated. Success should be measured by analyzing the captured frames, not by exit code.

### State
**CodeState**: Tracks execution state
- `episode_id` (str) - Unique identifier for the episode
- `step_count` (int) - Number of steps taken
- `last_exit_code` (int) - Exit code from the last execution

## Frame Capture for Animations

For animations that run continuously (e.g., `tkinter.mainloop()`), use frame capture mode:

```python
from envs.coding_env import CodeAction, CodingEnv

coding_env = CodingEnv.from_docker_image("coding-env-subprocess:latest")

# Animation code - runs forever until timeout
animation_code = '''
import tkinter as tk

root = tk.Tk()
canvas = tk.Canvas(root, width=400, height=400)
canvas.pack()

ball = canvas.create_oval(10, 10, 50, 50, fill="red")
dx, dy = 5, 3

def animate():
    canvas.move(ball, dx, dy)
    x1, y1, x2, y2 = canvas.coords(ball)
    if x1 <= 0 or x2 >= 400:
        global dx
        dx = -dx
    if y1 <= 0 or y2 >= 400:
        global dy
        dy = -dy
    root.after(16, animate)

animate()
root.mainloop()  # Runs forever - will be terminated by timeout
'''

result = coding_env.step(CodeAction(
    code=animation_code,
    capture_frames=True,
    capture_interval_ms=500,  # 2 FPS
    max_frames=10,
))

# Exit code will be 124 (timeout) - this is expected!
print(f"Exit code: {result.observation.exit_code}")  # 124
print(f"Frames captured: {result.observation.frame_count}")  # 10

# Success is measured by frame content, not exit code
import base64
for i, frame_b64 in enumerate(result.observation.frames):
    frame_bytes = base64.b64decode(frame_b64)
    with open(f"frame_{i:02d}.png", "wb") as f:
        f.write(frame_bytes)
```

### Data Flow for Frame Capture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CodeAction                                │
│  code="...", capture_frames=True, capture_interval_ms=500       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Subprocess Executor                           │
│  ┌──────────────┐    ┌─────────────────────────────────────┐   │
│  │ User Code    │    │ Background Capture Thread           │   │
│  │ (subprocess) │    │ - Captures X11 display every 500ms  │   │
│  │              │    │ - Stores frames in memory            │   │
│  │ mainloop()   │◄──►│ - Runs independently of user code   │   │
│  │ ...          │    │                                      │   │
│  │ [SIGKILL]    │    │ [Stops when subprocess terminates]  │   │
│  └──────────────┘    └─────────────────────────────────────┘   │
│         │                           │                           │
│         ▼                           ▼                           │
│    exit_code=-9              frames=[f1, f2, ..., fn]          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      CodeObservation                             │
│  stdout="", stderr="[Timeout]...", exit_code=124,               │
│  frames=["base64...", ...], frame_count=10, screenshot="..."    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Reward Calculation                           │
│  - Analyze captured frames (not exit code)                      │
│  - Compare to expected visual output                            │
│  - Return reward based on image similarity/correctness          │
└─────────────────────────────────────────────────────────────────┘
```

## Advanced Usage

### Connecting to an Existing Server

If you already have a Coding environment server running, you can connect directly:

```python
from envs.coding_env import CodingEnv

# Connect to existing server
coding_env = CodingEnv(base_url="<ENV_HTTP_URL_HERE>")

# Use as normal
result = coding_env.reset()
result = coding_env.step(CodeAction(code="print('Hello!')"))
```

Note: When connecting to an existing server, `coding_env.close()` will NOT stop the server.

## Development & Testing

### Running Tests

Install the coding_env package with dev dependencies and run the tests from the repo root:

```bash
# Install coding_env with dev dependencies (includes smolagents and pytest)
uv pip install -e "envs/coding_env[dev]"

# Run unit tests (no Docker required)
uv run pytest tests/envs/test_python_codeact_reset.py tests/envs/test_python_codeact_rewards.py -v

# Run integration tests (requires Docker image to be built)
docker build -t coding-env:latest -f envs/coding_env/server/Dockerfile .
SKIP_DOCKER_TESTS=0 uv run pytest tests/envs/test_coding_env_integration.py -v
```

### Running the Full Example

Run the complete example that demonstrates the full workflow:

```bash
python3 envs/coding_env/client/example_usage.py
```

This example shows:
- Creating an environment from a Docker image
- Resetting and executing code through the environment
- Automatic cleanup with `close()`

## Project Structure

```
coding_env/
├── README.md              # This file
├── models.py              # Action, Observation, and State models
├── client/
│   ├── coding_env_client.py  # CodingEnv client implementation
│   └── example_usage.py      # Usage examples
└── server/
    ├── python_codeact_env.py  # Core environment logic
    ├── app.py                 # FastAPI application
    ├── transforms.py          # Observation transforms
    ├── Dockerfile             # Container image definition
    └── README.md              # Server-specific documentation
```
