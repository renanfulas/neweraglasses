# New Era Mobile Text Scanner

Status: first Android POC scaffold  
Backend contract: `POST /api/jobs/documents/contract-analysis`  
Scanner source type: `mobile_text_scanner`

This workspace is intentionally isolated from the validated backend/PWA MVP. It proves the next mobile step:

```text
Android camera/photo -> ML Kit Text Recognition v2 -> normalized text -> existing backend document job
```

The app does not analyze contracts locally. It only extracts text, lets the user review it, and submits the existing backend payload.

## Current Scope

Included:

- Android/Kotlin app scaffold
- ML Kit Text Recognition v2 Latin bundled model
- camera preview capture
- image picker capture
- text normalization and 50,000 character bound
- stable idempotency key from extracted text
- local-dev submission with `X-New-Era-User-Id`

Not included yet:

- production native auth
- Gradle wrapper
- result polling UI
- multi-page scanning
- ML Kit Document Scanner UI
- real device validation results

## Run Backend For Local POC

From the repository root:

```powershell
$env:PYTHONPATH='src'
$env:NEW_ERA_ENABLE_DEV_AUTH='1'
$env:NEW_ERA_SQLITE_PATH='.new_era/runtime.sqlite3'
python -m uvicorn new_era.infrastructure.http.app:create_app --factory --host 0.0.0.0 --port 8000
```

Use these app backend URLs:

- Android emulator: `http://10.0.2.2:8000`
- physical phone: `http://<your-computer-lan-ip>:8000`

The `Local dev user header` field is for this POC only. It maps to the backend development auth gate and must not be treated as production mobile authentication.

## Build

Open `apps/mobile-text-scanner/` in Android Studio and let it sync the Gradle project.

The local environment used by Codex did not have `gradle` installed, so this scaffold was not compiled in this workspace. The backend contract and scanner simulation remain validated by:

```powershell
$env:PYTHONPATH='src'
python .\tools\validate_local.py --with-e2e --with-scanner-comparison
```

## ML Kit Notes

The POC uses the bundled Latin model:

```kotlin
implementation("com.google.mlkit:text-recognition:16.0.1")
```

That increases app size, but avoids first-run model download uncertainty. The backend payload stays vendor-neutral by sending `source_type="mobile_text_scanner"` instead of an ML Kit-specific adapter name.
