# Coding Environment - Implementation Status

## Overview

The Coding Environment (`coding_env`) provides a sandboxed Python code execution environment with GUI support, screenshot capture, and dynamic package installation capabilities.

## Core Features

### ✅ Implemented Features

#### 1. **Headless GUI Support (Xvfb)**
- **Status**: Fully implemented
- **Description**: Docker container runs Xvfb virtual display server to support GUI libraries (tkinter, matplotlib, pygame)
- **Key Files**:
  - `server/Dockerfile` - Installs Xvfb, python3-tk, and dependencies
  - `server/entrypoint.sh` - Starts Xvfb on display :99 before server launch
- **Documentation**: `HEADLESS_UI_IMPLEMENTATION.md`

#### 2. **Screenshot Capture During Execution**
- **Status**: Fully implemented
- **Description**: Captures screenshots of GUI applications DURING code execution (before UI elements are destroyed)
- **Key Components**:
  - `capture_screenshot` flag in `CodeAction` triggers screenshot capture
  - 0.5s rendering timeout ensures UI elements are fully rendered
  - Auto-injected code updates tkinter/matplotlib windows before capture
  - Uses ImageMagick `import` command to capture from Xvfb display
  - Returns base64-encoded PNG in `CodeObservation.screenshot`
- **Key Files**:
  - `server/python_executor.py` - Screenshot injection and capture logic
  - `client.py` - Client-side API with `capture_screenshot` parameter
  - `models.py` - `CodeAction` and `CodeObservation` with screenshot field
  - `server/python_codeact_env.py` - Retrieves captured screenshots
- **Documentation**: `SCREENSHOT_API.md`, `SCREENSHOT_USAGE.md`
- **Critical Bug Fixed**: `client.py` was missing `capture_screenshot` in HTTP payload

#### 3. **Dynamic Package Installation**
- **Status**: Fully implemented
- **Description**: Install PyPI packages at container startup without rebuilding Docker image
- **Key Features**:
  - Specify packages via `additional_imports` parameter
  - Automatic stdlib filtering (60+ common modules detected)
  - Auto-correction of common typos (e.g., `dataclass` → `dataclasses`)
  - PyPI packages installed via pip at startup
  - Stdlib modules authorized without installation
- **Key Files**:
  - `server/entrypoint.sh` - Filters stdlib, corrects typos, runs pip install
  - `client.py` - `additional_imports` parameter and `timeout_s` support
  - `server/app.py` - Reads `ADDITIONAL_IMPORTS` env var
  - `core/http_env_client.py` - Base class timeout support
- **Documentation**: `DYNAMIC_IMPORTS.md`
- **Usage Notes**:
  - Startup time: 10-120s depending on packages
  - Always use `timeout_s=120.0` or higher when installing packages

#### 4. **Code Execution (smolagents)**
- **Status**: Fully implemented
- **Description**: Sandboxed Python execution using smolagents LocalPythonExecutor
- **Key Features**:
  - Import whitelisting for security
  - Persistent execution context across steps (variables/functions retained)
  - Detailed stdout/stderr capture
  - Exit code tracking
- **Key Files**:
  - `server/python_executor.py` - Wrapper around smolagents
  - `server/python_codeact_env.py` - Environment implementation

## Known Limitations

### ⚠️ smolagents Decorator Limitation (Current Blocker)

- **Issue**: `@dataclass` decorator doesn't work in smolagents
- **Root Cause**: smolagents uses AST interpretation, not real Python execution. Decorators aren't properly applied.
- **Symptoms**: `TypeError: Ball() takes no arguments` when using `@dataclass` with fields
- **Status**: Fundamental limitation of smolagents architecture
- **Workarounds**:
  1. Write explicit `__init__` methods instead of using `@dataclass`
  2. Use simpler data structures (dict, namedtuple)
  3. Use plain classes with manual initialization
- **Documented In**: `SCREENSHOT_IMP_ISSUES.md`

## Architecture

