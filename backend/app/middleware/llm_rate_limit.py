from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status

from app.api.dependencies import current_user
from app.db.models.user import User

_requests: dict[UUID, deque[datetime]] = defaultdict(deque)
MAX_REQUESTS_PER_MINUTE = 30


def check_llm_rate_limit(user: Annotated[User, Depends(current_user)]) -> None:
    now = datetime.now(timezone.utc)
    window = _requests[user.id]
    cutoff = now - timedelta(minutes=1)
    while window and window[0] < cutoff:
        window.popleft()
    if len(window) >= MAX_REQUESTS_PER_MINUTE:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="AI request limit reached; please try again shortly")
    window.append(now)
