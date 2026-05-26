# MVP Execution Plan

Status: Active execution plan  
Last updated: 2026-05-26  
Owner: Technical coordinator

## Purpose

Close the MVP as a demonstrable and validated local product path:

```text
login -> grocery -> contracts with image/text -> async job -> trace/history -> feedback -> logout/relogin -> device bridge
```

This plan replaces loose parallel work with a merge-safe execution model. The core rule is:

```text
One owner per critical file per phase. Cross-boundary changes happen only through documented contracts.
```

The current repository already has a working auth/current-user migration and passing unit baseline. Treat the code plus tests as the runtime truth.

## Phase 0: Stabilize Before Parallel Work

No specialized agent starts product changes until Phase 0 is complete.

Required baseline:

- record `git status --short`
- record the current pytest result
- freeze this plan as the coordination document
- freeze the HTTP contract table below
- decide whether the current dirty workspace is committed, branched, or explicitly accepted as the starting integration state

Validation command:

```powershell
$env:PYTHONPATH='src'; python -m pytest
```

Exit rule:

- unit baseline passes
- current critical-file ownership is assigned
- each agent has a declared file list before editing

## Frozen MVP HTTP Contract

Canonical browser/PWA routes:

| Capability | Canonical route | Notes |
| --- | --- | --- |
| Auth bootstrap | `GET /api/auth/session` | Returns the backend-resolved current user or `401`. |
| Login | `POST /api/auth/login` | Uses local configured credentials for MVP. Must set server-managed cookie. |
| Logout | `POST /api/auth/logout` | Invalidates server session and clears cookie. |
| Grocery simulation | `POST /api/simulations/grocery/missing-item` | PWA may omit `user_id`; backend derives current user. |
| Contract simulation | `POST /api/simulations/documents/contract-review` | Accepts text or image payload. PWA may omit `user_id`. |
| Document job enqueue | `POST /api/jobs/documents/contract-analysis` | Accepts text or base64 image payload. PWA may omit `user_id`. |
| Document upload job | `POST /api/uploads/documents/contract-analysis` | Multipart path. PWA may omit `user_id`. |
| Job status | `GET /api/jobs/{job_id}` | Owner-scoped by backend. |
| Job transition | `POST /api/jobs/{job_id}/status` | Demo/manual status path. Owner-scoped by backend. |
| Job result | `GET /api/jobs/{job_id}/result` | Requires succeeded job and owner match. |
| Current-user sessions | `GET/POST /api/current-user/sessions` | Canonical companion session collection. |
| Current-user trace | `GET /api/current-user/sessions/{session_id}/trace` | Canonical companion trace path. |
| Current-user session jobs | `GET /api/current-user/sessions/{session_id}/jobs` | Canonical companion job history path. |
| Current-user feedback metrics | `GET /api/current-user/sessions/{session_id}/feedback-metrics` | Canonical companion document metrics path. |
| Lens feedback | `POST /api/lens-commands/{command_id}/feedback` | PWA may omit `user_id`; backend derives current user. |
| Analysis detail | `GET /api/document-analyses/{analysis_id}` | Owner-scoped by backend. |
| Analysis feedback | `POST /api/document-analyses/{analysis_id}/feedback` | PWA may omit `user_id`; backend derives current user. |
| Device capabilities | `GET /api/device/capabilities` | Public local capability probe. |
| Camera bridge input | `POST /api/device-bridge/camera/document-contract-review` | HTTP-owned route, device-owned harness. |

Compatibility routes:

- `/api/users/{user_id}/sessions`
- `/api/users/{user_id}/sessions/{session_id}/trace`
- `/api/users/{user_id}/sessions/{session_id}/jobs`
- `/api/users/{user_id}/sessions/{session_id}/feedback-metrics`

Compatibility rules:

- legacy user-scoped paths remain available for now
- legacy paths must enforce `path_user_id == current_user_id`
- browser/PWA code must not depend on `/api/users/{user_id}/...`
- removal of legacy paths requires a later spec update and migration notice

Auth/security rules:

- cookie-authenticated writes must validate same-origin browser intent
- missing/expired auth session returns `401`
- authenticated path/body mismatch returns `403`
- foreign owned resource returns resource-specific `404`
- dev header auth remains behind explicit configuration only

## File Ownership Matrix

Critical files are locked per phase:

