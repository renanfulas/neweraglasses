# Architecture Overview

## Purpose

New Era Glasses is being developed as a local-first MVP for contextual assistance through smart glasses workflows.

The current architectural target is:

```text
Observation -> Interpretation -> Attention Decision -> Lens Command -> Session/Event Trace
```

## Current Localhost Shape

The workspace indicates these main subsystems:

- `observations`: world input normalized into domain observations
- `attention`: central policy for whether something should interrupt the user
- `documents`: contract and document review flows
- `jobs`: async-style document processing lifecycle
- `sessions`: local user/session continuity
- `http`: backend and PWA entrypoint
- `feedback`: lens feedback capture for future ranking and attention tuning

## Runtime Defaults

- Local host: `127.0.0.1`
- Local port: `8000`
- Runtime directory: `.new_era/`
- Local database: `.new_era/runtime.sqlite3`

`.new_era/` is considered ephemeral local runtime state and must remain out of version control.

## Product Flow

The intended product flow for the current MVP is:

1. A user action creates an `Observation`.
2. The system interprets whether an alert candidate exists.
3. `AttentionPolicy` decides whether to suppress or deliver.
4. A `LensCommand` is produced for the UI or glasses surface.
5. The session and event history record what happened.
6. Document analysis may also produce a persisted `analysis_id`.
7. Async document jobs may eventually point at that persisted analysis.
8. Lens feedback can be recorded against delivered commands.

## Current Gaps

The repository is not yet in a fully reproducible state.

Known gaps:
- source files are not yet safely versioned in the current repo snapshot
- runtime artifacts currently carry part of the observable system state
- bootstrap is documented, but full dependency truth still needs to be locked in source control
- repository docs still lag the richer runtime surface inferred from bytecode inspection

## Near-Term Technical Priorities

1. Recover and version the real Python source tree.
2. Keep the local runtime predictable and disposable.
3. Preserve a small but canonical set of docs in the repository.
4. Recover the confirmed runtime surface into maintained Python source.
5. Resume MVP delivery only after the local foundation is recoverable.
