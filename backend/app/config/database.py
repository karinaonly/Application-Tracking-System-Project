from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlmodel import SQLModel, Session, create_engine

from app.config.settings import get_settings

# Register every model on SQLModel.metadata (init_db compares against it).
from app.auth import models as auth_models  # noqa: F401
from app.jobs import models as jobs_models  # noqa: F401
from app.resume import models as resume_models  # noqa: F401

settings = get_settings()

# F10: schema changes are versioned with Alembic. The baseline revision is the
# schema that ``create_all`` produced before migrations existed; databases from
# that era are stamped at the baseline instead of being rebuilt.
BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
MIGRATIONS_DIR = BACKEND_DIR / "migrations"
BASELINE_REVISION = "0001_initial"

# SQLite engine with check_same_thread=False for FastAPI concurrency.
# E5: echo defaults to off -- enabled SQL logging prints every bound value,
# including full resume text.
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    echo=settings.db_echo,
)


def alembic_config(database_url: str | None = None) -> Config:
    """Build an Alembic config for this app's migration scripts."""
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.attributes["database_url"] = database_url or settings.database_url
    return config


def init_db(database_url: str | None = None) -> None:
    """Bring the database schema up to date.

    * Empty database -> run every migration from the baseline.
    * Existing pre-Alembic database -> stamp the baseline (its schema is the
      baseline by definition), then run any migrations added since.
    * Already-versioned database -> run pending migrations only.

    Unlike ``create_all``, this can ALTER existing tables when models change.
    """
    url = database_url or settings.database_url
    config = alembic_config(url)

    # Use a short-lived engine for the inspection so callers can point the
    # migration at a temporary database without touching the app-wide engine.
    inspect_engine = create_engine(
        url,
        connect_args={"check_same_thread": False} if "sqlite" in url else {},
    )
    try:
        with inspect_engine.connect() as connection:
            inspector = inspect(connection)
            tables = set(inspector.get_table_names())
    finally:
        inspect_engine.dispose()

    has_version_table = "alembic_version" in tables
    user_tables = tables - {"alembic_version"}
    expected_tables = set(SQLModel.metadata.tables)

    if user_tables and not has_version_table:
        missing = expected_tables - user_tables
        if missing:
            raise RuntimeError(
                "Database has tables but no Alembic version and is missing "
                f"{sorted(missing)}. Refusing to guess a schema version; "
                "back up the database and migrate it manually."
            )
        # Adopt the existing schema at the baseline, then apply anything newer.
        command.stamp(config, BASELINE_REVISION)
        print(f"Adopted existing database at migration {BASELINE_REVISION}.")

    command.upgrade(config, "head")


def get_session():
    with Session(engine) as session:
        yield session
