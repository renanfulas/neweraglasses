# Recovery Artifacts

## Purpose

This directory stores reproducible disassembly artifacts for the highest-priority Python modules in the current source recovery effort.

These files are generated from local `.pyc` modules and are meant to support reconstruction of maintained source files.

## Available artifacts

- `http-app.dis.txt`
- `simulation-runtime.dis.txt`
- `document-analysis-jobs.dis.txt`
- `user-sessions.dis.txt`
- `record-lens-feedback.dis.txt`

## Generation

Artifacts are produced with:

```powershell
python tools/pyc_disassemble.py <pyc-path> --output <artifact-path>
```

## Rule

These files are recovery inputs.

They are not the maintained source of truth and should be replaced in importance by restored Python source as recovery progresses.
