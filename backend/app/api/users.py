from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import current_user
from app.db.database import get_db
from app.db.models.user import User
from app.db.models.domain import Interview, Job, Resume
from app.schemas.auth import UserResponse
from app.db.models.domain import Credit

router = APIRouter(prefix="/api/user", tags=["user"])


@router.get("/profile", response_model=UserResponse)
def profile(user: Annotated[User, Depends(current_user)]) -> UserResponse:
    return user


@router.get("/credits")
def credits(user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> dict[str, int]:
    credit = db.scalar(select(Credit).where(Credit.user_id == user.id))
    return {"balance_minutes": credit.balance_minutes if credit else 0}


@router.patch("/profile", response_model=UserResponse)
def update_profile(full_name: str, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> UserResponse:
    user.full_name = full_name.strip()
    db.commit()
    db.refresh(user)
    return user


@router.delete("/account", status_code=204)
def delete_account(user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> None:
    db.delete(user)
    db.commit()


@router.get("/export")
def export_account(user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> JSONResponse:
    resumes = db.scalars(select(Resume).where(Resume.user_id == user.id)).all()
    jobs = db.scalars(select(Job).where(Job.user_id == user.id)).all()
    interviews = db.scalars(select(Interview).where(Interview.user_id == user.id)).all()
    return JSONResponse({"account": {"id": str(user.id), "email": user.email, "full_name": user.full_name}, "resumes": [{"id": str(item.id), "filename": item.original_filename, "uploaded_at": item.uploaded_at.isoformat()} for item in resumes], "jobs": [{"id": str(item.id), "title": item.title, "created_at": item.created_at.isoformat()} for item in jobs], "interviews": [{"id": str(item.id), "status": item.status, "created_at": item.created_at.isoformat()} for item in interviews]})
