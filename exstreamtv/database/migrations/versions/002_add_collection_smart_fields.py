"""Add smart collection fields to playlists

Revision ID: 002
Revises: 001
Create Date: 2026-01-17

Adds fields to playlists table to support smart collections:
- collection_type: "static", "smart", or "manual"
- search_query: query string for smart collections

This is part of v2.5.0 Block Schedule Database Integration.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add smart collection fields to playlists table."""
    
    # Add collection_type column with default value "static"
    op.add_column(
        'playlists',
        sa.Column(
            'collection_type',
            sa.String(length=20),
            nullable=False,
            server_default='static',
        )
    )
    
    # Add search_query column for smart collections
    op.add_column(
        'playlists',
        sa.Column(
            'search_query',
            sa.Text(),
            nullable=True,
        )
    )
    
    # Create index for faster collection_type lookups
    op.create_index(
        'ix_playlists_collection_type',
        'playlists',
        ['collection_type'],
    )


def downgrade() -> None:
    """Remove smart collection fields from playlists table."""
    
    # Drop index first
    op.drop_index('ix_playlists_collection_type', table_name='playlists')
    
    # Drop columns
    op.drop_column('playlists', 'search_query')
    op.drop_column('playlists', 'collection_type')
