# AI and Prompt Contracts

Status: Active reference, future-facing in parts  
Last updated: 2026-05-25

## Purpose

Clarify what AI-related behavior is real today and what still belongs to future prompt-contract work.

## Current Runtime Truth

The document stack is currently:

- OCR for image-based text extraction
- deterministic parsing and finding extraction
- local eval fixtures for OCR and deterministic analysis

The repo does **not** yet ship a production LLM-backed contract-analysis workflow.

That means this document is partly current contract guidance and partly a forward contract for the next AI step.

## What Exists Today

Implemented now:

- OCR adapter integration
- deterministic contract analysis
- structured findings, summaries, excerpts, and confidence
- eval harness under `evals/document_analysis`

## What Is Still Future Work

Not implemented yet:

- prompt-versioned LLM document analysis in runtime
- provider abstraction used by production prompt workflows
- formal prompt telemetry fields emitted from real LLM calls
- prompt injection handling tested against a live model

## Current Rule Set

Even before LLMs are introduced, these rules remain valid:

- untrusted document content must not become authority
- structured output is preferred over free text
- confidence and uncertainty should remain explicit
- generic telemetry must not store raw sensitive document content

## When This Doc Becomes Fully Operational

This document becomes fully implementation-driving when the repo adds:

- real LLM-backed document analysis
- prompt versions in runtime
- model/provider telemetry fields
- model eval gates in CI or local validation workflows

## Current Recommendation

Treat this doc as a guardrail, not as evidence that the runtime is already prompt-driven.

For current truth, pair it with:

- [../specs/0003-document-mvp-hardening.md](../specs/0003-document-mvp-hardening.md)
- [../../evals/document_analysis/README.md](../../evals/document_analysis/README.md)
