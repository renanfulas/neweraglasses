# Performance and Latency Architecture

Status: Active reference  
Last updated: 2026-05-25

## Purpose

Capture the current performance posture of the repo and make clear which parts are architectural truth versus future measurement work.

## Latency Classes

The current system still fits three latency classes:

```text
Class A: immediate policy path
  deterministic backend compute

Class B: interactive HTTP path
  user-driven reads/writes and lens preview

Class C: analysis path
  OCR/document analysis jobs
```

## Current Architectural Wins

Already in place:

- document analysis is async
- expensive work is off the primary attention path
- retries and timeouts exist for document jobs
- session-level quotas prevent unbounded local queue growth
- PWA offline mode is read-only for sensitive operations

These are structural wins even before we have richer telemetry.

## Current Runtime Reality

This repo currently runs with:

- in-memory stores for tests and quick simulation
- SQLite for local-first durability
- a threaded in-process document worker

It does not yet have:

- distributed workers
- load-tested queue behavior
- production latency dashboards
- formal SLO instrumentation

## Path-by-Path Posture

### Grocery simulation path

Fast and synchronous by design.

Current gap:

- no browser-level latency assertions

### Document enqueue path

Fast acceptance path with server-side validation, idempotency, and policy rejection.

Current gap:

- no measured P95 budget published from telemetry

### Document analysis path

Correctly modeled as async.

Current gap:

- no queue-time metrics or throughput reporting yet

### History/read-model path

Usable today with SQLite-backed reads.

Current gap:

- no query/size benchmarks for large local histories

## What Progressed

The document hardening pass improved performance safety by adding:

- active-job limits per session
- rejection before local queue growth
- result/history survival even after raw artifact expiration
- explicit blocking reasons for the UI

That is not raw speed, but it is important performance hygiene.

## What Still Needs Work

1. Add timing telemetry around enqueue, worker runtime, and result lookup.
2. Add a small load or concurrency harness for local queue behavior.
3. Add browser performance checks for the PWA document flow.
4. Revisit read models once local history volume grows.

## Current Bottom Line

The architecture is performance-aware.

The measurement program is not mature yet.
