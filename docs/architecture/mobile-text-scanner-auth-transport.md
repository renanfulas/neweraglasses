# Mobile Text Scanner Auth And Transport Decision

Status: POC decision recorded  
Date: 2026-05-26  
Related spec: [../specs/0005-mobile-text-scanner.md](../specs/0005-mobile-text-scanner.md)  
Related plan: [mobile-text-scanner-execution-plan.md](mobile-text-scanner-execution-plan.md)

## Decision

The first mobile text scanner execution remains contract-only and harness-driven.

For the current repository state, scanner submission is validated through the existing backend endpoint:

```text
POST /api/jobs/documents/contract-analysis
```

with:

```json
{
  "source_type": "mobile_text_scanner",
  "document_text": "<scanner extracted text>"
}
```

The local scanner comparison harness may use explicit development auth inside an isolated local runtime. That is acceptable only for repo validation and does not define production mobile authentication.

## POC Boundary

The native mobile ML Kit client must not assume browser cookie or same-origin behavior as its auth model. The existing PWA auth boundary stays unchanged:

- the backend derives identity from the current authenticated user
- browser cookie-authenticated writes keep same-origin protection
- ownership checks remain server-side
- dev header auth remains a local-only validation mechanism

Until a mobile workspace exists, the supported scanner proof is:

```text
sample contract text -> simulated mobile_text_scanner payload -> existing document job -> result/history/feedback
```

The next native mobile proof may extract text locally with ML Kit, but it should either:

- submit through a documented local development bridge, or
- stop at extraction/review and hand the text to the backend harness for submission

It should not add a production-looking token scheme without a separate auth contract.

## Rejected For This POC

- Anonymous native submission.
- Reusing browser session cookies from a native app as the production story.
- Making `X-New-Era-User-Id` or any dev header a production mobile credential.
- Adding a scanner-specific backend endpoint before the existing job route proves insufficient.
- Sending ML Kit confidence as backend analysis confidence.

## Production Direction

If the scanner continues past the POC, define a first-class native auth contract before shipping mobile writes. The likely options are:

- a real identity-provider backed bearer token for native clients
- a companion-paired bridge token with short lifetime and explicit device binding
- a browser-mediated local handoff where the PWA remains the authenticated writer

That decision should be made in the auth boundary spec, not hidden inside scanner code.

## Validation

The current executable proof is:

```powershell
$env:PYTHONPATH='src'
python .\tools\scanner_comparison_harness.py
python .\tools\validate_local.py --skip-pytest --with-scanner-comparison
```

This validates the backend contract and comparison path only. It does not prove a real Android ML Kit integration yet.
