"""
Modified cells for OpenEnv Tutorial - Client-Only Mode

Copy these cells into your Jupyter notebook to connect to an external server
instead of starting the server within the notebook.

This allows you to:
1. Run the server in a separate terminal with full logging
2. See real-time server logs while debugging
3. Restart the server independently without restarting the kernel
"""

# ============================================================================
# CELL: Replace cell 19 (Server Startup) with this
# ============================================================================

print("🌐 " + "="*64 + " 🌐")
print("   Client-Only Mode - Connecting to External Server")
print("🌐 " + "="*64 + " 🌐\n")

print("📋 Instructions:")
print("   1. Open a separate terminal window")
print("   2. Navigate to the OpenEnv directory")
print("   3. Run: python examples/start_openspiel_server.py")
print("   4. Wait for the server to show 'Server Ready!'")
print("   5. Then run the cells below in this notebook\n")

print("⏳ Checking if server is already running...")

import requests
import time

max_retries = 5
retry_delay = 2

for attempt in range(max_retries):
    try:
        response = requests.get('http://localhost:8000/health', timeout=2)
        if response.status_code == 200:
            print("\n✅ OpenSpiel server is running and healthy!")
            print("🌐 Server URL: http://localhost:8000")
            print("📍 Endpoints available:")
            print("   • POST /reset")
            print("   • POST /step")
            print("   • GET /state")
            print("\n💡 You can now run the rest of the notebook cells!")
            print("   Server logs will appear in the other terminal window.\n")
            break
    except requests.RequestException:
        if attempt < max_retries - 1:
            print(f"   Attempt {attempt + 1}/{max_retries}: Server not ready, waiting {retry_delay}s...")
            time.sleep(retry_delay)
        else:
            print("\n❌ Server is not running!")
            print("\n🔧 To start the server:")
            print("   1. Open a NEW terminal/console window")
            print("   2. cd to your OpenEnv directory")
            print("   3. Run: python examples/start_openspiel_server.py")
            print("\n   Then re-run this cell to connect.\n")
            raise ConnectionError("Could not connect to server at http://localhost:8000")


# ============================================================================
# CELL: Helper functions to check server status
# ============================================================================

def check_server_health():
    """Check if the OpenSpiel server is healthy."""
    try:
        response = requests.get('http://localhost:8000/health', timeout=2)
        return response.status_code == 200
    except:
        return False

def get_server_state():
    """Get current server state for debugging."""
    try:
        response = requests.get('http://localhost:8000/state', timeout=2)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None

def ping_server():
    """Ping server and show status."""
    print("🔍 Pinging server...")

    if check_server_health():
        print("✅ Server is healthy")

        state = get_server_state()
        if state:
            print(f"📊 Current state:")
            print(f"   • Episode ID: {state.get('episode_id', 'N/A')}")
            print(f"   • Step count: {state.get('step_count', 0)}")
            print(f"   • Game: {state.get('game_name', 'N/A')}")
        return True
    else:
        print("❌ Server is not responding")
        print("   Check the server terminal for errors")
        return False

# Test it
print("\n" + "="*70)
ping_server()
print("="*70 + "\n")


# ============================================================================
# CELL: Modified run_episode with better error handling and logging
# ============================================================================

import time

