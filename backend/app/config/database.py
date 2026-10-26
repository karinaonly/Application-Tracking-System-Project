from sqlmodel import SQLModel, Session, create_engine
from app.config.settings import get_settings

settings = get_settings()

# SQLite engine with check_same_thread=False for FastAPI concurrency
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    echo=(settings.environment == "development")
)

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
