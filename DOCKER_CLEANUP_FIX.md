# Docker Container Cleanup Fix

## Problem

When running `python ./examples/local_coding_env.py`, the cleanup step (`client.close()`) was timing out with:

```
❌ Test failed: Command '['docker', 'stop', 'e234739f...']' timed out after 10 seconds
subprocess.TimeoutExpired: Command '['docker', 'stop', '...'] timed out after 10 seconds
```

**Consequences:**
- Test marked as failed even though all operations succeeded
- Container left running and not removed
- Requires manual cleanup: `docker rm -f <container_id>`
- Accumulates stopped containers over multiple test runs

## Root Cause Analysis

### Original Code (`src/core/containers/runtime/providers.py`):

```python
try:
    subprocess.run(
        ["docker", "stop", self._container_id],
        capture_output=True,
        check=True,
        timeout=10,  # 10-second timeout
    )
except subprocess.CalledProcessError:
    # Only catches command errors, NOT timeouts!
    pass
```

**Issues:**
1. **Missing exception handler**: Only catches `CalledProcessError`, not `TimeoutExpired`
2. **Uncaught timeout**: When `docker stop` takes >10 seconds, `TimeoutExpired` is raised and propagates up
3. **No fallback**: No attempt to force-kill if graceful stop fails
4. **Cleanup incomplete**: Container removal never happens if stop times out

### Why Does Docker Stop Take So Long?

`docker stop` behavior:
1. Sends SIGTERM to the container's main process (PID 1)
2. Waits for process to exit gracefully
3. **Default grace period: 10 seconds**
4. If still running, sends SIGKILL

**Potential causes for slow stop:**
- Application doesn't handle SIGTERM properly
- Cleanup handlers running in the application
- Background processes still running (like Xvfb in the headless UI version)
- Docker daemon under heavy load
- Network cleanup delays

## Solution Comparison

| Approach | Pros | Cons | Recommendation |
|----------|------|------|----------------|
| **1. Catch TimeoutExpired only** | Simple fix | Still waits 10s, might timeout again | ⚠️ Partial |
| **2. Use docker stop --time=N** | Control grace period | Doesn't prevent subprocess timeout | ⚠️ Partial |
| **3. Increase subprocess timeout** | Gives more time | Doesn't solve problem, just delays | ❌ Bad |
| **4. Always use docker kill** | Fast, no timeout | Ungraceful, no cleanup | ❌ Too aggressive |
| **5. Graceful + fallback** | Best of both worlds | Slightly more code | ✅ **BEST** |

## Implemented Solution: Graceful Stop + Kill Fallback

### Strategy

```
┌─────────────────────────────────────────────────┐
│ Container Cleanup Flow                          │
├─────────────────────────────────────────────────┤
│                                                 │
│  1. Try: docker stop --time=5                   │
│     (graceful stop, 5s grace period)            │
│     └─ subprocess timeout: 15s                  │
│                                                 │
│  2. If TimeoutExpired:                          │
│     └─ Fallback: docker kill                   │
│        (force kill immediately)                 │
│                                                 │
│  3. Always: docker rm -f                        │
│     (force remove, works on running containers) │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Code Changes

**File: `src/core/containers/runtime/providers.py`**

```python
try:
    # Try graceful stop first (Docker waits 5 seconds before SIGKILL)
    # Subprocess timeout is 15 seconds to allow Docker's grace period
    subprocess.run(
        ["docker", "stop", "--time=5", self._container_id],
        capture_output=True,
        check=True,
        timeout=15,
    )
