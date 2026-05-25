# SPEC-0001 Platform Foundation

## Goal

Create a minimum viable local foundation so the New Era project can keep moving in `localhost` without losing recoverability.

## Scope

This spec covers:
- repository hygiene
- local runtime conventions
- bootstrap documentation
- minimum architecture documentation

This spec does not yet cover:
- staging or production deployment
- cloud persistence
- external auth providers
- mobile or glasses hardware integration

## Decisions

- `localhost` is the official environment for the current phase.
- `.new_era/` is the local runtime directory.
- SQLite is the current local persistence default.
- Runtime databases and logs are ephemeral and must stay out of Git.
- Documentation should stay minimal and operational.

## Acceptance Criteria

- `.gitignore` excludes runtime artifacts, caches, and local logs.
- `README.md` explains how to run and reset the local environment.
- Architecture and spec docs exist in-repo.
- The repository clearly distinguishes source, tests, docs, and local runtime.

## Risks

- The current workspace still needs source recovery/versioning.
- Runtime artifacts currently expose system behavior that source control should own.
- Feature work should not outrun repository recoverability.
