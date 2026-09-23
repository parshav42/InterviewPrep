from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import current_user
from app.db.database import get_db
from app.db.models.domain import AnalyticsEvent
from app.db.models.user import User

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


class AnalyticsEventCreate(BaseModel):
    event_name: str
    metadata: dict | None = None


@router.post("/events", status_code=202)
def record_event(payload: AnalyticsEventCreate, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    safe_metadata = payload.metadata or {}
    forbidden = {"password", "token", "api_key", "authorization", "resume_text", "answer_text"}
    safe_metadata = {key: value for key, value in safe_metadata.items() if key.lower() not in forbidden}
    db.add(AnalyticsEvent(user_id=user.id, event_name=payload.event_name, metadata_json=safe_metadata))
    db.commit()
    return {"status": "accepted"}
