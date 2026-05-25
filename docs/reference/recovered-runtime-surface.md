# Recovered Runtime Surface

## Purpose

This document captures the runtime surface inferred from local Python bytecode inspection.

It is not a substitute for restored source files.
It is a temporary architectural reference so ongoing planning stays aligned with the actual system behavior present in the workspace.

## Confirmed application areas

Recovered from `new_era.infrastructure.http.app` and related runtime modules:

- grocery simulation endpoints
- document contract review endpoints
- camera-based contract review request model
- device capability serialization
- document analysis job enqueue/status/result endpoints
- lens feedback recording
- user session creation and listing

## Confirmed backend composition

Recovered from `new_era.application.services.simulation_runtime`:

- in-memory and SQLite-backed event stores
- in-memory and SQLite-backed session stores
- in-memory document analysis store
- in-memory document job payload store
- threaded document analysis worker
- browser simulation device adapter
- HTTP device bridge adapter
- OCR adapter
- contract analyzer
- job execution policy

## Confirmed async job shape

Recovered from `new_era.application.use_cases.document_analysis_jobs`:

- enqueue document analysis job
- read job status
- advance job status
- run document analysis job
- timeout-aware execution path
- persisted job payload support
- persisted document analysis result support

## Planning implication

The current system is ahead of the repository narrative.

That means the technical plan should now assume:
- sessions already exist as a first-class concept
- feedback already exists as a first-class concept
- async document execution already exists beyond a simple status mock
- local persistence already has at least partial SQLite intent

## Recovery priority

Source restoration should prioritize:

1. `new_era.infrastructure.http.app`
2. `new_era.application.services.simulation_runtime`
3. `new_era.application.use_cases.document_analysis_jobs`
4. `new_era.application.use_cases.user_sessions`
5. `new_era.application.use_cases.record_lens_feedback`