```
┌─────────────────────────────────────────┐
│  Client (Python)                        │
│  - CodingEnv.from_docker_image()        │
│  - CodeAction(code, capture_screenshot) │
└─────────────┬───────────────────────────┘
              │ HTTP (FastAPI)
┌─────────────▼───────────────────────────┐
│  Docker Container (coding-env:latest)   │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │ Xvfb :99 (Virtual Display)         │ │
│  └────────────────────────────────────┘ │
│              ▲                           │
│              │ DISPLAY=:99               │
│  ┌───────────┴──────────────────────┐   │
│  │ PythonCodeActEnv (FastAPI)       │   │
│  │   ├─ PyExecutor (smolagents)     │   │
│  │   └─ Screenshot capture          │   │
│  └──────────────────────────────────┘   │
└──────────────────────────────────────────┘
```

## File Structure

```
coding_env/
├── STATUS.md                          # This file
├── README.md                          # User documentation
├── SCREENSHOT_API.md                  # Screenshot design doc
├── SCREENSHOT_USAGE.md                # Screenshot usage guide
├── SCREENSHOT_IMP_ISSUES.md           # Implementation issues from previous session
├── HEADLESS_UI_IMPLEMENTATION.md      # Xvfb implementation plan
├── DYNAMIC_IMPORTS.md                 # Dynamic package installation guide
├── models.py                          # CodeAction, CodeObservation, CodeState
├── client.py                          # CodingEnv client implementation
└── server/
    ├── python_codeact_env.py          # Environment implementation
    ├── python_executor.py             # smolagents wrapper with screenshot support
    ├── app.py                         # FastAPI server
    ├── transforms.py                  # Observation transforms
    ├── entrypoint.sh                  # Container startup (Xvfb + pip install)
    └── Dockerfile                     # Container image definition
```

## Recent Implementation Work

### Screenshot Capture Feature
- Implemented code injection to capture screenshots DURING execution
- Added automatic UI update for tkinter and matplotlib
- Added 0.5s rendering timeout for proper rendering
- Fixed critical bug: `capture_screenshot` not passed in HTTP payload
- Added required imports to smolagents authorization (subprocess, base64, etc.)
- Added matplotlib and numpy to Docker image
- Added extensive debug output for troubleshooting

### Dynamic Package Installation
- Created entrypoint script with stdlib filtering (60+ modules)
- Added typo auto-correction (dataclass → dataclasses)
- Added timeout support for long pip installs
- Updated client API with `additional_imports` parameter
- Updated base class to support configurable timeouts

## Testing

### Example Files
- `examples/local_coding_env.py` - Basic usage example
- `examples/screenshot_capture_example.py` - Screenshot examples
- `examples/test_screenshot_tool.py` - Screenshot testing
- `examples/test_dynamic_install.py` - Dynamic package installation
- `examples/test_stdlib_filter.py` - Stdlib filtering test

### Running Tests
```bash
# Build image
docker build -t coding-env:latest -f src/envs/coding_env/server/Dockerfile .

# Run example
python examples/local_coding_env.py

# Test screenshot capture
python examples/screenshot_capture_example.py

# Test dynamic imports
python examples/test_dynamic_install.py
```

## Branch Assessment (Milestone M1 Kickoff)

- **History checkpoint**: Current head `f99ab869` adds the enhanced screenshot capture pipeline and dynamic install refinements on top of baseline commit `3167dbd0` (pre-screenshot). Keeping this head preserves the validated capture flow while we refactor execution backends.
- **Executor invariants**: `server/python_executor.py` couples screenshot capture to the smolagents `LocalPythonExecutor` wrapper via injected tooling, while `server/entrypoint.sh` and the Dockerfile manage import authorization and on-demand package installation. These pathways must remain untouched when we introduce a new backend.
- **Branch strategy**: Continue from the current head and introduce an abstraction layer (`ExecutorBackend`) so that RestrictedPython can be swapped in without rewriting screenshot logic or the dynamic import plumbing.
- **Rationale for reuse**: Retaining the existing screenshot capture implementation avoids revalidating Xvfb/ImageMagick integration and UI stabilization heuristics in later milestones; the only delta for Milestone M1 is the executor backend swap.

