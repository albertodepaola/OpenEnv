# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for SubprocessExecutor backend.

These tests verify that the SubprocessExecutor produces correct results
and matches the behavior expected from any executor backend.

Note: These tests run the subprocess executor directly on the host machine.
For full security testing, use the Docker integration tests.
"""

import os
import sys
from pathlib import Path

import pytest

# Add the project root and src to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "envs"))

from coding_env.server.subprocess_executor import (
    ExecutionConfig,
    ResourceLimits,
    SubprocessExecutor,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def executor():
    """Create a fresh SubprocessExecutor for each test."""
    return SubprocessExecutor()


@pytest.fixture
def executor_strict():
    """Create a SubprocessExecutor with stricter resource limits."""
    config = ExecutionConfig(
        limits=ResourceLimits(
            cpu_seconds=5,
            memory_bytes=128 * 1024 * 1024,  # 128MB
            max_processes=0,
            max_file_size=1 * 1024 * 1024,  # 1MB
            max_open_files=16,
        ),
        timeout=10,
    )
    return SubprocessExecutor(config=config)


# ============================================================================
# Basic Execution Tests
# ============================================================================


def test_simple_print(executor):
    """Test that simple print statements work."""
    result = executor.run("print('Hello, World!')")

    assert result.exit_code == 0
    assert "Hello, World!" in result.stdout
    assert result.stderr == ""


def test_simple_calculation(executor):
    """Test that calculations work correctly."""
    result = executor.run("x = 5 + 3\nprint(f'Result: {x}')")

    assert result.exit_code == 0
    assert "Result: 8" in result.stdout


def test_multiline_code(executor):
    """Test that multi-line code executes correctly."""
    code = """
for i in range(1, 4):
    print(f'{i} squared is {i**2}')
"""
    result = executor.run(code)

    assert result.exit_code == 0
    assert "1 squared is 1" in result.stdout
    assert "2 squared is 4" in result.stdout
    assert "3 squared is 9" in result.stdout


def test_import_math(executor):
    """Test that importing standard library modules works."""
    result = executor.run("import math\nprint(f'Pi: {math.pi:.4f}')")

    assert result.exit_code == 0
    assert "Pi: 3.1416" in result.stdout


def test_function_definition(executor):
    """Test that function definitions and calls work."""
    code = """
def greet(name):
    return f'Hello, {name}!'

print(greet('World'))
"""
    result = executor.run(code)

    assert result.exit_code == 0
    assert "Hello, World!" in result.stdout


def test_class_definition(executor):
    """Test that class definitions work (unlike RestrictedPython)."""
    code = """
class Counter:
    def __init__(self, start=0):
        self.value = start

    def increment(self):
        self.value += 1
        return self.value

counter = Counter()
print(counter.increment())
print(counter.increment())
"""
    result = executor.run(code)

    assert result.exit_code == 0
    assert "1" in result.stdout
    assert "2" in result.stdout


def test_dataclass_definition(executor):
    """Test that @dataclass decorators work (a key advantage over RestrictedPython)."""
    code = """
from dataclasses import dataclass

@dataclass
class Point:
    x: float
    y: float

p = Point(3.0, 4.0)
print(f'Point: ({p.x}, {p.y})')
"""
    result = executor.run(code)

    assert result.exit_code == 0
    assert "Point: (3.0, 4.0)" in result.stdout


def test_list_comprehension(executor):
    """Test that list comprehensions work."""
    code = "squares = [x**2 for x in range(5)]\nprint(squares)"
    result = executor.run(code)

    assert result.exit_code == 0
    assert "[0, 1, 4, 9, 16]" in result.stdout


def test_generator_expression(executor):
    """Test that generator expressions work."""
    code = "total = sum(x**2 for x in range(5))\nprint(total)"
    result = executor.run(code)

    assert result.exit_code == 0
    assert "30" in result.stdout


# ============================================================================
# Error Handling Tests
# ============================================================================


def test_division_by_zero(executor):
    """Test that division by zero returns error."""
    result = executor.run("x = 1 / 0")

    assert result.exit_code == 1
    assert "ZeroDivisionError" in result.stderr


def test_undefined_variable(executor):
    """Test that undefined variable returns error."""
    result = executor.run("print(undefined_variable)")

    assert result.exit_code == 1
    assert "NameError" in result.stderr


def test_syntax_error(executor):
    """Test that syntax errors are caught."""
    result = executor.run("print('unclosed")

    assert result.exit_code == 1
    assert "SyntaxError" in result.stderr


def test_type_error(executor):
    """Test that type errors are caught."""
    result = executor.run("'hello' + 5")

    assert result.exit_code == 1
    assert "TypeError" in result.stderr


def test_attribute_error(executor):
    """Test that attribute errors are caught."""
    result = executor.run("x = 5\nx.nonexistent")

    assert result.exit_code == 1
    assert "AttributeError" in result.stderr


# ============================================================================
# Resource Limit Tests
# ============================================================================


def test_timeout_enforcement(executor_strict):
    """Test that timeout is enforced."""
    # This should timeout
    code = """
