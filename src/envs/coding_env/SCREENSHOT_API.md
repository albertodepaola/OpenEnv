# Screenshot Capture API Design

## Problem

The current screenshot capture implementation has a critical timing issue:

```python
# Current flow (BROKEN):
1. Execute code → tkinter creates window
2. Code completes → tkinter objects destroyed
3. Capture screenshot → Nothing on display! ❌
```

**Result:** Screenshots always return `None` because GUI elements are destroyed before capture happens.

## Solution: In-Execution Screenshot API

Provide a `capture_screenshot()` function available **inside** the code execution environment, giving users control over exactly when to capture.

### Why This Approach?

✅ **User Control** - Capture at the exact right moment
✅ **Multiple Captures** - Take screenshots at different points
✅ **Library Agnostic** - Works with tkinter, matplotlib, pygame, etc.
✅ **No Race Conditions** - Synchronous capture while GUI is alive
✅ **Composable** - Screenshot becomes a tool in the execution sandbox

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Docker Container (coding-env)                      │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │  Xvfb :99 (Virtual Display)                  │  │
│  └──────────────────────────────────────────────┘  │
│         ↑                                           │
│         │ DISPLAY=:99                               │
│         │                                           │
│  ┌──────────────────────────────────────────────┐  │
│  │  PyExecutor (smolagents sandbox)             │  │
│  │                                               │  │
│  │  User Code:                                   │  │
│  │  ┌────────────────────────────────────────┐  │  │
│  │  │ import tkinter as tk                   │  │  │
│  │  │ root = tk.Tk()                         │  │  │
│  │  │ canvas = tk.Canvas(...)                │  │  │
│  │  │ canvas.create_rectangle(...)           │  │  │
│  │  │                                         │  │  │
│  │  │ root.update()  # Render to display     │  │  │
│  │  │ screenshot = capture_screenshot()  ←───┼──┼──┼─ Captures NOW
│  │  │                                         │  │  │
│  │  │ print(f"Got {len(screenshot)} bytes")  │  │  │
│  │  └────────────────────────────────────────┘  │  │
│  │                                               │  │
│  │  Screenshots stored in execution context     │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Usage Examples

### Example 1: Basic Tkinter Screenshot

```python
import tkinter as tk

# Create UI
root = tk.Tk()
root.geometry("400x300")
canvas = tk.Canvas(root, width=400, height=300, bg='white')
canvas.pack()

# Draw elements
canvas.create_rectangle(50, 50, 150, 150, fill='blue')
canvas.create_oval(200, 50, 300, 150, fill='red')

# Force rendering to X display
root.update()

# Capture screenshot (returns base64-encoded PNG string)
screenshot = capture_screenshot()

print(f"Screenshot captured: {len(screenshot)} bytes base64")
```

### Example 2: Multiple Screenshots

```python
import tkinter as tk

root = tk.Tk()
canvas = tk.Canvas(root, width=400, height=300)
canvas.pack()

# Initial state
canvas.create_rectangle(50, 50, 100, 100, fill='blue')
root.update()
screenshot1 = capture_screenshot()
print("Screenshot 1: Initial state")

# Add more elements
canvas.create_oval(200, 50, 300, 150, fill='red')
root.update()
screenshot2 = capture_screenshot()
print("Screenshot 2: After adding circle")

# Final state
canvas.create_line(50, 200, 300, 200, fill='green', width=3)
root.update()
screenshot3 = capture_screenshot()
print("Screenshot 3: Final state")
```

### Example 3: Matplotlib Plot

```python
import matplotlib
matplotlib.use('TkAgg')  # Use Tk backend for Xvfb
import matplotlib.pyplot as plt

# Create plot
plt.figure(figsize=(8, 6))
plt.plot([1, 2, 3, 4], [1, 4, 2, 3])
plt.title('Sample Plot')

# Show and force rendering
plt.draw()
plt.pause(0.1)  # Allow render to complete

# Capture
screenshot = capture_screenshot()
print(f"Plot screenshot: {len(screenshot)} bytes")
```

## Client-Side API

### Current API (keeps working)
```python
from envs.coding_env import CodeAction, CodingEnv

client = CodingEnv.from_docker_image("coding-env:latest")

# Old way (broken - for comparison)
result = client.step(CodeAction(
    code="...",
    capture_screenshot=True  # ❌ This doesn't work - captures AFTER code runs
))
```

### New API (recommended)
```python
from envs.coding_env import CodeAction, CodingEnv

client = CodingEnv.from_docker_image("coding-env:latest")

# New way (works correctly)
code = """
import tkinter as tk
root = tk.Tk()
canvas = tk.Canvas(root, width=400, height=300)
canvas.pack()
canvas.create_rectangle(50, 50, 150, 150, fill='blue')
root.update()
screenshot = capture_screenshot()  # ✅ Captures while GUI is alive
"""

result = client.step(CodeAction(code=code))

# Screenshot is in the observation
if result.observation.screenshot:
    import base64
    screenshot_bytes = base64.b64decode(result.observation.screenshot)
    print(f"Screenshot: {len(screenshot_bytes)} bytes PNG")

    # Save to file
    with open('screenshot.png', 'wb') as f:
        f.write(screenshot_bytes)
```

