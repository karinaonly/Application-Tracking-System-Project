from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config.database import init_db
from app.config.settings import get_settings, validate_security_settings
from app.auth.router import router as auth_router
from app.resume.router import router as resume_router
from app.jobs.router import router as jobs_router
from app.cover_letter.router import router as cover_letter_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # E1: refuse to serve with an insecure/missing JWT secret
    validate_security_settings(get_settings())
    init_db()
    print("✅ Database schema is up to date (Alembic).")
    print("🚀 LandIt API is live on http://127.0.0.1:8000")
    print("📚 Open Swagger Docs: http://127.0.0.1:8000/docs")
    yield

app = FastAPI(
    title="LandIt (Local Edition)",
    description="Your personal, local ATS resume inspection & optimization engine.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    # E2: explicit allowlist instead of "*"; override via CORS_ORIGINS in .env
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(resume_router, prefix="/resumes", tags=["Resumes"])
app.include_router(jobs_router, prefix="/jobs", tags=["Jobs"])
app.include_router(cover_letter_router, prefix="/cover-letters", tags=["Cover Letters"])

@app.get("/")
def root():
    return {"message": "LandIt API is running locally.", "docs": "/docs"}
