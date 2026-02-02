"""Add ErsatzTV-compatible tables

Revision ID: 001
Revises: 
Create Date: 2026-01-17

Creates tables for:
- multi_collections and multi_collection_links
- playout_build_sessions
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create new ErsatzTV-compatible tables."""
    
    # Create multi_collections table
    op.create_table(
        'multi_collections',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create multi_collection_links table
    op.create_table(
        'multi_collection_links',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('multi_collection_id', sa.Integer(), nullable=False),
        sa.Column('collection_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['multi_collection_id'], ['multi_collections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index for faster lookups
    op.create_index(
        'ix_multi_collection_links_multi_collection_id',
        'multi_collection_links',
        ['multi_collection_id']
    )
    op.create_index(
        'ix_multi_collection_links_collection_id',
        'multi_collection_links',
        ['collection_id']
    )
    
    # Create playout_build_sessions table
    op.create_table(
        'playout_build_sessions',
        sa.Column('id', sa.String(length=36), nullable=False),  # UUID
        sa.Column('playout_id', sa.Integer(), nullable=False),
        sa.Column('current_time', sa.DateTime(), nullable=False),
        sa.Column('state_json', sa.Text(), nullable=False, default='{}'),
        sa.Column('content_buffer', sa.Text(), nullable=False, default='[]'),
        sa.Column('status', sa.String(length=20), nullable=False, default='building'),
        sa.Column('watermark_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('graphics_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('pre_roll_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('epg_group_active', sa.Boolean(), nullable=False, default=False),
        sa.Column('epg_group_title', sa.String(length=500), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['playout_id'], ['playouts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index for playout lookups
    op.create_index(
        'ix_playout_build_sessions_playout_id',
        'playout_build_sessions',
        ['playout_id']
    )
    op.create_index(
        'ix_playout_build_sessions_status',
        'playout_build_sessions',
        ['status']
    )


def downgrade() -> None:
    """Remove ErsatzTV-compatible tables."""
    
    # Drop indexes first
    op.drop_index('ix_playout_build_sessions_status', table_name='playout_build_sessions')
    op.drop_index('ix_playout_build_sessions_playout_id', table_name='playout_build_sessions')
    op.drop_index('ix_multi_collection_links_collection_id', table_name='multi_collection_links')
    op.drop_index('ix_multi_collection_links_multi_collection_id', table_name='multi_collection_links')
    
    # Drop tables
    op.drop_table('playout_build_sessions')
    op.drop_table('multi_collection_links')
    op.drop_table('multi_collections')
