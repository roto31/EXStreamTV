"""Add EPG sync columns to channel_playback_positions

Revision ID: 004
Revises: 003
Create Date: 2026-02-02

Adds current_item_start_time and elapsed_seconds_in_item so the EPG
can align programme start times with what is actually streaming
(guide no longer behind/ahead of stream).
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa


revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(conn, table: str, column: str) -> bool:
    """Return True if column exists on table."""
    insp = inspect(conn)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols


def upgrade() -> None:
    """Add current_item_start_time and elapsed_seconds_in_item to channel_playback_positions."""
    conn = op.get_bind()
    table = "channel_playback_positions"
    if not _column_exists(conn, table, "current_item_start_time"):
        op.add_column(
            table,
            sa.Column("current_item_start_time", sa.DateTime(), nullable=True),
        )
    if not _column_exists(conn, table, "elapsed_seconds_in_item"):
        op.add_column(
            table,
            sa.Column("elapsed_seconds_in_item", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    """Remove EPG sync columns from channel_playback_positions."""
    conn = op.get_bind()
    table = "channel_playback_positions"
    if _column_exists(conn, table, "current_item_start_time"):
        op.drop_column(table, "current_item_start_time")
    if _column_exists(conn, table, "elapsed_seconds_in_item"):
        op.drop_column(table, "elapsed_seconds_in_item")
