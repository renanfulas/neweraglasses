# SPEC-0002 PWA Shell

## Goal

Define the local PWA shell as the user-facing surface for the current MVP phase.

## Intended Behavior

The PWA should act as the local operator shell for:
- running contextual simulations
- showing lens output
- visualizing session traces
- exposing async document job state
- navigating persisted document analyses

## Backend Relationship

The PWA is not the source of truth.

The backend owns:
- observations
- attention decisions
- jobs
- persisted analyses
- session history

The PWA owns:
- local user interaction
- form submission
- state display
- result navigation

## Local Runtime Assumptions

- The PWA is served by the local backend.
- The local backend runs on `127.0.0.1:8000` by default.
- Session, job, and analysis behavior should remain predictable under local reset.

## Acceptance Criteria

- The PWA can be launched from the local backend.
- The shell reflects backend-driven state, not invented client-only truth.
- The local runtime can be reset without needing manual repo cleanup.
