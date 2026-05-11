from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from pdf_parser.exceptions import PdfParserError
from pdf_parser.models import ParseOptions
from pdf_parser.parser import parse_pdf, parse_pdf_stream


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pdf-parser")
    parser.add_argument("input", help="PDF file to parse")
    parser.add_argument("-o", "--output", help="Write JSON to this file instead of stdout")
    parser.add_argument(
        "--output-dir",
        help="Create this directory and write JSON using the input PDF filename",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    parser.add_argument("--pages", help="Page range to parse, for example 1-3,5")
    parser.add_argument(
        "--no-tables",
        action="store_true",
        help="Skip pdfplumber table extraction",
    )
    parser.add_argument(
        "--jsonl",
        action="store_true",
        help="Stream one JSON object per line for large PDFs",
    )
    parser.add_argument(
        "--include-tables",
        action="store_true",
        help="Enable pdfplumber table extraction in JSONL mode",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arg_parser = build_parser()
    args = arg_parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"PDF not found: {input_path}", file=sys.stderr)
        return 2
    if args.output and args.output_dir:
        print("--output and --output-dir cannot be used together", file=sys.stderr)
        return 2
    if args.jsonl and args.pretty:
        print("--pretty cannot be used with --jsonl", file=sys.stderr)
        return 2
    if args.no_tables and args.include_tables:
        print("--no-tables and --include-tables cannot be used together", file=sys.stderr)
        return 2

    try:
        include_tables = args.include_tables if args.jsonl else not args.no_tables
        options = ParseOptions.from_page_spec(args.pages, include_tables=include_tables)
        if args.jsonl:
            return _write_jsonl(input_path, options, args.output, args.output_dir)

        document = parse_pdf(input_path, options)
    except (FileNotFoundError, ValueError, PdfParserError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    output = document.to_json(pretty=args.pretty)

    output_path = _resolve_output_path(input_path, args.output, args.output_dir, suffix=".json")
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output + "\n", encoding="utf-8")
        if args.output_dir:
            print(output_path)
    else:
        print(output)

    return 0


def _write_jsonl(
    input_path: Path,
    options: ParseOptions,
    output: str | None,
    output_dir: str | None,
) -> int:
    output_path = _resolve_output_path(input_path, output, output_dir, suffix=".jsonl")
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            for record in parse_pdf_stream(input_path, options):
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()
        if output_dir:
            print(output_path)
        return 0

    for record in parse_pdf_stream(input_path, options):
        print(json.dumps(record, ensure_ascii=False), flush=True)
    return 0


def _resolve_output_path(
    input_path: Path,
    output: str | None,
    output_dir: str | None,
    *,
    suffix: str,
) -> Path | None:
    if output:
        return Path(output)
    if output_dir:
        return Path(output_dir) / f"{input_path.stem}{suffix}"
    return None


if __name__ == "__main__":
    raise SystemExit(main())
