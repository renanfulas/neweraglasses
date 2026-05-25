# Document MVP Hardening

Status: In progress
Spec ID: SPEC-0003
Owner: Platform / Documents
Date: 2026-05-25

## Progress Snapshot

Completed so far:

- first-class document artifacts
- upload and active-job quotas
- `PolicyRejection` contract
- payload fingerprint idempotency
- feedback metrics read model
- local eval harness
- PWA polling/history/result flow
- post-terminal artifact expiration
- offline read-only shell boundaries

Still open:

- broader `validate_local.py` level validation for the hardened document path
- more product UX refinement around blocked states and install/offline affordances
- production-grade auth/security follow-through for document ownership beyond localhost
- stronger operational telemetry beyond unit/integration coverage

## 1. Objective

Harden the document MVP so uploaded artifacts, asynchronous analysis jobs, feedback signals, and the PWA document flow behave like a coherent local-first system without breaking the current modular monolith architecture.

This spec closes the practical gaps that still exist between the current document demo flow and a safer, more operable MVP:

- sensitive upload lifecycle
- delete and retention behavior
- feedback metrics as a product read model
- quality evaluation before LLM or RAG expansion
- PWA install and offline boundaries

## 2. Context

The current runtime already provides:

- document upload and async document analysis jobs
- persisted analysis history
- feedback recording for document analyses and lens commands
- SQLite-backed local persistence
- a static PWA shell served by FastAPI

The current implementation is now meaningfully hardened, but it is not finished:

- the core artifact lifecycle now exists
- quotas, idempotency, retention, and feedback metrics now exist
- the remaining gaps are mainly validation depth, production auth posture, and product polish

This spec evolves the current system instead of replacing it.

### Architecture Mental Model

Document hardening follows the Contextual Attention Pyramid:

```text
raw signal rises through the stack
each layer removes risk and noise
policy decides at the top
only a safe minimal response returns to the PWA or glasses
```

For this spec, the "circle" around the glasses is the session protection boundary. It owns privacy, quotas, idempotency, retention, and user-visible blocking reasons. The device/PWA must not guess these rules client-side; it only renders backend decisions.

## 3. User Story or System Story

```text
When a user uploads a contract image or submits contract text,
the system must create a controlled local artifact, enqueue or run analysis through the backend,
persist only the minimum necessary references and derived outputs,
allow safe deletion,
and expose clear progress and history to the PWA
so that the document MVP is useful, inspectable, and safer to operate locally.
```

## 4. In Scope

- local document artifact lifecycle for uploaded files
- `artifact_id` as the reference key for uploaded document blobs
- explicit retention defaults and local reset guidance
- user-owned delete path for uploaded artifacts
- session-level quotas for uploads and active jobs
- feedback metrics read model for document analysis usefulness
- local OCR and deterministic analysis eval harness
- PWA document job polling and automatic result opening
- PWA manifest and service worker hardening for read-only offline shell

## 5. Out of Scope

- external auth provider
- cloud object storage
- production malware scanning
- production encryption key management
- heavy RAG or vector database
- production LLM contract analysis
- browser offline mutation queue
- background sync replay
- real smart-glasses integration changes

## 6. Functional Requirements