| File group | Primary owner | Notes |
| --- | --- | --- |
| `docs/architecture/mvp-execution-plan.md` | Agent 0 | This plan and checklist only. |
| `docs/specs/README.md`, auth specs | Agent 0 with Agent 2 review | Contract changes are documented before code. |
| `src/new_era/infrastructure/http/app.py` | Agent 2 | No other agent edits during HTTP phase. |
| `src/new_era/infrastructure/http/document_routes.py` | Agent 2 | Device bridge route changes require Agent 2 coordination. |
| `src/new_era/infrastructure/http/dependencies.py` | Agent 2 | Auth/current-user dependency owner. |
| `src/new_era/infrastructure/http/schemas.py` | Agent 2 | Request/response contract owner. |
| `src/new_era/infrastructure/http/support.py` | Agent 2 | HTTP ownership/error helper owner. |
| `src/new_era/infrastructure/http/static/index.html` | Agent 3 | PWA hooks and shell only. |
| `src/new_era/infrastructure/http/static/app.js` | Agent 3 | PWA behavior only after HTTP freeze. |
| `src/new_era/infrastructure/http/static/styles.css` | Agent 3 | PWA states/responsive polish. |
| `tests/unit/test_http_app.py` | Agent 2 | HTTP contract and ownership tests. |
| `tests/unit/test_pwa_assets.py` | Agent 3 | Static asset and route dependency checks. |
| `tests/e2e/` | Agent 1 | Browser tests only. Product fixes become findings. |
| `src/new_era/infrastructure/device/` | Agent 4 | Adapter behavior only. |
| `tests/unit/test_http_device_bridge_adapter.py` | Agent 4 | Adapter transport tests. |
| `docs/architecture/device-adapters.md` | Agent 4 | Adapter docs. Route semantics need Agent 2 review. |
| `.env.example`, `README.md`, `tools/validate_local.py`, runbook docs | Agent 5 | Starts early for env contract, finishes late for demo pack. |

Cross-boundary rule:

- if an agent needs a file outside its ownership, it stops and records the requested contract change
- Agent 0 either reassigns the file for that phase or creates a new phase
- no agent silently fixes product code while writing E2E

## Execution Sequence

### Phase 0: Coordination lock

Owner: Agent 0

Tasks:

- confirm baseline tests
- freeze this execution plan
- assign critical files for the next phase
- capture known dirty workspace state

Output:

- current status matrix
- merge order
- unresolved risk list

### Phase 1: Local ops seed

Owner: Agent 5

This phase starts earlier than the original plan because E2E and demo depend on environment truth.

Tasks:

- update local auth variables in `.env.example`
- document SQLite/auth/dev-header knobs
- define a single local validation command target
- avoid broad README rewrites until later

Exit rule:

- a fresh local operator can configure auth without reading code

### Phase 2: HTTP contract closure

Owner: Agent 2

Tasks:

- finish current-user behavior
- keep legacy `/api/users/{user_id}/...` aliases compatible
- verify body/path mismatch handling
- verify ownership for sessions, jobs, analyses, artifacts, feedback, and traces
- confirm camera bridge route auth expectations

Tests:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/unit/test_http_app.py tests/unit/test_http_smoke.py
```

Exit rule:

- PWA canonical routes are stable
- legacy routes are clearly compatibility paths
- HTTP contract changes are documented

### Phase 3: PWA hardening

Owner: Agent 3

Tasks:

- remove companion dependency on `/api/users/{user_id}/...`
- add stable browser-test hooks where needed
- harden auth gate, loading, empty, error, mobile, job/history refresh, and reauth states
- ensure UI copy does not break compact layouts

Tests:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/unit/test_pwa_assets.py
```

Exit rule:

- static tests prove PWA avoids legacy user-scoped paths
- auth failure returns user to login gate
- refresh-safe job/history paths work through current-user routes

### Phase 4: Browser E2E smoke first

Owner: Agent 1

Tasks:

- add Playwright or selected browser runner in the smallest viable way
- create fixtures for local auth credentials and isolated runtime storage
- implement one smoke journey before expanding:

```text
login -> grocery -> contract text job -> job status/result -> feedback -> logout
```

Expanded journey:

```text
login -> grocery -> contract text -> contract image/upload -> async job -> trace/history -> feedback -> logout -> relogin after 401
```

Rules:

- E2E does not edit product code unless Agent 0 explicitly grants a PWA-hook change
- product failures are reported as findings for Agent 2 or Agent 3
- E2E storage must be isolated from the developer's `.new_era/runtime.sqlite3`

Exit rule:

- at least one browser smoke E2E passes locally
- E2E command is documented

### Phase 5: Device bridge validation

Owner: Agent 4

Split this into adapter-owned and HTTP-owned work:

Adapter-owned:

