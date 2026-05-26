# Spec-Driven Development

Status: Active process  
Last updated: 2026-05-25

## Purpose

New Era still uses specs to keep product behavior, architecture, privacy, and delivery aligned before code drifts.

The difference now is that the repo already has meaningful implementation, so spec status must be explicit:

- what is implemented
- what is partially implemented
- what is still open

## Delivery Loop

```text
problem -> spec -> design -> tasks -> implementation -> tests -> telemetry
```

## Spec Lifecycle Used In This Repo

- `Planned`: not started in code
- `In progress`: partially implemented, still driving active work
- `Mostly implemented`: core flow exists, but meaningful gaps remain
- `Foundation implemented`: broad base exists, but some modules or production concerns remain open
- `Template`: reusable authoring scaffold

## Active Spec Index

| Spec | Status | What progressed | What still lacks |
| --- | --- | --- | --- |
| [0001-platform-foundation.md](0001-platform-foundation.md) | Foundation implemented | modular monolith, device gateway, jobs, sessions, eventing, PWA HTTP surface | production auth, UV module, production observability depth |
| [0002-pwa-shell.md](0002-pwa-shell.md) | Mostly implemented | grocery shell, document shell, service worker, manifest, history and job UX | auth UX, offline mutation queue, browser E2E, push/install polish |
| [0003-document-mvp-hardening.md](0003-document-mvp-hardening.md) | In progress | artifacts, quotas, retention, feedback metrics, eval harness, offline guardrails | validate_local coverage, more UX polish, broader ops/security follow-through |
| [0004-auth-boundary.md](0004-auth-boundary.md) | In progress | cookie session boundary, current-user dependency, auth bootstrap endpoints, dev-auth gate | durable production-grade auth UX, full browser hardening, broader auth coverage |
| [spec-template.md](spec-template.md) | Template | reusable structure for future specs | no action needed |

## Current Working Rule

If a spec says something that the code and tests clearly contradict, the runtime wins and the spec must be updated.

## What Changed Recently

The repo is no longer in pure foundation mode. Specs now need to describe partial completion and remaining work, not just target-state design.