```text
REQ-DOC-001: The system must create a first-class document artifact record for each uploaded file accepted by `POST /api/uploads/documents/contract-analysis`.
REQ-DOC-002: The system must assign a stable `artifact_id` and store uploaded files only under a controlled local root derived from the runtime directory.
REQ-DOC-003: The system must sanitize upload filenames and reject unsupported content types and oversize payloads server-side.
REQ-DOC-004: The system must never write raw document text, raw OCR text, image bytes, or base64 document bodies into generic event metadata.
REQ-DOC-005: The system must expose `DELETE /api/document-artifacts/{artifact_id}` for owner-scoped manual deletion.
REQ-DOC-006: The delete endpoint must be idempotent from the client perspective and must mark the artifact lifecycle state even if the underlying blob has already been removed.
REQ-DOC-007: The system must keep uploaded document blobs until analysis reaches a terminal state or the user explicitly deletes the artifact, following the retention policy defined here.
REQ-DOC-008: The system must enforce per-session limits for accepted uploads and active document jobs before queuing additional work.
REQ-DOC-009: The system must expose a read model at `GET /api/users/{user_id}/sessions/{session_id}/feedback-metrics` with aggregated document usefulness metrics.
REQ-DOC-010: The feedback metrics read model must report counts and rates for `useful` and `not_useful` feedback, plus a breakdown by contract finding type.
REQ-DOC-011: The system must provide a local evaluation harness for OCR and deterministic contract analysis with textual fixtures and expected findings.
REQ-DOC-012: The PWA must treat the backend as the authority for document job state and result readiness and must not infer completion client-side.
REQ-DOC-013: The PWA document flow must support upload or text input, enqueue, polling, success, failure, automatic result opening, and refresh-safe history.
REQ-DOC-014: The service worker must not cache document uploads, API mutations, analysis results, or any other sensitive document content.
REQ-DOC-015: The offline PWA shell must remain read-only and must not pretend that document operations can complete offline.
REQ-DOC-016: All upload and job policy blocks must use the `PolicyRejection` contract.
REQ-DOC-017: Reusing an idempotency key with a different payload fingerprint must be rejected with `idempotency_payload_mismatch`.
REQ-DOC-018: Persisted document history must not retain full OCR text or full user-submitted document text after processing.
REQ-DOC-019: Artifact retention must run for every terminal job path, including worker-driven completion and manual job status transitions.
```

## 7. Non-Functional Requirements

- Reliability: document job status and artifact ownership behavior must remain consistent across refreshes when SQLite storage is enabled.
- Privacy: raw sensitive content must be scoped to artifact storage and job payload handling, not copied into generic telemetry.
- Security: all document resources remain server-validated and owner-scoped.
- Maintainability: changes must preserve current Clean Architecture boundaries across `domain`, `application`, and `infrastructure`.
- Modularity: the implementation must support parallel agent delivery with disjoint write scopes wherever possible.
- Offline behavior: degraded mode must be explicit and read-only.
- Local operability: all flows must remain runnable on localhost without additional infrastructure.

## 8. Domain Model

Key concepts:

- `DocumentArtifact`: lifecycle record for an uploaded blob
- `DocumentArtifactBlob`: bytes stored under the runtime upload root
- `DocumentAnalysisJobPayload`: analysis execution inputs and references
- `DocumentAnalysisRecord`: persisted derived analysis result
- `DocumentFeedbackMetrics`: session-level read model derived from events and analyses
- `DocumentQualityCase`: eval fixture describing an input and expected findings

Suggested artifact model:

```text
artifact_id
user_id
session_id
original_filename
safe_filename
content_type
byte_size
sha256
storage_key
status: active | deleted | expired
created_at
expires_at
deleted_at
linked_job_id
```

Invariants:

- artifact ownership must always match the job and session that reference it
- file paths must always resolve under the runtime uploads root
- event metadata may carry references and structured counters, not raw sensitive payloads
- a job may reference at most one primary uploaded artifact in this MVP
- artifact deletion must not delete a persisted `DocumentAnalysisRecord`
- persisted `DocumentAnalysisRecord` may keep summary, findings, excerpts, confidence, and parsing notes, but must not keep full OCR text or full raw submitted document text
- idempotent retries must compare payload fingerprints before reusing an existing job

## 9. API / Port / Contract

Primary endpoint contracts:

### `PolicyRejection`

All quota, upload-policy, idempotency, and retention blocks return a stable rejection detail:

```json
{
  "detail": {
    "code": "session_active_job_limit_exceeded",
    "message": "This session already has document analyses in progress. Wait for one to finish before sending another document.",
    "reason": "quota_exceeded",
    "scope": "session",
    "limit": 5,
    "current": 5,
    "retryable": true,
    "metadata": {
      "source_type": "pwa_multipart_upload"
    }
  }
}
```

