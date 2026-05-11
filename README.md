# pdf-parser

Python CLI and library for extracting structured JSON from PDF files.

## Setup

```bash
python3 -m pip install -e ".[dev]"
```

## CLI

```bash
pdf-parser input.pdf
pdf-parser input.pdf --output output.json --pretty
pdf-parser input.pdf --output-dir parsed-json --pretty
pdf-parser input.pdf --pages 1-3,5
pdf-parser input.pdf --no-tables
pdf-parser input.pdf --jsonl --output output.jsonl
```

## Python API

```python
from pdf_parser import parse_pdf

document = parse_pdf("input.pdf")
print(document.to_json(pretty=True))
```

For very large PDFs, stream one JSON object per line instead of building a full
document in memory:

```python
import json

from pdf_parser import parse_pdf_stream

for record in parse_pdf_stream("input.pdf"):
    print(json.dumps(record, ensure_ascii=False))
```

JSONL streaming emits `document`, `page`, `warning`, and `summary` records.
Table extraction is disabled by default in `--jsonl` mode to keep large runs
bounded; pass `--include-tables` to enable page-by-page table extraction.

## Development

```bash
python3 -m pytest
python3 -m ruff check .
```
