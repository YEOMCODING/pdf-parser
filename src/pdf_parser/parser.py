from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pdf_parser.models import ParsedDocument, ParseOptions, ParseWarning
from pdf_parser.pdfplumber_backend import extract_tables, extract_tables_for_page
from pdf_parser.pymupdf_backend import extract_document_structure, iter_document_structure


def parse_pdf(path: str | Path, options: ParseOptions | None = None) -> ParsedDocument:
    pdf_path = Path(path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF path is not a file: {pdf_path}")

    effective_options = options or ParseOptions()
    document = extract_document_structure(pdf_path, effective_options)

    if effective_options.include_tables:
        tables_by_page, table_warnings = extract_tables(pdf_path, effective_options)
        for page in document.pages:
            page.tables.extend(tables_by_page.get(page.number, []))
        document.warnings.extend(table_warnings)
    else:
        document.engine.tables = None

    if _looks_like_scanned_pdf(document, effective_options):
        document.warnings.append(
            ParseWarning(
                code="scanned_pdf_detected",
                message="This PDF appears to contain images without extractable text; OCR is not part of the MVP.",
            )
        )

    return document


def parse_pdf_stream(
    path: str | Path,
    options: ParseOptions | None = None,
) -> Iterator[dict[str, Any]]:
    pdf_path = Path(path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF path is not a file: {pdf_path}")

    effective_options = options or ParseOptions(include_tables=False)
    pages_processed = 0
    warning_count = 0
    pages_failed = 0
    total_images = 0
    total_text_length = 0

    for event in iter_document_structure(pdf_path, effective_options):
        event_type = event.get("type")

        if event_type == "document":
            engine = event["engine"]
            yield {
                "type": "document",
                "metadata": event["metadata"],
                "page_count": event["page_count"],
                "engine": engine.to_dict() if hasattr(engine, "to_dict") else engine,
                "options": {
                    "include_tables": effective_options.include_tables,
                    "page_numbers": effective_options.page_numbers,
                },
            }
            continue

        if event_type == "warning":
            warning = event["warning"]
            warning_count += 1
            if warning.code == "page_extraction_failed":
                pages_failed += 1
            yield {"type": "warning", "warning": warning.to_dict()}
            continue

        if event_type != "page":
            warning_count += 1
            yield {
                "type": "warning",
                "warning": ParseWarning(
                    code="unknown_stream_event",
                    message=f"Unknown stream event type: {event_type}",
                ).to_dict(),
            }
            continue

        page = event["page"]
        if effective_options.include_tables:
            tables, table_warnings = extract_tables_for_page(pdf_path, page.number)
            page.tables.extend(tables)
            for warning in table_warnings:
                warning_count += 1
                yield {"type": "warning", "warning": warning.to_dict()}

        pages_processed += 1
        total_images += page.image_count
        total_text_length += len(page.text_content().strip())
        yield {"type": "page", "page": page.to_dict()}

    if total_images > 0 and total_text_length < effective_options.scan_text_threshold:
        warning_count += 1
        yield {
            "type": "warning",
            "warning": ParseWarning(
                code="scanned_pdf_detected",
                message=(
                    "This PDF appears to contain images without extractable text; "
                    "OCR is not part of the MVP."
                ),
            ).to_dict(),
        }

    yield {
        "type": "summary",
        "pages_processed": pages_processed,
        "warnings": warning_count,
        "pages_failed": pages_failed,
    }


def _looks_like_scanned_pdf(document: ParsedDocument, options: ParseOptions) -> bool:
    if not document.pages:
        return False

    total_text = "".join(page.text_content().strip() for page in document.pages)
    total_images = sum(page.image_count for page in document.pages)

    return total_images > 0 and len(total_text) < options.scan_text_threshold