The application contract lives in `new_era.application.use_cases.policy_rejection.PolicyRejection`. HTTP adapters may wrap it in `HTTPException`, but must not invent another response shape.

### `POST /api/uploads/documents/contract-analysis`

Returns the existing `JobResponse` shape with additional metadata fields:

```json
{
  "job_id": "job_123",
  "status": "queued",
  "metadata": {
    "artifact_id": "artifact_123",
    "artifact_label": "contract-photo.jpg",
    "source_type": "pwa_multipart_upload",
    "payload_fingerprint": "sha256:abcd..."
  }
}
```

### `DELETE /api/document-artifacts/{artifact_id}`

```json
{
  "artifact_id": "artifact_123",
  "status": "deleted",
  "deleted_at": "2026-05-25T10:00:00+00:00"
}
```

Errors:

- `404 artifact_not_found`
- `409 artifact_delete_blocked` only if the implementation chooses to block deletion while a job is actively using the blob

Default MVP decision:

- prefer delete success plus lifecycle marking once the system can safely remove the blob after terminal-state analysis

### `GET /api/users/{user_id}/sessions/{session_id}/feedback-metrics`

```json
{
  "user_id": "demo-documents-user",
  "session_id": "demo-documents-session",
  "analysis_count": 8,
  "feedback_count": 5,
  "useful_count": 3,
  "not_useful_count": 2,
  "usefulness_rate": 0.6,
  "feedback_coverage_rate": 0.625,
  "by_finding_type": [
    {
      "finding_type": "automatic_renewal",
      "finding_count": 4,
      "useful_count": 3,
      "not_useful_count": 1,
      "usefulness_rate": 0.75
    }
  ],
  "friction_signals": {
    "repeated_not_useful_count": 1,
    "low_confidence_not_useful_count": 1,
    "no_finding_not_useful_count": 0
  }
}
```

Optional internal endpoint:

- `GET /api/users/{user_id}/sessions/{session_id}/document-quality-summary`

This endpoint is allowed only if the eval harness output is promoted into a stable read model later. It is not required for the first implementation batch.

Current ports in this area:

```text
DocumentArtifactStore
DocumentArtifactBlobStore
```

Current use cases in this area:

```text
StoreDocumentArtifact
DeleteDocumentArtifact
GetDocumentFeedbackMetrics
ExpireDocumentArtifacts
EnforceDocumentSessionQuota
```

## 10. Events and Observability

Required events:

- `document_uploaded`
- `document_deleted`
- `document_retention_expired`
- `upload_rejected`
- `feedback_metric_computed`
- `ocr_quality_evaluated`
- `rate_limit_exceeded`

Metadata allowlist guidance:

- `artifact_id`
- `analysis_id`
- `job_id`
- `job_type`
- `finding_type`
- `source_type`
- `content_type`
- `byte_size`
- `sha256_prefix`
- `payload_fingerprint`
- `error_code`
- `limit_scope`
- `limit_value`
- `current_value`
- `reason`
- `status`

Metadata forbidden in generic events:

- raw document bytes
- base64 image bodies
- full OCR text
- raw document text
- nested `extracted_text` values containing full document text
- absolute file system paths
- secrets or tokens

Observability notes:

- `feedback_metric_computed` is optional in the first pass if metrics are derived on read and the extra event would only create noise
- `ocr_quality_evaluated` should be emitted by the local eval harness only if that output is intentionally persisted

## 11. Data Classification and Privacy

Data processed:

- uploaded contract files
- OCR extracted text
- user-submitted contract text
- derived findings and summaries
- feedback and session history

Classification:

- uploaded contract files: sensitive personal
- OCR extracted text: sensitive personal
- user-submitted contract text: sensitive personal
- derived findings and summaries: sensitive personal
- session and feedback aggregates: internal plus user-scoped personal product data

