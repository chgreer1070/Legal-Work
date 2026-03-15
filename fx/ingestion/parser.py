"""
Contract document text extraction.
Reuses pypdf and mammoth already in project dependencies.
"""

from pathlib import Path


def extract_text_from_pdf(file_path: Path) -> str:
    """Extract text from a PDF file."""
    from pypdf import PdfReader

    reader = PdfReader(str(file_path))
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)
    return "\n\n".join(text_parts)


def extract_text_from_docx(file_path: Path) -> str:
    """Extract text from a DOCX file."""
    import mammoth

    with open(file_path, "rb") as f:
        result = mammoth.extract_raw_text(f)
    return result.value


def extract_text(file_path: Path) -> str:
    """Extract text from a contract file (PDF or DOCX)."""
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext in (".docx", ".doc"):
        return extract_text_from_docx(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")
