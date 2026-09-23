from typing import Annotated
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import current_user
from app.core.config import get_settings
from app.db.database import get_db
from app.db.models.domain import Resume
from app.db.models.user import User
from app.schemas.domain import ResumeResponse
from app.services.resume_service import extract_resume_text, parse_profile
from app.services.storage_service import PrivateStorage
from app.services.llm.factory import get_structured_llm_service
from app.services.usage_service import record_ai_usage
from app.services.llm.qwen_provider import LLMProviderError

router = APIRouter(prefix="/api/resumes", tags=["resumes"])
ALLOWED = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


@router.post("/upload", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(file: UploadFile, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> Resume:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED or file.content_type not in (ALLOWED[suffix], "application/octet-stream"):
        raise HTTPException(status_code=415, detail="Only PDF and DOCX resumes are accepted")
    content = await file.read()
    if len(content) > get_settings().max_resume_size_bytes:
        raise HTTPException(status_code=413, detail="Resume exceeds the 10MB limit")
    try:
        text = extract_resume_text(content, file.filename or "resume")
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail="Resume content could not be extracted") from exc
    try:
        profile, result = await get_structured_llm_service().analyze_resume(text)
        parsed_profile = profile.model_dump()
    except (ValueError, LLMProviderError) as exc:
        raise HTTPException(status_code=502, detail="Resume analysis is temporarily unavailable") from exc
    storage = PrivateStorage()
    key = storage.create_key(user.id, suffix)
    storage.put(key, content)
    resume = Resume(user_id=user.id, original_filename=file.filename or "resume", file_type=file.content_type or ALLOWED[suffix], file_size=len(content), storage_key=key, extracted_text=text, parsed_profile_json=parsed_profile or parse_profile(text))
    db.add(resume)
    db.commit()
    record_ai_usage(db, user_id=user.id, interview_id=None, request_type="resume_analysis", result=result)
    db.refresh(resume)
    return resume


@router.get("", response_model=list[ResumeResponse])
def list_resumes(user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> list[Resume]:
    return list(db.scalars(select(Resume).where(Resume.user_id == user.id, Resume.deleted_at.is_(None)).order_by(Resume.uploaded_at.desc())))


@router.get("/{resume_id}", response_model=ResumeResponse)
def get_resume(resume_id: UUID, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> Resume:
    resume = db.scalar(select(Resume).where(Resume.id == resume_id, Resume.user_id == user.id, Resume.deleted_at.is_(None)))
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return resume


@router.delete("/{resume_id}", status_code=204)
def delete_resume(resume_id: UUID, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> None:
    resume = db.scalar(select(Resume).where(Resume.id == resume_id, Resume.user_id == user.id, Resume.deleted_at.is_(None)))
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    resume.deleted_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    db.commit()
