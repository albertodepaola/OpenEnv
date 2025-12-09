# Debugging Summary: Tutorial Timeout Issue

## The Problem

When running the OpenEnv tutorial notebook, cell 27 (`evaluate_policies()` with 4 policies × 50 episodes) causes the server to timeout and become unresponsive. After the timeout, all subsequent calls to the server also timeout.

## Root Causes Identified

### 1. **SmartPolicy Bug** ⚠️
The `SmartPolicy` in the notebook assumes incorrect encoding for the Catch game's `info_state`:

```python
# Assumes ball=1.0 and paddle=0.5, but OpenSpiel uses different encoding
if abs(val - 1.0) < 0.01:  # Ball
    ball_col = idx % grid_size
elif abs(val - 0.5) < 0.01:  # Paddle
    paddle_col = idx % grid_size
```

**Result**: Policy never finds ball/paddle positions correctly, always returns STAY (action 1), performs no better than random.

### 2. **Shared Environment State** 🔄
The server (`src/envs/openspiel_env/server/app.py`) creates a single shared environment instance:

```python
env = OpenSpielEnvironment(...)  # Only ONE instance for ALL requests
```

**Result**: Rapid requests from 4 policies running 200 total episodes can cause:
- Race conditions during reset()
- State corruption between episodes
- Potential infinite loops in `_auto_play_opponents()`

### 3. **Short Default Timeout** ⏱️
Client timeout is only 15 seconds (`src/core/http_env_client.py:34`):

```python
request_timeout_s: float = 15.0  # Only 15 seconds!
```

**Result**: If server gets stuck, client times out quickly and can't recover.

## The Solution: Separate Server & Client

Instead of running the server inside the notebook (where you can't see logs), run it in a separate terminal window.

### Created Files

| File | Purpose |
|------|---------|
| `examples/start_openspiel_server.py` | Start server with verbose logging |
| `examples/stop_openspiel_server.py` | Kill server on port 8000 |
| `examples/debug_openspiel.py` | Test connectivity and inspect observations |
| `examples/notebook_client_only.py` | Modified notebook cells (client-only mode) |
| `examples/README_DEBUGGING.md` | Detailed debugging guide |
| `examples/QUICKSTART_DEBUG.md` | Quick 3-step setup |

### How It Works

**Before** (notebook runs everything):
```
┌─────────────────────────────────────┐
│  Jupyter Notebook                   │
│  ├─ Server (subprocess, no logs)    │  ← Can't see what's happening!
│  └─ Client (calls server)           │
└─────────────────────────────────────┘
```

**After** (separate server):
```
┌──────────────────────┐         ┌─────────────────────────┐
│  Terminal            │         │  Jupyter Notebook       │
│  Server with logs ←──┼─HTTP────┤  Client only           │
│  (you see requests!) │         │  (makes HTTP calls)    │
└──────────────────────┘         └─────────────────────────┘
```

## Usage

### Quick Start (3 commands)

**Terminal 1 (Server)**:
```bash
python examples/start_openspiel_server.py
# Watch logs appear here!
```

**Terminal 2 (Test)**:
```bash
python examples/debug_openspiel.py
# Verify connection and test
```

**Jupyter Notebook**:
```python
# Connect to external server (don't start one)
client = OpenSpielEnv(base_url="http://localhost:8000")

# Run policies
evaluate_policies(client, num_episodes=10)  # Start with 10
```

## What You'll See

### Server Terminal (Terminal 1)

**Normal operation**:
```
──────────────────────────────────────────────────────────────────────
📥 Incoming Request: POST /reset
📤 Response: 200 (took 0.012s)
──────────────────────────────────────────────────────────────────────
📥 Incoming Request: POST /step
📤 Response: 200 (took 0.008s)
──────────────────────────────────────────────────────────────────────
```

**Timeout/hang** (the bug!):
```
──────────────────────────────────────────────────────────────────────
📥 Incoming Request: POST /step
(no response - hangs here!)
```

**Error**:
```
──────────────────────────────────────────────────────────────────────
📥 Incoming Request: POST /step
❌ Error: IndexError: list index out of range (after 0.002s)
──────────────────────────────────────────────────────────────────────
Traceback (most recent call last):
  File "...", line 123, in step
    ...
```

Now you can **see exactly where and why** the server hangs!

## Debugging Steps

1. ✅ **Start server separately** to see logs
2. ✅ **Run debug script** to verify connection
3. ✅ **Test single episode** before batch
4. ✅ **Reduce num_episodes** to 5-10 for testing
5. ✅ **Test policies individually** to isolate issues
6. ✅ **Add max_steps limit** to prevent infinite loops
7. ✅ **Monitor server health** between batches

## Quick Fixes

### Fix 1: Increase Timeout
```python
client = OpenSpielEnv(
    base_url="http://localhost:8000",
    request_timeout_s=60.0  # Increase from 15 to 60
)
```

### Fix 2: Add Max Steps
```python
def run_episode(env, policy, max_steps=50):  # ← Add limit
    step = 0
    while not obs.done and step < max_steps:  # ← Check limit
        # ...
        step += 1
```

### Fix 3: Skip Buggy SmartPolicy
```python
policies = [
    RandomPolicy(),
    AlwaysStayPolicy(),
    # SmartPolicy(),  # ← Skip until fixed
    LearningPolicy(),
]
```

### Fix 4: Test Small Batches
```python
evaluate_policies(client, num_episodes=10)  # Not 50
```

## Next Steps

1. **Immediate**: Use the separate server to see what's happening
2. **Debug**: Use server logs to identify exact failure point
3. **Fix SmartPolicy**: Use `debug_openspiel.py` output to understand correct encoding
4. **Optimize**: Consider per-request environment instances (not shared)
5. **Improve**: Add better error handling and timeouts throughout

## Key Insight

The real issue isn't timeouts per se - it's **lack of visibility**. By separating the server and client, you can:

- ✅ See which exact request hangs
- ✅ See error tracebacks immediately
- ✅ Restart server without restarting notebook kernel
- ✅ Add debug logging without modifying notebook
- ✅ Monitor server health in real-time

This is a **much better development experience**!

## Files Location

All debugging tools are in `examples/`:

```
examples/
├── start_openspiel_server.py     ← Run this first!
├── stop_openspiel_server.py      ← Kill server
├── debug_openspiel.py            ← Test & inspect
├── notebook_client_only.py       ← Modified cells
├── QUICKSTART_DEBUG.md           ← 3-step setup
├── README_DEBUGGING.md           ← Full guide
└── DEBUGGING_SUMMARY.md          ← This file
```

## Support

- 📖 Read: `QUICKSTART_DEBUG.md` for quick setup
- 📚 Read: `README_DEBUGGING.md` for detailed troubleshooting
- 🔍 Run: `debug_openspiel.py` to inspect observations
- 💬 Share: Server logs when asking for help

Good luck! The separate server approach will make debugging much easier. 🎉
