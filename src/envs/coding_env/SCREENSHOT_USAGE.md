# Screenshot Capture API - Usage Guide

## Overview

The screenshot capture API allows you to capture screenshots of GUI applications running in the coding environment's virtual display (Xvfb). Screenshots are captured **during code execution** (not after), ensuring UI elements are still alive.

## Key Features

✅ **Captures during execution** - Screenshot taken while UI elements are still rendered
✅ **Automatic rendering timeout** - 0.5s delay ensures UI is fully rendered
✅ **Library agnostic** - Works with tkinter, matplotlib, pygame, etc.
✅ **Simple flag-based API** - Just set `capture_screenshot=True`
✅ **Base64 PNG output** - Easy to save or transmit

## Quick Start

```python
from envs.coding_env import CodeAction, CodingEnv
import base64

# Create client
client = CodingEnv.from_docker_image("coding-env:latest")

# Your GUI code
code = """
import tkinter as tk

root = tk.Tk()
root.geometry("400x300")
canvas = tk.Canvas(root, width=400, height=300, bg='white')
canvas.pack()

canvas.create_rectangle(50, 50, 150, 150, fill='blue')
canvas.create_oval(200, 50, 300, 150, fill='red')

print('GUI created successfully')
"""

# Execute with screenshot capture
result = client.step(CodeAction(code=code, capture_screenshot=True))

# Get the screenshot
if result.observation.screenshot:
    screenshot_bytes = base64.b64decode(result.observation.screenshot)
    with open('output.png', 'wb') as f:
        f.write(screenshot_bytes)
    print(f"Screenshot saved: {len(screenshot_bytes)} bytes")

client.close()
```

## How It Works

### The Problem (Old Approach)

Previously, screenshots were captured **after** code execution completed:

```
1. Execute code → tkinter creates window
2. Code completes → tkinter objects destroyed
3. Capture screenshot → Nothing on display! ❌
```

This resulted in empty or black screenshots because GUI elements were already destroyed.

### The Solution (New Approach)

Now, screenshots are captured **during** code execution:

```
1. Execute user code → tkinter creates window
2. Auto-injected code:
   - Force UI updates (root.update(), plt.draw(), etc.)
   - Sleep for 0.5s (rendering timeout)
   - Capture screenshot ✅
   - Store screenshot
3. Code completes → GUI destroyed (but screenshot already captured!)
```

### Code Injection

When `capture_screenshot=True`, the executor automatically appends this code to your script:

```python
# === Auto-injected screenshot capture code ===
import time

# Try to force UI updates for common GUI libraries
try:
    import tkinter as tk
    if tk._default_root:
        tk._default_root.update_idletasks()
        tk._default_root.update()
except:
    pass

try:
    import matplotlib.pyplot as plt
    plt.draw()
    plt.pause(0.001)
except:
    pass

# Wait for rendering to complete
time.sleep(0.5)

# Capture the screenshot
try:
    _screenshot_result = _internal_capture_screenshot()
    if _screenshot_result:
        print(f"[Screenshot captured: {len(_screenshot_result)} bytes base64]")
    else:
        print("[Screenshot capture failed]")
except Exception as _e:
    print(f"[Screenshot capture error: {_e}]")
# === End auto-injected code ===
```

## Examples

### Example 1: Tkinter GUI

```python
from envs.coding_env import CodeAction, CodingEnv
import base64
from pathlib import Path

client = CodingEnv.from_docker_image("coding-env:latest")

tkinter_code = """
import tkinter as tk

# Create main window
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
canvas.create_text(200, 250, text='Hello!', font=('Arial', 16, 'bold'))

print('Tkinter GUI created')
"""

result = client.step(CodeAction(code=tkinter_code, capture_screenshot=True))

if result.observation.screenshot:
    screenshot_bytes = base64.b64decode(result.observation.screenshot)
    Path("tkinter_output.png").write_bytes(screenshot_bytes)
    print(f"✅ Saved: {len(screenshot_bytes)} bytes")

client.close()
```

### Example 2: Matplotlib Plot

```python
from envs.coding_env import CodeAction, CodingEnv
import base64

client = CodingEnv.from_docker_image("coding-env:latest")

matplotlib_code = """
import matplotlib
matplotlib.use('TkAgg')  # Required for Xvfb
import matplotlib.pyplot as plt
import numpy as np

# Create plot
x = np.linspace(0, 2 * np.pi, 100)
y = np.sin(x)

plt.figure(figsize=(8, 6))
plt.plot(x, y, 'b-', linewidth=2, label='sin(x)')
plt.plot(x, np.cos(x), 'r--', linewidth=2, label='cos(x)')
plt.title('Sine and Cosine', fontsize=16)
plt.xlabel('x')
plt.ylabel('y')
plt.legend()
plt.grid(True)

print('Plot created')
"""

result = client.step(CodeAction(code=matplotlib_code, capture_screenshot=True))

if result.observation.screenshot:
    screenshot_bytes = base64.b64decode(result.observation.screenshot)
    with open('plot.png', 'wb') as f:
        f.write(screenshot_bytes)
    print(f"✅ Plot saved: {len(screenshot_bytes)} bytes")

client.close()
```

