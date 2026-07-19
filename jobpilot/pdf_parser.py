"""PDF and text file parsing for resume uploads."""

import hashlib
from pathlib import Path

from jobpilot.config import MAX_FILE_SIZE, ALLOWED_UPLOAD_TYPES


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text content from a PDF file."""
    try:
        from pypdf import PdfReader
        import io

        reader = PdfReader(io.BytesIO(file_bytes))
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n\n".join(text_parts).strip()
    except Exception as e:
        raise ValueError(f"Failed to parse PDF: {e}")


def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    """Extract text content from a file based on its extension."""
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        return extract_text_from_pdf(file_bytes)
    elif ext in (".txt", ".md", ".rtf"):
        try:
            return file_bytes.decode("utf-8").strip()
        except UnicodeDecodeError:
            try:
                return file_bytes.decode("latin-1").strip()
            except Exception:
                raise ValueError("Unable to decode file content")
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def validate_upload(file_bytes: bytes, filename: str) -> tuple[bool, str]:
    """Validate an uploaded file. Returns (is_valid, error_message)."""
    if not filename:
        return False, "No filename provided"

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_UPLOAD_TYPES:
        return (
            False,
            f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_UPLOAD_TYPES)}",
        )

    if len(file_bytes) > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE / (1024 * 1024)
        return False, f"File too large. Maximum size: {max_mb}MB"

    if len(file_bytes) == 0:
        return False, "File is empty"

    return True, ""


def generate_resume_id(file_bytes: bytes, filename: str) -> str:
    """Generate a deterministic ID for an uploaded resume."""
    content = f"{filename}|{len(file_bytes)}|{file_bytes[:1024]}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def get_file_type(filename: str) -> str:
    """Get the file type from filename."""
    ext = Path(filename).suffix.lower()
    type_map = {
        ".pdf": "pdf",
        ".txt": "txt",
        ".md": "txt",
        ".rtf": "txt",
    }
    return type_map.get(ext, "unknown")
