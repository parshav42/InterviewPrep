from io import BytesIO
from pathlib import Path

import fitz
from docx import Document


def extract_resume_text(content: bytes, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        document = fitz.open(stream=content, filetype="pdf")
        return "\n".join(page.get_text() for page in document).strip()
    if suffix == ".docx":
        document = Document(BytesIO(content))
        return "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
    raise ValueError("Unsupported resume format")


def parse_profile(text: str) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return {"skills": [], "education": [], "experience": [], "projects": [], "certifications": [], "source_line_count": len(lines)}
