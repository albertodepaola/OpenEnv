# RestrictedPython Investigation - Critical Findings

## Issue Summary

During implementation of Milestone M1 (RestrictedPython executor backend), we discovered a critical limitation: **RestrictedPython does not support type annotations by default**, which means `@dataclass` decorators will not work as intended.

## The Original Problem

The smolagents executor doesn't support decorators because it uses AST interpretation rather than actual Python execution:

```python
# This FAILS with smolagents
from dataclasses import dataclass

@dataclass
class Point:
    x: int  # Type annotation (AnnAssign)
    y: int  # Type annotation (AnnAssign)
```

Error: `TypeError: Point() takes no arguments` because the `@dataclass` decorator never actually runs.

## The RestrictedPython Limitation

RestrictedPython (version 8.1) rejects type annotations (`AnnAssign` AST nodes) by design:

```
SyntaxError: ('Line 6: AnnAssign statements are not allowed.', 'Line 7: AnnAssign statements are not allowed.')
```

This is a security feature - the `RestrictingNodeTransformer` class doesn't have a `visit_AnnAssign` method, so it rejects any code with type annotations.

## Why This Matters

1. **@dataclass requires type annotations** - The entire point of switching to RestrictedPython was to support @dataclass
2. **Type hints are ubiquitous** - Modern Python code heavily uses type annotations
3. **Security trade-off** - Allowing type annotations shouldn't pose a security risk (they're just metadata)

## Other Issues Discovered

1. **Print function handling** - RestrictedPython transforms `print()` calls to `_print_()` calls, requiring a proper handler
2. **API changes** - RestrictedPython 8.x has different API than older versions (returns code object directly, raises SyntaxError on compilation errors)

## Options Moving Forward

### Option 1: Custom RestrictedPython Policy (Recommended for M1)

Create a custom transformer that inherits from `RestrictingNodeTransformer` and adds support for `AnnAssign`:

```python
from RestrictedPython.transformer import RestrictingNodeTransformer
import ast

class PermissiveRestrictingTransformer(RestrictingNodeTransformer):
    """Custom transformer that allows type annotations."""

    def visit_AnnAssign(self, node):
        """Allow type annotations (required for @dataclass)."""
        # Visit the target and value as normal
        node.target = self.visit(node.target)
        if node.value:
            node.value = self.visit(node.value)
        # Visit the annotation but don't restrict it
        node.annotation = self.visit(node.annotation)
        return node
```

Then use this custom policy:

```python
byte_code = compile_restricted(
    code,
    filename="<user_code>",
    mode="exec",
    policy=PermissiveRestrictingTransformer
)
```

### Option 2: Use exec() with Import Hooks (Faster, Less Secure)

As documented in `SCREENSHOT_IMP_ISSUES.md`, we could use regular `exec()` with import restrictions:

```python
# Simple approach - no AST transformation
allowed_modules = set(["tkinter", "matplotlib", "numpy", ...])

def restricted_import(name, *args, **kwargs):
    if name.split('.')[0] not in allowed_modules:
        raise ImportError(f"Module {name} not allowed")
    return __import__(name, *args, **kwargs)

context = {"__builtins__": {...}, "__import__": restricted_import}
exec(code, context)
```

Pros:
- Full Python semantics (decorators, type annotations, everything works)
- Simpler implementation
- No AST transformation overhead

Cons:
- Less secure than RestrictedPython (no write guards, attribute access restrictions)
- We're already in a Docker container, so layered defense is valuable

### Option 3: Reconsider smolagents (Not Recommended)

Stay with smolagents and document the decorator limitation. This defeats the purpose of M1.

## Recommendation

**Proceed with Option 1**: Implement a custom RestrictedPython policy that allows type annotations.

Rationale:
1. Maintains the security benefits of RestrictedPython
2. Enables @dataclass and other decorator patterns
3. Still better than exec() for defense-in-depth
4. Aligns with the original M1 plan

## Implementation Plan

1. Create `PermissiveRestrictingTransformer` class
2. Update `RestrictedPythonExecutor` to use the custom policy
3. Fix the `_print_` handler setup
4. Test with @dataclass examples
5. Document the custom policy and its rationale

## Timeline Impact

This adds ~1-2 hours to M1 implementation but is necessary to achieve the milestone goals.

## References

- RestrictedPython docs: https://restrictedpython.readthedocs.io/
- Original issue: `SCREENSHOT_IMP_ISSUES.md`
- Milestone plan: `restrictedpython_executor_milestone1.plan.md`
