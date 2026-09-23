from pathlib import Path
from functools import lru_cache
from typing import Annotated

from pydantic import BeforeValidator, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def parse_cors_origins(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return value
    value = value.strip()
    if not value:
        return []
    if value.startswith("["):
        import json

        parsed = json.loads(value)
        if not isinstance(parsed, list) or not all(isinstance(origin, str) for origin in parsed):
            raise ValueError("CORS_ORIGINS must be a JSON array of strings")
        return [origin.strip() for origin in parsed if origin.strip()]
    return [origin.strip() for origin in value.split(",") if origin.strip()]


CorsOrigins = Annotated[list[str], NoDecode, BeforeValidator(parse_cors_origins)]


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./interviewai.db"
    jwt_secret: str = "development-only-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    cors_origins: CorsOrigins = ["http://localhost:4173"]
    max_resume_size_bytes: int = 10 * 1024 * 1024
    storage_endpoint: str | None = None
    storage_bucket: str = "interviewai-private"
    storage_access_key: str | None = None
    storage_secret_key: str | None = None
    storage_local_root: str = ".private_uploads"
    llm_api_key: str | None = None
    llm_provider: str = "huggingface"
    llm_base_url: str | None = None
    llm_model: str = "Qwen/Qwen3-8B"
    llm_timeout_seconds: float = 120.0
    llm_max_tokens: int = 1000
    llm_temperature: float = 0.7
    llm_input_cost_per_1m: float = 0.0
    llm_output_cost_per_1m: float = 0.0
    hf_token: str | None = None
    hf_base_url: str = "https://router.huggingface.co"
    hf_model: str = "Qwen/Qwen3-4B-Instruct-2507:fastest"
    speech_api_key: str | None = None
    tts_api_key: str | None = None
    audio_retention_days: int = 7
    max_interview_questions: int = 10
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    model_config = SettingsConfigDict(env_file=BACKEND_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    @classmethod
    def require_production_secret(cls, settings: "Settings") -> "Settings":
        if settings.app_env == "production" and settings.jwt_secret == "development-only-change-me":
            raise ValueError("JWT_SECRET must be configured in production")
        if settings.app_env == "production" and "*" in settings.cors_origins:
            raise ValueError("CORS_ORIGINS must explicitly list production origins")
        return settings

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: str | list[str]) -> list[str]:
        return parse_cors_origins(value)

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value.removeprefix("postgresql://")
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value.removeprefix("postgres://")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
