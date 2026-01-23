# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Parameterized tests that run against multiple executor backends.

These tests verify that all executor backends produce consistent results
for basic operations. Backend-specific behaviors are tested in their
respective test files.

Run with:
    PYTHONPATH=src:envs uv run pytest tests/envs/test_executor_backends.py -v
"""

import os
import sys
from pathlib import Path

import pytest

# Add the project root and src to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "envs"))

from coding_env.models import CodeAction
from coding_env.server.python_codeact_env import PythonCodeActEnv


# ============================================================================
# Fixtures - Parameterized by backend
# ============================================================================


# Note: subprocess backend is stateless (no variable persistence)
# So we separate tests into "common" (work for all) and "stateful" (only smolagents)
BACKENDS_ALL = ["smolagents", "subprocess"]
BACKENDS_STATEFUL = ["smolagents"]  # Only smolagents persists state between steps


@pytest.fixture(params=BACKENDS_ALL)
def env_any_backend(request):
    """Create PythonCodeActEnv with parameterized backend."""
    backend = request.param
    env = PythonCodeActEnv(executor_backend=backend)
    env.reset()
    return env, backend


@pytest.fixture(params=BACKENDS_STATEFUL)
def env_stateful_backend(request):
    """Create PythonCodeActEnv with stateful backend (smolagents only)."""
    backend = request.param
    env = PythonCodeActEnv(executor_backend=backend)
    env.reset()
    return env, backend


# ============================================================================
# Common Tests - Run on ALL backends
# ============================================================================


class TestAllBackends:
    """Tests that must pass on all backends."""

    def test_simple_print(self, env_any_backend):
        """Test that simple print works on all backends."""
        env, backend = env_any_backend

        action = CodeAction(code="print('Hello, World!')")
        obs = env.step(action)

        assert obs.exit_code == 0, f"Backend {backend}: print should succeed"
        assert "Hello, World!" in obs.stdout

    def test_simple_calculation(self, env_any_backend):
        """Test that calculations work on all backends."""
        env, backend = env_any_backend

        action = CodeAction(code="x = 5 + 3\nprint(f'Result: {x}')")
        obs = env.step(action)

        assert obs.exit_code == 0, f"Backend {backend}: calculation should succeed"
        assert "Result: 8" in obs.stdout

    def test_import_math(self, env_any_backend):
        """Test that math import works on all backends."""
        env, backend = env_any_backend

        action = CodeAction(code="import math\nprint(f'Pi: {math.pi:.4f}')")
        obs = env.step(action)

        assert obs.exit_code == 0, f"Backend {backend}: math import should succeed"
        assert "Pi: 3.1416" in obs.stdout

    def test_multiline_code(self, env_any_backend):
        """Test that multiline code works on all backends."""
        env, backend = env_any_backend

        code = """
for i in range(1, 4):
    print(f'{i} squared is {i**2}')
"""
        action = CodeAction(code=code)
        obs = env.step(action)

        assert obs.exit_code == 0, f"Backend {backend}: multiline should succeed"
        assert "1 squared is 1" in obs.stdout
        assert "2 squared is 4" in obs.stdout
        assert "3 squared is 9" in obs.stdout

    def test_division_by_zero(self, env_any_backend):
        """Test that division by zero is caught on all backends."""
        env, backend = env_any_backend

        action = CodeAction(code="x = 1 / 0")
        obs = env.step(action)

        assert obs.exit_code == 1, f"Backend {backend}: division by zero should fail"
        assert "ZeroDivisionError" in obs.stderr or obs.stderr != ""

    def test_undefined_variable(self, env_any_backend):
        """Test that undefined variable is caught on all backends."""
        env, backend = env_any_backend

        action = CodeAction(code="print(undefined_var)")
        obs = env.step(action)

        assert obs.exit_code == 1, f"Backend {backend}: undefined var should fail"

    def test_syntax_error(self, env_any_backend):
        """Test that syntax error is caught on all backends."""
        env, backend = env_any_backend

        action = CodeAction(code="print('unclosed")
        obs = env.step(action)

        assert obs.exit_code == 1, f"Backend {backend}: syntax error should fail"

    def test_function_definition_and_call(self, env_any_backend):
        """Test function definition in same step works on all backends."""
        env, backend = env_any_backend

        code = """
def greet(name):
    return f'Hello, {name}!'

