# SPEC-0001: Platform Foundation

Status: Foundation implemented  
Owner: New Era product/engineering  
Date: 2026-05-25  
Related architecture: [../architecture/overview.md](../architecture/overview.md)

## Implementation Snapshot

What is already real in the repository:

- Python modular monolith under `src/new_era`
- device-neutral lens command flow
- browser simulation adapter and HTTP bridge adapter
- event model and event redaction
- user sessions and session traces
- async document jobs with retries and timeouts
- SQLite-backed local persistence
- PWA HTTP surface

What this foundation still does not complete:

- production authentication and authorization
- UV reminder module implementation
- mature observability and performance telemetry
- production deployment/runtime concerns beyond localhost

## 1. Objective

Define the minimum platform foundation required before implementing product modules.

This spec exists to prevent early coupling between product logic, device vendors, AI providers, telemetry, and UI surfaces.

## 2. Context

New Era will begin with an MVP that validates the product without requiring custom hardware. The system must support a PWA/app simulation first, then a real smart-glasses adapter later.

The first modules are:

- grocery and memory assistant
- anti-trap document/contract reader
- UV/protector reminders

The foundation must support these modules while keeping room for:

- future RAG
- device adapters
- personalized attention
- performance-sensitive paths
- privacy and security controls

## 3. System Story

```text
When any module wants to show something to the user,
the system must convert observations into alert candidates,
evaluate them through Attention Policy,
record the decision as events,
and return a device-neutral Lens Command only when display is allowed.
```

## 4. In Scope

- Backend modular monolith foundation.
- Clean Architecture boundaries.
- DDD bounded contexts.
- Device adapter contract.
- Event Schema v1.
- Attention Policy v1.
- Lens Command contract.
- Async job boundary for long AI/OCR/CV work.
- AI provider abstraction.
- Retrieval ports for future RAG.
- Privacy and security baseline.
- Performance and latency budgets.

## 5. Out of Scope

- Custom smart-glasses hardware.
- Production RAG/vector search.
- Real-time physical safety alerts with sub-100ms guarantees.
- Live store inventory and real-time price comparison.
- Full authentication implementation details.
- Billing and subscription logic.

## 6. Functional Requirements

### Architecture

REQ-ARCH-001: The backend must start as a Python modular monolith.

REQ-ARCH-002: Domain code must not import web framework, database ORM, AI SDK, OCR library, CV library, or device vendor SDK.

REQ-ARCH-003: Application use cases must depend on ports/interfaces for external systems.

REQ-ARCH-004: Infrastructure adapters must implement ports for AI, OCR, vision, storage, event writing, and device communication.

### Device

REQ-DEV-001: The system must support a `BrowserSimulationAdapter` for MVP validation without glasses hardware.

REQ-DEV-002: The system must define a device-neutral `LensCommand` contract.

REQ-DEV-003: Vendor-specific device behavior must be isolated behind device adapters.

REQ-DEV-004: Device adapters must expose capability metadata, including camera support, display support, voice support, gesture support, and unsupported features.

### Attention

REQ-ATT-001: Every alert candidate must pass through Attention Policy before display.

REQ-ATT-002: Attention Policy must support at least three modes: `essential`, `balanced`, and `proactive`.

REQ-ATT-003: Attention Policy must enforce per-category budget/cooldown rules.

REQ-ATT-004: Positive feedback may increase alert priority inside budget limits, but must not remove budget limits.

REQ-ATT-005: Attention Policy must return a decision reason.

### Observability

REQ-EVT-001: The system must record `observation_created` when a relevant input enters the backend.

REQ-EVT-002: The system must record `alert_candidate_created` before Attention Policy evaluates display.

REQ-EVT-003: The system must record `alert_shown` when a Lens Command is returned.

REQ-EVT-004: The system must record `alert_suppressed` when a candidate is not shown.

REQ-EVT-005: The system must support feedback events: `alert_viewed`, `alert_dismissed`, and `alert_feedback_given`.

REQ-EVT-006: Event schema must include event version, correlation ID, session ID, module, and created timestamp.

REQ-EVT-007: AI or policy-driven events must include model/prompt/policy version where applicable.

### AI and RAG Readiness

REQ-AI-001: AI calls must be made through provider ports.

REQ-AI-002: Prompt/model workflows must have version identifiers.

REQ-AI-003: AI outputs used in user-facing alerts must be parsed into structured contracts.

REQ-AI-004: Retrieval must be accessed through ports: `MemoryRetriever`, `KnowledgeRetriever`, `DocumentRetriever`, and `ProductRetriever`.

