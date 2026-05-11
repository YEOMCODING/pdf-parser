import json

from pdf_parser.models import (
    EngineInfo,
    ParsedDocument,
    ParsedPage,
    ParseWarning,
    Table,
    TextBlock,
)


def test_document_serializes_to_page_block_json():
    document = ParsedDocument(
        metadata={"title": "Sample"},
        pages=[
            ParsedPage(
                number=1,
                width=612.0,
                height=792.0,
                text_blocks=[
                    TextBlock(text="Hello", bbox=(1.0, 2.0, 3.0, 4.0)),
                ],
                tables=[
                    Table(rows=[["A", "B"], ["1", "2"]], bbox=(10.0, 20.0, 30.0, 40.0)),
                ],
                warnings=[
                    ParseWarning(code="table_partial", message="Table extraction was partial"),
                ],
                image_count=0,
            ),
        ],
        warnings=[
            ParseWarning(code="document_warning", message="Document-level warning"),
        ],
        engine=EngineInfo(text="pymupdf", tables="pdfplumber"),
    )

    payload = document.to_dict()

    assert payload["metadata"] == {"title": "Sample"}
    assert payload["engine"] == {"text": "pymupdf", "tables": "pdfplumber"}
    assert payload["pages"][0]["number"] == 1
    assert payload["pages"][0]["text_blocks"][0]["text"] == "Hello"
    assert payload["pages"][0]["tables"][0]["rows"] == [["A", "B"], ["1", "2"]]
    assert payload["pages"][0]["warnings"][0]["code"] == "table_partial"
    assert payload["warnings"][0]["code"] == "document_warning"


def test_document_to_json_supports_pretty_output():
    document = ParsedDocument(
        metadata={},
        pages=[],
        warnings=[],
        engine=EngineInfo(text="pymupdf", tables="pdfplumber"),
    )

    raw = document.to_json(pretty=True)

    assert json.loads(raw)["pages"] == []
    assert "\n  " in raw

