from __future__ import annotations

from pathlib import Path
from typing import Any

from pdf_parser.exceptions import MissingDependencyError
from pdf_parser.models import ParseOptions, ParseWarning, Table


def extract_tables(path: Path, options: ParseOptions) -> tuple[dict[int, list[Table]], list[ParseWarning]]:
    try:
        import pdfplumber
    except ModuleNotFoundError as exc:
        raise MissingDependencyError(
            "pdfplumber is required for table extraction. Install dependencies with "
            "`python3 -m pip install -e .[dev]`."
        ) from exc

    tables_by_page: dict[int, list[Table]] = {}
    warnings: list[ParseWarning] = []

    with pdfplumber.open(str(path)) as pdf:
        selected_pages = _selected_page_numbers(len(pdf.pages), options)
        for page_number in selected_pages:
            page = pdf.pages[page_number - 1]
            try:
                tables_by_page[page_number] = [_to_table(table) for table in page.extract_tables()]
            except Exception as exc:  # pdfplumber can raise pdfminer or geometry exceptions.
                warnings.append(
                    ParseWarning(
                        code="table_extraction_failed",
                        message=f"Table extraction failed: {exc}",
                        page=page_number,
                    )
                )

    return tables_by_page, warnings


def extract_tables_for_page(path: Path, page_number: int) -> tuple[list[Table], list[ParseWarning]]:
    try:
        import pdfplumber
    except ModuleNotFoundError as exc:
        raise MissingDependencyError(
            "pdfplumber is required for table extraction. Install dependencies with "
            "`python3 -m pip install -e .[dev]`."
        ) from exc

    with pdfplumber.open(str(path)) as pdf:
        if page_number > len(pdf.pages):
            return [], [
                ParseWarning(
                    code="table_extraction_failed",
                    message=(
                        f"Table extraction failed: page {page_number} is out of range "
                        f"(document has {len(pdf.pages)} pages)"
                    ),
                    page=page_number,
                )
            ]

        page = pdf.pages[page_number - 1]
        try:
            return [_to_table(table) for table in page.extract_tables()], []
        except Exception as exc:  # pdfplumber can raise pdfminer or geometry exceptions.
            return [], [
                ParseWarning(
                    code="table_extraction_failed",
                    message=f"Table extraction failed: {exc}",
                    page=page_number,
                )
            ]


def _selected_page_numbers(page_count: int, options: ParseOptions) -> list[int]:
    if options.page_numbers is None:
        return list(range(1, page_count + 1))
    return [page for page in options.page_numbers if page <= page_count]


def _to_table(raw_table: list[list[Any]]) -> Table:
    rows: list[list[str | None]] = []
    for row in raw_table:
        rows.append([None if cell is None else str(cell) for cell in row])
    return Table(rows=rows)
