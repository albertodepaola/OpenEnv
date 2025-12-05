# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""RestrictedPython-based executor with screenshot capture support.

This module provides a RestrictedPython-based executor backend that supports
the same interface as PyExecutor but uses RestrictedPython for safer code
execution with full Python semantics (including decorator support).

Key features:
- Implements ExecutorBackend interface for uniform environment integration
- Provides helper utilities (format_exc, safe_json_dumps) to user code
- Screenshot capture during code execution
- Policy-based security with configurable import restrictions
"""

from __future__ import annotations

import ast

import json
import logging
import sys
import traceback
from io import StringIO
from typing import Optional

from RestrictedPython import compile_restricted
from RestrictedPython.Guards import safe_builtins, safe_globals
from RestrictedPython.PrintCollector import PrintCollector
from RestrictedPython.transformer import RestrictingNodeTransformer

# Support both standalone and in-repo imports
try:
    from openenv_core.env_server.types import CodeExecResult
except ImportError:
    from core.env_server.types import CodeExecResult

try:
    from coding_env.server.executor_backend import ExecutorBackend
    from coding_env.server.screenshot_utils import capture_screenshot_base64
except ImportError:
    from envs.coding_env.server.executor_backend import ExecutorBackend
    from envs.coding_env.server.screenshot_utils import capture_screenshot_base64

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class PermissiveRestrictingTransformer(RestrictingNodeTransformer):
    """Custom RestrictedPython transformer that allows type annotations.

    This transformer extends the default RestrictingNodeTransformer to support
    type annotations (AnnAssign nodes), which are required for @dataclass and
    other modern Python features. Type annotations are just metadata and don't
    pose a security risk, so it's safe to allow them.

    The transformer also allows TypeAlias and Match statements which are part
    of modern Python syntax.
    """

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.AnnAssign:
        """Allow type annotations (required for @dataclass).

        Examples:
            x: int = 5
            name: str
            items: List[str] = []
        """
        # Visit the target (variable being annotated)
        node.target = self.visit(node.target)

        # Visit the annotation (the type hint)
        node.annotation = self.visit(node.annotation)

        # Visit the value if present
        if node.value:
            node.value = self.visit(node.value)

        return node

    def visit_Match(self, node: ast.Match) -> ast.Match:
        """Allow match statements (Python 3.10+).

        Match/case statements are safe and part of standard control flow.
        """
        node.subject = self.visit(node.subject)
        node.cases = [self.visit(case) for case in node.cases]
        return node

    def visit_match_case(self, node: ast.match_case) -> ast.match_case:
        """Allow match case clauses."""
        node.pattern = self.visit(node.pattern)
        if node.guard:
            node.guard = self.visit(node.guard)
        node.body = [self.visit(stmt) for stmt in node.body]
        return node


class RestrictedPythonExecutor(ExecutorBackend):
    """RestrictedPython-based executor with full Python semantics.

    Unlike smolagents which uses AST interpretation, RestrictedPython compiles
    and executes code with CPython, preserving decorators and other advanced
    language features while maintaining security through policy restrictions.

    The executor maintains a persistent execution context across calls, allowing
    variables and functions defined in one execution to be available in subsequent
    executions (similar to Jupyter notebook behavior).
    """

    def __init__(self, additional_imports: list[str] | None = None):
        """Initialize the RestrictedPython executor.

        Args:
            additional_imports: List of additional module names to allow importing
                              (e.g., ["numpy", "pandas", "matplotlib"])
        """
        if additional_imports is None:
            additional_imports = []

        self._additional_imports = set(additional_imports)
        self._captured_screenshot: Optional[str] = None

        # Create a persistent execution context (globals dict)
        # This allows variables/functions to persist across executions
        self._execution_context = self._create_execution_context()

    def _create_execution_context(self) -> dict:
        """Create the execution context with restricted builtins and helpers.

        Returns:
            Dictionary to use as globals for code execution
        """
        # Import time module to make it available in execution context
        import time

        # Start with safe builtins from RestrictedPython
        context = {
            "__builtins__": self._create_safe_builtins(),
            "__name__": "__main__",
            "__metaclass__": type,
            "_getattr_": getattr,
            "_getitem_": lambda obj, index: obj[index],
            "_getiter_": iter,
            "_iter_unpack_sequence_": iter,
            "__import__": self._create_import_function(),
        }

        # Add helper utilities that user code can call
        context["format_exc"] = traceback.format_exc
        context["safe_json_dumps"] = lambda obj: json.dumps(
            obj, default=lambda o: repr(o)
        )

        # Add time module for screenshot capture (always available)
        context["time"] = time

        return context

    def _create_safe_builtins(self) -> dict:
        """Create a dictionary of safe builtin functions.

        Returns:
            Dictionary of builtin names to functions
        """
        # Start with RestrictedPython's safe_builtins
        builtins = safe_builtins.copy()

        # Add additional safe builtins that are commonly needed
        builtins.update(
            {
                "True": True,
                "False": False,
                "None": None,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "list": list,
                "dict": dict,
                "tuple": tuple,
                "set": set,
                "range": range,
                "len": len,
                "min": min,
                "max": max,
                "sum": sum,
                "abs": abs,
                "round": round,
                "sorted": sorted,
                "enumerate": enumerate,
                "zip": zip,
                "map": map,
                "filter": filter,
                "any": any,
                "all": all,
                "isinstance": isinstance,
                "issubclass": issubclass,
                "hasattr": hasattr,
                "getattr": getattr,
                "setattr": setattr,
                "type": type,
                "dir": dir,
                "help": help,
                "print": print,
                "open": open,
                "Exception": Exception,
                "ValueError": ValueError,
                "TypeError": TypeError,
                "KeyError": KeyError,
                "IndexError": IndexError,
                "AttributeError": AttributeError,
                "RuntimeError": RuntimeError,
                "ImportError": ImportError,
                "StopIteration": StopIteration,
                # Add __import__ to builtins so it's accessible during execution
                "__import__": self._create_import_function(),
            }
        )

        return builtins

    def _create_import_function(self):
        """Create a restricted __import__ function that enforces policy.

        Returns:
            Custom __import__ function with whitelist checking
        """

        def restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
            """Restricted import that only allows whitelisted modules."""
            # Split module name to get top-level package
            top_level_module = name.split(".")[0]

            # Check if module is in allowed list
            if top_level_module not in self._additional_imports:
                raise ImportError(
                    f"Import of '{name}' is not allowed. "
                    f"Allowed modules: {sorted(self._additional_imports)}"
                )

            # Perform the actual import
            return __import__(name, globals, locals, fromlist, level)

        return restricted_import

    def run(
        self,
        code: str,
        *,
        capture_screenshot: bool = False,
        render_timeout: float = 0.5,
    ) -> CodeExecResult:
        """Execute Python code using RestrictedPython.

        Args:
            code: Python code to execute
            capture_screenshot: If True, inject code to capture screenshot during execution
            render_timeout: Time in seconds to wait for UI rendering before screenshot

        Returns:
            CodeExecResult containing stdout, stderr, and exit_code
        """
        # Clear any previous screenshot
        self.clear_screenshot()

        # If screenshot capture is requested, inject screenshot capture code
        if capture_screenshot:
            logger.debug(
                "[RestrictedPythonExecutor.run] Injecting screenshot capture code"
            )
            code = self._inject_screenshot_capture(code, render_timeout)

        # Capture stdout and stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_capture = StringIO()
        stderr_capture = StringIO()
        try:
            # Redirect stdout/stderr
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture

            # Create a PrintCollector for this execution
            # This handles print() statements transformed by RestrictedPython
            # We pass the CLASS, not an instance - RestrictedPython instantiates it
            self._execution_context["_print_"] = PrintCollector

            # Ensure critical runtime support is available each execution
            # (These may get overwritten during exec, so we reset them)
            self._execution_context["_getattr_"] = getattr
            self._execution_context["_getitem_"] = lambda obj, index: obj[index]
            self._execution_context["_getiter_"] = iter
            self._execution_context["_iter_unpack_sequence_"] = iter
            self._execution_context["__import__"] = self._create_import_function()

            # Compile the code using RestrictedPython with custom policy
            # Note: In RestrictedPython 8.x, compile_restricted raises SyntaxError
            # on compilation errors and returns a code object on success
            # We use PermissiveRestrictingTransformer to allow type annotations (@dataclass support)
            try:
                byte_code = compile_restricted(
                    code,
                    filename="<user_code>",
                    mode="exec",
                    policy=PermissiveRestrictingTransformer,
                )
            except SyntaxError as syntax_err:
                # RestrictedPython compilation errors are raised as SyntaxError
                error_msg = str(syntax_err)
                logger.error(f"RestrictedPython compilation error: {error_msg}")
                return CodeExecResult(
                    stdout="", stderr=f"Compilation Error:\n{error_msg}", exit_code=1
                )

            # Execute the compiled code
            exec(byte_code, self._execution_context)

            # Get captured output - retrieve from PrintCollector and sys.stdout
            stdout_from_sys = stdout_capture.getvalue()

            # Get the _print_ which was converted from class to instance during exec
            print_instance = self._execution_context.get("_print")
            stdout_from_print = ""
            if print_instance and hasattr(print_instance, "__call__"):
                try:
                    stdout_from_print = print_instance()
                except:
                    pass

            # Combine both sources of stdout
            stdout = stdout_from_sys
            if stdout_from_print:
                stdout = stdout + stdout_from_print if stdout else stdout_from_print

            stderr = stderr_capture.getvalue()

            # Return successful result
            # Only return exit_code=1 if there's an actual exception/error, not just warnings
            return CodeExecResult(stdout=stdout, stderr=stderr, exit_code=0)

        except Exception as e:
            # Capture the exception and traceback
            stderr_output = stderr_capture.getvalue()
            exception_str = traceback.format_exc()

            logger.exception("RestrictedPython execution raised an exception")

            return CodeExecResult(
                stdout=stdout_capture.getvalue(),
                stderr=stderr_output + "\n" + exception_str,
                exit_code=1,
            )

        finally:
            # Restore stdout/stderr
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    def _inject_screenshot_capture(self, code: str, render_timeout: float) -> str:
        """Inject screenshot capture code at the end of user's code.

        This ensures the screenshot is captured DURING execution, while
        UI elements are still alive, with a timeout to allow rendering.

        Args:
            code: Original user code
            render_timeout: Time to wait for rendering before capture

        Returns:
            Modified code with screenshot capture injected
        """
        # Add screenshot capture tool to execution context
        self._execution_context["internal_capture_screenshot"] = (
            self._create_screenshot_capture_tool()
        )

        injection = f"""