print(greet('World'))
"""
        action = CodeAction(code=code)
        obs = env.step(action)

        assert obs.exit_code == 0, f"Backend {backend}: function def should succeed"
        assert "Hello, World!" in obs.stdout

    def test_list_comprehension(self, env_any_backend):
        """Test that list comprehensions work on all backends."""
        env, backend = env_any_backend

        action = CodeAction(code="squares = [x**2 for x in range(5)]\nprint(squares)")
        obs = env.step(action)

        assert obs.exit_code == 0, f"Backend {backend}: list comp should succeed"
        assert "[0, 1, 4, 9, 16]" in obs.stdout

    def test_reward_is_computed(self, env_any_backend):
        """Test that reward is computed on all backends."""
        env, backend = env_any_backend

        action = CodeAction(code="x = 5")
        obs = env.step(action)

        assert obs.reward is not None, f"Backend {backend}: reward should be computed"
        assert isinstance(obs.reward, (int, float))

    def test_metadata_includes_last_code(self, env_any_backend):
        """Test that metadata includes last_code on all backends."""
        env, backend = env_any_backend

        code = "print('test')"
        action = CodeAction(code=code)
        obs = env.step(action)

        assert (
            "last_code" in obs.metadata
        ), f"Backend {backend}: metadata should have last_code"
        assert obs.metadata["last_code"] == code

    def test_step_count_increments(self, env_any_backend):
        """Test that step count increments on all backends."""
        env, backend = env_any_backend

        initial_count = env.state.step_count
        env.step(CodeAction(code="x = 1"))
        assert (
            env.state.step_count == initial_count + 1
        ), f"Backend {backend}: step count should increment"

    def test_reset_resets_step_count(self, env_any_backend):
        """Test that reset resets step count on all backends."""
        env, backend = env_any_backend

        env.step(CodeAction(code="x = 1"))
        env.step(CodeAction(code="y = 2"))
        assert env.state.step_count > 0

        env.reset()
        assert (
            env.state.step_count == 0
        ), f"Backend {backend}: step count should reset to 0"

    def test_reset_changes_episode_id(self, env_any_backend):
        """Test that reset generates new episode ID on all backends."""
        env, backend = env_any_backend

        episode_id_1 = env.state.episode_id
        env.step(CodeAction(code="x = 1"))
        env.reset()
        episode_id_2 = env.state.episode_id

        assert (
            episode_id_1 != episode_id_2
        ), f"Backend {backend}: episode ID should change on reset"


# ============================================================================
# Stateful Tests - Only run on backends that persist state
# ============================================================================


class TestStatefulBackends:
    """Tests that only work on stateful backends (smolagents)."""

    def test_variable_persists_between_steps(self, env_stateful_backend):
        """Test that variables persist between steps for stateful backends."""
        env, backend = env_stateful_backend

        # Define variable
        obs1 = env.step(CodeAction(code="my_var = 42"))
        assert obs1.exit_code == 0

        # Use variable in next step
        obs2 = env.step(CodeAction(code="print(my_var)"))
        assert obs2.exit_code == 0, f"Backend {backend}: variable should persist"
        assert "42" in obs2.stdout

    def test_function_persists_between_steps(self, env_stateful_backend):
        """Test that functions persist between steps for stateful backends."""
        env, backend = env_stateful_backend

        # Define function
        obs1 = env.step(
            CodeAction(
                code="def my_func():\n    return 'hello from function'\n"
            )
        )
        assert obs1.exit_code == 0

        # Call function in next step
        obs2 = env.step(CodeAction(code="print(my_func())"))
        assert obs2.exit_code == 0, f"Backend {backend}: function should persist"
        assert "hello from function" in obs2.stdout

    def test_import_persists_between_steps(self, env_stateful_backend):
        """Test that imports persist between steps for stateful backends."""
        env, backend = env_stateful_backend

        # Import module with alias
        obs1 = env.step(CodeAction(code="import math as m"))
        assert obs1.exit_code == 0

        # Use alias in next step
        obs2 = env.step(CodeAction(code="print(f'Pi: {m.pi:.4f}')"))
        assert obs2.exit_code == 0, f"Backend {backend}: import should persist"
        assert "Pi: 3.1416" in obs2.stdout

    def test_reset_clears_variables(self, env_stateful_backend):
        """Test that reset clears variables for stateful backends."""
        env, backend = env_stateful_backend

        # Define variable
        env.step(CodeAction(code="my_var = 42"))

        # Reset
        env.reset()

        # Variable should be gone
        obs = env.step(CodeAction(code="print(my_var)"))
        assert (
            obs.exit_code == 1
        ), f"Backend {backend}: variable should be cleared after reset"

    def test_reset_clears_functions(self, env_stateful_backend):
        """Test that reset clears functions for stateful backends."""
        env, backend = env_stateful_backend

        # Define function
        env.step(CodeAction(code="def my_func(): return 42"))

        # Reset
        env.reset()

        # Function should be gone
        obs = env.step(CodeAction(code="print(my_func())"))
        assert (
            obs.exit_code == 1
        ), f"Backend {backend}: function should be cleared after reset"


# ============================================================================
# Dangerous Pattern Tests - All backends should handle these consistently
# ============================================================================


@pytest.mark.parametrize(
    "dangerous_code",
    [
        "import os",
        "import subprocess",
        "eval('1+1')",
        "exec('x=1')",
        "__import__('os')",
        "open('file.txt')",
    ],
)
def test_dangerous_patterns_penalized(dangerous_code):
    """Test that dangerous patterns get negative rewards on all backends."""
    for backend in BACKENDS_ALL:
        env = PythonCodeActEnv(executor_backend=backend)
        env.reset()

        action = CodeAction(code=dangerous_code)
        obs = env.step(action)

        assert obs.reward is not None, f"Backend {backend}: reward should be computed"
        assert obs.reward < 0, (
            f"Backend {backend}: dangerous code '{dangerous_code}' "
            f"should get negative reward, got {obs.reward}"
        )
