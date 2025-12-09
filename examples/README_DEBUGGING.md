# Debugging the OpenEnv Tutorial

This guide helps you debug timeout issues when running the OpenEnv tutorial notebook by separating the server and client.

## Problem

When running cell 27 in `OpenEnv_Tutorial.ipynb`, the server times out and becomes unresponsive. This makes it impossible to see what's happening server-side.

## Solution: Separate Server and Client

Run the server in a separate terminal window so you can see real-time logs while running the client from the notebook.

## Quick Start

### Step 1: Stop Any Running Servers

```bash
# Kill any existing server on port 8000
python examples/stop_openspiel_server.py
```

### Step 2: Start Server in Terminal

Open a **new terminal window** and run:

```bash
cd /path/to/OpenEnv
python examples/start_openspiel_server.py
```

You should see:
```
======================================================================
   🎮 OpenSpiel Server - Debug Mode
======================================================================

📋 Configuration:
   • Game: catch
   • Agent Player: 0
   • Opponent Policy: random
   • Port: 8000

✅ OpenSpiel is installed

======================================================================
   🚀 Starting Server with Verbose Logging
======================================================================

🎮 Creating OpenSpielEnvironment('catch')...
✅ Environment created successfully
   • Number of players: 1
   • Turn-based: True

📦 Creating FastAPI application...
✅ FastAPI app created

======================================================================
   ✨ Server Ready!
======================================================================

🌐 Server URL: http://localhost:8000

💡 Server logs will appear below as requests come in...
```

**Keep this terminal open!** You'll see logs as the client makes requests.

### Step 3: Run Debug Script (Optional)

In another terminal, test the server:

```bash
python examples/debug_openspiel.py
```

This will:
- Test connectivity
- Inspect observation format
- Play a test episode
- Run stress tests

### Step 4: Modify Your Notebook

In your Jupyter notebook, replace the server startup cells with the client-only code from `examples/notebook_client_only.py`.

The key changes:

#### Replace Cell 19 (Server Startup):
```python
# Instead of starting the server in the notebook,
# just check if external server is running

import requests
import time

print("⏳ Checking if server is running...")
try:
    response = requests.get('http://localhost:8000/health', timeout=2)
    if response.status_code == 200:
        print("✅ OpenSpiel server is running and healthy!")
    else:
        print("❌ Server not responding. Start it with:")
        print("   python examples/start_openspiel_server.py")
except:
    print("❌ Server not running!")
    raise
```

#### Add Helper Functions (New Cell):
```python
def check_server_health():
    """Check if the OpenSpiel server is healthy."""
    try:
        response = requests.get('http://localhost:8000/health', timeout=2)
        return response.status_code == 200
    except:
        return False

def ping_server():
    """Ping server and show status."""
    print("🔍 Pinging server...")
    if check_server_health():
        print("✅ Server is healthy")
        state = requests.get('http://localhost:8000/state', timeout=2).json()
        print(f"📊 Current state:")
        print(f"   • Episode ID: {state.get('episode_id', 'N/A')}")
        print(f"   • Step count: {state.get('step_count', 0)}")
        return True
    else:
        print("❌ Server is not responding")
        return False

ping_server()
```

#### Update run_episode (Replace Cell 25):
```python
def run_episode(env, policy, visualize=True, delay=0.3, max_steps=50):
    """Run episode with timeout protection."""
    if not check_server_health():
        print("⚠️  WARNING: Server not healthy!")
        return False

    try:
        result = env.reset()
        obs = result.observation
        # ... rest of the function with try/except around step()

    except requests.exceptions.Timeout:
        print(f"⚠️  Request timeout! Check server terminal.")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
```

See `examples/notebook_client_only.py` for complete modified functions.

### Step 5: Run the Notebook

Now run your notebook cells. Watch the **server terminal** for real-time logs:

```
──────────────────────────────────────────────────────────────────────
📥 Incoming Request: POST /reset
📤 Response: 200 (took 0.012s)
──────────────────────────────────────────────────────────────────────

──────────────────────────────────────────────────────────────────────
📥 Incoming Request: POST /step
📤 Response: 200 (took 0.008s)
──────────────────────────────────────────────────────────────────────
```

## What to Look For in Server Logs

### Normal Operation:
```
📥 Incoming Request: POST /reset
📤 Response: 200 (took 0.012s)
📥 Incoming Request: POST /step
📤 Response: 200 (took 0.008s)
```

### Timeout/Hang:
```
📥 Incoming Request: POST /step
(no response for >15 seconds - this is the bug!)
```

### Error:
```
📥 Incoming Request: POST /step
❌ Error: ... (after 0.002s)
Traceback...
```

