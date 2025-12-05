#!/usr/bin/env python3
"""Test RestrictedPython executor backend with various code examples.

This script tests the RestrictedPythonExecutor class with various code examples
to verify it provides the same CodeExecResult semantics as the PyExecutor.

It specifically tests:
1. Basic execution (print statements, calculations)
2. Exception handling and traceback formatting
3. Return values and JSON serialization
4. @dataclass decorator support (the main reason for switching from smolagents)
5. Persistent execution context (variables across calls)
"""

import sys
from pathlib import Path

# Add src to path for in-repo imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from envs.coding_env.server.restricted_python_executor import RestrictedPythonExecutor


def test_basic_execution():
    """Test basic print statements and calculations."""
    print("=" * 60)
    print("TEST 1: Basic Execution (Print and Calculations)")
    print("=" * 60)

    executor = RestrictedPythonExecutor(additional_imports=[])

    code = """
print("Hello from RestrictedPython!")
x = 10
y = 20
result = x + y
print(f"The sum of {x} and {y} is {result}")
"""

    result = executor.run(code)

    print(f"Exit Code: {result.exit_code}")
    print(f"Stdout:\n{result.stdout}")
    print(f"Stderr:\n{result.stderr}")

    assert result.exit_code == 0, "Expected exit code 0"
    assert "Hello from RestrictedPython!" in result.stdout
    assert "The sum of 10 and 20 is 30" in result.stdout

    print("✅ Test 1 PASSED\n")


def test_exception_handling():
    """Test that exceptions are properly caught and formatted."""
    print("=" * 60)
    print("TEST 2: Exception Handling")
    print("=" * 60)

    executor = RestrictedPythonExecutor(additional_imports=[])

    code = """
print("About to raise an exception...")
x = 1 / 0  # ZeroDivisionError
"""

    result = executor.run(code)

    print(f"Exit Code: {result.exit_code}")
    print(f"Stdout:\n{result.stdout}")
    print(f"Stderr:\n{result.stderr}")

    assert result.exit_code == 1, "Expected exit code 1 for exception"
    assert "ZeroDivisionError" in result.stderr
    # Note: With RestrictedPython, the exception occurs during execution
    # so the print statement before it may or may not complete
    # We just verify the exception is in stderr

    print("✅ Test 2 PASSED\n")


def test_dataclass_support():
    """Test @dataclass decorator support (the main reason for using RestrictedPython)."""
    print("=" * 60)
    print("TEST 3: @dataclass Decorator Support")
    print("=" * 60)

    executor = RestrictedPythonExecutor(additional_imports=["dataclasses"])

    code = """
from dataclasses import dataclass

@dataclass
class Point:
    x: int
    y: int

    def distance_from_origin(self):
        return (self.x ** 2 + self.y ** 2) ** 0.5

# Create instances using the auto-generated __init__
p1 = Point(3, 4)
p2 = Point(5, 12)

print(f"p1: {p1}")
print(f"p1.x: {p1.x}")
print(f"p1.y: {p1.y}")
print(f"p1.distance_from_origin(): {p1.distance_from_origin()}")

print(f"p2: {p2}")
print(f"p2.distance_from_origin(): {p2.distance_from_origin()}")
"""

    result = executor.run(code)

    print(f"Exit Code: {result.exit_code}")
    print(f"Stdout:\n{result.stdout}")
    print(f"Stderr:\n{result.stderr}")

    assert result.exit_code == 0, "Expected exit code 0"
    assert "p1: Point(x=3, y=4)" in result.stdout
    assert "p1.x: 3" in result.stdout
    assert "p1.y: 4" in result.stdout
    assert "p1.distance_from_origin(): 5.0" in result.stdout
    assert "p2: Point(x=5, y=12)" in result.stdout
    assert "p2.distance_from_origin(): 13.0" in result.stdout

    print("✅ Test 3 PASSED - @dataclass WORKS! 🎉\n")


