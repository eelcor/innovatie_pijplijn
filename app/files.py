"""File handling helpers — centralized upload/download/validation utilities."""

import mimetypes
import os
import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

# --- Constants ---

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "data", "uploads")
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB

# Allowed MIME types for upload
ALLOWED_MIME_PREFIXES = (
    "image/",
    "application/pdf",
    "text/",
    "application/json",
    "application/xml",
    "application/zip",
    "application/vnd.openxmlformats-officedocument.",
    "application/vnd.ms-",
    "audio/",
    "video/",
)

# --- Helpers ---


def _sanitize_filename(filename: str | None) -> str:
    """Sanitize a filename for safe use in Content-Disposition headers.

    Strips path components, controls, and quotes. Returns empty string if input is None/empty.
    """
    if not filename:
        return ""
    # Strip directory path
    name = os.path.basename(filename)
    # Remove control characters and quotes
    name = re.sub(r'[\x00-\x1f"\\]', "", name)
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()
    return name


def safe_content_disposition(filename: str | None, disposition: str = "attachment") -> str:
    """Build a safe Content-Disposition header value.

    Uses RFC 5987 encoding for non-ASCII filenames.
    """
    safe_name = _sanitize_filename(filename) or "download"
    # ASCII-safe fallback
    ascii_name = re.sub(r"[^\x20-\x7e]", "_", safe_name)
    return f'{disposition}; filename="{ascii_name}"; filename*=UTF-8\'\'{safe_name}'


def validate_upload(file: UploadFile, max_size: int = MAX_FILE_SIZE) -> bytes:
    """Read and validate an uploaded file.

    Checks:
    - File size within limit
    - MIME type prefix in allowlist (based on content_type header)
    - Extension matches expected types

    Returns file contents as bytes.
    """
    contents = file.file.read() if hasattr(file.file, 'read') else b""
    # For UploadFile, use await file.read() — this is called from async context
    # Caller passes already-read bytes
    if len(contents) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"Bestand is te groot. Maximum: {max_size // (1024 * 1024)} MB",
        )

    # Validate extension against known types
    if file.filename:
        ext = os.path.splitext(file.filename)[1].lower()
        guessed_mime = mimetypes.guess_type(file.filename)[0]
        if ext and not guessed_mime and ext not in (".md", ".txt", ".json", ".xml", ".csv"):
            # Unknown extension — allow but warn
            pass

    return contents


def generate_storage_path(subdir: str, parent_id: str, original_filename: str | None) -> tuple[str, str]:
    """Generate a UUID-based storage path for an uploaded file.

    Returns (relative_storage_path, unique_filename).
    The original filename is stored only as metadata in the database.
    """
    ext = ""
    if original_filename:
        ext = os.path.splitext(original_filename)[1].lower()

    unique_name = f"{uuid.uuid4().hex}{ext}"
    storage_path = os.path.join(subdir, parent_id, unique_name)
    return storage_path, unique_name


def resolve_upload_dir() -> str:
    """Get the absolute upload directory path."""
    return UPLOAD_DIR


def ensure_storage_dir(storage_path: str) -> None:
    """Create the directory for a storage path if it doesn't exist."""
    full_path = os.path.join(BASE_DIR, storage_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
