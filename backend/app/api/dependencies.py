from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.database import get_db
from app.db.models.user import User, UserRole, UserSession

bearer = HTTPBearer(auto_error=False)


def current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)], db: Annotated[Session, Depends(get_db)]) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    claims = decode_access_token(credentials.credentials)
    subject = claims.get("sub") if claims else None
    try:
        user_id = UUID(subject or "")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication token") from exc
    try:
        session_id = UUID(claims["sid"]) if claims else None
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication token") from exc
    session = db.scalar(select(UserSession).where(UserSession.id == session_id, UserSession.user_id == user_id, UserSession.ended_at.is_(None))) if session_id else None
    user = db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True))) if session else None
    if not user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    return user


def admin_user(user: Annotated[User, Depends(current_user)]) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
