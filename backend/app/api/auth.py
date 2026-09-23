import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_email_verification_token, decode_access_token, decode_email_verification_token, hash_password, verify_password
from app.db.database import get_db
from app.db.models.user import User, UserSession
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from app.services.credit_service import ensure_credit_account

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def issue_auth(user: User, db: Session) -> AuthResponse:
    now = datetime.now(timezone.utc)
    user.last_login_at = now
    session = UserSession(user_id=user.id)
    db.add(session)
    db.flush()
    db.commit()
    db.refresh(user)
    return AuthResponse(access_token=create_access_token(str(user.id), str(session.id)), user=user)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(email=email, password_hash=hash_password(payload.password), full_name=payload.full_name.strip())
    db.add(user)
    db.commit()
    db.refresh(user)
    ensure_credit_account(db, user.id)
    db.commit()
    response = issue_auth(user, db)
    response.verification_token = create_email_verification_token(str(user.id))
    return response


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is inactive")
    # if not user.email_verified:
    #     raise HTTPException(status_code=403, detail="Email verification required")
    return issue_auth(user, db)


@router.post("/token", response_model=AuthResponse, include_in_schema=False)
def token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> AuthResponse:
    return login(LoginRequest(email=form_data.username, password=form_data.password), db)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)), db: Session = Depends(get_db)) -> None:
    if not credentials:
        return
    claims = decode_access_token(credentials.credentials)
    if not claims:
        return
    try:
        session_id = UUID(claims["sid"])
    except ValueError:
        return
    session = db.get(UserSession, session_id)
    if session and session.ended_at is None:
        session.ended_at = datetime.now(timezone.utc)
        started_at = session.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        session.session_duration_seconds = max(0, int((session.ended_at - started_at).total_seconds()))
        db.commit()


@router.post("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)) -> dict[str, str]:
    subject = decode_email_verification_token(token)
    if not subject:
        raise HTTPException(status_code=400, detail="Invalid or expired email verification token")
    try:
        user_id = UUID(subject)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid email verification token") from exc
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.email_verified = True
    db.commit()
    return {"status": "verified"}
