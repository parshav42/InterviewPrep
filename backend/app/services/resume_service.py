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
    name = ""
    email = ""
    summary = " ".join(lines[:3])[:500] if lines else ""
    for line in lines:
        lowered = line.lower()
        if "@" in line and "." in line:
            email = line
            break
    for line in lines:
        if len(line.split()) <= 5 and not any(marker in line.lower() for marker in ["@", "http", "linkedin", "github", "education", "experience", "skills"]):
            name = line
            break
    skills = []
    for keyword in ["python", "sql", "javascript", "aws", "docker", "fastapi", "react", "postgres", "ml", "machine learning", "data", "api"]:
        if keyword in " ".join(lines).lower() and keyword not in skills:
            skills.append(keyword)
    experience_years = 0
    for line in lines:
        match = __import__("re").search(r"(\d+)\s*(?:\+\s*)?years?", line, __import__("re").IGNORECASE)
        if match:
            experience_years = max(experience_years, int(match.group(1)))
    return {
        "name": name,
        "email": email,
        "skills": skills,
        "experience_years": experience_years,
        "experience": [],
        "education": [],
        "projects": [],
        "certifications": [],
        "summary": summary,
        "source_line_count": len(lines),
    }
