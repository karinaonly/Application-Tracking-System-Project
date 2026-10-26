from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config.database import init_db
from app.auth.router import router as auth_router
from app.resume.router import router as resume_router
from app.jobs.router import router as jobs_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("✅ SQLite database initialized.")
    print("🚀 ATS Resume Fixer API is live on http://127.0.0.1:8000")
    print("📚 Open Swagger Docs: http://127.0.0.1:8000/docs")
    yield

app = FastAPI(
    title="ATS Resume Fixer (Local Edition)",
    description="Your personal, local ATS resume inspection & optimization engine.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(resume_router, prefix="/resumes", tags=["Resumes"])
app.include_router(jobs_router, prefix="/jobs", tags=["Jobs"])

@app.get("/")
def root():
    return {"message": "ATS Resume Fixer API is running locally.", "docs": "/docs"}