Retention defaults:

- uploaded artifact blobs: keep until analysis reaches a terminal state, then remove the blob and mark the artifact `expired`
- document artifact lifecycle records: keep until manual reset
- persisted analysis records: keep for local session history until manual reset, but keep only summaries, findings, excerpts, confidence, and parsing notes
- job payload raw content: delete when the analysis job reaches a terminal state

Raw text persistence decision:

```text
Do not persist full OCR text or full user-submitted document text as durable history.
The MVP may persist short finding excerpts because they are the product evidence users need.
```

Consent stance:

- localhost MVP uses explicit user action as the trigger for processing
- no background document capture or automatic upload is allowed

## 12. Security Requirements

- all ownership checks remain server-side
- upload content type and size must be validated before persistence
- upload paths must be normalized and constrained under the runtime upload root
- delete requests must verify artifact ownership against the authenticated user
- quotas must be enforced server-side by session and user scope
- generic events must keep forbidden sensitive content out of metadata
- service worker caching must exclude all document-sensitive routes

MVP local quotas:

```text
accepted uploads per session: 20
active document jobs per session: 5
```

These limits are local defaults and may later move to configuration.

Idempotency:

```text
same idempotency_key + same payload_fingerprint -> return the existing job
same idempotency_key + different payload_fingerprint -> reject with 409 idempotency_payload_mismatch
```

The fingerprint must be derived from stable safe inputs. For file uploads, use content type, byte size, and SHA-256 of the uploaded bytes. For text jobs, use source type and SHA-256 of the submitted text. Events may include only the fingerprint or a prefix, never the raw payload.

Local concurrency:

```text
Quota checks should use a per-session lock in the local runtime.
SQLite may use a short transaction or be documented as localhost best effort until production storage exists.
```

## 13. Performance Budget

```text
Target upload acceptance latency: under 250 ms excluding OCR or job execution
P95 upload acceptance latency: under 750 ms on localhost
Target job status poll latency: under 150 ms on localhost
Max upload payload: 7.5 MB
Expected request volume: single-user localhost and manual QA
Cost budget: local CPU only, no external paid provider required
Async boundary: OCR and document analysis jobs remain async when enqueued
```

Frontend polling guidance:

- default interval: 1000 ms
- stop on terminal state
- show explicit degraded state if polling fails

## 14. Failure Modes

| Failure | Expected behavior | Event/metric |
| --- | --- | --- |
| Unsupported upload MIME type | Reject request with safe error | `upload_rejected` |
| Upload too large | Reject request with safe error | `upload_rejected` |
| Session exceeds upload quota | Reject request | `rate_limit_exceeded` |
| Session exceeds active job quota | Reject request | `rate_limit_exceeded` |
| Same idempotency key with different payload | Reject request with conflict | `upload_rejected` |
| Missing job payload | Fail job cleanly | existing job failure events |
| OCR or analysis timeout | Fail job with safe error state | existing job failure events |
| Artifact already deleted | Delete endpoint remains idempotent | `document_deleted` optional |
| Job reaches terminal state | Expire linked raw artifact blob | `document_retention_expired` |
| Offline PWA mutation attempt | UI blocks the action and shows offline read-only state | frontend state only |
| Eval fixture mismatch | Eval runner reports false positive or false negative clearly | local eval output |

Error matrix:

| Case | HTTP | Code | Event | PWA message | Event metadata |
| --- | ---: | --- | --- | --- | --- |
| Unsupported MIME type | 415 | `unsupported_upload_content_type` | `upload_rejected` | Use PNG, JPEG, or WebP. | `content_type`, `source_type`, `error_code` |
| Empty upload | 422 | `upload_file_empty` | `upload_rejected` | The selected file is empty. | `source_type`, `error_code` |
| Payload above policy | 413 | `upload_payload_too_large` | `upload_rejected` | The file is above the local upload limit. | `byte_size`, `limit_value`, `source_type`, `error_code` |
| Session upload quota full | 429 | `session_upload_quota_exceeded` | `rate_limit_exceeded` | This session reached the upload limit. | `current_value`, `limit_value`, `limit_scope`, `error_code` |
| Session active jobs full | 429 | `session_active_job_limit_exceeded` | `rate_limit_exceeded` | Wait for an analysis to finish before sending another document. | `current_value`, `limit_value`, `limit_scope`, `error_code` |
| Idempotency payload mismatch | 409 | `idempotency_payload_mismatch` | `upload_rejected` | This retry does not match the original upload. Start a new upload. | `job_id`, `source_type`, `error_code` |