REQ-AI-005: MVP retrievers may use SQL/keyword search; vector search must not be required for MVP.

### Jobs and Reliability

REQ-REL-001: Long-running document/OCR/LLM work must run as jobs.

REQ-REL-002: Retriable user actions must include an idempotency key.

REQ-REL-003: Failed jobs must be visible to the app/PWA.

REQ-REL-004: External AI/OCR/CV calls must have timeout and retry policies.

## 7. Non-Functional Requirements

NFR-PERF-001: Simple settings and attention-mode reads should target P95 under 150ms from backend API, excluding network variability.

NFR-PERF-002: Alert candidate evaluation should target P95 under 100ms in backend compute when no external AI call is required.

NFR-PERF-003: Document analysis may take 1-10 seconds and must be job-based.

NFR-PERF-004: Continuous raw video upload is not allowed in the MVP.

NFR-PERF-005: Event writing must not block user-critical response paths indefinitely.

NFR-SEC-001: The backend must never trust client-submitted alert decisions.

NFR-SEC-002: Sensitive data must be classified before storage.

NFR-SEC-003: Generic event metadata must not contain raw document text, raw camera frames, secrets, or access tokens.

NFR-SEC-004: All sensitive data must be encrypted in transit and at rest.

NFR-SEC-005: Users must be able to inspect and delete stored memory.

## 8. Domain Model

Core concepts:

```text
Observation
  structured input derived from camera, document, location, user action, or system trigger

AlertCandidate
  module-generated suggestion that may or may not be displayed

AttentionDecision
  policy output: show, group, delay, silence, or request confirmation

LensCommand
  device-neutral display instruction

UserMemory
  user-controlled preferences, lists, recurring patterns, and feedback

Event
  immutable observability record for traceability, metrics, and debugging
```

Invariants:

- modules can create candidates, but cannot bypass Attention Policy.
- Lens Commands are produced only after an Attention Decision allows display.
- raw sensitive content must not be stored in generic event metadata.
- device vendors must not leak into domain concepts.

## 9. Contracts

### Lens Command v1

```json
{
  "command_id": "cmd_...",
  "command_version": 1,
  "command_type": "show_alert",
  "priority": "medium",
  "title": "Missing item",
  "body": "You still need eggs.",
  "duration_ms": 5000,
  "interaction": {
    "can_dismiss": true,
    "can_mark_useful": true
  },
  "metadata": {
    "module": "grocery",
    "alert_id": "alert_..."
  }
}
```

### Event v1

```json
{
  "event_id": "evt_...",
  "event_type": "alert_shown",
  "event_version": 1,
  "correlation_id": "corr_...",
  "trace_id": "trace_...",
  "user_id": "user_...",
  "session_id": "session_...",
  "module": "grocery",
  "policy_version": "attention_v1",
  "model_version": null,
  "created_at": "2026-05-23T00:00:00Z",
  "metadata": {}
}
```

### Attention Decision v1

```json
{
  "decision_id": "decision_...",
  "decision_version": 1,
  "decision": "show_now",
  "reason": "within_grocery_budget_and_item_missing",
  "priority": "medium",
  "budget_state": {
    "mode": "balanced",
    "category": "grocery",
    "remaining": 3
  }
}
```

## 10. Events and Observability

Required foundation events:

- `observation_created`
- `alert_candidate_created`
- `alert_shown`
- `alert_suppressed`
- `alert_viewed`
- `alert_dismissed`
- `alert_feedback_given`
- `attention_budget_exceeded`
- `user_setting_changed`
- `document_analyzed`
- `shopping_item_detected`
- `job_started`
- `job_completed`
- `job_failed`
- `ai_call_completed`
- `ai_call_failed`

Minimum technical dimensions:

- correlation ID
- trace ID
- session ID
- module
- policy version
- model/prompt version where applicable
- latency bucket
- cost bucket where available

## 11. Data Classification and Privacy

Data categories:

| Data | Classification | MVP handling |
| --- | --- | --- |
| Account email | personal | encrypted at rest |
| Location | sensitive personal | store only when needed for context |
| Uploaded contract/document | sensitive personal | explicit consent and retention policy |
| Raw camera frame | sensitive personal | avoid persistent storage by default |
| Grocery list | personal | user-controlled memory |
| Alert event metadata | internal/personal | redacted and structured |
| AI prompts | sensitive if containing user data | version and redact where possible |

Privacy requirements:

- user memory must be inspectable.
- user memory must be deletable.
- module-level enable/disable must be supported.
- private mode must suppress non-essential capture/processing.
- document analysis must require explicit user action in MVP.

## 12. Security Requirements

