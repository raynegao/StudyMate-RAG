from __future__ import annotations

import re
import shutil
import unicodedata
from inspect import isawaitable
from pathlib import Path
from typing import BinaryIO

from app.core.errors import InvalidDocumentIdError, UploadTooLargeError

DOCUMENT_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{32}$")
UPLOAD_CHUNK_SIZE = 1024 * 1024


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_filename(filename: str) -> str:
    # Browsers may submit either POSIX or Windows-style client paths.
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    normalized = unicodedata.normalize("NFC", basename)
    safe_name = "".join(
        character
        for character in normalized
        if character not in {"/", "\\", "\x00"}
        and (ord(character) >= 32 and ord(character) != 127)
    ).strip(" .")
    if not safe_name or safe_name in {".", ".."}:
        return "document.pdf"

    suffix = Path(safe_name).suffix
    stem = safe_name[: -len(suffix)] if suffix else safe_name
    suffix_bytes = suffix.encode("utf-8")[:20]
    suffix = suffix_bytes.decode("utf-8", errors="ignore")
    remaining_bytes = max(1, 180 - len(suffix.encode("utf-8")))
    truncated_stem = ""
    for character in stem:
        encoded = (truncated_stem + character).encode("utf-8")
        if len(encoded) > remaining_bytes:
            break
        truncated_stem += character
    return f"{truncated_stem}{suffix}" or "document.pdf"


def validate_document_id(document_id: str) -> str:
    if not DOCUMENT_ID_PATTERN.fullmatch(document_id):
        raise InvalidDocumentIdError()
    return document_id.lower()


async def save_upload_file(
    upload_file,
    destination: Path,
    *,
    max_bytes: int | None = None,
) -> Path:
    ensure_directory(destination.parent)
    written = 0
    try:
        with destination.open("wb") as target:
            while True:
                chunk = upload_file.read(UPLOAD_CHUNK_SIZE)
                if isawaitable(chunk):
                    chunk = await chunk
                if not chunk:
                    break
                written += len(chunk)
                if max_bytes is not None and written > max_bytes:
                    raise UploadTooLargeError(
                        details={"max_size_bytes": max_bytes},
                    )
                target.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination


def copy_fileobj(source: BinaryIO, destination: Path) -> Path:
    ensure_directory(destination.parent)
    with destination.open("wb") as target:
        shutil.copyfileobj(source, target)
    return destination
