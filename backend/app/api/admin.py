from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import admin_user
from app.db.database import get_db
from app.db.models.domain import AdminAuditLog, AIUsage, AnalyticsEvent, Interview, Job, Resume
from app.db.models.user import User
from app.services.storage_service import PrivateStorage

router = APIRouter(prefix="/api/admin", tags=["admin"])


def initials_for(name: str | None, email: str | None) -> str:
    source = (name or email or "U").strip()
    if not source:
        return "U"
    parts = [p for p in source.replace("-", " ").split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return source[0].upper() if source else "U"


def resume_payload_for_user(db: Session, user_id: str | UUID) -> dict | None:
    resume = db.scalar(select(Resume).where(Resume.user_id == user_id, Resume.deleted_at.is_(None)).order_by(Resume.uploaded_at.desc()))
    if not resume:
        return None
    return {"id": str(resume.id), "filename": resume.original_filename, "file_type": resume.file_type, "url": f"/api/admin/users/{user_id}/resume"}


def audit(db: Session, admin: User, action: str, target_type: str, target_id: str | None = None, request: Request | None = None) -> None:
    db.add(AdminAuditLog(admin_user_id=admin.id, action=action, target_type=target_type, target_id=target_id, ip_address=request.client.host if request and request.client else None))
    db.commit()


@router.get("/dashboard", dependencies=[Depends(admin_user)])
def dashboard(db: Annotated[Session, Depends(get_db)]) -> dict:
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today - timedelta(days=7)
    total_users = db.scalar(select(func.count()).select_from(User)) or 0
    active_users = db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0
    active_users_today = db.scalar(select(func.count()).select_from(User).where(User.last_login_at >= today)) or 0
    new_users_today = db.scalar(select(func.count()).select_from(User).where(User.created_at >= today)) or 0
    total_resumes = db.scalar(select(func.count()).select_from(Resume)) or 0
    total_jobs = db.scalar(select(func.count()).select_from(Job)) or 0
    total_interviews = db.scalar(select(func.count()).select_from(Interview)) or 0
    completed = db.scalar(select(func.count()).select_from(Interview).where(Interview.status == "COMPLETED")) or 0
    interviews_today = db.scalar(select(func.count()).select_from(Interview).where(Interview.created_at >= today)) or 0
    interviews_this_week = db.scalar(select(func.count()).select_from(Interview).where(Interview.created_at >= week_start)) or 0
    avg_score = db.scalar(select(func.avg(Interview.overall_score)).where(Interview.overall_score.is_not(None)))
    average_duration = db.scalar(select(func.avg(Interview.actual_duration_seconds)).where(Interview.actual_duration_seconds.is_not(None))) or 0
    ai_requests = db.scalar(select(func.count()).select_from(AIUsage)) or 0
    failures = db.scalar(select(func.count()).select_from(AIUsage).where(AIUsage.status != "success")) or 0
    average_latency = db.scalar(select(func.avg(AIUsage.latency_ms)).where(AIUsage.status == "success")) or 0
    average_tokens = db.scalar(select(func.avg(AIUsage.input_tokens + AIUsage.output_tokens))) or 0
    recent_users = list(db.scalars(select(User).order_by(User.created_at.desc()).limit(5)))
    recent_interviews = list(db.scalars(select(Interview).order_by(Interview.created_at.desc()).limit(5)))
    recent_users_payload = []
    for user in recent_users:
        resume = resume_payload_for_user(db, user.id)
        recent_users_payload.append({
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at,
            "avatar_initials": initials_for(user.full_name, user.email),
            "resume_filename": resume["filename"] if resume else None,
            "resume_url": resume["url"] if resume else None,
        })
    return {
        "total_users": total_users,
        "active_users": active_users,
        "active_users_today": active_users_today,
        "new_users_today": new_users_today,
        "total_resumes": total_resumes,
        "total_jobs": total_jobs,
        "total_interviews": total_interviews,
        "interviews_today": interviews_today,
        "interviews_this_week": interviews_this_week,
        "completed_interviews": completed,
        "average_interview_duration_seconds": round(float(average_duration), 2),
        "average_interview_score": round(float(avg_score or 0), 2),
        "resume_uploads": total_resumes,
        "ai_requests": ai_requests,
        "ai_failures": failures,
        "average_llm_latency_ms": round(float(average_latency), 2),
        "average_tokens_per_request": round(float(average_tokens), 2),
        "estimated_ai_cost": float(db.scalar(select(func.coalesce(func.sum(AIUsage.estimated_cost), 0))) or 0),
        "recent_users": recent_users_payload,
        "recent_interviews": [{"id": str(interview.id), "user_id": str(interview.user_id), "status": interview.status, "score": interview.overall_score, "created_at": interview.created_at} for interview in recent_interviews],
    }


@router.get("/users", dependencies=[Depends(admin_user)])
def users(page: int = 1, page_size: int = 25, search: str | None = None, db: Session = Depends(get_db)) -> dict:
    page = max(1, page); page_size = min(max(1, page_size), 100)
    query = select(User).order_by(User.created_at.desc())
    count_query = select(func.count()).select_from(User)
    if search:
        term = f"%{search.lower()}%"
        query = query.where(func.lower(User.email).like(term) | func.lower(User.full_name).like(term))
        count_query = count_query.where(func.lower(User.email).like(term) | func.lower(User.full_name).like(term))
    rows = list(db.scalars(query.offset((page - 1) * page_size).limit(page_size)))
    items = []
    for row in rows:
        resume = resume_payload_for_user(db, row.id)
        items.append({
            "id": str(row.id),
            "email": row.email,
            "full_name": row.full_name,
            "role": row.role,
            "is_active": row.is_active,
            "created_at": row.created_at,
            "last_login_at": row.last_login_at,
            "avatar_initials": initials_for(row.full_name, row.email),
            "resume_filename": resume["filename"] if resume else None,
            "resume_url": resume["url"] if resume else None,
        })
    return {"items": items, "page": page, "page_size": page_size, "total": db.scalar(count_query) or 0}


@router.get("/users/{user_id}/resume")
def user_resume_download(user_id: UUID, admin: Annotated[User, Depends(admin_user)], db: Annotated[Session, Depends(get_db)]) -> Response:
    resume = db.scalar(select(Resume).where(Resume.user_id == user_id, Resume.deleted_at.is_(None)).order_by(Resume.uploaded_at.desc()))
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    storage = PrivateStorage()
    try:
        content = storage.get(resume.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Resume file not found") from exc
    return Response(content=content, media_type=resume.file_type or "application/octet-stream", headers={"Content-Disposition": f'inline; filename="{resume.original_filename}"'})


@router.get("/users/{user_id}")
def user_detail(user_id: UUID, request: Request, admin: Annotated[User, Depends(admin_user)], db: Annotated[Session, Depends(get_db)]) -> dict:
    target = db.get(User, user_id)
    if not target:
        return {"detail": "User not found"}
    audit(db, admin, "view_user", "user", str(user_id), request)
    interview_count = db.scalar(select(func.count()).select_from(Interview).where(Interview.user_id == user_id)) or 0
    return {"id": str(target.id), "email": target.email, "full_name": target.full_name, "role": target.role, "created_at": target.created_at, "last_login_at": target.last_login_at, "interview_count": interview_count}


@router.get("/interviews", dependencies=[Depends(admin_user)])
def interviews(page: int = 1, page_size: int = 25, db: Session = Depends(get_db)) -> dict:
    page_size = min(max(1, page_size), 100)
    query = select(Interview).order_by(Interview.created_at.desc())
    rows = list(db.scalars(query.offset((max(1, page) - 1) * page_size).limit(page_size)))
    return {"items": [{"id": str(row.id), "user_id": str(row.user_id), "status": row.status, "score": row.overall_score, "duration_seconds": row.actual_duration_seconds, "created_at": row.created_at} for row in rows], "page": max(1, page), "page_size": page_size}


@router.get("/resumes", dependencies=[Depends(admin_user)])
def resumes(page: int = 1, page_size: int = 25, db: Session = Depends(get_db)) -> dict:
    page_size = min(max(1, page_size), 100)
    rows = list(db.scalars(select(Resume).order_by(Resume.uploaded_at.desc()).offset((max(1, page) - 1) * page_size).limit(page_size)))
    return {"items": [{"id": str(row.id), "user_id": str(row.user_id), "filename": row.original_filename, "file_size": row.file_size, "uploaded_at": row.uploaded_at, "deleted": row.deleted_at is not None} for row in rows], "page": max(1, page), "page_size": page_size}


@router.get("/analytics", dependencies=[Depends(admin_user)])
def analytics(db: Annotated[Session, Depends(get_db)]) -> dict:
    return {"events": db.scalar(select(func.count()).select_from(AnalyticsEvent)) or 0, "interviews": db.scalar(select(func.count()).select_from(Interview)) or 0}


@router.get("/ai-usage", dependencies=[Depends(admin_user)])
def ai_usage(db: Annotated[Session, Depends(get_db)]) -> dict:
    return {"requests": db.scalar(select(func.count()).select_from(AIUsage)) or 0, "failed_requests": db.scalar(select(func.count()).select_from(AIUsage).where(AIUsage.status != "success")) or 0, "input_tokens": db.scalar(select(func.coalesce(func.sum(AIUsage.input_tokens), 0))) or 0, "output_tokens": db.scalar(select(func.coalesce(func.sum(AIUsage.output_tokens), 0))) or 0, "average_latency_ms": float(db.scalar(select(func.coalesce(func.avg(AIUsage.latency_ms), 0))) or 0), "estimated_cost": float(db.scalar(select(func.coalesce(func.sum(AIUsage.estimated_cost), 0))) or 0)}


@router.get("/audit-logs", dependencies=[Depends(admin_user)])
def audit_logs(page: int = 1, page_size: int = 50, db: Session = Depends(get_db)) -> dict:
    rows = list(db.scalars(select(AdminAuditLog).order_by(AdminAuditLog.timestamp.desc()).offset((max(1, page) - 1) * min(page_size, 100)).limit(min(page_size, 100))))
    return {"items": [{"id": str(row.id), "action": row.action, "target_type": row.target_type, "target_id": row.target_id, "timestamp": row.timestamp} for row in rows], "page": max(1, page)}