# === Auto-injected screenshot capture code ===
print("[DEBUG] Screenshot capture: Starting auto-injected code")


# Wait for rendering to complete (time module is pre-loaded in context)
print(f"[DEBUG] Screenshot capture: Waiting {render_timeout}s for rendering")
time.sleep({render_timeout})
print("[DEBUG] Screenshot capture: Rendering timeout complete")

# Capture the screenshot
print("[DEBUG] Screenshot capture: Calling internal_capture_screenshot()")
try:
    capture_result = internal_capture_screenshot()

    # Print debug messages from the capture tool
    if isinstance(capture_result, dict):
        for msg in capture_result.get('debug', []):
            print(msg)

        if capture_result.get('success'):
            screenshot = capture_result.get('screenshot')
            if screenshot:
                print(f"[Screenshot captured: {{len(screenshot)}} bytes base64]")
            else:
                print("[Screenshot capture failed: success=True but no screenshot data]")
        else:
            print("[Screenshot capture failed]")
            if 'error' in capture_result:
                print(f"[Screenshot error: {{capture_result['error']}}]")
    else:
        print(f"[DEBUG] Unexpected return type from internal_capture_screenshot: {{type(capture_result)}}")
        print(f"[DEBUG] Value: {{capture_result}}")

except Exception as e:
    print(f"[Screenshot capture exception: {{e}}]")
    print(f"[Screenshot capture traceback:\\n{{format_exc()}}]")
