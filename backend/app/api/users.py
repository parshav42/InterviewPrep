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
    balance = credit.balance_minutes if credit else 0
    return {"balance_minutes": balance, "balance_interviews": balance}


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


@router.delete("/data")
def delete_user_data(user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> dict[str, dict[str, int]]:
    from app.db.models.domain import AnalyticsEvent, Answer, Feedback, InterviewQuestion

    interview_ids = db.scalars(select(Interview.id).where(Interview.user_id == user.id)).all()
    answer_ids = db.scalars(select(Answer.id).where(Answer.user_id == user.id)).all()
    removed = {
        "resumes": len(db.scalars(select(Resume.id).where(Resume.user_id == user.id)).all()),
        "jobs": len(db.scalars(select(Job.id).where(Job.user_id == user.id)).all()),
        "interviews": len(interview_ids),
    }
    if answer_ids:
        db.query(Feedback).filter(Feedback.answer_id.in_(answer_ids)).delete(synchronize_session=False)
    db.query(Answer).filter(Answer.user_id == user.id).delete(synchronize_session=False)
    if interview_ids:
        db.query(InterviewQuestion).filter(InterviewQuestion.interview_id.in_(interview_ids)).delete(synchronize_session=False)
    db.query(AnalyticsEvent).filter(AnalyticsEvent.user_id == user.id).delete(synchronize_session=False)
    db.query(Interview).filter(Interview.user_id == user.id).delete(synchronize_session=False)
    db.query(Job).filter(Job.user_id == user.id).delete(synchronize_session=False)
    db.query(Resume).filter(Resume.user_id == user.id).delete(synchronize_session=False)
    db.commit()
    return {"removed": {"resumes": removed["resumes"], "jobs": removed["jobs"], "interviews": removed["interviews"]}}


@router.get("/export")
def export_account(user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> JSONResponse:
    resumes = db.scalars(select(Resume).where(Resume.user_id == user.id)).all()
    jobs = db.scalars(select(Job).where(Job.user_id == user.id)).all()
    interviews = db.scalars(select(Interview).where(Interview.user_id == user.id)).all()
    return JSONResponse({"account": {"id": str(user.id), "email": user.email, "full_name": user.full_name}, "resumes": [{"id": str(item.id), "filename": item.original_filename, "uploaded_at": item.uploaded_at.isoformat()} for item in resumes], "jobs": [{"id": str(item.id), "title": item.title, "created_at": item.created_at.isoformat()} for item in jobs], "interviews": [{"id": str(item.id), "status": item.status, "created_at": item.created_at.isoformat()} for item in interviews]})
