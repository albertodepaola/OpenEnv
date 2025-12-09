# Screenshot Implementation Report

## Executive Summary
- Consolidated the work completed to date to enable reliable screenshot capture within the coding environment.
- Documented dynamic package installation enhancements that unblock GUI- and data-heavy workloads without Docker rebuilds.
- Highlighted the remaining blocker caused by smolagents' AST interpreter and why `@dataclass`-driven workflows fail.
- Proposed a RestrictedPython-based path forward (Option 2) with milestone-driven execution to restore decorator compatibility while preserving sandboxing guarantees.

## Completed Screenshot Capture Work
### Architecture Highlights
- Captures now occur during code execution, ensuring GUI elements remain alive when the capture runs.
- The `capture_screenshot` flag propagates end-to-end: client payload → server executor → injected capture routine.
- A headless X11 stack (Xvfb + ImageMagick) delivers PNG captures that are base64-encoded into the observation stream.

**Diagram: Current Capture Flow**
```
Client (capture_screenshot=True)
    ↓ HTTP payload includes flag
Server PythonCodeActEnv
    ↓ Proxy run(...) with capture injection
Python Executor
    ↓ Injects GUI refresh + `import` capture
Xvfb Virtual Display → ImageMagick → Base64 Screenshot
    ↓
Observation.screenshot returned to client
```

### Key Fixes Delivered
- Authorized `subprocess`, `tempfile`, `matplotlib`, and related modules so injected capture logic can run under smolagents.
- Resolved client payload omission that previously forced `capture_screenshot=False` on the server.
- Added Matplotlib and supporting libraries to the Docker image and ensured entrypoint starts Xvfb.
- Injected GUI refresh logic (Tkinter `update`, Matplotlib `draw/pause`) prior to capture to stabilize render timing.
- Swapped logger calls for `print` statements inside injected code so diagnostics propagate through executor stdout.

## Dynamic Package Installation Enhancements
### Runtime Installation Pipeline
- Startup entrypoint filters requested imports, auto-corrects common typos (e.g., `dataclass` → `dataclasses`), and installs missing PyPI packages.
- Standard-library modules remain on the authorized-import list while skipping unnecessary `pip install` requests.
- Timeout configuration propagates from client to container provisioning so long-running installs can complete safely.

**Diagram: Entrypoint Install Flow**
```
ADDITIONAL_IMPORTS env var
    ↓
Entrypoint Filter & Typo Correction
    ↓               ↘
Stdlib Modules      PyPI Modules
    ↓                ↓
Authorization List  `pip install`
    ↘               ↙
Updated ADDITIONAL_IMPORTS exported
```

## Current Blocker: smolagents Decorator Limitation
- smolagents executes an AST interpreter; decorators like `@dataclass` do not run, leaving classes uninitialized and raising `TypeError: Ball() takes no arguments`.
- Workarounds (manual `__init__`, namedtuples) regress ergonomics and complicate LLM-generated examples.
- Screenshot capture logic is otherwise functional, but real-world notebook/UI users often rely on dataclasses, blocking adoption.

## Option 2 Plan: Adopt RestrictedPython Executor
RestrictedPython offers a production-grade sandbox that executes transformed AST back under CPython semantics, preserving decorator behavior while enforcing security policies.

### Milestone Overview
- **M1 — Restricted Execution Core ("Code executes with RestrictedPython")**
  - Replace or wrap the current executor with a `RestrictedPythonExecutor` class that mirrors `PyExecutor` semantics.
  - Port existing helper tooling (`format_exc`, `safe_json_dumps`) and observation wiring.
  - Validate base scenarios: pure Python snippets, stdout/stderr propagation, error handling parity.

- **M2 — GUI Rendering Compatibility ("UI rendering in virtual buffers works")**
  - Ensure RestrictedPython sandbox allows Tkinter/Matplotlib imports via policy configuration while maintaining security guardrails.
  - Confirm that Xvfb-backed rendering succeeds for representative Tkinter and Matplotlib scripts.
  - Audit policy hooks to confirm subprocess/ImageMagick access remains blocked except via our managed utilities.

- **M3 — Screenshot Pipeline Validation ("Screenshot capture for UI code is stable")**
  - Exercise end-to-end capture flows under RestrictedPython for: Tkinter windows, Matplotlib figures, mixed console/UI workloads.
  - Measure capture latency and reliability with existing render timeout logic; adjust if RestrictedPython introduces overhead.
  - Update documentation to reflect new executor backend and highlight any behavioral differences for users.

- **M4 — Rollout & Observability ("Fallback and monitoring in place")**
  - Introduce an environment toggle (e.g., `EXECUTOR_BACKEND`) to switch between smolagents and RestrictedPython for staged rollout.
  - Instrument metrics/logging around execution failures, policy violations, and screenshot success rates.
  - Document operational playbooks and escalation paths for RestrictedPython policy tuning.

### Implementation Tasks by Milestone
**M1 Tasks**
- Evaluate RestrictedPython release for compatibility; add dependency and container packaging updates.
- Implement executor wrapper, mapping RestrictedPython result objects into `CodeExecResult`.
- Create regression suite ensuring parity with current smolagents-backed behavior (unit + integration tests).

**M2 Tasks**
- Configure RestrictedPython policy to allow safe access to GUI modules while preserving built-in safety checks.
- Validate virtual framebuffer initialization with Xvfb under the new executor.
- Update entrypoint scripts if additional capabilities are needed (e.g., policy resource files).

**M3 Tasks**
- Run existing screenshot examples (`test_screenshot_tool`, `screenshot_capture_example`) under RestrictedPython.
- Capture performance metrics (success rate, runtime) and compare to smolagents baseline.
- Update documentation and example narratives to reflect the new execution path.

**M4 Tasks**
- Wire configuration flag through client/server stack to select executor backend.
- Add structured logging to differentiate RestrictedPython vs smolagents runs and surface policy denials.
- Prepare rollout checklist and launch criteria, including fallback and monitoring dashboards.

### Risk & Mitigation Summary
- **Policy Tightening Risk**: RestrictedPython may block APIs currently allowed. Mitigate via targeted policy auditing during M2.
- **Performance Variability**: Slight AST transformation overhead; track metrics during M3 and adjust render timeout defaults if necessary.
- **Operational Complexity**: New dependency and configuration path; mitigated by staged rollout (M4) and clear documentation.

## Next Steps
1. Secure approval on the Option 2 plan documented above.
2. Sequence implementation starting with M1 tasks; allocate dedicated QA for GUI workloads.
3. Maintain smolagents as fallback until RestrictedPython passes milestones M1–M3 in production-like testing.
