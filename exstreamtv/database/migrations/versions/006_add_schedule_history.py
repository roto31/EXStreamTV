"""Add schedule_history for memento / revert

Revision ID: 006
Revises: 005
Create Date: 2026-04-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from sqlalchemy import inspect

    conn = op.get_bind()
    if "schedule_history" in inspect(conn).get_table_names():
        return
    op.create_table(
        "schedule_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("persona_id", sa.String(length=64), nullable=True),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("applied", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("pre_apply_snapshot", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_schedule_history_persona_id", "schedule_history", ["persona_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_schedule_history_persona_id", table_name="schedule_history")
    op.drop_table("schedule_history")
