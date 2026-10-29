from pathlib import Path

from pydantic_settings import BaseSettings
from functools import lru_cache

# Anchor the default DB to the backend package so the working directory
# cannot create a stray database file (F17).
BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_URL = f"sqlite:///{(BACKEND_DIR / 'ats_resume_fixer.db').as_posix()}"

class Settings(BaseSettings):
    database_url: str = DEFAULT_DATABASE_URL
    groq_api_key: str = ""
    ai_provider: str = "auto"
    ai_model: str = "openai/gpt-oss-120b"
    ai_base_url: str = "https://api.groq.com/openai/v1"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    ai_timeout_seconds: int = 20
    # E4: server-wide hard switch. When false, resume text is never sent to an
    # AI provider -- the analysis still runs locally and says why rewrites are
    # unavailable. Users can also opt out per analysis from the UI.
    ai_rewriting_enabled: bool = True
    # E3: keep auth (the data model is multi-user and resumes are personal),
    # but let a local instance close sign-ups after the owner registers.
    allow_registration: bool = True
    # E1: no insecure default -- the secret must come from .env (see validate_security_settings)
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 43200
    environment: str = "development"
    # E2: comma-separated allowlist; override with CORS_ORIGINS in .env if the
    # frontend is served from another origin (e.g. a preview URL).
    cors_origins: str = "http://localhost:8443,http://127.0.0.1:8443,http://localhost:5173,http://127.0.0.1:5173"
    # E5: SQL logging prints bound values (full resume text); opt in via DB_ECHO=true
    db_echo: bool = False
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 10
    allowed_extensions: list[str] = [".pdf", ".docx", ".txt"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

MIN_JWT_SECRET_LENGTH = 32

def validate_security_settings(settings: "Settings") -> None:
    """E1: fail startup unless a real JWT secret is configured."""
    if not settings.jwt_secret:
        raise RuntimeError(
            "JWT_SECRET is not set. Add JWT_SECRET to backend/.env "
            "(generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\")."
        )
    if len(settings.jwt_secret) < MIN_JWT_SECRET_LENGTH:
        raise RuntimeError(
            f"JWT_SECRET is too short ({len(settings.jwt_secret)} chars); "
            f"use at least {MIN_JWT_SECRET_LENGTH}."
        )

@lru_cache()
def get_settings() -> Settings:
    return Settings()
