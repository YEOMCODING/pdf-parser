from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

BBox = tuple[float, float, float, float]


@dataclass(slots=True)
class ParseWarning:
    code: str
    message: str
    page: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.page is not None:
            payload["page"] = self.page
        return payload


@dataclass(slots=True)
class TextBlock:
    text: str
    bbox: BBox | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"text": self.text}
        if self.bbox is not None:
            payload["bbox"] = list(self.bbox)
        return payload


@dataclass(slots=True)
class Table:
    rows: list[list[str | None]]
    bbox: BBox | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"rows": self.rows}
        if self.bbox is not None:
            payload["bbox"] = list(self.bbox)
        return payload


@dataclass(slots=True)
class ParsedPage:
    number: int
    width: float
    height: float
    text_blocks: list[TextBlock] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    warnings: list[ParseWarning] = field(default_factory=list)
    image_count: int = 0

    def text_content(self) -> str:
        return "\n".join(block.text for block in self.text_blocks if block.text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "width": self.width,
            "height": self.height,
            "text_blocks": [block.to_dict() for block in self.text_blocks],
            "tables": [table.to_dict() for table in self.tables],
            "warnings": [warning.to_dict() for warning in self.warnings],
            "image_count": self.image_count,
        }


@dataclass(slots=True)
class EngineInfo:
    text: str
    tables: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "tables": self.tables,
        }


@dataclass(slots=True)
class ParsedDocument:
    metadata: dict[str, Any]
    pages: list[ParsedPage]
    warnings: list[ParseWarning]
    engine: EngineInfo

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata,
            "pages": [page.to_dict() for page in self.pages],
            "warnings": [warning.to_dict() for warning in self.warnings],
            "engine": self.engine.to_dict(),
        }

    def to_json(self, *, pretty: bool = False) -> str:
        indent = 2 if pretty else None
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


@dataclass(frozen=True, slots=True)
class ParseOptions:
    page_numbers: list[int] | None = None
    include_tables: bool = True
    scan_text_threshold: int = 20

    @classmethod
    def from_page_spec(
        cls,
        page_spec: str | None,
        *,
        include_tables: bool = True,
        scan_text_threshold: int = 20,
    ) -> ParseOptions:
        return cls(
            page_numbers=parse_page_spec(page_spec),
            include_tables=include_tables,
            scan_text_threshold=scan_text_threshold,
        )


def parse_page_spec(page_spec: str | None) -> list[int] | None:
    if page_spec is None or page_spec.strip() == "":
        return None

    pages: list[int] = []
    seen: set[int] = set()

    for raw_part in page_spec.split(","):
        part = raw_part.strip()
        if not part:
            raise ValueError(f"Invalid page range: {page_spec}")

        if "-" in part:
            start_raw, end_raw = part.split("-", 1)
            try:
                start = int(start_raw)
                end = int(end_raw)
            except ValueError as exc:
                raise ValueError(f"Invalid page range: {page_spec}") from exc
            if start < 1 or end < start:
                raise ValueError(f"Invalid page range: {page_spec}")
            candidates = range(start, end + 1)
        else:
            try:
                page = int(part)
            except ValueError as exc:
                raise ValueError(f"Invalid page range: {page_spec}") from exc
            if page < 1:
                raise ValueError(f"Invalid page range: {page_spec}")
            candidates = (page,)

        for page in candidates:
            if page not in seen:
                pages.append(page)
                seen.add(page)

    return pages

