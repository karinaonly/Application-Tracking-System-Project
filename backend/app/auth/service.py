from datetime import datetime, timedelta, timezone
from uuid import UUID
from jose import jwt
from passlib.context import CryptContext
from sqlmodel import Session, select
from fastapi import HTTPException, status

from app.config.settings import get_settings
from app.auth.models import User
from app.auth.schemas import UserRegister, ProfileUpdate, PasswordChange

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

    def login(self, email: str, password: str) -> User:
        user = self.session.exec(select(User).where(User.email == email)).first()
        if not user or not self.verify_password(password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
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
