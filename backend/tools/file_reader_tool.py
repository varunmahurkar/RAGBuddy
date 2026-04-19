"""
file_reader_tool — extracts raw text from PDF, DOCX, TXT, and Markdown files.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def read_file(path: str | Path) -> str:
    """
    Read a document and return its plain-text content.
    Supports: .pdf, .docx, .txt, .md
    """
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix == ".pdf":
        return _read_pdf(p)
    elif suffix == ".docx":
        return _read_docx(p)
    elif suffix in (".txt", ".md", ".markdown"):
        return _read_text(p)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError("pypdf is required for PDF support: pip install pypdf")

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text.strip())
    return "\n\n".join(pages)


def _read_docx(path: Path) -> str:
    try:
        from docx import Document
    except ImportError:
        raise ImportError("python-docx is required: pip install python-docx")

    doc = Document(str(path))
    paragraphs = []
    for para in doc.paragraphs:
        if para.text.strip():
            paragraphs.append(para.text.strip())
    return "\n\n".join(paragraphs)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")
