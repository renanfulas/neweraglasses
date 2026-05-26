# SPEC-0004: Auth Boundary and Ownership Model

Status: In progress  
Owner: Platform / Companion  
Date: 2026-05-25  
Related architecture:

- [../architecture/auth-boundary.md](../architecture/auth-boundary.md)
- [../architecture/security-implementation.md](../architecture/security-implementation.md)

## 1. Objective

Replace localhost header auth with a real browser companion identity boundary that defines:

- authenticated session
- current user
- ownership checks
- the first MVP auth mechanism

## 2. Context

The runtime already has real owner scoping for sessions, jobs, analyses, artifacts, and feedback. The remaining weakness is not authorization shape. It is the identity input.

Today identity still enters through a local header:

```text
X-New-Era-User-Id
```

That is acceptable for localhost simulation and tests, but it is not a viable product boundary for the companion PWA.

## 3. Decision

The MVP web companion will use a backend-managed authenticated session cookie.

Decision summary:

- choose same-origin cookie session for the PWA
- resolve `current_user` server-side from authenticated identity
- keep the local auth header only as a development-only bootstrap
- defer external provider integration until after the first real auth boundary is stable

## 4. In Scope

- authenticated browser session contract
- current-user resolution contract
- ownership enforcement rules
- auth session bootstrap/read endpoints
- migration away from primary header-based identity
- authorization test matrix for cross-user access

## 5. Out of Scope

- production SSO provider selection
- social login
- billing identity
- device bridge credential redesign
- multi-tenant org model
- account recovery and production email delivery

## 6. Functional Requirements

REQ-AUTH-001: The browser companion must authenticate through a backend-managed session cookie.

REQ-AUTH-002: The backend must resolve an `AuthenticatedIdentity` for authenticated requests.

REQ-AUTH-003: The backend must derive `current_user_id` from `AuthenticatedIdentity`, not from request body values.

REQ-AUTH-004: Mutating browser endpoints must reject requests that attempt to act as a different user than the authenticated identity.

REQ-AUTH-005: User-owned resources must remain server-validated and owner-scoped.

REQ-AUTH-006: The backend must expose `GET /api/auth/session` so the PWA can bootstrap authenticated state.

REQ-AUTH-007: The backend must expose login and logout endpoints for the MVP auth session lifecycle.

REQ-AUTH-008: The local auth header must be treated as development-only and must not remain the primary contract.

REQ-AUTH-009: Product sessions must remain distinct from authenticated sessions.

REQ-AUTH-010: The backend must support multiple product sessions for one authenticated user.

REQ-AUTH-011: Browser write endpoints should progressively stop requiring client-supplied `user_id` in request bodies.

REQ-AUTH-012: Authorization HTTP tests must cover cross-user access to sessions, jobs, analyses, artifacts, and feedback routes.

## 7. Non-Functional Requirements

- Security: browser auth state must not require exposing access tokens to frontend JavaScript by default
- Simplicity: the first real auth boundary must fit the current same-origin FastAPI plus PWA shape
- Maintainability: ownership enforcement should continue to live server-side near the existing application boundary
- Local operability: localhost setup should remain easy for QA and development
- Migration safety: the runtime should support a phased transition from header auth to cookie session auth

## 8. Domain and Session Model

Core terms:

- `AuthenticatedIdentity`: who the browser is acting as
- `AuthSession`: server-side authenticated session referenced by cookie
- `UserSession`: product workflow session already used by grocery/documents

Relationship:

```text
one AuthSession -> one AuthenticatedIdentity -> one current user
one current user -> many UserSession records
```

Invariant:

- auth expiry changes access, not ownership

## 9. API Contract

### `GET /api/auth/session`

```json
{
  "authenticated": true,
  "current_user": {
    "user_id": "user_123"
  },
  "auth_session": {
    "auth_session_id": "authsess_123",
    "expires_at": "2026-05-25T18:00:00+00:00"
  }
}
```

### `POST /api/auth/login`