## Implementation Plan

### 1. Update PyExecutor to Register `capture_screenshot()` Tool

**File:** `src/envs/coding_env/server/python_executor.py`

- Add screenshot capture function to the tools dictionary
- Store captured screenshots in execution context
- Make screenshots available after execution completes

### 2. Update PythonCodeActEnv to Collect Screenshots

**File:** `src/envs/coding_env/server/python_codeact_env.py`

- After code execution, retrieve any screenshots from PyExecutor
- Include screenshots in CodeObservation
- Handle multiple screenshots (return all, or just last, or first?)

### 3. Update CodeObservation Model

**File:** `src/envs/coding_env/models.py`

- Keep existing `screenshot: Optional[str]` field
- Optionally add `screenshots: List[str]` for multiple captures
- Document the new API

### 4. Deprecate `capture_screenshot` Parameter (Optional)

**File:** `src/envs/coding_env/models.py`

- Mark `CodeAction.capture_screenshot` as deprecated
- Keep for backward compatibility
- Update documentation to recommend new API

### 5. Update Examples

**File:** `examples/local_coding_env.py`

- Add example using new `capture_screenshot()` API
- Show single and multiple screenshot captures
- Demonstrate saving screenshots to files

## Technical Details

### Screenshot Storage Strategy

**Option A: Single Screenshot (Simplest)**
- Store only the most recent screenshot
- `CodeObservation.screenshot: Optional[str]`

**Option B: Multiple Screenshots (More Flexible)**
- Store all captured screenshots
- `CodeObservation.screenshots: List[str]`
- Also keep `screenshot: Optional[str]` as alias to first/last

**Recommendation:** Start with Option A, add Option B if users need it.

### Screenshot Function Signature

```python
def capture_screenshot(display: str = ":99") -> str:
    """
    Capture screenshot from Xvfb display.

    Returns:
        Base64-encoded PNG string

    Raises:
        RuntimeError: If screenshot capture fails

    Example:
        >>> screenshot = capture_screenshot()
        >>> print(f"Captured {len(screenshot)} bytes")
    """
```

### Error Handling

```python
# If screenshot capture fails:
try:
    screenshot = capture_screenshot()
except RuntimeError as e:
    print(f"Screenshot failed: {e}")
    screenshot = None
```

## Migration Guide

### For Existing Code Using `capture_screenshot=True`

**Before (broken):**
```python
result = client.step(CodeAction(
    code=tkinter_code,
    capture_screenshot=True  # Doesn't work
))
```

**After (working):**
```python
code_with_capture = """
import tkinter as tk
root = tk.Tk()
# ... create UI ...
root.update()
screenshot = capture_screenshot()  # Works!
"""

result = client.step(CodeAction(code=code_with_capture))
```

### Backward Compatibility

The old `capture_screenshot=True` parameter can remain for backward compatibility:
- If set, attempt screenshot after execution (may fail)
- Log deprecation warning
- Recommend using in-code `capture_screenshot()` function

## Testing Strategy

### Unit Tests
1. Test `capture_screenshot()` function in isolation
2. Test PyExecutor screenshot tool registration
3. Test screenshot storage in execution context

### Integration Tests
1. Test single screenshot capture with tkinter
2. Test multiple screenshots in one execution
3. Test screenshot with matplotlib
4. Test error handling (Xvfb not running, etc.)
5. Test base64 encoding/decoding

### Example Test Case
```python
def test_screenshot_capture():
    code = """
import tkinter as tk
root = tk.Tk()
canvas = tk.Canvas(root, width=100, height=100)
canvas.pack()
canvas.create_rectangle(10, 10, 50, 50, fill='blue')
root.update()
screenshot = capture_screenshot()
assert screenshot is not None
assert len(screenshot) > 1000  # PNG should be at least 1KB
"""
    client = CodingEnv.from_docker_image("coding-env:latest")
    result = client.step(CodeAction(code=code))

    assert result.observation.exit_code == 0
    assert result.observation.screenshot is not None

    # Verify it's valid base64 PNG
    import base64
    png_bytes = base64.b64decode(result.observation.screenshot)
    assert png_bytes[:8] == b'\x89PNG\r\n\x1a\n'  # PNG header
```

## Future Enhancements

1. **Screenshot with coordinates:** `capture_screenshot(x=0, y=0, width=100, height=100)`
3. **Window-specific capture:** `capture_screenshot(window_id=...)`
5. **Video recording:** `start_recording()` / `stop_recording()`

## References

- Xvfb documentation: Virtual frame buffer display server
- ImageMagick `import` command: Screenshot capture tool
- smolagents `send_tools`: API for adding functions to execution sandbox
- Base64 encoding: For transmitting binary PNG data over JSON API

## Decision

**Proceeding with in-execution screenshot API** for:
- ✅ Correct timing (capture while GUI is alive)
- ✅ User control (explicit capture points)
- ✅ Multiple screenshots (progressive captures)
- ✅ Library agnostic (works with any GUI toolkit)
- ✅ No magic/guessing (explicit > implicit)
