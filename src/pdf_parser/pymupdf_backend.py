from __future__ import annotations

from pathlib import Path
from collections.abc import Iterator
from typing import Any

from pdf_parser.exceptions import MissingDependencyError, PdfParserError
from pdf_parser.models import (
    EngineInfo,
    ParsedDocument,
    ParsedPage,
    ParseOptions,
    ParseWarning,
    TextBlock,
)


def extract_document_structure(path: Path, options: ParseOptions) -> ParsedDocument:
    try:
        import fitz
    except ModuleNotFoundError as exc:
        raise MissingDependencyError(
            "PyMuPDF is required for text extraction. Install dependencies with "
            "`python3 -m pip install -e .[dev]`."
        ) from exc

    try:
        pdf = fitz.open(str(path))
    except Exception as exc:  # PyMuPDF raises several backend-specific exception types.
        raise PdfParserError(f"Unable to open PDF: {path}") from exc

    try:
        pages = [
            _extract_page(pdf.load_page(page_number - 1), page_number)
            for page_number in _selected_page_numbers(pdf.page_count, options)
        ]
        metadata = dict(pdf.metadata or {})
    finally:
        pdf.close()

    return ParsedDocument(
        metadata=metadata,
        pages=pages,
        warnings=[],
        engine=EngineInfo(text="pymupdf", tables="pdfplumber" if options.include_tables else None),
    )


def iter_document_structure(path: Path, options: ParseOptions) -> Iterator[dict[str, Any]]:
    try:
        import fitz
    except ModuleNotFoundError as exc:
        raise MissingDependencyError(
            "PyMuPDF is required for text extraction. Install dependencies with "
            "`python3 -m pip install -e .[dev]`."
        ) from exc

    try:
        pdf = fitz.open(str(path))
    except Exception as exc:  # PyMuPDF raises several backend-specific exception types.
        raise PdfParserError(f"Unable to open PDF: {path}") from exc

    try:
        page_numbers = _selected_page_numbers(pdf.page_count, options)
        yield {
            "type": "document",
            "metadata": dict(pdf.metadata or {}),
            "page_count": pdf.page_count,
            "engine": EngineInfo(
                text="pymupdf",
                tables="pdfplumber" if options.include_tables else None,
            ),
        }
        for page_number in page_numbers:
            try:
                page = _extract_page(pdf.load_page(page_number - 1), page_number)
            except Exception as exc:  # Keep large streaming runs moving past one bad page.
                yield {
                    "type": "warning",
                    "warning": ParseWarning(
                        code="page_extraction_failed",
                        message=f"Page extraction failed: {exc}",
                        page=page_number,
                    ),
                }
                continue
            yield {"type": "page", "page": page}
    finally:
        pdf.close()


def _selected_page_numbers(page_count: int, options: ParseOptions) -> list[int]:
    if options.page_numbers is None:
        return list(range(1, page_count + 1))

    out_of_range = [page for page in options.page_numbers if page > page_count]
    if out_of_range:
        raise ValueError(
            f"Page number out of range: {out_of_range[0]} (document has {page_count} pages)"
        )

    return options.page_numbers


def _extract_page(page: Any, page_number: int) -> ParsedPage:
    rect = page.rect
    blocks = []

    for raw_block in page.get_text("blocks"):
        if len(raw_block) < 5:
            continue
        text = str(raw_block[4]).strip()
        if not text:
            continue
        blocks.append(
            TextBlock(
                text=text,
                bbox=(
                    float(raw_block[0]),
                    float(raw_block[1]),
                    float(raw_block[2]),
                    float(raw_block[3]),
                ),
            )
        )

    return ParsedPage(
        number=page_number,
        width=float(rect.width),
        height=float(rect.height),
        text_blocks=blocks,
        image_count=len(page.get_images(full=True)),
    )