# === End auto-injected code ===
"""
        return code + "\n" + injection

    def _create_screenshot_capture_tool(self):
        """Create the screenshot capture tool for the execution sandbox.

        This function is injected into the user's execution environment and
        captures screenshots from the Xvfb display using the shared screenshot_utils.

        Returns:
            Function that captures screenshots and returns result dict
        """

        def capture_screenshot_internal(display: str = ":99") -> dict:
            """Capture screenshot from Xvfb display during code execution.

            Args:
                display: X11 display to capture (default :99)

            Returns:
                Dictionary with 'screenshot' (base64 string or None) and 'debug' (list of messages)
            """
            # Use the shared screenshot utility
            screenshot_b64, debug_messages = capture_screenshot_base64(
                display=display, verbose=True
            )

            # Store the screenshot in the executor instance
            if screenshot_b64:
                self._captured_screenshot = screenshot_b64

            return {
                "screenshot": screenshot_b64,
                "debug": debug_messages,
                "success": screenshot_b64 is not None,
                "error": None if screenshot_b64 else "Screenshot capture failed",
            }

        return capture_screenshot_internal

    def get_captured_screenshot(self) -> Optional[str]:
        """Get the screenshot captured during the last execution.

        Returns:
            Base64-encoded PNG string, or None if no screenshot was captured
        """
        return self._captured_screenshot

    def clear_screenshot(self) -> None:
        """Clear the stored screenshot."""
        self._captured_screenshot = None
