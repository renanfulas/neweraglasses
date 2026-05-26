# Authentication Boundary

Status: Active reference  
Last updated: 2026-05-25  
Related specs:

- [../specs/0001-platform-foundation.md](../specs/0001-platform-foundation.md)
- [../specs/0004-auth-boundary.md](../specs/0004-auth-boundary.md)

## Purpose

Define the real identity boundary New Era should use for the MVP companion surface, replacing the current localhost header convention with an explicit authenticated-session contract.

This document is intentionally practical. It is not trying to solve every future integration at once. It closes the current ambiguity around:

- who the authenticated user is
- what "current user" means in the backend
- how product sessions relate to authentication sessions
- what ownership rules are enforced server-side
- which auth mechanism the MVP should adopt first

## Current Runtime Reality

Today the backend already enforces meaningful owner scoping for:

- product sessions
- jobs
- document analyses
- document artifacts
- feedback endpoints

However, the identity input is still local-development grade:

- `X-New-Era-User-Id`
- optional local app state fallback for tests and localhost

That was enough for simulation and unit coverage, but it was not a product boundary.

Current runtime progress:

- `GET /api/auth/session` exists
- `POST /api/auth/login` exists
- `POST /api/auth/logout` exists
- the browser companion now boots from a cookie-backed session path
- login now requires explicit local credentials configured in the runtime
- the old header fallback is available only when an explicit development gate is enabled
- when the runtime uses SQLite, auth sessions can persist across local app restarts
- cookie-authenticated writes now validate same-origin browser intent
- `current-user` route aliases exist so the browser can stop carrying `user_id` in companion URLs

What is still incomplete:

- local password auth is still a local-first MVP boundary, not a provider-backed production identity flow
- full browser auth hardening is not done yet

## Decision Summary

The MVP web companion should use a backend-managed authenticated session cookie.

This is the chosen boundary for the browser/PWA because:

- the PWA and API already live on the same FastAPI origin
- server-managed cookies keep browser auth state out of the JS bundle and out of local storage
- ownership checks already exist server-side and can be fed from one current-user dependency
- this path is materially smaller and safer than introducing a third-party provider now

The current local header must be treated as a development bootstrap only and must not remain the primary contract.

## What We Are Choosing

### MVP browser auth

Use:

- same-origin authenticated cookie
- backend-resolved current user
- server-side session store

Do not use as the main browser auth contract:

- browser-stored bearer token
- external provider as a first implementation step

### Device and native future

This decision is specifically for the browser/PWA companion boundary.

Future device bridge or native clients may still need token-based or bridge-specific credentials later. That is a separate transport trust problem and should not force the browser companion to start with bearer tokens.

## Why Cookie Session Wins For The MVP

### Option A: simple bearer token in the browser

Pros:

- familiar API pattern
- easy to test manually

Cons:

- token handling leaks into client JS
- storage and rotation decisions appear immediately
- weaker fit for a same-origin PWA shell
- encourages "frontend carries identity" instead of "backend resolves identity"

Decision:

- reject for the PWA MVP

### Option B: backend-managed session cookie

Pros:

- best fit for same-origin FastAPI plus PWA
- current user is resolved server-side
- no access token exposed to frontend code by default
- smaller migration from today's dependency model
- keeps ownership logic where the repo already wants it

Cons:

- requires session lifecycle design now
- requires CSRF/origin posture for mutating routes
- less reusable for non-browser clients

Decision:

- choose for the PWA MVP

### Option C: external provider first

Pros:

- future-friendly for production org auth
- offloads password and identity UX

Cons:

- introduces provider complexity before the product loop is settled
- slows the MVP for little near-term leverage
- forces product and deployment decisions the repo is not ready to own yet

Decision:

- defer until after the first real auth boundary lands and is exercised

## Identity Contract

The backend should resolve an `AuthenticatedIdentity` for every authenticated request.

Suggested contract:

```text
AuthenticatedIdentity
  subject_id
  user_id
  auth_session_id
  auth_method
  issued_at
  expires_at
  scopes
```

Field meaning:

- `subject_id`: stable identity subject inside the auth system
- `user_id`: the application-level owner key used by New Era resources
- `auth_session_id`: the current authenticated web session
- `auth_method`: `local_password`, `magic_link`, or later `oidc`
- `issued_at`: authenticated session issuance time
- `expires_at`: authenticated session expiry time
- `scopes`: minimal permission set, for example `companion`

For the MVP, `subject_id` and `user_id` may be equal if that keeps the model simple. The important rule is that the backend owns that mapping.