- capabilities success/failure
- delivery success
- delivery failure
- timeout behavior
- sensitive metadata redaction

HTTP-owned coordination:

- camera bridge endpoint auth expectations
- image payload through document contract pipeline
- trace visibility for camera-originated review

Tests:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/unit/test_http_device_bridge_adapter.py
```

Exit rule:

- bridge behavior is repeatable without real hardware
- docs explain what is simulated, what is real, and what is deferred

### Phase 6: Demo pack and final validation

Owner: Agent 5 with Agent 0 final sweep

Tasks:

- finalize README/runbook demo steps
- finalize `tools/validate_local.py`
- include pytest plus smoke probes plus optional E2E command
- document known MVP limits

Final validation:

```powershell
$env:PYTHONPATH='src'; python -m pytest
python .\tools\validate_local.py
```

Plus at least one browser smoke E2E command once Phase 4 lands.

## Agent Prompts

### Agent 0: Technical Coordinator

You are the technical coordinator for the New Era Glasses MVP. Own only coordination docs, status matrix, conflict resolution, and merge sequencing. Do not edit product code. Start by recording `git status --short`, current test baseline, intended owners, and current blockers. Contract changes must be documented before code changes.

Deliver:

- status matrix
- frozen contracts
- merge order
- unresolved risks

### Agent 1: Browser E2E

You own browser-level E2E validation for the companion MVP. Add tests under `tests/e2e/` and the smallest required runner configuration. Cover login, logout, relogin after 401, grocery, contract review, async job, feedback, and history. Do not edit backend or PWA product files unless Agent 0 explicitly grants a hook-only exception.

Deliver:

- E2E command
- smoke E2E first, expanded flow second
- findings for product failures

### Agent 2: HTTP Contract Cleanup

You own the HTTP current-user contract. Finish backend routes so the browser can use current-user paths without `user_id` in main companion flows. Keep legacy `/api/users/{user_id}/...` paths compatible and owner-checked. Test mismatch, ownership, `401`, `403`, and `404` semantics.

Deliver:

- contract summary
- touched files
- HTTP/unit tests run
- remaining compatibility risks

### Agent 3: PWA UX Hardening

You own the PWA shell after the HTTP contract is frozen. Do not change backend behavior. Polish auth gate, loading, empty, error, mobile, refresh-safe job/history, and reauth states. Add stable test hooks only when needed. Prove the companion does not depend on `/api/users`.

Deliver:

- PWA behavior summary
- static asset tests run
- browser-test hook list
- remaining UX risks

### Agent 4: Device Bridge Validation

You own device adapter validation and device docs. Keep adapter work inside `src/new_era/infrastructure/device/`, adapter tests, and `docs/architecture/device-adapters.md`. If the camera bridge HTTP route must change, stop and request Agent 2 coordination.

Deliver:

- repeatable bridge harness/tests
- capability, timeout, delivery failure, and retry/observability notes
- device adapter doc update

### Agent 5: Local Ops And Demo Pack

You own local operability and demo packaging. Start early with `.env.example` and local auth documentation, then finish late with README/runbook and `tools/validate_local.py`. Do not redefine product contracts; consume the frozen HTTP/PWA contract.

Deliver:

- local environment variables
- one-command validation path
- demo script
- known local limitations

## Merge Gates

Every agent must report:

- files touched
- tests run
- files intentionally not touched
- contract changes requested
- residual risks

Merge order:

1. Agent 0 coordination plan
2. Agent 5 local auth/env seed
3. Agent 2 HTTP contract closure
4. Agent 3 PWA hardening
5. Agent 1 E2E smoke, then expanded E2E
6. Agent 4 adapter validation, with HTTP route changes sequenced through Agent 2 if needed
7. Agent 5 final demo pack
8. Agent 0 final sweep

Hard blockers:

- failing unit baseline without an explicit accepted reason
- two agents editing the same critical file in the same phase
- PWA depending on `/api/users/{user_id}/...`
- E2E sharing mutable runtime data with a developer demo database
- local demo requiring undocumented auth variables
- device bridge route changes bypassing HTTP contract ownership

## MVP Ready Definition

The MVP is ready when a fresh local operator can:

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
- relogin after expired/missing session
- validate device bridge behavior through a repeatable local harness/checklist

Required validation:

- full pytest passes
- local validation command passes
- at least one browser smoke E2E passes

Deferred explicitly:

- provider-backed production identity
- native vendor glasses SDK
- distributed production queue
- production observability stack
- complete removal of legacy `/api/users/{user_id}/...` routes