## Common Issues and Fixes

### Issue 1: Server Times Out on Certain Actions

**Symptom**: Server receives request but never responds

**Likely cause**: Bug in environment logic (e.g., infinite loop in `_auto_play_opponents`)

**Fix**: Check server logs for where it hangs. Add print statements in `src/envs/openspiel_env/server/openspiel_environment.py`

### Issue 2: SmartPolicy Always Returns STAY

**Symptom**: SmartPolicy gets ~20% success rate (same as random)

**Likely cause**: Wrong encoding assumptions in the policy

**Fix**: Run `python examples/debug_openspiel.py` to see the actual observation encoding, then fix the policy

### Issue 3: Server Dies After a Few Requests

**Symptom**: Server stops responding and terminal shows error

**Fix**: Check the error traceback in server terminal, fix the bug, restart server

## Files Created

- `examples/start_openspiel_server.py` - Start server with logging
- `examples/stop_openspiel_server.py` - Kill server on port 8000
- `examples/debug_openspiel.py` - Debug connection and observation format
- `examples/notebook_client_only.py` - Modified notebook cells for client-only mode
- `examples/README_DEBUGGING.md` - This file

## Tips

1. **Always check server logs first** when debugging timeouts
2. **Add max_steps limit** to prevent infinite episodes
3. **Use ping_server()** between policy evaluations to check health
4. **Reduce num_episodes** while debugging (try 5 instead of 50)
5. **Test policies individually** before running all 4 together

## Advanced: Adding More Logging

To add more detailed logging to the environment, edit:

`src/envs/openspiel_env/server/openspiel_environment.py`

Add print statements in key methods:

```python
def step(self, action: Action) -> Observation:
    print(f"[DEBUG] step() called with action_id={action.action_id}")

    # ... existing code ...

    print(f"[DEBUG] step() returning, done={obs.done}, reward={obs.reward}")
    return obs
```

Restart the server to see these logs.

## Still Having Issues?

1. Check `examples/debug_openspiel.py` output for observation format
2. Share server logs when asking for help
3. Try different games: `OPENSPIEL_GAME=tic_tac_toe python examples/start_openspiel_server.py`
4. Check if it's a race condition by adding delays between requests

Good luck debugging! 🐛🔍


# Working scrappad

 ON this:  Incomplete Docker build: Doesn't explain this builds in-repo mode by default, when I tested standalone, I didn't need to build the image differently. Why is that? am I using the wrong image or building


TODO: Validate these assertions from claude, they don't seem right

ON this:  Incomplete Docker build: Doesn't explain this builds in-repo mode by default, when I tested standalone, I didn't need to build the image differently. Why is that? am I using the wrong image or building with and without that does
not make a difference?

⏺ Excellent observation! You've discovered something important: the client mode and server mode are independent.

  Let me explain what's actually happening:

  Client vs Server Modes

  When you tested standalone, you were using:
  - Client (your Python code): Standalone mode - installed package using from coding_env import...
  - Server (Docker container): In-repo mode - built with default Dockerfile settings

  And it worked perfectly because: The client and server communicate over HTTP. The client doesn't care what's inside the Docker container - it just makes HTTP requests to http://localhost:PORT.

  When Does BUILD_MODE Actually Matter?

  The Docker BUILD_MODE only matters in these scenarios:

  Scenario 1: Distributing the Docker image

  If you want to publish the Docker image to Docker Hub/GitHub Packages without the full OpenEnv repo:

  # This won't work - needs the entire src/ directory from repo
  docker build -t coding-env:standalone --build-arg BUILD_MODE=standalone .

  # This needs to be run from within the coding_env package directory only

  Scenario 2: What's copied into the image

  - In-repo mode: Copies entire src/ directory (~large)
  - Standalone mode: Copies only coding_env/ package (~small)

  Scenario 3: Dependencies

  - In-repo mode: Installs dependencies directly via pip
  - Standalone mode: Installs from pyproject.toml (which would pull openenv-core from PyPI if it were published)

  For Your Testing: In-Repo Docker Works Fine

  You can keep using the in-repo Docker image for both:

  # Build once (in-repo mode - default)
  docker build -t coding-env:latest -f src/envs/coding_env/server/Dockerfile .

  # Use with in-repo client
  python ./examples/local_coding_env.py

  # Use with standalone client
  python ~/test_coding_env_standalone.py  # Uses standalone imports but connects to in-repo container

  Both work because the client-server interface is just HTTP!

  So to answer your question: You're using the "in-repo" Docker image for both tests, and that's perfectly fine. The BUILD_MODE distinction is mainly for distribution/packaging purposes, not for local development/testing.
