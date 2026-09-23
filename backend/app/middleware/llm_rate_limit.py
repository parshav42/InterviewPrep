from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import current_user
from app.db.database import get_db
from app.db.models.domain import AIUsage
from app.db.models.user import User

MAX_REQUESTS_PER_MINUTE = 30


def check_llm_rate_limit(user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> None:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=1)
    count = db.scalar(select(func.count(AIUsage.id)).where(AIUsage.user_id == user.id, AIUsage.created_at >= cutoff)) or 0
    if count >= MAX_REQUESTS_PER_MINUTE:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="AI request limit reached; please try again shortly", headers={"Retry-After": "60"})
