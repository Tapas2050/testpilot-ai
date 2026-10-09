"""Document text extractors and validation for PDF, TXT, Markdown, and JSON."""

import json
from pathlib import Path
from typing import Tuple

import fitz  # PyMuPDF


class DocumentValidationError(Exception):
    """Raised when an uploaded document fails type, size, or content validation."""
    pass


class ExtractionError(Exception):
    """Raised when an uploaded document cannot be parsed or text extracted."""
    pass


ALLOWED_EXTENSIONS = {
    ".pdf": "pdf",
    ".txt": "txt",
    ".md": "markdown",
    ".markdown": "markdown",
    ".json": "json",
}


def validate_file_upload(filename: str, content: bytes, max_mb: int = 10) -> Tuple[str, str]:
    """Validate file extension, size, and content header.

    Returns:
        (canonical_type, safe_stored_filename_extension)
    """
    if not content or len(content) == 0:
        raise DocumentValidationError("File is empty (0 bytes).")

    max_bytes = max_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise DocumentValidationError(f"File exceeds maximum allowed size of {max_mb} MB.")

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise DocumentValidationError(
            f"Unsupported file extension '{ext}'. Allowed types: PDF, TXT, Markdown, JSON."
        )

    file_type = ALLOWED_EXTENSIONS[ext]

    # Content-level validation against spoofing
    if file_type == "pdf":
        if not content.startswith(b"%PDF"):
            raise DocumentValidationError("Invalid PDF: Missing %PDF file header.")
    elif file_type == "json":
        try:
            text = content.decode("utf-8")
            json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise DocumentValidationError(f"Invalid JSON content: {str(e)}") from e
    else:  # txt or markdown
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as e:
            msg = f"Invalid text content (must be UTF-8 encoded): {str(e)}"
            raise DocumentValidationError(msg) from e

    return file_type, ext


def extract_text(file_type: str, content: bytes) -> str:
    """Extract plain text from file content based on verified file type."""
    if file_type == "pdf":
        return _extract_pdf(content)
    elif file_type == "json":
        return _extract_json(content)
    elif file_type in ("txt", "markdown"):
        return _extract_text(content)
    else:
        raise ExtractionError(f"Unsupported extraction file type: {file_type}")


def _extract_pdf(content: bytes) -> str:
    try:
        doc = fitz.open(stream=content, filetype="pdf")
        pages_text = []
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            text = page.get_text()
            if text.strip():
                pages_text.append(f"--- Page {page_idx + 1} ---\n{text.strip()}")
        doc.close()
        extracted = "\n\n".join(pages_text).strip()
        if not extracted:
            return ""
        return extracted
    except Exception as e:
        raise ExtractionError(f"Failed to extract text from PDF: {str(e)}") from e


def _extract_json(content: bytes) -> str:
    try:
        parsed = json.loads(content.decode("utf-8"))
        return json.dumps(parsed, indent=2, ensure_ascii=False)
    except Exception as e:
        raise ExtractionError(f"Failed to extract text from JSON: {str(e)}") from e


def _extract_text(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except Exception as e:
        raise ExtractionError(f"Failed to decode text file: {str(e)}") from e
