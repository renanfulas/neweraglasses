# Mobile Text Scanner Multi-Agent Plan

Status: Partially executed coordination plan  
Last updated: 2026-05-26  
Owner: Technical coordinator  
Related spec: [../specs/0005-mobile-text-scanner.md](../specs/0005-mobile-text-scanner.md)
Auth/transport decision: [mobile-text-scanner-auth-transport.md](mobile-text-scanner-auth-transport.md)

## Purpose

Coordinate the implementation of the mobile text scanner path without destabilizing the validated MVP.

The target is deliberately small:

```text
mobile camera/photo -> ML Kit Text Recognition v2 -> extracted text -> existing document job -> analysis/history/feedback
```

The first implementation must not move contract-risk analysis into the mobile client. The backend remains the authority for ownership, policy, jobs, analysis, history, and feedback.

## Core Decision

Start with a contract-only POC against the existing backend endpoint:

```text
POST /api/jobs/documents/contract-analysis
```

Use:

```json
{
  "source_type": "mobile_text_scanner",
  "document_text": "<scanner extracted text>"
}
```

Do not add a new backend endpoint until the contract-only POC proves the current route is insufficient.

Auth/transport is a precondition for the mobile POC, not a cleanup task. The current route is protected by the current-user boundary, and cookie-authenticated browser writes require same-origin intent. A native mobile client must not pretend that browser cookie/same-origin behavior is its production auth story. For the current repository state, the approved executable proof is harness-driven scanner submission with local-only dev auth, documented in [mobile-text-scanner-auth-transport.md](mobile-text-scanner-auth-transport.md).

Scanner text is the only scanner-originated backend input in the first POC. ML Kit recognition confidence, language, blocks, bounding boxes, and line metadata must stay local to the client or comparison notes unless a later schema is approved. Do not map ML Kit confidence directly into the backend `confidence` field for the POC.

## Workstreams

### Agent 0: Technical Coordinator

Owns:

- this coordination plan
- cross-agent sequencing
- conflict resolution
- final acceptance checklist

Files:

- `docs/architecture/mobile-text-scanner-execution-plan.md`
- `docs/specs/0005-mobile-text-scanner.md`
- `docs/specs/README.md`

Does not own:

- backend implementation
- mobile app implementation
- PWA product files

Deliverables:

- frozen scanner payload contract
- merge order
- auth/transport precondition before native mobile submission
- open decisions log
- final MVP scanner readiness assessment

### Agent 1: Backend Contract Harness

Mission:

Prove the scanner text payload works through the existing document job path before mobile code exists.

Owns:

- `tests/unit/test_http_app.py`
- optional scanner comparison helper under `tools/`
- backend docs only when describing validated behavior

May touch with coordination:

- `src/new_era/infrastructure/http/schemas.py`
- `src/new_era/infrastructure/http/document_routes.py`

Rules:

- do not add a new endpoint in the first pass
- do not introduce ML Kit-specific backend branches
- keep `source_type="mobile_text_scanner"` vendor-neutral
- preserve current auth/current-user behavior