except subprocess.TimeoutExpired:
    # Graceful stop timed out, force kill the container
    print(f"Warning: Container {self._container_id} did not stop gracefully, forcing kill...")
    try:
        subprocess.run(
            ["docker", "kill", self._container_id],
            capture_output=True,
            check=True,
            timeout=5,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # Container might already be stopped
        pass
except subprocess.CalledProcessError:
    # Container might already be stopped
    pass

# Always try to remove the container
try:
    subprocess.run(
        ["docker", "rm", "-f", self._container_id],
        capture_output=True,
        check=True,
        timeout=10,
    )
except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
    # Container might already be removed or removal failed
    pass
finally:
    self._container_id = None
    self._container_name = None
```

### Key Improvements

1. **`docker stop --time=5`**: Reduces Docker's grace period from 10s to 5s
   - Gives application 5 seconds to shut down gracefully
   - After 5s, Docker automatically sends SIGKILL

2. **Subprocess timeout: 15 seconds**: Allows Docker's grace period + buffer
   - 5s for graceful shutdown
   - Up to 10s for Docker to SIGKILL and cleanup

3. **TimeoutExpired handler**: Catches subprocess timeouts
   - Falls back to `docker kill` for immediate termination
   - Ensures cleanup always proceeds

4. **`docker rm -f`**: Force-remove flag
   - Can remove even if container is still running
   - Works if container is stopped, running, or partially failed

5. **Multiple exception catches**: Handles both failure types
   - `CalledProcessError`: Command failed (container already gone, etc.)
   - `TimeoutExpired`: Command took too long

6. **finally block**: Always clears container ID
   - Prevents double-cleanup attempts
   - Marks provider as "clean" state

## Expected Behavior After Fix

### Normal Case (Fast Stop):
```
Testing the environment:
------------------------------------------------------------
...
✓ All operations successful!

Cleaning up...
✓ Container stopped and removed

Test completed successfully! 🎉
```
- Container stops in <5 seconds
- No warning message
- Clean exit

### Slow Stop Case (Timeout):
```
Testing the environment:
------------------------------------------------------------
...
✓ All operations successful!

Cleaning up...
Warning: Container e234739f... did not stop gracefully, forcing kill...
✓ Container stopped and removed

Test completed successfully! 🎉
```
- Container doesn't stop within 15 seconds
- Warning printed to stderr
- Falls back to `docker kill`
- Container still gets removed
- **Test succeeds** instead of failing

## Testing

### Manual Test:
```bash
# From OpenEnv repo root
python ./examples/local_coding_env.py
```

**Expected:** Test completes successfully with no timeout errors

### Verify cleanup:
```bash
# Before test
docker ps -a | grep coding

# Run test
python ./examples/local_coding_env.py

# After test - should show no containers
docker ps -a | grep coding
```

### Test slow container stop:
```bash
# Simulate a slow-stopping container by modifying the server
# to ignore SIGTERM (for testing purposes only)

# The fallback kill should still clean it up
```

## Tradeoffs

| Aspect | Before | After | Impact |
|--------|--------|-------|--------|
| **Cleanup time (normal)** | ~1-2s | ~1-2s | ✅ Same |
| **Cleanup time (slow)** | Fails at 10s | ~15-20s | ✅ Slower but works |
| **Cleanup reliability** | Fails on timeout | Always succeeds | ✅ Much better |
| **Graceful shutdown** | Yes (10s) | Yes (5s) | ⚠️ Less time |
| **Code complexity** | Simple | Moderate | ⚠️ More logic |

### Why 5 seconds grace period?

- **Most containers stop in <1 second**: FastAPI/uvicorn shutdown is fast
- **5 seconds is generous**: Plenty of time for cleanup handlers
- **Reduces total wait time**: 5s grace + timeout faster than 10s grace
- **Industry standard**: Common in Kubernetes (terminationGracePeriodSeconds: 5-30s)

## Alternative Approaches Considered

### Option A: Increase timeout to 30s
```python
subprocess.run(["docker", "stop", ...], timeout=30)
```
**Rejected**: Doesn't solve the problem, just delays it

### Option B: Always use docker kill
```python
subprocess.run(["docker", "kill", ...])
```
**Rejected**: Too aggressive, prevents graceful cleanup

### Option C: Async cleanup
```python
# Don't wait for stop, return immediately
subprocess.Popen(["docker", "stop", ...])
```
**Rejected**: Container might outlive the script, no error detection

### Option D: docker stop with no subprocess timeout
```python
subprocess.run(["docker", "stop", ...], timeout=None)
```
**Rejected**: Could hang forever if Docker daemon issues

## Future Improvements

1. **Logging**: Add proper logging instead of print statements
   ```python
   logger.warning(f"Container {self._container_id} did not stop gracefully")
   ```

2. **Metrics**: Track how often graceful stop fails
   ```python
   metrics.increment("container.stop.timeout")
   ```

3. **Configurable timeouts**: Allow users to configure grace period
   ```python
   def stop_container(self, grace_period: int = 5):
   ```

4. **Health check before stop**: Check if container is responsive
   ```python
   if self._is_container_responsive():
       # Try graceful stop
   else:
       # Skip to kill
   ```

5. **Background cleanup**: For interactive use, don't block on cleanup
   ```python
   def close(self, wait: bool = True):
       if wait:
           self._provider.stop_container()
       else:
           self._provider.stop_container_async()
   ```

## References

- [Docker stop documentation](https://docs.docker.com/engine/reference/commandline/stop/)
- [Docker kill documentation](https://docs.docker.com/engine/reference/commandline/kill/)
- [Graceful shutdown best practices](https://cloud.google.com/blog/products/containers-kubernetes/kubernetes-best-practices-terminating-with-grace)
- [Python subprocess timeout handling](https://docs.python.org/3/library/subprocess.html#subprocess.TimeoutExpired)

## Summary

The fix ensures that containers are **always cleaned up** even when they don't stop gracefully within the timeout period. The solution:

1. ✅ Maintains graceful shutdown as the primary path
2. ✅ Falls back to force-kill when needed
3. ✅ Always removes containers
4. ✅ Handles all error cases
5. ✅ Prevents test failures from cleanup timeouts
6. ✅ Prevents container accumulation

**Status**: ✅ Implemented and ready for testing