## 15. AI/Prompt Contract

This spec does not introduce a new LLM contract.

Relevant local AI-like workflow:

```text
Prompt version: n/a
Objective: evaluate deterministic analysis plus OCR quality locally
Trusted inputs: local fixture definitions
Untrusted inputs: OCR text and user document text
Output schema: expected findings versus observed findings
Safety limits: no legal advice claims beyond current derived analysis behavior
Fallback behavior: report missing or weak evidence instead of inventing findings
Eval cases: safe contract, automatic renewal, cancellation fee, minimum commitment, fees/interest, blurry OCR
```

## 16. Acceptance Criteria

- AC-DOC-001: a successful multipart upload produces a stable `artifact_id`
- AC-DOC-002: uploaded files are stored only under `.new_era/uploads/documents` relative to the runtime root
- AC-DOC-003: filename sanitization prevents path traversal and unsafe path segments
- AC-DOC-004: no generic event metadata contains raw document text, OCR text, image bytes, or base64 payloads
- AC-DOC-005: `DELETE /api/document-artifacts/{artifact_id}` works for the owner and is refresh-safe
- AC-DOC-006: raw job payload content is removed after terminal job completion
- AC-DOC-007: `GET /api/users/{user_id}/sessions/{session_id}/feedback-metrics` returns aggregate metrics and finding-type breakdowns
- AC-DOC-008: the eval harness runs locally and reports expected findings, false positives, and false negatives
- AC-DOC-009: the PWA performs automatic polling and opens the result view when a document job succeeds
- AC-DOC-010: the document history remains readable after refresh when persistence is enabled
- AC-DOC-011: the service worker does not cache API POSTs, uploads, or sensitive document reads
- AC-DOC-012: `python -m unittest discover` and `python .\tools\validate_local.py` continue to pass

## 17. Test and Eval Plan

- unit tests for artifact lifecycle and path safety
- unit tests for delete semantics and ownership checks
- unit tests for session quota enforcement
- unit tests for feedback metrics aggregation
- unit tests for service worker or HTTP smoke expectations where practical
- unit tests for eval harness runner and fixture scoring
- local smoke tests for upload, polling, result opening, feedback, and delete
- privacy tests asserting event metadata does not leak forbidden document fields

Validation commands:

```powershell
$env:PYTHONPATH='src'; python -m unittest discover
$env:PYTHONPATH='src'; python .\tools\validate_local.py
$env:PYTHONPATH='src'; python .\tools\evaluate_document_analysis.py
```

## 18. Rollout Plan

Completed:

- artifact lifecycle and quotas
- feedback metrics read model
- eval harness
- service worker and manifest hardening
- runtime and HTTP integration
- unit-test coverage for the hardening pass

Still to finish:

- local bootstrap validation coverage at the same confidence level
- manual mobile/PWA checklist refresh
- broader production-oriented auth and observability follow-through

## 19. Open Questions

1. Should delete be allowed while a job is still running if the runner has already loaded the blob into memory?
2. Should artifact lifecycle records persist after delete for auditability in localhost mode, or should local reset be the only durable cleanup story?
3. Should session quotas become environment-configurable in this batch or stay hard-coded until after the MVP hardening lands?
4. Should SQLite enforce active-job quota atomically in this batch, or should production-grade atomic quota enforcement wait for the next persistence hardening spec?
