from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    database_url: str = "sqlite:///./ats_resume_fixer.db"
    groq_api_key: str = ""
    ai_provider: str = "auto"
    ai_model: str = "openai/gpt-oss-120b"
    ai_base_url: str = "https://api.groq.com/openai/v1"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    ai_timeout_seconds: int = 20
    jwt_secret: str = "local-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 43200
    environment: str = "development"
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 10
    allowed_extensions: list[str] = [".pdf", ".docx", ".txt"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
