import pytest


def test_production_rejects_default_jwt_secret():
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError, match="JWT_SECRET must be configured in production"):
        Settings(app_env="production", jwt_secret="development-only-change-me")


def test_production_rejects_wildcard_cors():
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError, match="CORS_ORIGINS must explicitly list production origins"):
        Settings(app_env="production", jwt_secret="production-secret", cors_origins=["*"])


def test_security_headers_are_present(client):
    headers = client.get("/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "same-origin"
    assert "default-src 'self'" in headers["content-security-policy"]


def test_production_security_headers_include_hsts():
    from app.main import app, settings
    from fastapi.testclient import TestClient
    original = settings.app_env
    settings.app_env = "production"
    try:
        assert "max-age=31536000" in TestClient(app).get("/health").headers["strict-transport-security"]
    finally:
        settings.app_env = original


def test_register_and_me(client):
    response = client.post("/api/auth/register", json={"email": "alex@example.com", "password": "correct horse battery", "full_name": "Alex Kim"})
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "alex@example.com"
    assert body["token_type"] == "bearer"
    profile = client.get("/api/user/profile", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert profile.status_code == 200
    assert profile.json()["id"] == body["user"]["id"]


def test_root_serves_frontend(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "InterviewAI" in response.text


def test_login_rejects_wrong_password(client):
    client.post("/api/auth/register", json={"email": "alex@example.com", "password": "correct horse battery", "full_name": "Alex Kim"})
    response = client.post("/api/auth/login", json={"email": "alex@example.com", "password": "wrong password"})
    assert response.status_code == 401


def test_duplicate_email_is_rejected(client):
    payload = {"email": "alex@example.com", "password": "correct horse battery", "full_name": "Alex Kim"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    assert client.post("/api/auth/register", json=payload).status_code == 409


def test_logout_revokes_session(client):
    response = client.post("/api/auth/register", json={"email": "alex@example.com", "password": "correct horse battery", "full_name": "Alex Kim"})
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/user/profile", headers=headers).status_code == 200
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/user/profile", headers=headers).status_code == 401


def test_email_verification(client):
    response = client.post("/api/auth/register", json={"email": "verify@example.com", "password": "correct horse battery", "full_name": "Verify User"})
    from app.core.security import create_email_verification_token
    from app.db.database import SessionLocal
    from app.db.models.user import User
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "verify@example.com").one()
        assert user.email_verified is False
        token = create_email_verification_token(str(user.id))
    assert client.post("/api/auth/verify-email", params={"token": token}).json() == {"status": "verified"}
    with SessionLocal() as db:
        assert db.query(User).filter(User.email == "verify@example.com").one().email_verified is True
