"""Alembic environment for the ATS resume optimizer.

The database URL always comes from the application settings, so the CLI and the
running app can never migrate different databases by accident.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from app.config.settings import get_settings

# Importing the model modules registers every table on SQLModel.metadata.
from app.auth import models as auth_models  # noqa: F401
from app.jobs import models as jobs_models  # noqa: F401
from app.resume import models as resume_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    # Keep uvicorn/FastAPI loggers alive when migrations run inside app startup.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Programmatic callers (app startup, tests) pass the URL explicitly so they
# cannot pick up a cached setting that points at a different database.
database_url = config.attributes.get("database_url") or get_settings().database_url
config.set_main_option("sqlalchemy.url", database_url)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Render SQL without a live connection (``alembic upgrade --sql``)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
