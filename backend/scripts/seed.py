import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.security import hash_password
from app.db.database import SessionLocal
from app.db.models.user import User, UserRole


def main() -> None:
    password = os.environ.get("SEED_ADMIN_PASSWORD")
    if not password:
        raise SystemExit("Set SEED_ADMIN_PASSWORD in the environment; it is never hard-coded.")
    with SessionLocal() as db:
        email = os.environ.get("SEED_ADMIN_EMAIL", "admin@example.com").lower()
        user = db.scalar(select(User).where(User.email == email))
        if user:
            user.role = UserRole.ADMIN
        else:
            db.add(User(email=email, password_hash=hash_password(password), full_name="InterviewAI Admin", role=UserRole.ADMIN, email_verified=True))
        db.commit()
        print(f"Admin account ready: {email}")


if __name__ == "__main__":
    main()