### Example 3: Pygame Application

```python
from envs.coding_env import CodeAction, CodingEnv

client = CodingEnv.from_docker_image("coding-env:latest")

pygame_code = """
import pygame
import os

# Set SDL to use dummy video driver for Xvfb
os.environ['SDL_VIDEODRIVER'] = 'x11'

pygame.init()
screen = pygame.display.set_mode((400, 300))
screen.fill((255, 255, 255))

# Draw shapes
pygame.draw.rect(screen, (0, 0, 255), (50, 50, 100, 100))
pygame.draw.circle(screen, (255, 0, 0), (250, 100), 50)
pygame.draw.line(screen, (0, 255, 0), (50, 200), (300, 200), 3)

pygame.display.flip()

print('Pygame scene rendered')
"""

result = client.step(CodeAction(code=pygame_code, capture_screenshot=True))

if result.observation.screenshot:
    import base64
    screenshot_bytes = base64.b64decode(result.observation.screenshot)
    with open('pygame_output.png', 'wb') as f:
        f.write(screenshot_bytes)

client.close()
```

## API Reference

### CodeAction

```python
@dataclass
class CodeAction(Action):
    code: str
    capture_screenshot: bool = False
```

**Parameters:**
- `code` (str): Python code to execute
- `capture_screenshot` (bool): If True, capture screenshot during execution with 0.5s rendering timeout

### CodeObservation

```python
@dataclass
class CodeObservation(Observation):
    stdout: str
    stderr: str
    exit_code: int
    screenshot: Optional[str] = None
```

**Fields:**
- `screenshot` (Optional[str]): Base64-encoded PNG screenshot, or None if:
  - `capture_screenshot` was False
  - Screenshot capture failed
  - No UI elements were rendered

## Configuration

### Rendering Timeout

The default rendering timeout is **0.5 seconds**. This is configured in `PyExecutor.run()`:

```python
result = self._executor.run(
    action.code,
    capture_screenshot=action.capture_screenshot,
    # render_timeout=0.5  # Default value
)
```

For applications that need more time to render, you can modify the `render_timeout` parameter in the PyExecutor code.

## Troubleshooting

### Screenshot is None

**Possible causes:**
1. Xvfb is not running in the container
2. No GUI elements were created
3. GUI library didn't render to the display

**Solutions:**
- Ensure the Docker image has Xvfb installed and running
- Check that your code creates visible UI elements
- For matplotlib, use `matplotlib.use('TkAgg')` before importing pyplot

### Screenshot is black/empty

**Possible causes:**
1. Rendering timeout too short
2. UI elements not properly updated

**Solutions:**
- Increase `render_timeout` in PyExecutor
- Ensure you're calling update methods (e.g., `root.update()` for tkinter)

### Screenshot shows partial rendering

**Possible causes:**
1. Complex UI needs more time to render

**Solutions:**
- Increase the rendering timeout
- Add explicit update calls in your code before the injected screenshot code runs

## Performance Considerations

- The 0.5s rendering timeout adds latency to each step with screenshot capture
- Screenshots are base64-encoded, increasing response size (typically 50-500KB)
- For high-frequency screenshot capture, consider using a video recording approach instead

## Limitations

- Screenshots capture the entire virtual display (typically 1024x768)
- Cannot capture specific windows or regions (captures all visible content)
- Rendering timeout is fixed per execution (not adjustable via CodeAction)
- Screenshot format is PNG only (not configurable)

## Future Enhancements

Potential future improvements:
- Configurable rendering timeout per action
- Region-based screenshot capture (x, y, width, height)
- Multiple screenshot formats (JPEG, WebP, etc.)
- Video recording (capture multiple frames during execution)
- Window-specific capture by window ID

## See Also

- [examples/screenshot_capture_example.py](../examples/screenshot_capture_example.py) - Complete working examples
- [examples/local_coding_env.py](../examples/local_coding_env.py) - Integration tests
- [SCREENSHOT_API.md](SCREENSHOT_API.md) - Original design document
- [server/screenshot_utils.py](server/screenshot_utils.py) - Low-level screenshot utilities
