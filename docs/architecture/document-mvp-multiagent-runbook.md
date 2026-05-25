# Document MVP Multi-Agent Runbook

Status: Draft
Date: 2026-05-25
Related spec: [0003-document-mvp-hardening.md](/C:/Users/renan/OneDrive/Documents/New%20Era%20Glasses/docs/specs/0003-document-mvp-hardening.md)

## Purpose

This runbook defines how to implement `SPEC-0003` with multiple agents without turning the current repo state into a merge fight.

The core rule is simple:

> parallelize by ownership boundary, then integrate through one coordinator.

## Current Risk Snapshot

The repository already has uncommitted changes in central files such as:

- `src/new_era/infrastructure/http/app.py`
- `src/new_era/infrastructure/http/static/app.js`
- job stores and document analysis job code
- several unit tests

This means the document hardening work must not begin as five unconstrained workers editing shared files directly.

## Roles

### Agent 0: Coordinator / Integrator

Owns:

- shared contracts
- `SPEC-0003`
- multi-agent execution rules
- runtime wiring integration
- final smoke validation

Allowed write scope:

- `docs/specs/0003-document-mvp-hardening.md`
- `docs/architecture/document-mvp-multiagent-runbook.md`
- `src/new_era/application/services/simulation_runtime.py`
- `src/new_era/application/use_cases/__init__.py`
- `src/new_era/infrastructure/http/app.py`
- cross-cutting smoke tests and README updates

### Agent 1: Upload Lifecycle And Local Security

Owns:

- document artifact model and lifecycle
- local blob storage rules
- delete behavior
- quota enforcement for uploads and active jobs

Preferred write scope:

- `src/new_era/domain/documents/*`
- `src/new_era/application/ports/*artifact*`
- `src/new_era/application/use_cases/*artifact*`
- `src/new_era/infrastructure/documents/*artifact*`
- dedicated unit tests for artifacts and quotas

Must not edit:

- `src/new_era/infrastructure/http/app.py`
- `src/new_era/infrastructure/http/static/app.js`

### Agent 2: Feedback Metrics Read Model

Owns:

- document feedback aggregate models
- session-level metrics use case
- finding-type breakdown logic

Preferred write scope:

- `src/new_era/domain/metrics/*`
- `src/new_era/application/use_cases/*feedback_metrics*`
- optional supporting read utilities under `application`
- dedicated unit tests

Must not edit:

- attention policy
- `src/new_era/infrastructure/http/static/app.js`
- `src/new_era/infrastructure/http/app.py`

### Agent 3: OCR / Analysis Eval Harness

Owns:

- local fixtures
- eval runner
- scoring rules for expected findings and confidence checks

Preferred write scope:

- `evals/document_analysis/fixtures/*`
- `tools/evaluate_document_analysis.py`
- dedicated unit tests
- short doc section for running evals

Must not edit:

- runtime HTTP files
- service worker or manifest

### Agent 4: PWA Document Flow UX

Owns:

- document flow UX states in the PWA
- polling behavior
- result opening
- better job and history readability

Preferred write scope:

- `src/new_era/infrastructure/http/static/app.js`
- `src/new_era/infrastructure/http/static/index.html`
- `src/new_era/infrastructure/http/static/styles.css`

Must not edit:

- backend contracts
- `src/new_era/infrastructure/http/app.py`

### Agent 5: PWA Install / Offline

Owns:

- manifest improvements
- service worker caching rules
- offline read-only shell behavior
- mobile/PWA test documentation

Preferred write scope:

- `src/new_era/infrastructure/http/static/manifest.webmanifest`
- `src/new_era/infrastructure/http/static/service-worker.js`
- `docs/architecture/pwa-frontend.md`
- small smoke coverage only if isolated

Must not edit:

- document UX logic in `app.js`
- backend contracts

## Sequence

### Phase 0: Contract Freeze

The coordinator completes:

- `SPEC-0003`
- endpoint names
- event names
- retention defaults
- quota defaults
- ownership map

No worker should implement against a moving contract.

### Phase 1: Safe Parallel Work

Run in parallel:

- Agent 1
- Agent 2
- Agent 3
- Agent 5

Agent 4 may start only with UI-state preparation that does not depend on unfinished endpoint wiring.

### Phase 2: Integration

The coordinator:

- reviews worker diffs
- resolves collisions with current uncommitted work
- wires runtime dependencies
- wires HTTP endpoints
- finalizes imports and smoke tests

Agent 4 then connects the PWA to the final backend contracts if any UI-only assumptions changed.

### Phase 3: Validation

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest discover
$env:PYTHONPATH='src'; python .\tools\validate_local.py
$env:PYTHONPATH='src'; python .\tools\evaluate_document_analysis.py
```

Manual checks:

- upload an image
- queue a job
- observe polling
- confirm automatic result opening
- refresh and confirm history
- submit feedback
- verify offline shell blocks document mutations
- delete the artifact

## Integration Rules

- One coordinator owns `app.py`.
- One coordinator owns `simulation_runtime.py`.
- Frontend UX and offline behavior are split between Agent 4 and Agent 5.
- Workers must assume the worktree is dirty and must not revert unrelated edits.
- Workers should prefer additive modules, new files, and dedicated tests over invasive edits.
- If a worker needs a shared contract change, it should stop at the use case or helper boundary and let the coordinator wire it.

## Shared Contracts

Frozen endpoint set:

```text
POST   /api/uploads/documents/contract-analysis
DELETE /api/document-artifacts/{artifact_id}
GET    /api/users/{user_id}/sessions/{session_id}/feedback-metrics
```

Optional later endpoint:

```text
GET /api/users/{user_id}/sessions/{session_id}/document-quality-summary
```

Frozen event set:

```text
document_uploaded
document_deleted
document_retention_expired
upload_rejected
feedback_metric_computed
ocr_quality_evaluated
rate_limit_exceeded
```

Frozen local defaults:

```text
upload root: .new_era/uploads/documents
accepted uploads per session: 20
active jobs per session: 5
```

## Worker Output Contract

Each worker must return:

- contract assumptions used
- files changed
- tests added
- risks left open
- validation command run

## Merge Strategy

Use this order:

1. Coordinator lands spec and runbook
2. Agent 1 artifact lifecycle
3. Agent 2 feedback metrics
4. Agent 3 eval harness
5. Agent 5 manifest and service worker
6. Coordinator wiring
7. Agent 4 final PWA hookup and UX polish
8. Coordinator validation and README touch-up

## Red Zones

These files are integration choke points and should not be edited by multiple workers in parallel:

- `src/new_era/infrastructure/http/app.py`
- `src/new_era/application/services/simulation_runtime.py`
- `src/new_era/application/use_cases/__init__.py`
- `src/new_era/infrastructure/http/static/app.js`

`app.js` is a special case:

- Agent 4 owns functional UX changes
- Agent 5 may propose offline interaction constraints but should keep code edits out of `app.js` unless the coordinator explicitly hands over that file
