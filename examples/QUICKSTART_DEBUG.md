# Quick Start: Debug Tutorial Timeout

Follow these 3 simple steps to debug the timeout issue.

## Step 1: Open Two Terminals

### Terminal 1 (Server)
```bash
cd /Users/betodepaola/projects/OpenEnv
python examples/start_openspiel_server.py
```

Wait until you see:
```
✨ Server Ready!
🌐 Server URL: http://localhost:8000
💡 Server logs will appear below as requests come in...
```

**Leave this terminal open!** This is where you'll see the server logs.

---

### Terminal 2 (Test)
```bash
cd /Users/betodepaola/projects/OpenEnv
python examples/debug_openspiel.py
```

This will test the connection and show you the observation format.

---

## Step 2: Update Your Notebook

In your Jupyter notebook, **modify cell 19** to NOT start the server:

```python
# Replace the entire cell 19 with this:
import requests

print("⏳ Checking if external server is running...")
try:
    response = requests.get('http://localhost:8000/health', timeout=2)
    if response.status_code == 200:
        print("✅ Server is running!")
    else:
        raise ConnectionError("Server not healthy")
except:
    print("❌ Server not running!")
    print("Run: python examples/start_openspiel_server.py")
    raise
```

**Add helper functions** (new cell after cell 19):

```python
# Copy the helper functions from examples/notebook_client_only.py
# Specifically: check_server_health(), ping_server(), and modified run_episode()

import requests

def check_server_health():
    try:
        response = requests.get('http://localhost:8000/health', timeout=2)
        return response.status_code == 200
    except:
        return False

def ping_server():
    if check_server_health():
        print("✅ Server is healthy")
        return True
    else:
        print("❌ Server not responding")
        return False
```

**Update run_episode function** (replace cell 25):

Add `max_steps=50` parameter and timeout handling:

```python
def run_episode(env, policy, visualize=True, delay=0.3, max_steps=50):
    """Run episode with max steps limit."""

    if not check_server_health():
        print("⚠️  Server not healthy!")
        return False

    try:
        result = env.reset()
        obs = result.observation

        total_reward = 0
        step = 0

        while not obs.done and step < max_steps:  # ← Add max_steps!
            action_id = policy.select_action(obs)
            action = OpenSpielAction(action_id=action_id, game_name="catch")

            try:
                result = env.step(action)
            except Exception as e:
                print(f"⚠️  Step failed: {e}")
                return False

            obs = result.observation
            if result.reward is not None:
                total_reward += result.reward

            step += 1

        return total_reward > 0

    except Exception as e:
        print(f"❌ Episode error: {e}")
        return False
```

---

## Step 3: Run the Notebook

1. **In notebook**: Run cell 20 to create the client:
   ```python
   client = OpenSpielEnv(base_url="http://localhost:8000")
   ```

2. **In notebook**: Run cell 25 to watch a single episode:
   ```python
   policy = SmartPolicy()
   run_episode(client, policy, visualize=True, delay=0.5)
   ```

3. **Watch Terminal 1** for server logs - you'll see:
   ```
   📥 Incoming Request: POST /reset
   📤 Response: 200 (took 0.012s)
   📥 Incoming Request: POST /step
   📤 Response: 200 (took 0.008s)
   ```

4. **In notebook**: Run cell 27 (but start with fewer episodes):
   ```python
   evaluate_policies(client, num_episodes=10)  # Start with 10 instead of 50
   ```

---

## What to Watch For

### In Server Terminal (Terminal 1):

**Good** ✅:
```
📥 Incoming Request: POST /step
📤 Response: 200 (took 0.008s)
```

**Timeout** ⏱️ (this is the bug!):
```
📥 Incoming Request: POST /step
(hangs here - no response)
```

**Error** ❌:
```
📥 Incoming Request: POST /step
❌ Error: ...
Traceback...
```

---

## If Server Hangs or Crashes

### Stop the server:
```bash
# In Terminal 2:
python examples/stop_openspiel_server.py
```

### Restart it:
```bash
# In Terminal 1:
python examples/start_openspiel_server.py
```

### In notebook:
```python
# Check connection:
ping_server()
```

---

## Pro Tips

1. **Start small**: Test with `num_episodes=5` first
2. **Test one policy at a time**: Comment out SmartPolicy initially
3. **Watch both terminals**: Server logs + notebook output
4. **Add delays**: Between episode batches, add `time.sleep(0.1)`
5. **Check health**: Run `ping_server()` between policy tests

---

## Full Example Workflow

```bash
# Terminal 1
cd /Users/betodepaola/projects/OpenEnv
python examples/start_openspiel_server.py
# ← Keep open, watch logs

# Terminal 2
cd /Users/betodepaola/projects/OpenEnv
python examples/debug_openspiel.py
# ← Should show "✅ Completed all debug steps!"
```

Then in notebook:
```python
# Test connection
ping_server()

# Test single episode
policy = RandomPolicy()
run_episode(client, policy, visualize=True)

# Test batch (start small!)
evaluate_policies(client, num_episodes=5)
```

---

## Need More Help?

See `examples/README_DEBUGGING.md` for detailed troubleshooting.

The key insight: **Separate server logs from client** makes debugging 100x easier!
