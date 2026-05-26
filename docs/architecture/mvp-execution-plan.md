# MVP Execution Plan

Status: Active coordination reference  
Last updated: 2026-05-26  
Owner: Technical coordinator

## Purpose

Keep the MVP demo path stable while future work continues.

This document is no longer a phase-by-phase implementation script. The MVP path is already implemented. From here, this file exists to coordinate changes, protect the validated flow, and keep multi-agent work from colliding.

The demonstrable MVP path is:

```text
login -> grocery -> contracts with text/image -> async job -> trace/history -> feedback -> logout/relogin -> device bridge
```

## Current Validated State

The maintained local validation command is:

```powershell
python .\tools\validate_local.py --with-e2e
```

Latest validated result:

```text
141 passed, 1 skipped
authenticated smoke probes passed
device bridge harness passed
browser E2E smoke passed
```

The browser smoke currently validates:

- login and logout
- grocery simulation plus feedback
- contract simulation from text
- multipart contract upload job from image
- async job completion
- session trace/history refresh
- relogin after an authenticated `401`

The default `pytest` pass skips the browser E2E module unless `NEW_ERA_RUN_E2E=1`.

## Coordination Rules

These rules remain active for future MVP changes:

- one owner per critical file at a time
- cross-boundary changes happen through documented contracts first
- browser/PWA code does not reintroduce `/api/users/{user_id}/...` as a primary dependency
- E2E should reveal product problems before it starts fixing them
- local validation must remain reproducible from documented environment variables and commands

If multiple agents are working in parallel, they should record:

- files they intend to touch
- tests they ran
- contract changes they need from another owner
- residual risks

## Frozen MVP Contracts

### Browser and PWA contract

Canonical companion routes:

| Capability | Canonical route |
| --- | --- |
| Auth bootstrap | `GET /api/auth/session` |
| Login | `POST /api/auth/login` |
| Logout | `POST /api/auth/logout` |
| Grocery simulation | `POST /api/simulations/grocery/missing-item` |
| Contract simulation | `POST /api/simulations/documents/contract-review` |
| Document job enqueue | `POST /api/jobs/documents/contract-analysis` |
| Document upload job | `POST /api/uploads/documents/contract-analysis` |
| Job status | `GET /api/jobs/{job_id}` |
| Job transition | `POST /api/jobs/{job_id}/status` |
| Job result | `GET /api/jobs/{job_id}/result` |
| Current-user trace | `GET /api/current-user/sessions/{session_id}/trace` |
| Current-user session jobs | `GET /api/current-user/sessions/{session_id}/jobs` |
| Current-user feedback metrics | `GET /api/current-user/sessions/{session_id}/feedback-metrics` |
| Lens feedback | `POST /api/lens-commands/{command_id}/feedback` |
| Analysis detail | `GET /api/document-analyses/{analysis_id}` |
| Analysis feedback | `POST /api/document-analyses/{analysis_id}/feedback` |

Compatibility routes still present:

- `/api/users/{user_id}/sessions`
- `/api/users/{user_id}/sessions/{session_id}/trace`
- `/api/users/{user_id}/sessions/{session_id}/jobs`
- `/api/users/{user_id}/sessions/{session_id}/feedback-metrics`

Compatibility rules:

- legacy user-scoped paths remain compatibility-only
- legacy paths must enforce `path_user_id == current_user_id`
- browser/PWA work must continue using current-user routes
- removal of legacy paths requires a separate contract update

### Auth and ownership contract

- cookie-authenticated writes must validate same-origin intent
- missing or expired auth returns `401`
- authenticated path/body mismatch returns `403`
- foreign-owned resource access returns resource-specific `404`
- development header auth remains behind explicit runtime configuration

### Device bridge contract

- `GET /api/device/capabilities` remains the local capability probe
- `POST /api/device-bridge/camera/document-contract-review` stays HTTP-owned even when device validation is owned elsewhere
- bridge validation must continue covering capability discovery, token delivery, failure surfacing, timeout surfacing, and metadata redaction

## Ownership Hotspots

These are still the main collision points during MVP work:

| File group | Ownership concern |
| --- | --- |
| `src/new_era/infrastructure/http/app.py` | auth/bootstrap/runtime wiring |
| `src/new_era/infrastructure/http/document_routes.py` | contract, upload, and bridge route semantics |
| `src/new_era/infrastructure/http/dependencies.py` | current-user and auth dependency behavior |
| `src/new_era/infrastructure/http/static/app.js` | PWA route usage, auth state, history/job UX |
| `src/new_era/infrastructure/http/static/index.html` | stable browser hooks and shell layout |
| `src/new_era/infrastructure/http/static/styles.css` | responsive and auth-state behavior |
| `tests/unit/test_http_app.py` | contract regression coverage |
| `tests/unit/test_pwa_assets.py` | static route dependency checks |
| `tests/e2e/` | browser smoke coverage |
| `src/new_era/infrastructure/device/` | adapter behavior |
| `tools/validate_local.py` | local validation contract |
| `tools/device_bridge_harness.py` | repeatable bridge validation contract |

If a change needs more than one hotspot owner at once, coordinate the contract first and sequence the edits.

## Required Validation

Baseline:

```powershell
$env:PYTHONPATH='src'; python -m pytest
```

MVP validation pack:

```powershell
python .\tools\validate_local.py --with-e2e
```

Optional focused commands:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/unit/test_http_app.py tests/unit/test_pwa_assets.py
$env:PYTHONPATH='src'; python .\tools\device_bridge_harness.py
$env:NEW_ERA_RUN_E2E='1'; python -m pytest tests/e2e -m e2e
```

## MVP Ready Definition

The MVP remains ready when a fresh local operator can:

- configure local auth
- start the app
- authenticate
- run grocery simulation
- run contract review with text
- run contract review with image or upload
- queue and inspect async job status/result
- inspect trace/history
- submit lens and document feedback
- logout
- relogin after expired or missing session
- validate device bridge behavior through the local harness

Required signals:

- full `pytest` passes
- `tools/validate_local.py --with-e2e` passes
- the browser smoke still covers at least one complete end-to-end companion flow

## Deferred On Purpose

Still out of MVP scope:

- provider-backed production identity
- native vendor glasses SDK integration
- distributed production queue design
- production observability stack
- full removal of legacy `/api/users/{user_id}/...` routes