## Milestone M1 - Restricted Execution Core ✅ PHASE 1 & 2 COMPLETED

### Phase 1: Backend Abstraction & RestrictedPython Integration ✅ COMPLETED

**All components successfully implemented:**

1. **ExecutorBackend Interface** (`server/executor_backend.py`)
   - Created abstract base class defining the minimal contract for executor implementations
   - Includes `run()`, `get_captured_screenshot()`, and `clear_screenshot()` methods
   - Allows uniform interaction with different backends

2. **PyExecutor** Updated (`server/python_executor.py`)
   - Modified to implement `ExecutorBackend` interface
   - Maintains backward compatibility with existing smolagents-based execution
   - Screenshot capture functionality preserved and working

3. **RestrictedPythonExecutor** Implemented (`server/restricted_python_executor.py`)
   - Created new executor backend using RestrictedPython 8.x
   - Implements `ExecutorBackend` interface
   - **Custom `PermissiveRestrictingTransformer`** policy that allows type annotations
   - Persistent execution context (variables/functions persist across calls)
   - Helper utilities (format_exc, safe_json_dumps) available to user code
   - Custom import restrictions via whitelist
   - Screenshot injection pipeline implemented
   - **Full Python semantics including decorators and type annotations!**

4. **PythonCodeActEnv** Updated (`server/python_codeact_env.py`)
   - Added `executor_backend` parameter to constructor
   - Supports selecting between "smolagents" and "restrictedpython" backends
   - Dynamically creates appropriate executor based on configuration

5. **FastAPI Server** Updated (`server/app.py`)
   - Added `EXECUTOR_BACKEND` environment variable support
   - Defaults to "smolagents" for backward compatibility
   - Passes backend selection through to environment

6. **Docker Image** Updated (`server/Dockerfile`)
   - Added RestrictedPython 8.x as a dependency
   - Both backends now available in the container

**Critical Blocker RESOLVED: ✅**

The blocker where **RestrictedPython 8.x does not support type annotations by default** was resolved by implementing a custom `PermissiveRestrictingTransformer` that extends `RestrictingNodeTransformer` to allow `AnnAssign` nodes (type annotations).

The custom transformer:
- Allows type annotations (`x: int`, `name: str`, etc.)
- Allows match/case statements (Python 3.10+)
- Maintains all other security restrictions from RestrictedPython
- Enables `@dataclass` and other decorator patterns that require type annotations

Details documented in: `RESTRICTEDPYTHON_INVESTIGATION.md`

### Phase 2: Validation & Testing ✅ COMPLETED

**Test Results: 🎉 ALL TESTS PASSING (6/6)**

Test file: `examples/test_restrictedpython_executor.py`

✅ **Test 1**: Basic Execution (Print and Calculations) - PASSED
- Print statements work correctly
- Variable assignments and calculations work
- Stdout captured properly

✅ **Test 2**: Exception Handling - PASSED
- Exceptions are caught and formatted in stderr
- Tracebacks include full stack information
- Exit code correctly set to 1 for exceptions

✅ **Test 3**: @dataclass Decorator Support - PASSED **🎯 PRIMARY GOAL ACHIEVED**
- Type annotations work (`x: int`, `y: int`)
- `@dataclass` decorator properly generates `__init__` method
- Decorated classes can be instantiated with arguments
- Custom methods in dataclasses work correctly
- **This was the main reason for switching to RestrictedPython!**

✅ **Test 4**: Persistent Execution Context - PASSED
- Variables defined in one execution available in subsequent executions
- Functions defined in one execution can be called later
- Behaves like a Jupyter notebook (stateful execution)

✅ **Test 5**: Import Restrictions - PASSED
- Whitelisted modules (e.g., `math`) can be imported
- Non-whitelisted modules (e.g., `os`) are blocked with ImportError
- Security policy enforced correctly