def test_persistent_context():
    """Test that variables persist across multiple executor runs."""
    print("=" * 60)
    print("TEST 4: Persistent Execution Context")
    print("=" * 60)

    executor = RestrictedPythonExecutor(additional_imports=[])

    # First execution: define variables
    code1 = """
x = 10
y = 20
print(f"First execution: x={x}, y={y}")
"""
    result1 = executor.run(code1)
    print("--- First Execution ---")
    print(f"Stdout: {result1.stdout}")
    assert result1.exit_code == 0
    assert "First execution: x=10, y=20" in result1.stdout

    # Second execution: use variables from first execution
    code2 = """
z = x + y
print(f"Second execution: z={z} (from x={x} + y={y})")
"""
    result2 = executor.run(code2)
    print("\n--- Second Execution ---")
    print(f"Stdout: {result2.stdout}")
    assert result2.exit_code == 0
    assert "Second execution: z=30" in result2.stdout

    # Third execution: define a function
    code3 = """
def multiply(a, b):
    return a * b

result = multiply(x, y)
print(f"Third execution: multiply({x}, {y}) = {result}")
"""
    result3 = executor.run(code3)
    print("\n--- Third Execution ---")
    print(f"Stdout: {result3.stdout}")
    assert result3.exit_code == 0
    assert "Third execution: multiply(10, 20) = 200" in result3.stdout

    print("✅ Test 4 PASSED\n")


def test_import_restrictions():
    """Test that imports are restricted by policy."""
    print("=" * 60)
    print("TEST 5: Import Restrictions")
    print("=" * 60)

    executor = RestrictedPythonExecutor(additional_imports=["math"])

    # Allowed import
    code1 = """
import math
print(f"math.pi = {math.pi}")
"""
    result1 = executor.run(code1)
    print("--- Allowed Import (math) ---")
    print(f"Exit Code: {result1.exit_code}")
    print(f"Stdout: {result1.stdout}")
    assert result1.exit_code == 0
    assert "math.pi = 3.14" in result1.stdout

    # Disallowed import
    code2 = """
import os
print(os.getcwd())
"""
    result2 = executor.run(code2)
    print("\n--- Disallowed Import (os) ---")
    print(f"Exit Code: {result2.exit_code}")
    print(f"Stderr: {result2.stderr}")
    assert result2.exit_code == 1
    assert "ImportError" in result2.stderr
    assert "not allowed" in result2.stderr

    print("✅ Test 5 PASSED\n")


def test_helper_utilities():
    """Test that helper utilities (format_exc, safe_json_dumps) are available."""
    print("=" * 60)
    print("TEST 6: Helper Utilities")
    print("=" * 60)

    executor = RestrictedPythonExecutor(additional_imports=[])

    code = """
# Test safe_json_dumps
data = {"name": "Test", "value": 42}
json_str = safe_json_dumps(data)
print(f"JSON: {json_str}")

# Test format_exc (in exception context)
try:
    raise ValueError("Test exception")
except:
    exc_str = format_exc()
    print(f"Exception captured: {len(exc_str)} bytes")
    print("Exception contains 'ValueError':", "ValueError" in exc_str)
"""

    result = executor.run(code)

    print(f"Exit Code: {result.exit_code}")
    print(f"Stdout:\n{result.stdout}")
    print(f"Stderr:\n{result.stderr}")

    assert result.exit_code == 0
    assert '"name": "Test"' in result.stdout
    assert "Exception captured:" in result.stdout
    assert "Exception contains 'ValueError': True" in result.stdout

    print("✅ Test 6 PASSED\n")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("TESTING RestrictedPython Executor")
    print("=" * 60 + "\n")

    tests = [
        test_basic_execution,
        test_exception_handling,
        test_dataclass_support,
        test_persistent_context,
        test_import_restrictions,
        test_helper_utilities,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ Test FAILED: {e}\n")
            failed += 1
        except Exception as e:
            print(f"❌ Test ERROR: {e}\n")
            import traceback

            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"TEST SUMMARY: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")

    if failed > 0:
        sys.exit(1)
    else:
        print("🎉 ALL TESTS PASSED!")


if __name__ == "__main__":
    main()
