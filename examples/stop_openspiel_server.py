#!/usr/bin/env python3
"""
Stop OpenSpiel Server

This script finds and kills any running OpenSpiel server on port 8000.

Usage:
    python examples/stop_openspiel_server.py
"""

import subprocess
import sys
import platform

print("=" * 70)
print("   🛑 Stopping OpenSpiel Server")
print("=" * 70)
print()

port = 8000

# Find process using the port
if platform.system() == "Darwin" or platform.system() == "Linux":
    # macOS and Linux
    try:
        # Find the PID using the port
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"Found {len(pids)} process(es) using port {port}:")

            for pid in pids:
                pid = pid.strip()
                if pid:
                    # Get process info
                    try:
                        ps_result = subprocess.run(
                            ["ps", "-p", pid, "-o", "command="],
                            capture_output=True,
                            text=True,
                            timeout=2
                        )
                        print(f"   • PID {pid}: {ps_result.stdout.strip()[:60]}...")
                    except:
                        print(f"   • PID {pid}")

                    # Kill the process
                    try:
                        subprocess.run(["kill", pid], check=True, timeout=5)
                        print(f"   ✅ Killed PID {pid}")
                    except subprocess.CalledProcessError:
                        print(f"   ⚠️  Failed to kill PID {pid}, trying with -9...")
                        try:
                            subprocess.run(["kill", "-9", pid], check=True, timeout=5)
                            print(f"   ✅ Force-killed PID {pid}")
                        except:
                            print(f"   ❌ Could not kill PID {pid}")

            print()
            print("✅ Server stopped successfully")
        else:
            print(f"ℹ️  No process found using port {port}")
            print("   Server may already be stopped")

    except FileNotFoundError:
        print("❌ 'lsof' command not found")
        print("   Please install lsof or manually kill the server process")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("❌ Timeout while trying to find/kill process")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

elif platform.system() == "Windows":
    # Windows
    try:
        # Find the PID using the port
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            timeout=5
        )

        pids = set()
        for line in result.stdout.split('\n'):
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    pids.add(pid)

        if pids:
            print(f"Found {len(pids)} process(es) using port {port}:")

            for pid in pids:
                print(f"   • PID {pid}")
                try:
                    subprocess.run(["taskkill", "/F", "/PID", pid], check=True, timeout=5)
                    print(f"   ✅ Killed PID {pid}")
                except:
                    print(f"   ❌ Could not kill PID {pid}")

            print()
            print("✅ Server stopped successfully")
        else:
            print(f"ℹ️  No process found using port {port}")
            print("   Server may already be stopped")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

else:
    print(f"❌ Unsupported platform: {platform.system()}")
    sys.exit(1)

print()
print("=" * 70)
