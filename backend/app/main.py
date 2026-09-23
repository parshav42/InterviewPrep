from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import admin, analytics, auth, interviews, jobs, resumes, users
from app.core.config import get_settings
from app.db.database import Base, engine
from app.services.llm.service import get_llm_service

settings = get_settings()
project_root = Path("/app") if (Path("/app") / "index.html").exists() else Path(__file__).resolve().parents[2]
app = FastAPI(title="InterviewAI API", version="0.1.0")
app.mount("/css", StaticFiles(directory=project_root / "css"), name="css")
app.mount("/js", StaticFiles(directory=project_root / "js"), name="js")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(resumes.router)
app.include_router(jobs.router)
app.include_router(interviews.router)
app.include_router(analytics.router)
app.include_router(admin.router)


@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; connect-src 'self' http://127.0.0.1:8002 http://localhost:8002; media-src 'self' blob:; script-src 'self'; style-src 'self' 'unsafe-inline'"
    if settings.app_env == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.on_event("startup")
def create_development_tables() -> None:
    if settings.app_env == "development" and settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(project_root / "index.html")


@app.get("/health/llm", tags=["system"])
async def llm_health() -> dict[str, str | bool]:
    healthy = await get_llm_service().health()
    configured = settings.llm_provider == "mock" or (settings.llm_provider == "huggingface" and bool(settings.hf_token)) or (settings.llm_provider == "qwen_remote" and bool(settings.llm_base_url))
    return {"status": "ok" if healthy else "unavailable", "configured": configured, "reachable": healthy}


@app.get("/admin", include_in_schema=False)
def admin_panel() -> FileResponse:
    return FileResponse(project_root / "admin.html")


@app.get("/admin.js", include_in_schema=False)
def admin_script() -> FileResponse:
    return FileResponse(project_root / "admin.js", media_type="application/javascript")
