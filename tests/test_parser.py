from pathlib import Path

import pytest

from pdf_parser import parser
from pdf_parser.models import (
    EngineInfo,
    ParsedDocument,
    ParsedPage,
    ParseOptions,
    ParseWarning,
    Table,
)


def test_parse_options_expands_page_ranges():
    options = ParseOptions.from_page_spec("1-3,5")

    assert options.page_numbers == [1, 2, 3, 5]


def test_parse_options_rejects_invalid_page_ranges():
    with pytest.raises(ValueError, match="Invalid page range"):
        ParseOptions.from_page_spec("3-1")


def test_parse_pdf_merges_text_pages_and_tables(tmp_path, monkeypatch):
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")

    def fake_text_backend(path: Path, options: ParseOptions) -> ParsedDocument:
        assert path == pdf
        assert options.page_numbers == [1]
        return ParsedDocument(
            metadata={"title": "Sample"},
            pages=[
                ParsedPage(
                    number=1,
                    width=100,
                    height=200,
                    text_blocks=[],
                    tables=[],
                    warnings=[],
                    image_count=0,
                )
            ],
            warnings=[],
            engine=EngineInfo(text="pymupdf", tables="pdfplumber"),
        )

    def fake_table_backend(path: Path, options: ParseOptions):
        assert path == pdf
        assert options.page_numbers == [1]
        return {
            1: [
                Table(rows=[["Name", "Value"], ["A", "1"]]),
            ]
        }, []

    monkeypatch.setattr(parser, "extract_document_structure", fake_text_backend)
    monkeypatch.setattr(parser, "extract_tables", fake_table_backend)

    result = parser.parse_pdf(pdf, ParseOptions(page_numbers=[1]))

    assert result.metadata == {"title": "Sample"}
    assert result.pages[0].tables[0].rows == [["Name", "Value"], ["A", "1"]]


def test_parse_pdf_adds_scanned_warning_for_image_only_pages(tmp_path, monkeypatch):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")

    def fake_text_backend(path: Path, options: ParseOptions) -> ParsedDocument:
        return ParsedDocument(
            metadata={},
            pages=[
                ParsedPage(
                    number=1,
                    width=100,
                    height=200,
                    text_blocks=[],
                    tables=[],
                    warnings=[],
                    image_count=2,
                )
            ],
            warnings=[],
            engine=EngineInfo(text="pymupdf", tables="pdfplumber"),
        )

    monkeypatch.setattr(parser, "extract_document_structure", fake_text_backend)
    monkeypatch.setattr(parser, "extract_tables", lambda path, options: ({}, []))

    result = parser.parse_pdf(pdf)

    assert result.warnings[0].code == "scanned_pdf_detected"


def test_parse_pdf_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        parser.parse_pdf(tmp_path / "missing.pdf")


def test_parse_pdf_stream_yields_document_pages_and_summary(tmp_path, monkeypatch):
    pdf = tmp_path / "large.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")

    def fake_iter_document_structure(path: Path, options: ParseOptions):
        assert path == pdf
        assert options.include_tables is False
        yield {
            "type": "document",
            "metadata": {"title": "Large"},
            "page_count": 2,
            "engine": EngineInfo(text="pymupdf", tables=None),
        }
        yield {
            "type": "page",
            "page": ParsedPage(number=1, width=100, height=200),
        }
        yield {
            "type": "page",
            "page": ParsedPage(number=2, width=100, height=200),
        }

    monkeypatch.setattr(parser, "iter_document_structure", fake_iter_document_structure)
    monkeypatch.setattr(
        parser,
        "extract_tables_for_page",
        lambda path, page_number: pytest.fail("tables should be disabled by default"),
    )

    records = list(parser.parse_pdf_stream(pdf))

    assert [record["type"] for record in records] == ["document", "page", "page", "summary"]
    assert records[0]["metadata"] == {"title": "Large"}
    assert records[1]["page"]["number"] == 1
    assert records[-1] == {
        "type": "summary",
        "pages_processed": 2,
        "warnings": 0,
        "pages_failed": 0,
    }


def test_parse_pdf_stream_continues_after_page_warning(tmp_path, monkeypatch):
    pdf = tmp_path / "large.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")

    def fake_iter_document_structure(path: Path, options: ParseOptions):
        yield {
            "type": "document",
            "metadata": {},
            "page_count": 3,
            "engine": EngineInfo(text="pymupdf", tables=None),
        }
        yield {"type": "page", "page": ParsedPage(number=1, width=100, height=200)}
        yield {
            "type": "warning",
            "warning": ParseWarning(
                code="page_extraction_failed",
                message="Page extraction failed: boom",
                page=2,
            ),
        }
        yield {"type": "page", "page": ParsedPage(number=3, width=100, height=200)}

    monkeypatch.setattr(parser, "iter_document_structure", fake_iter_document_structure)

    records = list(parser.parse_pdf_stream(pdf))

    assert [record["type"] for record in records] == [
        "document",
        "page",
        "warning",
        "page",
        "summary",
    ]
    assert records[2]["warning"]["page"] == 2
    assert records[-1]["pages_processed"] == 2
    assert records[-1]["warnings"] == 1
    assert records[-1]["pages_failed"] == 1


def test_parse_pdf_stream_can_extract_tables_per_page(tmp_path, monkeypatch):
    pdf = tmp_path / "tables.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")

    def fake_iter_document_structure(path: Path, options: ParseOptions):
        yield {
            "type": "document",
            "metadata": {},
            "page_count": 1,
            "engine": EngineInfo(text="pymupdf", tables="pdfplumber"),
        }
        yield {"type": "page", "page": ParsedPage(number=1, width=100, height=200)}

    monkeypatch.setattr(parser, "iter_document_structure", fake_iter_document_structure)
    monkeypatch.setattr(
        parser,
        "extract_tables_for_page",
        lambda path, page_number: ([Table(rows=[["A", "B"]])], []),
    )

    records = list(parser.parse_pdf_stream(pdf, ParseOptions(include_tables=True)))

    assert records[1]["page"]["tables"] == [{"rows": [["A", "B"]]}]
