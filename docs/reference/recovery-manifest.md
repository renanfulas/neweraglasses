# Recovery Manifest

## Purpose

This manifest turns source recovery into an explicit, repeatable queue.

Use it together with:
- `python tools/pyc_inventory.py --pretty`
- `python tools/pyc_disassemble.py <pyc-path> --output <artifact-path>`

## Priority queue

1. `new_era.infrastructure.http.app`
   - Why: defines the external application surface, request models, routes, and wiring
   - Expected artifact: `docs/reference/recovery/http-app.dis.txt`
   - Status: generated

2. `new_era.application.services.simulation_runtime`
   - Why: composes stores, adapters, workers, services, and runtime defaults
   - Expected artifact: `docs/reference/recovery/simulation-runtime.dis.txt`
   - Status: generated

3. `new_era.application.use_cases.document_analysis_jobs`
   - Why: owns async execution semantics, job state, payload flow, timeout behavior, and result linkage
   - Expected artifact: `docs/reference/recovery/document-analysis-jobs.dis.txt`
   - Status: generated

4. `new_era.application.use_cases.user_sessions`
   - Why: confirms session ownership, pagination shape, and user isolation assumptions
   - Expected artifact: `docs/reference/recovery/user-sessions.dis.txt`
   - Status: generated

5. `new_era.application.use_cases.record_lens_feedback`
   - Why: confirms the feedback model that will eventually tune ranking and attention behavior
   - Expected artifact: `docs/reference/recovery/record-lens-feedback.dis.txt`
   - Status: generated

## Local commands

Example commands:

```powershell
python tools/pyc_disassemble.py `
  src/new_era/infrastructure/http/__pycache__/app.cpython-312.pyc `
  --output docs/reference/recovery/http-app.dis.txt

python tools/pyc_disassemble.py `
  src/new_era/application/services/__pycache__/simulation_runtime.cpython-312.pyc `
  --output docs/reference/recovery/simulation-runtime.dis.txt
```

## Rule of use

These disassembly artifacts are planning and reconstruction inputs.

They are not maintained source code, and they should not be treated as the final authored implementation.

## Next implementation move

With the disassembly set now generated, the next engineering step is source reconstruction in this order:

1. `new_era.infrastructure.http.app`
2. `new_era.application.services.simulation_runtime`
3. `new_era.application.use_cases.document_analysis_jobs`

Those three modules define the main runtime skeleton, so recovering them first gives the rest of the system a stable spine.