import time
while True:
    time.sleep(0.1)
"""
    result = executor_strict.run(code)

    assert result.exit_code != 0
    # Should indicate timeout occurred
    assert "timeout" in result.stderr.lower() or result.exit_code == 124


def test_memory_limit_respected():
    """Test that memory limits prevent excessive allocation.

    Note: RLIMIT_AS (address space limit) works differently on different platforms.
    On macOS, this limit is often not enforced. This test is skipped on non-Linux
    platforms since the subprocess executor with resource limits is designed
    to run in Linux containers.
    """
    if sys.platform != "linux":
        pytest.skip("Memory limits via RLIMIT_AS only work reliably on Linux")

    # Use very strict memory limit
    config = ExecutionConfig(
        limits=ResourceLimits(
            memory_bytes=64 * 1024 * 1024,  # 64MB
        ),
        timeout=10,
    )
    executor = SubprocessExecutor(config=config)

    # Try to allocate a lot of memory
    code = """
# Try to allocate ~500MB
data = [0] * (100 * 1024 * 1024)
print('Allocated successfully')
"""
    result = executor.run(code)

    # Should either fail with MemoryError or be killed
    assert result.exit_code != 0 or "MemoryError" in result.stderr


# ============================================================================
# Statelessness Tests (each run is independent)
# ============================================================================


def test_no_state_persistence(executor):
    """Test that variables don't persist between runs."""
    # Define a variable
    result1 = executor.run("my_var = 42\nprint(my_var)")
    assert result1.exit_code == 0
    assert "42" in result1.stdout

    # Try to use it in a new run - should fail
    result2 = executor.run("print(my_var)")
    assert result2.exit_code == 1
    assert "NameError" in result2.stderr


def test_no_function_persistence(executor):
    """Test that functions don't persist between runs."""
    # Define a function
    result1 = executor.run("def my_func(): return 'hello'\nprint(my_func())")
    assert result1.exit_code == 0
    assert "hello" in result1.stdout

    # Try to use it in a new run - should fail
    result2 = executor.run("print(my_func())")
    assert result2.exit_code == 1
    assert "NameError" in result2.stderr


# ============================================================================
# Screenshot Capture Tests
# ============================================================================


def test_screenshot_flag_accepted(executor):
    """Test that capture_screenshot flag is accepted."""
    result = executor.run("print('test')", capture_screenshot=True)

    # Should still execute successfully
    assert result.exit_code == 0
    assert "test" in result.stdout


def test_screenshot_cleared_between_runs(executor):
    """Test that screenshots are cleared between runs."""
    # First run without screenshot
    executor.run("print('no screenshot')")
    assert executor.get_captured_screenshot() is None

    # Run with screenshot flag (may not capture if no display)
    executor.run("print('with screenshot')", capture_screenshot=True)

    # Clear and verify
    executor.clear_screenshot()
    assert executor.get_captured_screenshot() is None


# ============================================================================
# Environment Variable Tests
# ============================================================================


def test_minimal_environment(executor):
    """Test that subprocess has minimal environment variables."""
    code = """
import os
# Print some common sensitive env vars that should NOT be present
for var in ['API_KEY', 'SECRET', 'PASSWORD', 'AWS_ACCESS_KEY_ID']:
    val = os.environ.get(var)
    if val:
        print(f'{var}=PRESENT')
    else:
        print(f'{var}=NOT_PRESENT')
"""
    result = executor.run(code)

    assert result.exit_code == 0
    # All should be NOT_PRESENT
    assert "API_KEY=NOT_PRESENT" in result.stdout
    assert "SECRET=NOT_PRESENT" in result.stdout
