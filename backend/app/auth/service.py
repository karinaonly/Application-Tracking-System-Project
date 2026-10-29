from datetime import datetime, timedelta, timezone
from uuid import UUID
from jose import jwt
from passlib.context import CryptContext
from sqlmodel import Session, select
from fastapi import HTTPException, status

from app.config.settings import get_settings
from app.auth.models import User
from app.auth.schemas import UserRegister, ProfileUpdate, PasswordChange
from app.auth.throttle import login_throttle, throttle_key

MIN_PASSWORD_LENGTH = 8

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    def __init__(self, session: Session):
        self.session = session

    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)

    def create_token(self, user_id: UUID) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expiration_minutes)
        payload = {"sub": str(user_id), "exp": expire}
        return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    def register(self, data: UserRegister) -> User:
        # E3: the same password policy as change-password, and an operator can
        # close sign-ups once the owner's account exists.
        if not get_settings().allow_registration:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Registration is disabled on this instance.",
            )
        if len(data.password) < MIN_PASSWORD_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters",
            )
        exists = self.session.exec(select(User).where(User.email == data.email)).first()
        if exists:
            raise HTTPException(status_code=400, detail="Email already registered")
        user = User(
            email=data.email,
            hashed_password=self.hash_password(data.password),
            full_name=data.full_name
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def login(self, email: str, password: str, client: str | None = None) -> User:
        # E3: reject repeated failures before touching the password hash, so
        # the endpoint cannot be used as an offline-speed oracle.
        key = throttle_key(email, client)
        wait = login_throttle.retry_after(key)
        if wait:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Too many failed sign-in attempts. Try again in "
                    f"{max(1, wait // 60)} minute(s)."
                ),
                headers={"Retry-After": str(wait)},
            )

        user = self.session.exec(select(User).where(User.email == email)).first()
        if not user or not self.verify_password(password, user.hashed_password):
            login_throttle.record_failure(key)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        login_throttle.reset(key)
        return user

    def update_profile(self, user: User, data: ProfileUpdate) -> User:
        # A21: real profile save -- only full_name is editable; email is fixed.
        user.full_name = data.full_name.strip()
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def change_password(self, user: User, data: PasswordChange) -> None:
        # A21: verify the current password before accepting a new one.
        if not self.verify_password(data.current_password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
        new = data.new_password
        if len(new) < MIN_PASSWORD_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"New password must be at least {MIN_PASSWORD_LENGTH} characters",
            )
        user.hashed_password = self.hash_password(new)
        self.session.add(user)
        self.session.commit()
