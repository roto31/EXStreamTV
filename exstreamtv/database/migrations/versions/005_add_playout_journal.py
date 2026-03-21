"""Add playout_journal table for crash-safe deterministic playout

Revision ID: 005
Revises: 004
Create Date: 2026-02-21

Adds playout_journal for persistent journal (crash-safe resume).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from sqlalchemy import inspect
    conn = op.get_bind()
    if "playout_journal" in inspect(conn).get_table_names():
        return
    op.create_table(
        "playout_journal",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("current_index", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("accumulated_valid_play_time", sa.Float(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("bytes_sent", sa.Integer(), nullable=False),
        sa.Column("last_known_state", sa.String(50), nullable=False),
        sa.Column("last_exit_classification", sa.String(50), nullable=True),
        sa.Column("last_stderr_snippet", sa.Text(), nullable=True),
        sa.Column("journal_updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_playout_journal_channel_id", "playout_journal", ["channel_id"])


def downgrade() -> None:
    op.drop_index("ix_playout_journal_channel_id", table_name="playout_journal")
    op.drop_table("playout_journal")
