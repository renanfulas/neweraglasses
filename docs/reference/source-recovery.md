# Source Recovery

## Why this exists

The current workspace exposes meaningful runtime behavior through Python bytecode caches and local runtime state, while the repository itself is still light on recoverable source.

This document defines the local recovery posture so we can keep moving without pretending the source-control story is already complete.

## Current state

- Local runtime artifacts live in `.new_era/`
- Python bytecode caches exist under `src/**/__pycache__/` and `tests/**/__pycache__/`
- The Git-tracked repository foundation is now in place, but code recovery remains active work

## Inventory workflow

Use the recovery inventory script to build a factual map of the Python bytecode currently present in the workspace:

```powershell
python tools/pyc_inventory.py --pretty
```

Use the standard-library disassembly helper when you need a reproducible text artifact for a specific module:

```powershell
python tools/pyc_disassemble.py <pyc-path> --output <artifact-path>
```

What the script extracts:
- `.pyc` path
- embedded source filename
- inferred module name
- first source line
- compile timestamp
- source size marker
- top-level imported and referenced names
- nested code object names

## Recovery workflow

Recommended order:

1. Build the inventory.
2. Prioritize public entrypoints and runtime composition modules.
3. Use local disassembly tooling against those modules to reconstruct contracts and behavior.
4. Restore source files back into `src/` and `tests/`.
5. Run the bootstrap and test flow only after the restored source tree is coherent.

The current priority queue lives in `docs/reference/recovery-manifest.md`.

## High-value modules

Based on current runtime signals, start recovery with:

- `new_era.infrastructure.http.app`
- `new_era.application.services.simulation_runtime`
- `new_era.application.use_cases.document_analysis_jobs`
- `new_era.application.use_cases.user_sessions`
- `new_era.application.use_cases.record_lens_feedback`

These modules appear to define the current application surface and async orchestration.

## Local-only tooling

Recovery tools installed under `.new_era/tools/` are local runtime helpers.

They are intentionally not versioned:
- `decompyle3`
- `uncompyle6`
- `pydisasm`

## Important constraint

`decompyle3` currently reports Python `3.12` as unsupported for full source decompilation in this workspace.

That means:
- disassembly is still useful
- exact source reconstruction must be done deliberately
- we should not treat bytecode output as a drop-in substitute for maintained source files
