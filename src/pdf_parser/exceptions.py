class PdfParserError(Exception):
    """Base exception for pdf-parser failures."""


class MissingDependencyError(PdfParserError):
    """Raised when an optional PDF backend dependency is not installed."""