def run_episode(env, policy, visualize=True, delay=0.3, max_steps=50):
    """
    Run one episode with a policy against OpenSpiel environment.

    Added features:
    - Max steps limit to prevent infinite loops
    - Better error handling
    - Server health check
    """

    # Check server health before starting
    if not check_server_health():
        print("⚠️  WARNING: Server not healthy before episode!")
        return False

    try:
        # RESET
        result = env.reset()
        obs = result.observation

        if visualize:
            print(f"\n{'='*60}")
            print(f"   🎮 {policy.name}")
            print(f"   🎲 Playing against OpenSpiel Catch")
            print('='*60 + '\n')
            time.sleep(delay)

        total_reward = 0
        step = 0
        action_names = ["⬅️  LEFT", "🛑 STAY", "➡️  RIGHT"]

        # THE RL LOOP
        while not obs.done and step < max_steps:
            # 1. Policy chooses action
            action_id = policy.select_action(obs)

            # 2. Environment executes (via HTTP!)
            action = OpenSpielAction(action_id=action_id, game_name="catch")

            try:
                result = env.step(action)
                obs = result.observation
            except requests.exceptions.Timeout:
                print(f"\n⚠️  Request timeout at step {step + 1}!")
                print(f"   Check server terminal for errors")
                return False
            except Exception as e:
                print(f"\n❌ Error during step: {e}")
                return False

            # 3. Collect reward
            if result.reward is not None:
                total_reward += result.reward

            if visualize:
                print(f"📍 Step {step + 1}: {action_names[action_id]} → Reward: {result.reward}")
                time.sleep(delay)

            step += 1

        if step >= max_steps:
            print(f"\n⚠️  Hit max steps limit ({max_steps})")

        if visualize:
            result_text = "🎉 CAUGHT!" if total_reward > 0 else "😢 MISSED"
            print(f"\n{'='*60}")
            print(f"   {result_text} Total Reward: {total_reward}")
            print('='*60)

        return total_reward > 0

    except Exception as e:
        print(f"\n❌ Episode failed with error: {e}")
        import traceback
        traceback.print_exc()

        # Check if server is still alive
        if not check_server_health():
            print("\n⚠️  Server appears to be down!")
            print("   Restart the server in the other terminal")

        return False


# ============================================================================
# CELL: Modified evaluate_policies with progress tracking
# ============================================================================

def evaluate_policies(env, num_episodes=50):
    """
    Compare all policies over many episodes using real OpenSpiel.

    Enhanced with:
    - Progress tracking
    - Health checks between policies
    - Graceful error handling
    """
    policies = [
        RandomPolicy(),
        AlwaysStayPolicy(),
        SmartPolicy(),
        LearningPolicy(),
    ]

    print("\n🏆 " + "="*66 + " 🏆")
    print(f"   POLICY SHOWDOWN - {num_episodes} Episodes Each")
    print(f"   Playing against REAL OpenSpiel Catch!")
    print("🏆 " + "="*66 + " 🏆\n")

    results = []

    for policy_idx, policy in enumerate(policies, 1):
        print(f"⚡ Testing {policy.name} ({policy_idx}/{len(policies)})...")

        # Check server health before starting
        if not check_server_health():
            print(f"   ❌ Server not healthy! Skipping remaining policies.")
            break

        successes = 0
        failures = 0

        for ep in range(num_episodes):
            # Show progress every 10 episodes
            if (ep + 1) % 10 == 0:
                print(f"   Progress: {ep + 1}/{num_episodes} episodes...")

            try:
                success = run_episode(env, policy, visualize=False)
                if success:
                    successes += 1
                else:
                    failures += 1

                # If too many failures, check server
                if failures > 3:
                    if not check_server_health():
                        print(f"   ⚠️  Server health check failed after {failures} failures")
                        print(f"   Stopping evaluation. Completed {ep + 1}/{num_episodes} episodes.")
                        break

            except Exception as e:
                print(f"   ⚠️  Episode {ep + 1} failed: {e}")
                failures += 1

                if failures > 3:
                    print(f"   ⚠️  Too many failures, stopping this policy")
                    break

        completed_episodes = successes + failures
        if completed_episodes > 0:
            success_rate = (successes / completed_episodes) * 100
            results.append((policy.name, success_rate, successes, completed_episodes))
            print(f"   ✓ Done! {successes}/{completed_episodes} successful")
        else:
            print(f"   ✗ No episodes completed")

    if not results:
        print("\n❌ No results to display - all policies failed")
        print("   Check server logs in the other terminal for errors")
        return

    print("\n" + "="*70)
    print("   📊 FINAL RESULTS")
    print("="*70 + "\n")

    # Sort by success rate (descending)
    results.sort(key=lambda x: x[1], reverse=True)

    # Award medals to top 3
    medals = ["🥇", "🥈", "🥉", "  "]

    for i, (name, rate, successes, total) in enumerate(results):
        medal = medals[i] if i < len(medals) else "  "
        bar = "█" * int(rate / 2)
        print(f"{medal} {name:25s} [{bar:<50}] {rate:5.1f}% ({successes}/{total})")

    print("\n" + "="*70)


print("\n✅ Modified functions loaded!")
print("   • run_episode() - with timeout protection")
print("   • evaluate_policies() - with progress tracking")
print("   • Helper functions for server health checks\n")
