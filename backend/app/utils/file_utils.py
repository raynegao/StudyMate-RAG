from __future__ import annotations

import re
import shutil
from inspect import isawaitable
from pathlib import Path
from typing import BinaryIO


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_filename(filename: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    return safe_name or "document.pdf"


async def save_upload_file(upload_file, destination: Path) -> Path:
    ensure_directory(destination.parent)
    contents = upload_file.read()
    if isawaitable(contents):
        contents = await contents
    destination.write_bytes(contents)
    return destination


def copy_fileobj(source: BinaryIO, destination: Path) -> Path:
    ensure_directory(destination.parent)
    with destination.open("wb") as target:
        shutil.copyfileobj(source, target)
    return destination
