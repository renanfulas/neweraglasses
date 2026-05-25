# Spec Template

Status: Draft  
Spec ID: SPEC-XXXX  
Owner: TBD  
Date: YYYY-MM-DD

## 1. Objective

What outcome should this spec produce?

## 2. Context

Why does this matter now? What product/architecture problem does it solve?

## 3. User Story or System Story

```text
As a ...
I want ...
So that ...
```

For system specs:

```text
When ...
The system must ...
So that ...
```

## 4. In Scope

- TBD

## 5. Out of Scope

- TBD

## 6. Functional Requirements

Use stable IDs:

```text
REQ-XXX-001: The system must ...
REQ-XXX-002: The system must ...
```

## 7. Non-Functional Requirements

Cover:

- latency
- throughput
- cost
- reliability
- offline/degraded mode
- privacy
- security
- accessibility where relevant

## 8. Domain Model

Key domain concepts:

- TBD

Invariants:

- TBD

## 9. API / Port / Contract

Define input/output contracts and versioning.

```json
{
  "example": "contract"
}
```

## 10. Events and Observability

Required events:

- TBD

Event metadata rules:

- TBD

## 11. Data Classification and Privacy

Data processed:

- TBD

Classification:

- public
- internal
- personal
- sensitive personal
- secret

Retention:

- TBD

Consent requirements:

- TBD

## 12. Security Requirements

Cover:

- authentication
- authorization
- server-side validation
- rate limiting
- audit trail
- abuse cases
- redaction
- encryption

## 13. Performance Budget

```text
Target latency:
P95 latency:
Max payload:
Expected request volume:
Cost budget:
Async boundary:
```

## 14. Failure Modes

| Failure | Expected behavior | Event/metric |
| --- | --- | --- |
| TBD | TBD | TBD |

## 15. AI/Prompt Contract

Use only if the spec involves AI.

```text
Prompt version:
Objective:
Trusted inputs:
Untrusted inputs:
Output schema:
Safety limits:
Fallback behavior:
Eval cases:
```

## 16. Acceptance Criteria

- TBD

## 17. Test and Eval Plan

- unit tests
- integration tests
- contract tests
- privacy tests
- prompt/model evals
- performance tests

## 18. Rollout Plan

- TBD

## 19. Open Questions

1. TBD
