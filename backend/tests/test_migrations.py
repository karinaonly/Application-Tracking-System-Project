"""F10: Alembic migrations must create, adopt, and upgrade real databases."""

import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect
from sqlmodel import Session, SQLModel, select

from app.auth.models import User
from app.config.database import alembic_config, init_db


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.url = f"sqlite:///{(Path(self.tmp.name) / 'test.db').as_posix()}"
        self.engine = create_engine(
            self.url, connect_args={"check_same_thread": False}
        )

    def tearDown(self):
        self.engine.dispose()
        self.tmp.cleanup()

    def _tables(self) -> set[str]:
        return set(inspect(self.engine).get_table_names())

    def _version(self) -> str:
        with self.engine.connect() as connection:
            return connection.exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalar_one()

    def _head(self) -> str:
        return ScriptDirectory.from_config(alembic_config(self.url)).get_current_head()

    def test_empty_database_is_created_at_head(self):
        init_db(self.url)

        expected = set(SQLModel.metadata.tables) | {"alembic_version"}
        self.assertEqual(self._tables(), expected)
        self.assertEqual(self._version(), self._head())

    def test_existing_database_is_adopted_without_data_loss(self):
        SQLModel.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            session.add(
                User(
                    email="keep@example.com",
                    hashed_password="hashed",
                    full_name="Keep Me",
                )
            )
            session.commit()

        init_db(self.url)

        with Session(self.engine) as session:
            users = session.exec(select(User)).all()
        self.assertEqual([user.email for user in users], ["keep@example.com"])
        self.assertEqual(self._version(), self._head())

    def test_init_db_is_idempotent(self):
        init_db(self.url)
        init_db(self.url)

        self.assertEqual(self._version(), self._head())
        self.assertIn("resumes", self._tables())

    def test_migrated_schema_matches_models(self):
        init_db(self.url)

        with self.engine.connect() as connection:
            context = MigrationContext.configure(
                connection,
                opts={"compare_type": True, "render_as_batch": True},
            )
            differences = compare_metadata(context, SQLModel.metadata)

        self.assertEqual(
            differences,
            [],
            "Models changed without a matching Alembic migration: "
            f"{differences}",
        )

    def test_partial_schema_without_version_is_rejected(self):
        User.__table__.create(self.engine)

        with self.assertRaises(RuntimeError) as raised:
            init_db(self.url)

        self.assertIn("no Alembic version", str(raised.exception))
        self.assertNotIn("alembic_version", self._tables())

    def test_baseline_downgrade_is_reversible(self):
        init_db(self.url)
        command.downgrade(alembic_config(self.url), "base")

        self.assertEqual(self._tables() - {"alembic_version"}, set())

        init_db(self.url)
        self.assertIn("users", self._tables())
        self.assertEqual(self._version(), self._head())


if __name__ == "__main__":
    unittest.main()
