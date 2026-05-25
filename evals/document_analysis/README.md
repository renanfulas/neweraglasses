# OCR and Document Analysis Eval Harness

Status: Active reference  
Last updated: 2026-05-25

## Purpose

This harness validates the current local document stack:

- OCR extraction
- deterministic contract parsing
- finding detection
- confidence and summary expectations

It is not yet a full LLM eval harness.

## Files

- fixtures: [evals/document_analysis/fixtures](/C:/Users/renan/OneDrive/Documents/New%20Era%20Glasses/evals/document_analysis/fixtures)
- runner: [tools/evaluate_document_analysis.py](/C:/Users/renan/OneDrive/Documents/New%20Era%20Glasses/tools/evaluate_document_analysis.py)

## Run All Fixtures

```powershell
$env:PYTHONPATH='src'; python .\tools\evaluate_document_analysis.py
```

## Run One Fixture With JSON Output

```powershell
$env:PYTHONPATH='src'; python .\tools\evaluate_document_analysis.py --fixture evals/document_analysis/fixtures/plain_text_risk_signals.json --json
```

## What It Covers Today

Each fixture can assert:

- expected findings
- confidence expectations
- parsing notes
- excerpt presence
- OCR-derived behavior when image fixtures are used

## What It Still Does Not Cover

- live LLM prompt behavior
- adversarial prompt-injection evals against a real model
- large-scale benchmark reporting
- CI-enforced score thresholds