MVP may start with local credentials or a controlled dev login flow, but successful login must issue the server-managed session cookie.

### `POST /api/auth/logout`

Must invalidate the current authenticated session server-side and clear the cookie.

## 10. Ownership Rules

Owner-scoped resources:

- user sessions
- session traces
- jobs
- document analyses
- document artifacts
- lens feedback
- document feedback
- feedback metrics

Enforcement rule:

```text
resource.user_id == authenticated_identity.user_id
```

HTTP semantics:

- unauthenticated or expired auth session -> `401`
- authenticated user mismatch in body/path -> `403 authenticated_user_mismatch`
- foreign or missing owned resource -> resource-specific `404`

## 11. Security Requirements

- session cookie must be `HttpOnly`
- session cookie must be `Secure` outside localhost
- session cookie must be `SameSite=Lax`
- only opaque session identifiers may be stored in the cookie
- mutating routes must validate same-origin browser intent through origin checks
- permissive cross-origin credentialed access must not be enabled
- dev header auth must be behind an explicit configuration gate

## 12. Migration Plan

Phase 1:

- introduce `AuthenticatedIdentity`
- add auth session store and cookie issuance
- add session bootstrap endpoint

Current state:

- implemented with a backend-managed cookie session path
- current user is resolved through FastAPI dependencies
- development header auth is behind an explicit gate
- SQLite-backed local runtime can persist auth sessions across app restarts
- login now uses runtime-configured local credentials instead of arbitrary demo bootstrap

Phase 2:

- migrate PWA boot flow to `GET /api/auth/session`
- keep header auth only for explicit dev mode
- add cross-user and expired-session HTTP tests

Current state:

- the PWA now bootstraps through the auth session endpoint
- write flows can omit `user_id` and derive ownership server-side
- the PWA has explicit login, logout, and relogin handling for session expiry
- `current-user` routes remove `user_id` from the companion URLs that matter most
- HTTP tests cover cookie bootstrap, expired-session behavior, dev-header rejection when disabled, and mismatch behavior

Phase 3:

- remove browser dependence on request-body `user_id`
- evaluate provider-backed auth only after the local boundary is stable

Still open:

- provider-backed login semantics beyond local-first credentials
- broader browser security hardening and E2E coverage
- full removal plan for the legacy user-scoped path aliases in the public HTTP contract

## 13. Failure Modes

| Failure | Expected behavior |
| --- | --- |
| Missing cookie | `401` and auth bootstrap reports unauthenticated |
| Expired session | `401` and PWA returns to auth gate |
| Body/path user mismatch | `403 authenticated_user_mismatch` |
| Foreign resource access | `404` for the owned resource type |
| Dev header disabled but sent | ignored or rejected by configuration policy |
| Cross-origin credentialed write | rejected |

## 14. Acceptance Criteria

- AC-AUTH-001: The PWA can determine authenticated state from `GET /api/auth/session`
- AC-AUTH-002: Browser requests no longer rely on `X-New-Era-User-Id` as the primary auth contract
- AC-AUTH-003: Current user is derived server-side for write flows
- AC-AUTH-004: Cross-user access attempts are rejected consistently
- AC-AUTH-005: Product sessions remain resumable and owner-scoped under the authenticated user
- AC-AUTH-006: Logout invalidates the authenticated session and removes browser access

## 15. Test Plan

- HTTP tests for unauthenticated `401` behavior
- HTTP tests for expired-session behavior
- HTTP tests for `authenticated_user_mismatch`
- HTTP tests for cross-user reads and writes across sessions, jobs, analyses, artifacts, and feedback
- browser smoke tests for auth bootstrap, login, logout, and session resume once E2E coverage exists

## 16. Open Questions

1. Should the first non-dev login be local password, magic link, or another low-complexity backend-managed flow?
2. Should user-path routes remain in the public HTTP contract once `current_user` is fully server-derived, or should they collapse into current-user scoped routes later?
3. At what point should the HTTP device bridge receive its own formal auth spec instead of sharing language with the PWA companion boundary?
