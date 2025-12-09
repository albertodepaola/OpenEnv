#!/usr/bin/env python3
"""
Start OpenSpiel Server for Tutorial Debugging

This script starts the OpenSpiel server with verbose logging enabled.
Run this in a separate terminal to see real-time server logs.

Usage:
    python examples/start_openspiel_server.py

    # Or with custom game:
    OPENSPIEL_GAME=tic_tac_toe python examples/start_openspiel_server.py
"""

import os
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

print("=" * 70)
print("   🎮 OpenSpiel Server - Debug Mode")
print("=" * 70)

# Configuration
game_name = os.getenv("OPENSPIEL_GAME", "catch")
agent_player = int(os.getenv("OPENSPIEL_AGENT_PLAYER", "0"))
opponent_policy = os.getenv("OPENSPIEL_OPPONENT_POLICY", "random")
port = int(os.getenv("PORT", "8000"))

print(f"\n📋 Configuration:")
print(f"   • Game: {game_name}")
print(f"   • Agent Player: {agent_player}")
print(f"   • Opponent Policy: {opponent_policy}")
print(f"   • Port: {port}")
print()

# Check if open_spiel is installed
try:
    import pyspiel
    print("✅ OpenSpiel is installed")
except ImportError:
    print("⚠️  OpenSpiel not found. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "open_spiel"])
    print("✅ OpenSpiel installed!")

print()
print("=" * 70)
print("   🚀 Starting Server with Verbose Logging")
print("=" * 70)
print()

# Import after ensuring pyspiel is available
from envs.openspiel_env.server.openspiel_environment import OpenSpielEnvironment
from envs.openspiel_env.models import OpenSpielAction, OpenSpielObservation
from core.env_server import create_fastapi_app

# Create environment with logging
print(f"🎮 Creating OpenSpielEnvironment('{game_name}')...")
try:
    env = OpenSpielEnvironment(
        game_name=game_name,
        agent_player=agent_player,
        opponent_policy=opponent_policy,
    )
    print(f"✅ Environment created successfully")
    print(f"   • Number of players: {env.num_players}")
    print(f"   • Turn-based: {env.is_turn_based}")
except Exception as e:
    print(f"❌ Failed to create environment: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Create FastAPI app
print(f"\n📦 Creating FastAPI application...")
app = create_fastapi_app(env, OpenSpielAction, OpenSpielObservation)
print(f"✅ FastAPI app created")

# Add custom logging middleware to track requests
from fastapi import Request
import time

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests with timing."""
    start_time = time.time()

    print(f"\n{'─' * 70}")
    print(f"📥 Incoming Request: {request.method} {request.url.path}")

    # Log request body for POST requests
    if request.method == "POST":
        # Note: We can't read the body here as it's a stream
        # The actual endpoint will handle it
        pass

    # Process the request
    try:
        response = await call_next(request)
        duration = time.time() - start_time

        print(f"📤 Response: {response.status_code} (took {duration:.3f}s)")
        print(f"{'─' * 70}")

        return response
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ Error: {e} (after {duration:.3f}s)")
        print(f"{'─' * 70}")
        import traceback
        traceback.print_exc()
        raise

print(f"\n{'=' * 70}")
print(f"   ✨ Server Ready!")
print(f"{'=' * 70}")
print(f"\n🌐 Server URL: http://localhost:{port}")
print(f"\n📍 Available Endpoints:")
print(f"   • POST http://localhost:{port}/reset")
print(f"   • POST http://localhost:{port}/step")
print(f"   • GET  http://localhost:{port}/state")
print(f"   • GET  http://localhost:{port}/health")
print(f"\n💡 Server logs will appear below as requests come in...")
print(f"\n{'=' * 70}")
print()

# Run the server with uvicorn
if __name__ == "__main__":
    import uvicorn

    # Run with access log enabled
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True,
    )
