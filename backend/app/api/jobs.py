from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import current_user
from app.db.database import get_db
from app.db.models.domain import Job
from app.db.models.user import User
from app.schemas.domain import JobCreate, JobResponse
from app.services.llm.factory import get_structured_llm_service
from app.services.usage_service import record_ai_usage
from app.services.llm.qwen_provider import LLMProviderError

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(payload: JobCreate, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> Job:
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Job title is required")
    payload.title = title
    payload.job_description = payload.job_description or ""
    try:
        analysis, result = await get_structured_llm_service().analyze_job_description(payload.title, payload.job_description)
    except (ValueError, LLMProviderError) as exc:
        raise HTTPException(status_code=502, detail="Job description analysis is temporarily unavailable") from exc
    job = Job(user_id=user.id, parsed_analysis_json=analysis.model_dump(), **payload.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)
    record_ai_usage(db, user_id=user.id, interview_id=None, request_type="job_analysis", result=result)
    return job


@router.get("", response_model=list[JobResponse])
def list_jobs(user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> list[Job]:
    return list(db.scalars(select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc())))


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: UUID, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> Job:
    job = db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user.id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: UUID, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> None:
    job = db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user.id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()
