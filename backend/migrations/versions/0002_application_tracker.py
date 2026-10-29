"""Application tracker columns on job descriptions.

Revision ID: 0002_application_tracker
Revises: 0001_initial
Create Date: 2026-10-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002_application_tracker"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("job_descriptions", schema=None) as batch_op:
        # server_default backfills existing rows; new rows use the model default.
        batch_op.add_column(
            sa.Column(
                "application_status",
                sa.String(),
                nullable=False,
                server_default="saved",
            )
        )
        batch_op.add_column(
            sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("notes", sa.String(), nullable=False, server_default="")
        )
        batch_op.create_index(
            batch_op.f("ix_job_descriptions_application_status"),
            ["application_status"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("job_descriptions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_job_descriptions_application_status"))
        batch_op.drop_column("notes")
        batch_op.drop_column("applied_at")
        batch_op.drop_column("application_status")
