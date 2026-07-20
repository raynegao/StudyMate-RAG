from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.core.errors import (
    EncryptedPdfError,
    InvalidPdfError,
    PdfTextUnavailableError,
)


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str


def extract_pdf_pages(pdf_path: Path) -> list[PageText]:
    try:
        reader = PdfReader(str(pdf_path))
        if reader.is_encrypted:
            raise EncryptedPdfError()

        pages: list[PageText] = []
        for index, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(PageText(page_number=index, text=text))
    except EncryptedPdfError:
        raise
    except (PdfReadError, OSError, ValueError, TypeError) as exc:
        raise InvalidPdfError() from exc
    except Exception as exc:
        raise InvalidPdfError() from exc

    if not pages:
        raise PdfTextUnavailableError()

    return pages
