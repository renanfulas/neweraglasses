# OCR Analysis Eval Harness

Fixtures live in [evals/document_analysis/fixtures](/C:/Users/renan/OneDrive/Documents/New%20Era%20Glasses/evals/document_analysis/fixtures) and are executed by [tools/evaluate_document_analysis.py](/C:/Users/renan/OneDrive/Documents/New%20Era%20Glasses/tools/evaluate_document_analysis.py).

Run all fixtures:

```bash
python tools/evaluate_document_analysis.py
```

Run one fixture and print JSON:

```bash
python tools/evaluate_document_analysis.py --fixture evals/document_analysis/fixtures/plain_text_risk_signals.json --json
```

Each fixture declares:

- `input.document_text` for deterministic analyzer evals
- `input.document_image_base64` or `input.document_image_path` for OCR + analyzer evals
- `expected.*` assertions for findings, confidence, parsing notes, and extracted text snippets
