import json

from pdf_parser import cli
from pdf_parser.models import EngineInfo, ParsedDocument


def sample_document() -> ParsedDocument:
    return ParsedDocument(
        metadata={"title": "CLI"},
        pages=[],
        warnings=[],
        engine=EngineInfo(text="pymupdf", tables="pdfplumber"),
    )


def test_cli_writes_json_to_stdout(tmp_path, capsys, monkeypatch):
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")

    monkeypatch.setattr(cli, "parse_pdf", lambda path, options: sample_document())

    result = cli.main([str(pdf)])

    captured = capsys.readouterr()
    assert result == 0
    assert json.loads(captured.out)["metadata"] == {"title": "CLI"}


def test_cli_writes_json_to_output_file(tmp_path, capsys, monkeypatch):
    pdf = tmp_path / "sample.pdf"
    output = tmp_path / "output.json"
    pdf.write_bytes(b"%PDF-1.7\n")

    monkeypatch.setattr(cli, "parse_pdf", lambda path, options: sample_document())

    result = cli.main([str(pdf), "--output", str(output), "--pretty"])

    captured = capsys.readouterr()
    assert result == 0
    assert captured.out == ""
    assert json.loads(output.read_text(encoding="utf-8"))["metadata"]["title"] == "CLI"


def test_cli_creates_output_dir_and_writes_json_named_after_pdf(tmp_path, capsys, monkeypatch):
    pdf = tmp_path / "PDF 샘플 문서 (PDF Sample).pdf"
    output_dir = tmp_path / "parsed-json"
    pdf.write_bytes(b"%PDF-1.7\n")

    monkeypatch.setattr(cli, "parse_pdf", lambda path, options: sample_document())

    result = cli.main([str(pdf), "--output-dir", str(output_dir), "--pretty"])

    captured = capsys.readouterr()
    output_file = output_dir / "PDF 샘플 문서 (PDF Sample).json"
    assert result == 0
    assert captured.out == str(output_file) + "\n"
    assert json.loads(output_file.read_text(encoding="utf-8"))["metadata"]["title"] == "CLI"


def test_cli_rejects_output_and_output_dir_together(tmp_path, capsys, monkeypatch):
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")

    monkeypatch.setattr(cli, "parse_pdf", lambda path, options: sample_document())

    result = cli.main(
        [
            str(pdf),
            "--output",
            str(tmp_path / "output.json"),
            "--output-dir",
            str(tmp_path / "parsed"),
        ]
    )

    captured = capsys.readouterr()
    assert result == 2
    assert "cannot be used together" in captured.err


def test_cli_returns_nonzero_for_missing_file(tmp_path, capsys):
    result = cli.main([str(tmp_path / "missing.pdf")])

    captured = capsys.readouterr()
    assert result == 2
    assert "not found" in captured.err


def test_cli_writes_jsonl_to_stdout(tmp_path, capsys, monkeypatch):
    pdf = tmp_path / "large.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")

    def fake_parse_pdf_stream(path, options):
        assert path == pdf
        assert options.include_tables is False
        yield {"type": "document", "metadata": {"title": "Large"}, "page_count": 1}
        yield {"type": "summary", "pages_processed": 0, "warnings": 0, "pages_failed": 0}

    monkeypatch.setattr(cli, "parse_pdf_stream", fake_parse_pdf_stream)

    result = cli.main([str(pdf), "--jsonl"])

    captured = capsys.readouterr()
    lines = captured.out.strip().splitlines()
    assert result == 0
    assert json.loads(lines[0])["type"] == "document"
    assert json.loads(lines[1])["type"] == "summary"


def test_cli_writes_jsonl_to_output_file(tmp_path, capsys, monkeypatch):
    pdf = tmp_path / "large.pdf"
    output = tmp_path / "output.jsonl"
    pdf.write_bytes(b"%PDF-1.7\n")

    monkeypatch.setattr(
        cli,
        "parse_pdf_stream",
        lambda path, options: iter(
            [
                {"type": "document", "metadata": {}, "page_count": 1},
                {"type": "summary", "pages_processed": 0, "warnings": 0, "pages_failed": 0},
            ]
        ),
    )

    result = cli.main([str(pdf), "--jsonl", "--output", str(output)])

    captured = capsys.readouterr()
    assert result == 0
    assert captured.out == ""
    assert [json.loads(line)["type"] for line in output.read_text(encoding="utf-8").splitlines()] == [
        "document",
        "summary",
    ]


def test_cli_jsonl_output_dir_uses_jsonl_extension(tmp_path, capsys, monkeypatch):
    pdf = tmp_path / "large.pdf"
    output_dir = tmp_path / "parsed-json"
    pdf.write_bytes(b"%PDF-1.7\n")

    monkeypatch.setattr(
        cli,
        "parse_pdf_stream",
        lambda path, options: iter(
            [{"type": "summary", "pages_processed": 0, "warnings": 0, "pages_failed": 0}]
        ),
    )

    result = cli.main([str(pdf), "--jsonl", "--output-dir", str(output_dir)])

    captured = capsys.readouterr()
    output_file = output_dir / "large.jsonl"
    assert result == 0
    assert captured.out == str(output_file) + "\n"
    assert json.loads(output_file.read_text(encoding="utf-8"))["type"] == "summary"


def test_cli_jsonl_can_enable_tables(tmp_path, monkeypatch):
    pdf = tmp_path / "large.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    captured_options = []

    def fake_parse_pdf_stream(path, options):
        captured_options.append(options)
        yield {"type": "summary", "pages_processed": 0, "warnings": 0, "pages_failed": 0}

    monkeypatch.setattr(cli, "parse_pdf_stream", fake_parse_pdf_stream)

    result = cli.main([str(pdf), "--jsonl", "--include-tables"])

    assert result == 0
    assert captured_options[0].include_tables is True


def test_cli_rejects_pretty_jsonl(tmp_path, capsys):
    pdf = tmp_path / "large.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")

    result = cli.main([str(pdf), "--jsonl", "--pretty"])

    captured = capsys.readouterr()
    assert result == 2
    assert "--pretty cannot be used with --jsonl" in captured.err