✅ **Test 6**: Helper Utilities - PASSED
- `format_exc()` available and working
- `safe_json_dumps()` available and working
- Helper functions accessible from user code

**Key Findings:**
- ✅ Backend abstraction working correctly
- ✅ Executor selection via environment variable working
- ✅ Screenshot injection code integrated (not yet tested with actual screenshots)
- ✅ RestrictedPython execution working with custom policy
- ✅ Print function working (using PrintCollector)
- ✅ Import restrictions enforced
- ✅ Type annotations and @dataclass working!

**Comparison with smolagents:**
- smolagents: ❌ Decorators don't work (AST interpretation, not execution)
- RestrictedPython: ✅ Decorators work (real Python execution with security policy)
- smolagents: ❌ Type annotations not supported
- RestrictedPython: ✅ Type annotations supported (with custom policy)
- Both: ✅ Import restrictions
- Both: ✅ Persistent execution context
- Both: ✅ Helper utilities available

### Phase 3: Documentation ✅ COMPLETED

Documentation files created/updated:
- ✅ `STATUS.md` - Updated with M1 progress
- ✅ `RESTRICTEDPYTHON_INVESTIGATION.md` - Documents the blocker and solution
- ✅ `M1_COMPLETION_SUMMARY.md` - Comprehensive completion report
- ✅ `examples/test_restrictedpython_screenshot.py` - Screenshot test with RestrictedPython
- ✅ `client.py` - Updated with `executor_backend` parameter support

**Screenshot Testing Status:**

Screenshot test file created and ready: `examples/test_restrictedpython_screenshot.py`

The test verifies:
1. Tkinter GUI screenshot capture with RestrictedPython backend
2. Matplotlib figure screenshot capture with RestrictedPython backend
3. Valid PNG data returned in base64 format

**Client API Updated:**

The `CodingEnv.from_docker_image()` method now supports `executor_backend` parameter:

```python
env = CodingEnv.from_docker_image(
    "coding-env:latest",
    executor_backend="restrictedpython",  # or "smolagents" (default)
    additional_imports=["tkinter", "matplotlib", "numpy"]
)
```

**To run screenshot tests:**
1. Rebuild Docker image: `docker build -t coding-env:latest -f src/envs/coding_env/server/Dockerfile .`
2. Run test: `python examples/test_restrictedpython_screenshot.py`

**Expected Results:**
- Screenshot capture should work identically with both backends
- RestrictedPython's screenshot injection uses the same pipeline as smolagents
- All screenshot timing and rendering logic preserved

## Next Steps / Future Enhancements

1. **Investigate smolagents alternatives** for full Python compatibility (including decorators)
2. **Video recording** - Capture multiple frames during execution
3. **Region-based screenshots** - Capture specific window areas
4. **Package caching** - Pre-cache common PyPI packages in base image
5. **Dynamic stdlib detection** - Use `sys.stdlib_module_names` instead of hardcoded list
6. **Multiple displays** - Per-session display numbers (:100, :101, etc.)

## Dependencies

### System (Docker)
- python3-tk, tk-dev, tcl-dev
- xvfb, x11-utils
- imagemagick (for screenshot capture)

### Python
- smolagents
- fastapi, uvicorn
- requests (client)
- matplotlib, numpy (for GUI examples)

## Configuration

### Environment Variables
- `DISPLAY=:99` - X11 display for GUI applications
- `ADDITIONAL_IMPORTS` - Comma-separated list of modules to authorize/install

### Client Parameters
- `additional_imports: List[str]` - Modules to authorize (stdlib + PyPI)
- `timeout_s: float` - Container startup timeout (default 30s, use 120s+ for packages)
- `capture_screenshot: bool` - Enable screenshot capture during execution

## Support

For issues, questions, or contributions:
- See `README.md` for usage documentation
- See `SCREENSHOT_API.md` for screenshot implementation details
- See `DYNAMIC_IMPORTS.md` for package installation details
- See `HEADLESS_UI_IMPLEMENTATION.md` for Xvfb architecture