Minimum tests:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/unit/test_http_app.py
```

Exit criteria:

- scanner-style text payload queues a job
- job succeeds
- result persists with `source_type="mobile_text_scanner"`
- trace/history includes the scanner-originated job
- idempotency still works
- malformed/short scanner text is rejected predictably

### Agent 2: Mobile ML Kit POC

Mission:

Build the smallest mobile proof that extracts text with ML Kit Text Recognition v2 and posts the existing JSON payload.

Proposed ownership:

- new mobile workspace, for example `apps/mobile-text-scanner/`
- mobile README/run instructions inside that workspace
- no backend files

Rules:

- use ML Kit Text Recognition v2 for OCR
- prefer the bundled Latin model for first-run demo reliability
- keep Document Scanner optional until capture quality demands it
- normalize and bound the recognized text before sending it as `document_text`
- send neutral `source_type="mobile_text_scanner"`
- do not map ML Kit confidence directly to backend `confidence`
- do not post from a native client until the POC auth/transport path is documented
- do not display contract-risk labels before backend analysis returns

Open implementation choice:

- native Android first
- React Native
- Flutter
- thin local harness before native UI

Exit criteria:

- one contract photo can be scanned
- extracted text can be reviewed before submit
- backend job is created from mobile payload
- result can be inspected through existing API/PWA routes

### Agent 3: Capture UX And Client Quality Gate

Mission:

Keep the scanner usable without turning it into a full native product too early.

Owns:

- mobile capture/review UI files after Agent 2 creates the mobile workspace
- client-side validation states
- scanner UX notes in docs

Does not own:

- backend policy
- contract-risk analysis
- long-term auth strategy

Minimum UX states:

- scanning
- text found
- review extracted text
- sending
- queued
- retry capture

Client-side quality gate:

- block empty extracted text
- warn below backend minimum length
- allow manual correction before submit
- retry with stable `idempotency_key` for the same capture

Exit criteria:

- user can understand whether the scanner found usable text
- user can correct text before backend analysis
- poor extraction does not silently become a confident analysis

### Agent 4: Auth And Transport Boundary

Mission:

Decide how the mobile POC authenticates before native submission work begins, without weakening the current browser auth boundary.

Owns:

- auth/transport decision note
- any future native-client auth contract

May touch with coordination:

- `src/new_era/infrastructure/http/auth.py`
- `src/new_era/infrastructure/http/dependencies.py`
- `docs/architecture/auth-boundary.md`

Rules:

- do not bypass ownership checks
- do not make dev header auth the production mobile story
- distinguish POC transport from future native auth
- keep cookie/same-origin behavior intact for the PWA

POC options:

- use existing browser session through a local dev flow
- use a temporary local bridge token documented as non-production
- defer native auth by testing payload through a harness first

Exit criteria:

- mobile POC can submit without weakening PWA auth
- production auth gap is explicitly documented
- any temporary auth path is clearly non-production
- Agent 2 has a documented POC transport path before native POST testing

### Agent 5: Scanner Comparison And Quality Evaluation

Mission:

Measure whether scanner text is materially better than raw image OCR.

Owns:

- comparison fixtures
- evaluation notes
- optional tool under `tools/`
- example documents under `docs/examples/` or `evals/`

Comparison set:

- direct text input
- current image OCR upload
- scanner-extracted text

Required samples:

- clean one-page contract
- medium-quality photo
- poor-quality photo

Success signal:

- scanner-extracted text should produce findings and confidence closer to direct text input than raw image OCR.

Exit criteria:

- comparison results are captured
- failure cases are documented
- recommendation is clear: continue, adjust capture, or stop

### Agent 6: Demo Pack And Documentation

Mission:

Make the scanner path explainable and repeatable once it works.

Owns:

- README updates
- scanner runbook
- demo checklist
- final docs alignment

Does not own:

- mobile implementation
- backend contract changes

Exit criteria:

- a fresh operator can run the scanner demo path
- docs explain what is simulated, what is real, and what is deferred
- `tools/validate_local.py --with-e2e` remains the MVP baseline

## Ownership Matrix

| Area | Primary owner | Notes |
| --- | --- | --- |
| Scanner spec | Agent 0 | Contract changes documented before code. |
| Backend job contract | Agent 1 | No new endpoint in POC unless proven necessary. |
| HTTP auth/dependencies | Agent 4 | Mobile auth must not weaken browser auth. |
| Mobile app/workspace | Agent 2 | Prefer a new isolated workspace. |
| Mobile scanner UX | Agent 3 | No backend policy logic in UI. |
| Comparison harness/evals | Agent 5 | Measures scanner vs text vs image OCR. |
| README/runbook | Agent 6 | Final packaging only after POC succeeds. |
| PWA files | No default owner | Do not touch unless needed for result inspection/demo. |

## Execution Sequence

### Phase 0: Freeze Contract

Owner: Agent 0

Status: Complete for the contract-only POC.

Tasks:

- confirm `SPEC-0005` is the active scanner contract
- freeze `source_type="mobile_text_scanner"`
- record the current auth boundary: current-user required, cookie-authenticated browser writes require same-origin intent
- move auth/transport from open-ended follow-up to precondition for native mobile POC
- confirm no new endpoint for POC
- confirm ML Kit confidence is not mapped directly to backend `confidence` in the POC
- confirm `document_text` normalization and bounds

Exit criteria:

- every agent knows what they may edit
- scanner payload contract is stable
- auth/transport decision is queued before native mobile submission work

### Phase 1: Backend Contract Harness

Owner: Agent 1

Status: Complete for the existing backend route.

Tasks:

- add scanner-style backend test or harness
- verify result metadata
- verify short/empty text behavior
- verify idempotency behavior

Exit criteria:

- backend can already accept scanner text
- no mobile work is blocked by unknown backend behavior

### Phase 2: Scanner Comparison Baseline

Owner: Agent 5

Status: Complete for the generated sample baseline; real mobile photos remain pending.

Tasks:

- use the current sample contract
- compare direct text vs current image OCR
- define the target quality delta for scanner text

Exit criteria:

- the team knows what improvement ML Kit must prove

### Phase 3: Auth Boundary Decision

Owner: Agent 4

Status: Complete for harness-driven POC; production native auth remains deferred.

Tasks:

- decide the POC auth/transport path before native mobile POST testing
- document what is temporary
- define production direction if scanner continues
- keep the PWA cookie/current-user/same-origin behavior intact

Exit criteria:

- mobile submission path is clear enough for Agent 2 to test
- PWA cookie auth remains intact
- no new endpoint is introduced for the POC
- no ownership check is bypassed

### Phase 4: Mobile ML Kit POC

Owner: Agent 2 with Agent 3 support

Status: Scaffolded. `apps/mobile-text-scanner/` contains an isolated Android/Kotlin POC with ML Kit Text Recognition v2, camera/photo capture, text review, normalization, stable idempotency key, and existing backend job submission. Build/device validation is pending Android Studio or Gradle availability.

Tasks:

- create isolated mobile workspace or harness
- integrate ML Kit Text Recognition v2
- extract, normalize, review, and bound recognized text
- let user review text
- submit existing backend payload

Exit criteria:

- one mobile-scanned contract reaches backend job success through the documented POC auth/transport path
- result can be inspected through existing API/PWA

### Phase 5: MVP-Good Scanner

Owners: Agents 2, 3, 5

Status: Pending real device photo comparison set.

Tasks:

- test clean/medium/poor contract photos
- decide whether Document Scanner or CameraX live analysis is needed
- decide whether to send image evidence through multipart
- refine user review/retry path

Exit criteria:

- scanner text is measurably better than raw image OCR
- demo path is stable enough to show

### Phase 6: Demo Pack And Final Validation

Owner: Agent 6 with Agent 0 sweep

Status: Partially complete. README and local validation support the scanner comparison harness.

Tasks:

- update README/runbook
- record known limitations
- keep MVP validation green

Validation:

```powershell
$env:PYTHONPATH='src'; python -m pytest
python .\tools\validate_local.py --with-e2e --with-scanner-comparison
```

Exit criteria:

- scanner docs are clear
- MVP baseline remains intact
- scanner limitations are explicit

## Merge Gates

Required before merge:

- owner reports files touched
- tests or manual validation recorded
- contract changes documented first
- auth/transport decision recorded before native mobile POST testing
- no hidden dependency on `/api/users/{user_id}/...`
- no ML Kit-specific backend branching
- no legal/risk analysis on the client
- no weakening of cookie/same-origin PWA auth
- no direct mapping from ML Kit confidence to backend `confidence`
- scanner `document_text` is normalized and bounded before submit

Hard blockers:

- adding a new endpoint before contract-only POC proves it is needed
- native mobile submission that assumes browser cookie/same-origin behavior without an explicit POC decision
- mobile client bypassing current-user ownership
- raw scanner text written into generic event metadata
- scanner confidence driving backend policy directly
- mobile work requiring changes to the validated MVP flow without a coordination note

## Agent Prompt Templates

### Agent 0 Prompt

You are the technical coordinator for the Mobile Text Scanner POC. Own only coordination docs, contract freezing, merge order, and risk tracking. Do not edit backend or mobile product code. Keep `SPEC-0005` as the source of truth and stop any work that adds a new endpoint before the contract-only POC proves it is needed.

Deliver:

- frozen payload contract
- auth/transport sequencing decision before native mobile POST testing
- owner matrix
- merge order
- unresolved risks

### Agent 1 Prompt

You own the backend contract harness for scanner text. Prove that `source_type="mobile_text_scanner"` and `document_text` work through the existing `POST /api/jobs/documents/contract-analysis` path. Do not add a new endpoint. Test success, validation failure, metadata, history, ownership, and idempotency.

Deliver:

- tests/harness summary
- files touched
- tests run
- backend risks

### Agent 2 Prompt

You own the ML Kit Text Recognition v2 POC client. Build the smallest mobile or local client that extracts text and submits the existing backend JSON payload after Agent 4 documents the POC auth/transport path. Keep the implementation isolated from backend files. Use neutral source metadata, normalize and bound `document_text`, do not map ML Kit confidence directly into backend `confidence`, and do not run contract-risk analysis in the client.

Deliver:

- client run instructions
- scanner payload example
- tested contract images
- mobile risks

### Agent 3 Prompt

You own capture UX and client quality gates. Add only the UX needed to prevent bad OCR from silently becoming an analysis: review text, retry capture, and submit state. Do not create legal findings in the UI before backend analysis returns.

Deliver:

- UX states
- correction/retry behavior
- screenshots or demo notes
- remaining UX risks

### Agent 4 Prompt

You own mobile auth and transport boundary decisions. Decide how the POC submits to the backend before native mobile POST testing begins, without weakening current browser auth. The current backend route uses current-user identity, and browser cookie-authenticated writes require same-origin intent. Document temporary POC behavior separately from production direction.

Deliver:

- auth decision note
- rejected options
- production follow-up risks

### Agent 5 Prompt

You own scanner quality evaluation. Compare direct text, current image OCR, and scanner-extracted text using clean, medium, and poor contract photos. Measure whether scanner text improves findings and confidence.

Deliver:

- comparison table
- sample inputs
- quality recommendation
- failure cases

### Agent 6 Prompt

You own demo packaging and docs after the scanner POC works. Update runbooks and README so a fresh operator can understand what is real, what is simulated, and what remains deferred.

Deliver:

- runbook
- demo checklist
- final validation command results
- limitations

## Ready Definition

The mobile text scanner POC is ready when:

- the existing backend endpoint accepts scanner text
- ML Kit extracts usable text from at least one contract image
- the extracted text queues and completes a document analysis job
- trace/history records the scanner-originated path
- result quality is compared against text input and raw image OCR
- auth limitations are explicitly documented
- the validated MVP baseline still passes

The MVP-good scanner is ready when:

- clean, medium, and poor contract images have comparison results
- user can review/correct extracted text before submit
- retry/idempotency behavior is stable
- capture path is better than raw image OCR often enough to justify continuing
- docs explain the scanner as capture assistance, not backend replacement

## Current Executable Proof

Run:

```powershell
$env:PYTHONPATH='src'
python .\tools\scanner_comparison_harness.py
python .\tools\validate_local.py --skip-pytest --with-scanner-comparison
```

This proves:

- direct contract text still produces an analysis
- generated image OCR still reaches the existing upload/job path
- simulated mobile scanner text reaches the existing document job path
- `source_type="mobile_text_scanner"` is preserved through job and analysis result metadata

It does not prove:

- Android SDK build in this workspace
- real device camera capture against a running local backend
- production native mobile authentication

## Mobile Workspace

Location:

```text
apps/mobile-text-scanner/
```

Current mobile POC behavior:

- opens camera preview capture or image picker
- extracts text with ML Kit Text Recognition v2 Latin bundled model
- normalizes line endings and control characters
- blocks text below 20 characters or above 50,000 characters
- creates a stable `scan_<sha256>` idempotency key from the reviewed text
- posts `source_type="mobile_text_scanner"` to the existing document job endpoint
- uses local-only dev header auth for POC submission

Validation gap:

- Codex workspace did not have `gradle` installed, so Android compilation was not run here.
- Open `apps/mobile-text-scanner/` in Android Studio to sync/build/run.
