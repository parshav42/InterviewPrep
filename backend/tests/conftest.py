import os

os.environ["DATABASE_URL"] = "sqlite:///./test_interviewai.db"
os.environ["JWT_SECRET"] = "test-secret-with-enough-length"
os.environ["APP_ENV"] = "development"
os.environ["LLM_PROVIDER"] = "mock"

import pytest
from fastapi.testclient import TestClient

from app.db.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
