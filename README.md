# New Era Glasses

Local-first foundation for the New Era contextual glasses MVP.

## Current Status

This repository is currently being normalized around a `localhost` workflow.

Observed runtime shape:
- Python backend serving a local PWA shell
- SQLite runtime stored under `.new_era/`
- Domain areas inferred from the current workspace include `observations`, `attention`, `jobs`, `documents`, `sessions`, and `http`

Important limitation:
- The current workspace contains runtime artifacts and Python bytecode caches.
- Source recovery and source versioning remain part of the active foundation work.

## Local Development Defaults

- Host: `127.0.0.1`
- Port: `8000`
- Runtime directory: `.new_era/`
- Local database: `.new_era/runtime.sqlite3`

## Bootstrap

1. Create and activate a virtual environment.
2. Install project dependencies once the Python source and package manifest are fully restored.
3. Export `PYTHONPATH=src` when running tests or the backend directly.

PowerShell shape:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH='src'
python -m unittest discover
python .\tools\validate_local.py
uvicorn new_era.infrastructure.http.app:create_app --factory --host 127.0.0.1 --port 8000
```

## Runtime Notes

- `.new_era/` is local-only and is not versioned.
- Resetting local runtime means stopping the app and removing `.new_era/runtime.sqlite3`.
- Log files in `.new_era/` are disposable local artifacts.

## Documentation

- Architecture overview: `docs/architecture/overview.md`
- Platform foundation: `docs/specs/0001-platform-foundation.md`
- PWA shell spec: `docs/specs/0002-pwa-shell.md`
- Source recovery notes: `docs/reference/source-recovery.md`

## Recovery Tooling

The workspace currently includes Python bytecode caches that can be inventoried while source recovery is in progress.

```powershell
python tools/pyc_inventory.py --pretty
python tools/pyc_disassemble.py <pyc-path> --output <artifact-path>
```

## MVP Direction

Near-term roadmap:
1. Recover and version the real Python source base
2. Lock local bootstrap and test reproducibility
3. Continue the contracts-first MVP path
4. Add durable persistence, auth, upload, worker, result views, feedback, and operational security
