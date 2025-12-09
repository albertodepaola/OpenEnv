#!/usr/bin/env python3
"""
Debug OpenSpiel Integration

This script helps debug issues with OpenSpiel environments by:
1. Testing server connectivity
2. Inspecting observation format
3. Testing policies one at a time
4. Analyzing the Catch game encoding

Usage:
    # Make sure server is running first!
    python examples/start_openspiel_server.py

    # Then in another terminal:
    python examples/debug_openspiel.py
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

import requests
import time
from envs.openspiel_env import OpenSpielEnv
from envs.openspiel_env.models import OpenSpielAction, OpenSpielObservation

print("=" * 70)
print("   🔍 OpenSpiel Debug Tool")
print("=" * 70)
print()

# Step 1: Check server connectivity
print("📡 Step 1: Checking server connectivity...")
try:
    response = requests.get('http://localhost:8000/health', timeout=2)
    if response.status_code == 200:
        print("✅ Server is healthy\n")
    else:
        print(f"⚠️  Server returned status {response.status_code}\n")
except Exception as e:
    print(f"❌ Cannot connect to server: {e}")
    print("\n💡 Start the server first:")
    print("   python examples/start_openspiel_server.py\n")
    sys.exit(1)

# Step 2: Create client
print("📱 Step 2: Creating client...")
client = OpenSpielEnv(base_url="http://localhost:8000", request_timeout_s=30.0)
print("✅ Client created\n")

# Step 3: Test reset and inspect observation
print("🔄 Step 3: Testing reset and inspecting observation format...")
try:
    result = client.reset()
    obs = result.observation

    print("✅ Reset successful!")
    print(f"\n📋 Observation structure:")
    print(f"   • Type: {type(obs)}")
    print(f"   • info_state length: {len(obs.info_state)}")
    print(f"   • info_state type: {type(obs.info_state)}")
    print(f"   • legal_actions: {obs.legal_actions}")
    print(f"   • game_phase: {obs.game_phase}")
    print(f"   • current_player_id: {obs.current_player_id}")
    print(f"   • done: {obs.done}")
    print(f"   • reward: {obs.reward}")

    print(f"\n📊 info_state values:")
    info = obs.info_state

    # For Catch, this should be a 5x5 grid (25 values)
    if len(info) == 25:
        print(f"   Grid size appears to be 5x5 (25 values)")
        print(f"\n   Visualizing as 5x5 grid:")
        for row in range(5):
            values = [info[row * 5 + col] for col in range(5)]
            formatted = [f"{v:4.1f}" for v in values]
            print(f"   Row {row}: [{' '.join(formatted)}]")

        # Analyze the encoding
        print(f"\n   📈 Value distribution:")
        unique_values = set(info)
        for val in sorted(unique_values):
            count = info.count(val)
            positions = [i for i, v in enumerate(info) if v == val]
            print(f"   • {val:4.1f}: appears {count} time(s) at positions {positions}")
    else:
        print(f"   Unexpected info_state length: {len(info)}")
        print(f"   First 10 values: {info[:10]}")

    print()

except Exception as e:
    print(f"❌ Reset failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 4: Test a single step
print("👟 Step 4: Testing a single step (action=1, STAY)...")
try:
    action = OpenSpielAction(action_id=1, game_name="catch")
    result = client.step(action)
    obs = result.observation

    print("✅ Step successful!")
    print(f"   • Reward: {result.reward}")
    print(f"   • Done: {result.done}")
    print(f"   • New legal_actions: {obs.legal_actions}")
    print()

except Exception as e:
    print(f"❌ Step failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 5: Play a complete episode with verbose logging
print("🎮 Step 5: Playing a complete episode with action logging...")
print("="*70)

try:
    result = client.reset()
    obs = result.observation

    step = 0
    max_steps = 20
    action_names = ["LEFT", "STAY", "RIGHT"]

    print(f"\n🎯 Episode Start")
    print(f"   Initial state:")
    print(f"   • Game phase: {obs.game_phase}")
    print(f"   • Legal actions: {obs.legal_actions}")

    total_reward = 0

    while not obs.done and step < max_steps:
        # Try different actions to see what happens
        if step < 3:
            action_id = 1  # STAY for first few steps
        else:
            action_id = 2  # Then move RIGHT

        print(f"\n   Step {step + 1}: Taking action {action_id} ({action_names[action_id]})")

        action = OpenSpielAction(action_id=action_id, game_name="catch")
        result = client.step(action)
        obs = result.observation

        if result.reward is not None:
            total_reward += result.reward

        print(f"      → Reward: {result.reward}")
        print(f"      → Done: {obs.done}")
        print(f"      → Total reward so far: {total_reward}")

        step += 1
        time.sleep(0.2)

    print(f"\n   Episode ended after {step} steps")
    print(f"   Final reward: {total_reward}")

    if total_reward > 0:
        print(f"   🎉 SUCCESS - Ball was caught!")
    else:
        print(f"   😢 FAILURE - Ball was missed")

    print()

except Exception as e:
    print(f"❌ Episode failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 6: Test rapid requests to see if server can handle load
print("🔥 Step 6: Testing rapid requests (stress test)...")
print("="*70)

success_count = 0
failure_count = 0
timeout_count = 0

for i in range(10):
    try:
        result = client.reset()
        success_count += 1
        print(f"   Reset {i+1}/10: ✓", end="\r")
    except requests.exceptions.Timeout:
        timeout_count += 1
        print(f"   Reset {i+1}/10: ⏱️  TIMEOUT")
    except Exception as e:
        failure_count += 1
        print(f"   Reset {i+1}/10: ✗ {e}")

print(f"\n   Results: {success_count} success, {failure_count} failures, {timeout_count} timeouts")

if timeout_count > 0 or failure_count > 0:
    print(f"\n   ⚠️  Server appears to have issues handling rapid requests")
    print(f"   This could explain the timeout during policy evaluation")
else:
    print(f"\n   ✅ Server handled rapid requests successfully")

print()

# Final summary
print("=" * 70)
print("   📊 Debug Summary")
print("=" * 70)
print()
print("✅ Completed all debug steps!")
print()
print("💡 Next steps:")
print("   1. Review the observation format above")
print("   2. Fix the SmartPolicy to use the correct encoding")
print("   3. Run the tutorial notebook with the modified cells")
print()
print("📝 Observation Format Summary:")
print(f"   • info_state is a flattened {len(obs.info_state)}-element array")
print(f"   • Values appear to represent grid cells")
print(f"   • Use the value distribution above to understand encoding")
print()
