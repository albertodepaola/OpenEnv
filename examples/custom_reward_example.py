"""
Example: Customizing coding_env rewards using Transforms.

This demonstrates the RECOMMENDED approach from RFC-001 for reward customization.
"""

from core.env_server.interfaces import Transform
from core.env_server.base_transforms import CompositeTransform
from envs.coding_env.models import CodeObservation
from envs.coding_env.server.python_codeact_env import PythonCodeActEnv


# Example 1: Simple custom transform
class CodeLengthRewardTransform(Transform):
    """Reward shorter code solutions."""

    def __init__(self, target_length: int = 50, bonus: float = 0.5):
        self.target_length = target_length
        self.bonus = bonus

    def __call__(self, observation):
        if not isinstance(observation, CodeObservation):
            return observation

        # Access code from metadata (set by environment)
        code = observation.metadata.get("last_code", "")

        # Reward concise solutions
        if len(code.strip()) <= self.target_length:
            observation.reward = (observation.reward or 0) + self.bonus
            observation.metadata["length_bonus"] = self.bonus

        return observation


# Example 2: Task-specific reward (while keeping data-independence)
class CorrectOutputRewardTransform(Transform):
    """Reward based on stdout matching expected pattern."""

    def __init__(self, expected_output_pattern: str = None, reward: float = 1.0):
        self.pattern = expected_output_pattern
        self.reward_value = reward

    def __call__(self, observation):
        if not isinstance(observation, CodeObservation):
            return observation

        # Check stdout (already in observation)
        if self.pattern and self.pattern in observation.stdout:
            observation.reward = self.reward_value
            observation.metadata["output_match"] = True
        else:
            observation.reward = 0.0
            observation.metadata["output_match"] = False

        return observation


# Example 3: Multi-criteria composite transform
class ComprehensiveCodeRewardTransform(CompositeTransform):
    """Combines multiple reward criteria."""

    def __init__(self):
        transforms = [
            # 1. Safety (no dangerous imports)
            CodeSafetyTransform(penalty=-2.0),

            # 2. Execution success (exit code 0)
            ExecutionSuccessTransform(success_bonus=0.5),

            # 3. Code efficiency (reward short code)
            CodeLengthRewardTransform(target_length=100, bonus=0.3),
        ]
        super().__init__(transforms)


class CodeSafetyTransform(Transform):
    """Penalize dangerous code patterns."""

    def __init__(self, penalty: float = -1.0):
        self.penalty = penalty

    def __call__(self, observation):
        if not isinstance(observation, CodeObservation):
            return observation

        code = observation.metadata.get("last_code", "")
        dangerous_patterns = [r"import\s+os", r"subprocess", r"eval\(", r"exec\("]

        for pattern in dangerous_patterns:
            if re.search(pattern, code):
                observation.reward = self.penalty
                observation.metadata["safety_violation"] = pattern
                return observation

        return observation


class ExecutionSuccessTransform(Transform):
    """Reward successful execution (exit_code=0)."""

    def __init__(self, success_bonus: float = 1.0):
        self.success_bonus = success_bonus

    def __call__(self, observation):
        if not isinstance(observation, CodeObservation):
            return observation

        if observation.exit_code == 0:
            observation.reward = (observation.reward or 0) + self.success_bonus
        else:
            # Penalize errors
            observation.reward = (observation.reward or 0) - 0.5

        return observation


# ============================================================================
# Usage Examples
# ============================================================================

def example_1_simple_custom_transform():
    """Use a single custom transform."""
    import re

    # Create environment with custom transform
    env = PythonCodeActEnv()
    env.transform = CodeLengthRewardTransform(target_length=50, bonus=0.5)

    obs = env.reset()

    from envs.coding_env.models import CodeAction
    action = CodeAction(code="print('Hello')")
    obs = env.step(action)

    print(f"Reward: {obs.reward}")
    print(f"Metadata: {obs.metadata}")


def example_2_composite_transform():
    """Compose multiple transforms for complex reward shaping."""
    import re

    # Create multi-criteria reward function
    composite_transform = CompositeTransform([
        ExecutionSuccessTransform(success_bonus=1.0),
        CodeLengthRewardTransform(target_length=100, bonus=0.3),
        CodeSafetyTransform(penalty=-2.0),
    ])

    env = PythonCodeActEnv()
    env.transform = composite_transform

    obs = env.reset()

    from envs.coding_env.models import CodeAction
    # Good code: short, safe, works
    action = CodeAction(code="result = 2 + 2\nprint(result)")
    obs = env.step(action)
    print(f"Good code reward: {obs.reward}")  # ~1.3 (success + length bonus)

    # Bad code: dangerous
    action = CodeAction(code="import os; os.system('rm -rf /')")
    obs = env.step(action)
    print(f"Dangerous code reward: {obs.reward}")  # -2.0


def example_3_custom_environment_with_default_transform():
    """Override the environment's default transform at initialization."""

    # Option A: Modify transform after creation
    env = PythonCodeActEnv()
    env.transform = ComprehensiveCodeRewardTransform()

    # Option B: Subclass to change default (see Alternative #2 below)


def example_4_dynamic_reward_based_on_task():
    """
    For task-dependent rewards, you can create transforms with task context.

    Note: RFC-001 says rewards should be data-independent, but you can encode
    expected behaviors as patterns without tying to specific dataset instances.
    """
    import re

    # Create a transform that checks for expected output pattern
    # (task-agnostic pattern matching, not tied to specific dataset)
    transform = CorrectOutputRewardTransform(
        expected_output_pattern="42",  # Expected answer
        reward=1.0
    )

    env = PythonCodeActEnv()
    env.transform = transform

    obs = env.reset()

    from envs.coding_env.models import CodeAction
    action = CodeAction(code="print(40 + 2)")
    obs = env.step(action)
    print(f"Correct output reward: {obs.reward}")  # 1.0


if __name__ == "__main__":
    print("=" * 70)
    print("Example 1: Simple Custom Transform")
    print("=" * 70)
    example_1_simple_custom_transform()

    print("\n" + "=" * 70)
    print("Example 2: Composite Transform (Multi-Criteria)")
    print("=" * 70)
    example_2_composite_transform()

    print("\n" + "=" * 70)
    print("Example 4: Dynamic Reward (Pattern Matching)")
    print("=" * 70)
    example_4_dynamic_reward_based_on_task()
