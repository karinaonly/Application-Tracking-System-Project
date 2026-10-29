from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select
from app.config.database import get_session
from app.auth.schemas import UserRegister, UserLogin, TokenResponse, UserResponse, ProfileUpdate, PasswordChange
from app.auth.service import AuthService
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.config.settings import get_settings
from app.analyzer.ai_config import resolve_ai_config
from app.resume.models import Resume, ResumeAnalysis

router = APIRouter()

@router.get("/config")
def public_config():
    """E3/E4: non-secret switches the UI needs before anyone signs in."""
    settings = get_settings()
    return {
        "registration_enabled": settings.allow_registration,
        "ai_rewriting_enabled": settings.ai_rewriting_enabled,
    }

@router.get("/ai-status")
def ai_status(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    settings = get_settings()
    config = resolve_ai_config(settings)
    configured = config.configured
    reason = config.reason
    provider = config.provider
    if configured:
        latest = session.exec(
            select(ResumeAnalysis)
            .join(Resume, Resume.id == ResumeAnalysis.resume_id)
            .where(Resume.user_id == user.id)
            .order_by(ResumeAnalysis.created_at.desc())
        ).first()
        errors = [
            value.get("error", "")
            for value in (latest.report or {}).get("ai_rewritten_examples", {}).values()
            if isinstance(value, dict)
        ] if latest else []
        if any("model" in error.lower() and ("not found" in error.lower() or "no longer available" in error.lower()) for error in errors):
            reason = "model_unavailable"
        elif any("insufficient_quota" in error or "no credits remaining" in error.lower() for error in errors):
            reason = "quota_exhausted"
    return {
        "configured": configured,
        "reason": reason,
        "model": config.model,
        "provider": provider,
        # E4: a false value means no resume text leaves the machine, even if
        # the provider is configured.
        "rewriting_enabled": settings.ai_rewriting_enabled,
    }

@router.post("/register", response_model=UserResponse, status_code=201)
def register(data: UserRegister, session: Session = Depends(get_session)):
    service = AuthService(session)
    return service.register(data)

@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, request: Request, session: Session = Depends(get_session)):
    service = AuthService(session)
    client = request.client.host if request.client else None
    user = service.login(data.email, data.password, client=client)
    token = service.create_token(user.id)
    return {"access_token": token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return user

@router.patch("/me", response_model=UserResponse)
def update_me(data: ProfileUpdate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    # A21: Settings "Save Changes" now persists the display name.
    service = AuthService(session)
    return service.update_profile(user, data)

@router.post("/change-password", status_code=204)
def change_password(data: PasswordChange, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    # A21: real password change -- verifies the current password.
    service = AuthService(session)
    service.change_password(user, data)