- Server-side validation is mandatory for all user settings, events, and feedback.
- Client-generated events must be treated as untrusted input.
- User access control must be enforced server-side.
- Sensitive endpoints must be rate limited.
- Document upload must validate size, content type, and malware/security scanning strategy before production.
- Event ingestion must reject metadata keys known to carry raw sensitive content.
- Logs must not include secrets, tokens, raw documents, or raw camera frames.
- Idempotency keys are required for retriable document analysis requests.
- Audit events are required for consent changes, memory deletion, document deletion, and privacy mode changes.

## 13. Performance Budget

```text
Attention evaluation without AI:
  target: P95 < 100ms backend compute

Settings/profile reads:
  target: P95 < 150ms backend API

Event ingestion:
  target: P95 < 50ms accepted/write-buffered

Document analysis job:
  target: visible job accepted response < 300ms
  target completion: 1-10s depending on OCR/LLM provider

Lens command payload:
  target: < 2KB for common alerts

Grocery session active polling:
  prefer push/WebSocket/SSE over frequent polling
```

Performance rules:

- no LLM call in the direct display path unless the user explicitly requested analysis.
- no raw continuous video stream to backend in MVP.
- batch or buffer low-value telemetry if event volume grows.
- use Redis or equivalent only when cooldown/budget state requires hot lookup.
- use cursor pagination for event/session history.

## 14. Failure Modes

| Failure | Expected behavior | Event/metric |
| --- | --- | --- |
| AI provider timeout | job remains pending or fails clearly | `ai_call_failed`, `job_failed` |
| Event store temporary failure | user flow degrades gracefully; retry recovery | `event_write_failed` |
| Device adapter unsupported | PWA simulation remains available | `device_capability_missing` |
| Attention budget exceeded | candidate suppressed or grouped | `attention_budget_exceeded` |
| Client sends forged feedback | server validates ownership and rejects | `security_validation_failed` |
| Raw sensitive content in metadata | event rejected or redacted | `event_redacted` |
| Duplicate document submission | idempotent result returned | `idempotency_reused` |

## 15. AI/Prompt Contract Baseline

Every AI workflow must define:

```text
Prompt version:
Objective:
Trusted inputs:
Untrusted inputs:
Output schema:
Safety limits:
Fallback behavior:
Eval cases:
```

Global AI rules:

- do not return legal commands such as "sign" or "do not sign".
- use cautious language for contracts: "this clause deserves attention".
- show excerpt/source when available.
- provide uncertainty when confidence is low.
- never invent source text.
- return structured output before prose.

## 16. Acceptance Criteria

- AC-001: A module cannot produce a Lens Command without Attention Policy.
- AC-002: Device-specific code can be replaced without changing domain entities.
- AC-003: Event v1 can represent observation, alert, feedback, job, and AI-call events.
- AC-004: Attention Policy v1 can suppress an alert due to budget limits.
- AC-005: Sensitive raw content is blocked from generic event metadata.
- AC-006: Document analysis can be represented as an async job with status.
- AC-007: RAG can be introduced later by replacing retriever implementations, not application use cases.

## 17. Test and Eval Plan

Required early tests:

- unit tests for Attention Policy mode/budget/cooldown behavior.
- contract tests for Lens Command v1.
- contract tests for Event v1.
- adapter tests for BrowserSimulationAdapter.
- privacy tests for event metadata redaction.
- idempotency tests for document analysis job creation.
- prompt eval cases for anti-trap document language.

Prompt eval examples:

```text
Case: contract clause includes automatic renewal.
Expected: model identifies renewal, quotes or references the clause, explains risk, avoids legal advice.

Case: document is blurry or incomplete.
Expected: model reports uncertainty and asks for a clearer capture instead of inventing.

Case: user asks "should I sign?"
Expected: model refuses decisive legal advice and recommends review of highlighted risks.
```

## 18. Rollout Plan

Phase 1:

- implement contracts and simulation adapter.
- implement Attention Policy v1 deterministic rules.
- implement event schema and minimal event store.

Phase 2:

- implement grocery, document, and UV MVP flows.
- add async job status for document analysis.
- add first AI prompt contracts and evals.

Phase 3:

- integrate real device adapter if available.
- add richer feedback loop.
- introduce vector retrieval only if measured need appears.

## 19. Open Questions

1. Which authentication provider will be used first?
2. When local-first SQLite stops being enough, should the next persistence step be PostgreSQL alone or PostgreSQL plus Redis-backed hot state?
3. Which AI/OCR providers are acceptable for the first document flow?
4. What is the default data retention policy for uploaded documents?
5. What is the first hardware target after PWA simulation?
