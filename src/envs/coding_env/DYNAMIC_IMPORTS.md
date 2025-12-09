# Dynamic Package Installation - Implementation Summary

## Overview

The CodingEnv now supports **dynamic package installation** at container startup. You can specify any Python package (PyPI or stdlib) in your client code, and:

- **PyPI packages** are automatically installed via `pip install` when the container starts
- **Stdlib modules** are automatically authorized without installation
- **Common typos** are auto-corrected (e.g., `dataclass` → `dataclasses`)

**No Docker rebuild required!**

## Usage

```python
from envs.coding_env import CodeAction, CodingEnv

# Specify packages directly in your code
client = CodingEnv.from_docker_image(
    "coding-env:latest",
    additional_imports=[
        "pandas",       # PyPI - will be installed
        "scipy",        # PyPI - will be installed
        "dataclass",    # Typo - auto-corrected to "dataclasses"
        "typing",       # Stdlib - authorized without install
        "numpy",        # PyPI - will be installed
    ],
    timeout_s=120.0  # Allow time for pip install
)

# Use the packages in your code
code = """
import pandas as pd
from dataclasses import dataclass
from typing import List

@dataclass
class DataPoint:
    value: float

df = pd.DataFrame({'x': [1, 2, 3]})
print(f"Mean: {df['x'].mean()}")
"""

result = client.step(CodeAction(code=code))
print(result.observation.stdout)
client.close()
```

## How It Works

### 1. Client Side (`client.py`)

```python
# Clean API - just list what you need!
additional_imports=["pandas", "numpy", "dataclasses"]
```

The client converts this to the `ADDITIONAL_IMPORTS` environment variable and passes it to the Docker container.

### 2. Container Startup (`entrypoint.sh`)

When the container starts:

1. **Reads `ADDITIONAL_IMPORTS`** environment variable
2. **Filters** the list:
   - Stdlib modules → Skip pip install, keep in authorization list
   - Typos → Auto-correct (e.g., `dataclass` → `dataclasses`)
   - PyPI packages → Install via `pip install`
3. **Updates `ADDITIONAL_IMPORTS`** with filtered/corrected list
4. **Exports** the updated env var for the server

### 3. Server Side (`app.py`)

The server reads the updated `ADDITIONAL_IMPORTS` and authorizes all modules (both stdlib and installed PyPI packages) in smolagents.

## Auto-Correction

Common typos are automatically fixed:

| User Specifies | Auto-Corrected To | Type |
|----------------|-------------------|------|
| `dataclass` | `dataclasses` | Stdlib |
| *(more can be added)* | | |

## Stdlib Filtering

These modules are **automatically detected** as stdlib and skipped from installation:

### Built-in Types
- `dataclasses`, `typing`, `types`, `collections`, `functools`, `itertools`
- `operator`, `copy`, `pickle`, `json`, `csv`, `xml`, `html`

### System/OS
- `os`, `sys`, `pathlib`, `subprocess`, `shutil`, `tempfile`
- `glob`, `fnmatch`, `io`, `time`, `datetime`, `calendar`

### Math/Numbers
- `math`, `cmath`, `decimal`, `fractions`, `random`, `statistics`

### Text/String
- `string`, `re`, `textwrap`, `unicodedata`, `codecs`

### Data Structures
- `array`, `queue`, `heapq`, `bisect`, `weakref`, `enum`

### Networking/Web
- `urllib`, `http`, `httplib`, `email`, `mimetypes`, `base64`, `binascii`

### Threading/Concurrency
- `threading`, `multiprocessing`, `concurrent`, `asyncio`

### Testing/Debugging
- `unittest`, `doctest`, `pdb`, `trace`, `traceback`, `warnings`

### GUI
- `tkinter`, `turtle`

### Misc
- `argparse`, `logging`, `abc`, `contextlib`, `importlib`

## Important Notes

### Startup Time

- **No extra packages**: ~10-15 seconds
- **Small packages** (requests): ~20-30 seconds
- **Large packages** (pandas, scipy): ~60-120 seconds

**Always use a longer `timeout_s` when installing packages!**

### Installation Logs

You can see what happened during startup:

```bash
docker logs <container-id>
```

Example output:
```
=== Coding Environment Startup ===
Processing ADDITIONAL_IMPORTS: dataclass,types,typing,pandas,numpy
  - Skipping stdlib module from installation: dataclass
    → Corrected to: dataclasses
  - Skipping stdlib module from installation: types
  - Skipping stdlib module from installation: typing
  - Installing PyPI packages: pandas, numpy
  ✓ Successfully installed: pandas, numpy
  - Updated ADDITIONAL_IMPORTS to: dataclasses,types,typing,pandas,numpy
```

### Why Environment Variables?

**Q: Why pass through environment variables instead of HTTP?**

**A:** The client and server are **separate processes**. The container needs configuration **before** the HTTP server starts listening (because the server needs to know which imports to authorize when it initializes smolagents). Environment variables are the standard Docker pattern for startup configuration.

## Modified Files

### Core Changes

1. **`src/envs/coding_env/server/entrypoint.sh`** (NEW)
   - Filters stdlib from pip install
   - Auto-corrects common typos
   - Updates ADDITIONAL_IMPORTS env var

2. **`src/envs/coding_env/server/Dockerfile`**
   - Uses new entrypoint script instead of inline startup

3. **`src/envs/coding_env/client.py`**
   - Added `additional_imports` parameter
   - Added `timeout_s` parameter
   - Converts list to env var automatically

4. **`src/core/http_env_client.py`**
   - Added `timeout_s` parameter to base class

## Testing

Run the test example:

```bash
# Test stdlib filtering and typo correction
python examples/test_stdlib_filter.py

# Test dynamic installation of PyPI packages
python examples/quick_dynamic_test.py
```

## Troubleshooting

### Container times out on startup

- **Cause**: Large packages take time to install
- **Fix**: Increase `timeout_s` parameter (try 120.0 or 180.0)

### "Non-installed authorized modules" error

- **Cause**: Typo in module name or not in stdlib filter list
- **Fix**: Check spelling, or add to TYPO_TO_CORRECT map in entrypoint.sh

### Package installation fails

- **Cause**: Invalid package name or network issues
- **Fix**: Check Docker logs with `docker logs <container-id>`

## Future Enhancements

Possible improvements:

1. **Dynamic stdlib detection** - Instead of hardcoded list, check `sys.stdlib_module_names`
2. **Package caching** - Cache common packages in base image layer
3. **Parallel installation** - Install packages concurrently for speed
4. **Requirements file support** - Accept requirements.txt format