## Session Model

New Era must distinguish two different session concepts.

### Authenticated session

This answers:

```text
Who is this browser acting as right now?
```

Properties:

- created by login
- stored server-side
- referenced by cookie
- expires independently of product workflow state

### Product session

This answers:

```text
What grocery or document workflow is the user currently in?
```

Properties:

- already exists in the repo as `UserSession`
- belongs to one `user_id`
- may be created or resumed after auth
- many product sessions may exist under one authenticated session

Relationship:

```text
one authenticated session -> one current user
one current user -> many product sessions
```

This distinction matters because auth expiry must not redefine product ownership.

## Current User Contract

`current_user` must become a server-resolved fact, not a user-supplied hint.

Rules:

- the request cookie identifies the authenticated session
- the backend resolves `AuthenticatedIdentity`
- application endpoints derive `current_user_id` from that identity
- request bodies must not be trusted to declare who the acting user is

Short-term migration rule:

- endpoints may temporarily continue accepting `user_id` in request bodies or paths
- if supplied, it must match the authenticated identity exactly
- new endpoint contracts should prefer removing client-supplied `user_id` for write flows

## Ownership Rules

The ownership boundary stays server-side.

The authenticated user may access only resources whose owner matches `current_user_id`.

Owner-scoped resources:

- `UserSession`
- `JobRecord`
- `DocumentAnalysisRecord`
- `DocumentArtifact`
- lens feedback
- document feedback
- feedback metrics and session history

Enforcement rules:

- ownership is never inferred from frontend state
- path parameters do not grant access
- request body `user_id` does not grant access
- session IDs are opaque references, not authority

Resource check rule:

```text
resource.user_id must equal authenticated_identity.user_id
```

## HTTP Behavior Rules

Recommended auth and ownership semantics:

- `401`: no authenticated session, expired session, or invalid session cookie
- `403`: authenticated user tries to act as another explicit user in a path or body
- `404`: resource does not exist or does not belong to the authenticated user

This keeps product behavior explicit while still hiding foreign resources.

## PWA Bootstrapping Contract

The PWA should bootstrap identity from a real auth endpoint instead of inventing it locally.

Recommended endpoints:

```text
GET /api/auth/session
POST /api/auth/login
POST /api/auth/logout
```

`GET /api/auth/session` should return only the minimum safe state needed to boot the companion:

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

The PWA should treat that endpoint as the only authority for:

- authenticated or not
- who the current user is
- whether session refresh or re-login is required

## Cookie Posture

The MVP cookie contract should be:

- `HttpOnly`
- `Secure` outside localhost
- `SameSite=Lax`
- explicit expiry
- server-side invalidation on logout

The cookie should carry only the auth session reference, not user profile data.

Suggested shape:

```text
Cookie: newera_session=<opaque session id>
```

## CSRF and Browser Security Posture

A cookie-based write surface needs browser protections.

Minimum MVP posture:

- same-origin PWA and API
- reject cross-origin credentialed writes
- validate `Origin` on mutating routes
- do not enable permissive CORS

If the app later becomes cross-site or multi-origin, add a real CSRF token strategy before claiming production readiness.

## Development Boundary

The current header:

```text
X-New-Era-User-Id
```

should move to explicit development-only status.

Recommended rule:

- disabled by default outside development
- enabled only under an explicit dev flag
- never documented as the product auth contract

Current runtime flag:

- `NEW_ERA_ENABLE_DEV_AUTH=1`

This keeps local tests fast without confusing the long-term boundary.

## Migration Guidance

Recommended sequence:

1. Introduce `AuthenticatedIdentity` and make it the dependency return type.
2. Add a server-side auth session store and same-origin cookie issuance.
3. Add `GET /api/auth/session`, login, and logout endpoints.
4. Keep header auth only behind an explicit development gate.
5. Remove body-level `user_id` from browser write endpoints where practical.
6. Expand authorization HTTP tests for cross-user and expired-session cases.

## What Not To Do Yet

- do not start with an external auth provider
- do not put bearer tokens into local storage for the PWA
- do not let the frontend authoritatively choose `current_user`
- do not merge product session identity with auth session lifecycle

## Architecture Summary

The smallest strong move is:

```text
same-origin PWA
-> backend-issued cookie session
-> backend-resolved AuthenticatedIdentity
-> current_user derived server-side
-> ownership enforced against user-owned resources
```

That gives the MVP a real identity boundary without overbuilding the stack.
