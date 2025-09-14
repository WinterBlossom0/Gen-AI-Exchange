from __future__ import annotations

from pathlib import Path
from typing import Optional

from pypdf import PdfReader


def load_pdf_text(pdf_path: Path) -> str:
    """Extract text from a PDF using pypdf with simple cleanup.

    Args:
        pdf_path: Path to the PDF file.
    Returns:
        Concatenated text string extracted from the PDF.
    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the PDF has no extractable text.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    reader = PdfReader(str(pdf_path))
    texts = []
    for page in reader.pages:
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        texts.append(t)

    text = "\n".join(texts)

    # Basic cleanup
    text = "\n".join(line.strip() for line in text.splitlines())
    text = "\n".join([l for l in text.splitlines() if l])

    if not text.strip():
        raise ValueError("No extractable text found in PDF. Consider OCR.")

    return text
