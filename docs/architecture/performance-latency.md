# Performance and Latency Architecture

Status: Draft v1  
Date: 2026-05-23  
Related spec: [../specs/0001-platform-foundation.md](../specs/0001-platform-foundation.md)

## 1. Purpose

This document defines the first performance posture for New Era.

New Era is latency-sensitive because the product displays information near the user's field of view. A slow response is not just a technical issue; it can break trust, increase annoyance, and make the product feel intrusive.

The performance goal is not to optimize everything early. The goal is to classify paths correctly so expensive work never blocks fast interaction paths.

## 2. Performance Thesis

New Era has three latency classes:

```text
Class A: Immediate path
  0-100ms backend compute target
  deterministic, no external AI calls

Class B: Interactive path
  100-800ms end-to-end target where possible
  may use cached context or lightweight processing

Class C: Analysis path
  1-10s or more
  async jobs, visible progress, retryable
```

The MVP should avoid promising Class A physical safety behavior until hardware and local runtime can guarantee it.

## 3. Critical Paths

### Attention Decision Path

```text
alert candidate -> context lookup -> budget/cooldown check -> decision -> event -> lens command
```

Target:

- P95 backend compute under 100ms.
- no LLM call.
- no heavy OCR/CV.
- no slow external network dependency.

Risk:

- if this path calls AI, the glasses feel slow.
- if this path writes too much telemetry synchronously, alerts become laggy.

Mitigation:

- keep Attention Policy deterministic in MVP.
- use hot budget state when needed.
- write events with short timeout or buffered path.
- keep Lens Command payload small.

### Document Analysis Path

```text
document upload/capture -> job accepted -> OCR -> AI analysis -> structured findings -> user review
```

Target:

- job accepted response under 300ms.
- analysis completion 1-10s depending on provider and document size.
- clear pending/failed/completed states.

Risk:

- trying to make document analysis synchronous will create timeouts and bad UX.

Mitigation:

- job queue from day one for document flow.
- idempotency key for retriable submissions.
- provider timeouts and retries.
- store partial progress where useful.

### Grocery Session Path

```text
user enters grocery context -> list loaded -> item detected/selected -> missing item alert candidate -> attention policy
```

Target:

- list/settings reads under 150ms backend P95.
- item state updates under 250ms backend P95.
- avoid chatty polling.

Risk:

- frequent client polling drains battery and creates backend noise.
- recognition mistakes can create alert spam.

Mitigation:

- prefer push/WebSocket/SSE for active sessions later.
- cache active shopping session state.
- budget grocery alerts per session.
- batch item state updates when possible.

### UV/Protector Reminder Path

```text
location/time/context -> weather/UV lookup -> reminder candidate -> attention policy
```

Target:

- cached weather/UV responses where possible.
- cooldown-based reminders.

Risk:

- calling weather APIs too frequently wastes money and battery.

Mitigation:

- cache by coarse geolocation and time bucket.
- avoid precise location storage unless required.
- suppress repeated reminders through cooldown.

## 4. First Latency Budgets

| Flow | Target | Notes |
| --- | --- | --- |
| Read user settings | P95 < 150ms backend | cache if needed |
| Update attention mode | P95 < 200ms backend | audit event required |
| Evaluate alert candidate | P95 < 100ms backend compute | no external AI |
| Accept document job | P95 < 300ms backend | returns job ID |
| Complete document analysis | 1-10s typical | async |
| Event ingestion | P95 < 50ms accepted/write-buffered | do not block critical paths indefinitely |
| Lens command payload | < 2KB common alerts | payload diet |

## 5. Payload Diet

Lens commands and event payloads must be compact.

Rules:

- send IDs, not full objects, unless display requires the text.
- avoid raw camera frames in telemetry.
- avoid raw document text in event metadata.
- cap alert body length for lens display.
- use structured enums instead of verbose prose in contracts.
- compress large HTTP payloads where appropriate.

Example Lens Command should remain small:

```json
{
  "command_type": "show_alert",
  "priority": "medium",
  "title": "Missing item",
  "body": "You still need eggs.",
  "duration_ms": 5000
}
```

## 6. Caching Strategy

Cache only where invalidation is clear.

Good MVP candidates:

- user settings
- attention mode
- active grocery list/session
- weather/UV by coarse location/time bucket
- document job status short-lived reads
- device capability metadata

Avoid early:

- caching AI outputs without versioning.
- caching sensitive documents in generic cache.
- caching personalized memory without invalidation.

If Redis is introduced, it should be for:

- hot attention budget state
- cooldown counters
- active sessions
- rate limits
- short-lived job status

## 7. Database Performance Rules

Expected early data store: PostgreSQL.

Rules:

- design indexes from access patterns, not guesswork.
- use cursor pagination for event/session history.
- do not query raw event history for every user-facing page.
- introduce read models/snapshots only after repeated expensive reads appear.
- batch insert low-value telemetry if event volume grows.

Likely early indexes:

```text
events(user_id, created_at)
events(session_id, created_at)
events(correlation_id)
alerts(user_id, created_at)
jobs(user_id, status, created_at)
shopping_items(user_id, list_id, status)
```

## 8. Async and Backpressure

Async boundaries:

- document OCR
- LLM analysis
- embedding generation later
- large image processing
- batch telemetry aggregation

Backpressure rules:

- cap concurrent jobs per user.
- cap document size/pages for MVP.
- rate limit expensive endpoints.
- expose pending state instead of queueing silently.
- degrade gracefully when providers are slow.

## 9. Observability for Performance

Every important flow should emit:

- request latency
- backend compute time
- external provider time
- queue time
- event write time
- payload size bucket
- model/provider version
- cost bucket when available

Recommended trace dimensions:

```text
trace_id
correlation_id
user_id
session_id
module
flow
policy_version
model_version
device_adapter
```

## 10. Performance Anti-Patterns

Avoid:

- LLM calls in the direct alert display path.
- raw continuous video upload to backend in MVP.
- storing raw frames in event metadata.
- unbounded document upload size.
- synchronous audit/event writes with no timeout.
- polling active sessions every few seconds when push can be used later.
- returning full object graphs where the lens needs one sentence.
- adding microservices before measuring independent scaling pressure.

## 11. Performance Validation Plan

Before runtime implementation is considered healthy:

- test Attention Policy with synthetic high-frequency alert candidates.
- test document job creation with duplicate idempotency keys.
- test event ingestion under burst.
- measure payload sizes for Lens Commands.
- measure document analysis queue time separately from provider time.
- track cost per document analysis and active grocery session.

## 12. Performance Decision Summary

New Era should feel fast because the fast path is small, deterministic, and protected.

The important rule:

> Do not make the user wait for deep AI when the system only needs to decide whether to show a small alert.
