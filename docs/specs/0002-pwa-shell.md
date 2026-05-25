# SPEC-0002: PWA Shell and Grocery Simulation

Status: Draft v1  
Owner: New Era product/engineering  
Date: 2026-05-23  
Related architecture: [../architecture/pwa-frontend.md](../architecture/pwa-frontend.md)

## 1. Objective

Define the first PWA shell that lets the team exercise the grocery simulation flow from browser input to backend decision to lens preview.

## 2. Context

The backend now exposes a grocery simulation endpoint and serves static files through FastAPI. The next risk is unstructured frontend growth: API behavior, shell caching, lens preview, and error states could drift if they are not documented now.

This spec keeps the first PWA useful, safe, and intentionally thin.

## 3. User Story

```text
As a team member validating the MVP,
I want to submit a simulated grocery observation in the browser
and immediately see whether the system delivers or suppresses an alert,
so that we can verify the product loop before smart-glasses hardware exists.
```

## 4. In Scope

- root PWA shell
- manifest and service worker shell
- grocery simulation form
- lens preview
- network/loading/error states
- integration with `POST /api/simulations/grocery/missing-item`

## 5. Out of Scope

- real authentication
- document upload flow
- offline write queue
- push notifications
- background sync
- local storage of sensitive user data
- frontend-side alert decision logic

## 6. Functional Requirements

REQ-PWA-001: The PWA must be served from `GET /`.

REQ-PWA-002: The PWA must expose a grocery simulation form.

REQ-PWA-003: The PWA must call `POST /api/simulations/grocery/missing-item` with structured JSON.

REQ-PWA-004: The PWA must render a lens preview from backend `command` data when present.

REQ-PWA-005: The PWA must show a valid suppressed state when no command is returned.

REQ-PWA-006: The PWA must show request error state when the API request fails.

REQ-PWA-007: The PWA must register a service worker if the browser supports it.

REQ-PWA-008: The PWA must expose a web manifest.

## 7. Non-Functional Requirements

NFR-PWA-001: The PWA should avoid heavy frontend dependencies at this stage.

NFR-PWA-002: Static shell assets should be cacheable without caching API POST bodies.

NFR-PWA-003: The frontend must not contain business rules that decide alert suppression or delivery.

NFR-PWA-004: The PWA should remain usable on both desktop and mobile widths.

NFR-PWA-005: Error states must be explicit and understandable.

## 8. Security and Privacy

- No secrets in the frontend bundle.
- No raw sensitive content stored in service worker cache.
- No personal identifiers persisted to browser storage by default.
- Demo identifiers are acceptable in the simulation shell.
- Future document flows must not be added without explicit consent and retention design.

## 9. API Contract

Input:

```json
{
  "user_id": "demo-user",
  "session_id": "demo-session",
  "item_name": "eggs",
  "confidence": 0.88,
  "mode": "balanced",
  "recent_category_count": 0
}
```

Output:

```json
{
  "outcome": "delivered",
  "candidate_created": true,
  "command": {
    "title": "Missing eggs",
    "body": "You still need eggs."
  },
  "event_count": 4,
  "delivered_commands_count": 1
}
```

## 10. Failure Modes

| Failure | Expected behavior |
| --- | --- |
| API unavailable | Show error state and keep shell interactive |
| Suppressed alert | Show suppressed result without fake lens alert |
| Invalid response shape | Treat as error |
| Service worker registration failure | Keep app usable and show non-fatal status |

## 11. Acceptance Criteria

- AC-PWA-001: Opening `/` shows the PWA shell.
- AC-PWA-002: Submitting a valid grocery simulation with high confidence can produce a delivered alert.
- AC-PWA-003: Low-confidence simulation can produce a suppressed outcome with no lens command.
- AC-PWA-004: The service worker does not intercept POST bodies for caching.
- AC-PWA-005: The frontend does not decide whether an alert should be shown.

## 12. Test Plan

- endpoint test for `/`
- endpoint test for `/manifest.webmanifest`
- endpoint test for grocery simulation delivered state
- endpoint test for grocery simulation suppressed state
- manual browser check for mobile/desktop layout

## 13. Open Questions

1. When should we introduce auth into the shell?
2. Do we want a session trace panel with raw event types next?
3. Should the next PWA module be documents or grocery session history?
