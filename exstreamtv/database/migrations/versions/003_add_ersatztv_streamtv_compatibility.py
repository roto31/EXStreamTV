"""Add ErsatzTV and StreamTV compatibility fields

Revision ID: 003
Revises: 002
Create Date: 2026-01-17

Adds comprehensive schema updates for full ErsatzTV and StreamTV compatibility:

FFmpegProfile:
- video_format, video_profile, allow_b_frames, bit_depth
- audio_format, audio_buffer_size, scaling_behavior
- tonemap_algorithm, normalize_loudness_mode, target_loudness
- vaapi_driver, vaapi_device, qsv_extra_hardware_frames
- normalize_framerate, deinterlace_video, gop_size, global_watermark_id

Channel:
- unique_id, sort_number, categories

Deco (new structure):
- watermark_mode, watermark_id, graphics_elements_mode
- break_content_mode, default_filler_mode, default_filler_collection_id
- default_filler_trim_to_fit, dead_air_fallback_mode, dead_air_fallback_collection_id

ProgramSchedule:
- fixed_start_time_behavior

ProgramScheduleItem:
- multi_collection_id, smart_collection_id, search_query, search_title
- marathon_batch_size, marathon_group_by
- preferred_audio_language_code, preferred_audio_title
- preferred_subtitle_language_code, subtitle_mode

Block:
- minutes, stop_scheduling

BlockItem:
- multi_collection_id, smart_collection_id, search_query, search_title
- disable_watermarks

Playout:
- deco_id, schedule_kind, schedule_file, seed

FillerPreset:
- filler_kind, expression, allow_watermarks
- collection_id, smart_collection_id, multi_collection_id

MediaItem (source-specific):
- Archive.org: identifier, filename, creator, collection, subject
- YouTube: video_id, channel_id, channel_name, tags, category, like_count
- Plex: rating_key, guid, library_section_id, library_section_title
- Jellyfin/Emby: item_id
- External IDs: tvdb_id, tmdb_id, imdb_id
- AI enhancement: ai_enhanced_title, ai_enhanced_description, ai_enhanced_at, ai_enhancement_model

New tables:
- smart_collections
- smart_collection_items
- rerun_collections
- rerun_history_items
- deco_break_contents
- deco_templates
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ErsatzTV and StreamTV compatibility fields."""
    
    # ========================================
    # FFmpegProfile updates
    # ========================================
    op.add_column('ffmpeg_profiles', sa.Column('video_format', sa.String(20), nullable=False, server_default='h264'))
    op.add_column('ffmpeg_profiles', sa.Column('video_profile', sa.String(20), nullable=True))
    op.add_column('ffmpeg_profiles', sa.Column('allow_b_frames', sa.Boolean(), nullable=False, server_default='1'))
    op.add_column('ffmpeg_profiles', sa.Column('bit_depth', sa.String(10), nullable=False, server_default='8bit'))
    op.add_column('ffmpeg_profiles', sa.Column('audio_format', sa.String(20), nullable=False, server_default='aac'))
    op.add_column('ffmpeg_profiles', sa.Column('audio_buffer_size', sa.String(20), nullable=False, server_default='384k'))
    op.add_column('ffmpeg_profiles', sa.Column('scaling_behavior', sa.String(30), nullable=False, server_default='scale_and_pad'))
    op.add_column('ffmpeg_profiles', sa.Column('tonemap_algorithm', sa.String(30), nullable=True))
    op.add_column('ffmpeg_profiles', sa.Column('normalize_loudness_mode', sa.String(20), nullable=False, server_default='off'))
    op.add_column('ffmpeg_profiles', sa.Column('target_loudness', sa.Float(), nullable=True))
    op.add_column('ffmpeg_profiles', sa.Column('vaapi_driver', sa.String(50), nullable=True))
    op.add_column('ffmpeg_profiles', sa.Column('vaapi_device', sa.String(100), nullable=True))
    op.add_column('ffmpeg_profiles', sa.Column('qsv_extra_hardware_frames', sa.Integer(), nullable=True))
    op.add_column('ffmpeg_profiles', sa.Column('normalize_framerate', sa.Boolean(), nullable=False, server_default='1'))
    op.add_column('ffmpeg_profiles', sa.Column('deinterlace_video', sa.Boolean(), nullable=True))
    op.add_column('ffmpeg_profiles', sa.Column('gop_size', sa.Integer(), nullable=True))
    op.add_column('ffmpeg_profiles', sa.Column('global_watermark_id', sa.Integer(), nullable=True))
    
    # ========================================
    # Channel updates
    # ========================================
    op.add_column('channels', sa.Column('unique_id', sa.String(36), nullable=True, unique=True))
    op.add_column('channels', sa.Column('sort_number', sa.Float(), nullable=True))
    op.add_column('channels', sa.Column('categories', sa.Text(), nullable=True))
    op.create_index('ix_channels_unique_id', 'channels', ['unique_id'], unique=True)
    
    # ========================================
    # ProgramSchedule updates
    # ========================================
    op.add_column('program_schedules', sa.Column('fixed_start_time_behavior', sa.String(20), nullable=False, server_default='fill'))
    
    # ========================================
    # ProgramScheduleItem updates
    # ========================================
    op.add_column('program_schedule_items', sa.Column('multi_collection_id', sa.Integer(), sa.ForeignKey('multi_collections.id'), nullable=True))
    op.add_column('program_schedule_items', sa.Column('smart_collection_id', sa.Integer(), sa.ForeignKey('smart_collections.id'), nullable=True))
    op.add_column('program_schedule_items', sa.Column('search_query', sa.Text(), nullable=True))
    op.add_column('program_schedule_items', sa.Column('search_title', sa.String(500), nullable=True))
    op.add_column('program_schedule_items', sa.Column('marathon_batch_size', sa.Integer(), nullable=True))
    op.add_column('program_schedule_items', sa.Column('marathon_group_by', sa.String(20), nullable=True))
    op.add_column('program_schedule_items', sa.Column('preferred_audio_language_code', sa.String(10), nullable=True))
    op.add_column('program_schedule_items', sa.Column('preferred_audio_title', sa.String(255), nullable=True))
    op.add_column('program_schedule_items', sa.Column('preferred_subtitle_language_code', sa.String(10), nullable=True))
    op.add_column('program_schedule_items', sa.Column('subtitle_mode', sa.String(20), nullable=True))
    
    # Make collection_id nullable (for search-based items)
    op.alter_column('program_schedule_items', 'collection_id', existing_type=sa.Integer(), nullable=True)
    
    # ========================================
    # Block updates
    # ========================================
    op.add_column('blocks', sa.Column('minutes', sa.Integer(), nullable=True))
    op.add_column('blocks', sa.Column('stop_scheduling', sa.Boolean(), nullable=False, server_default='0'))
    
    # ========================================
    # BlockItem updates
    # ========================================
    op.add_column('block_items', sa.Column('multi_collection_id', sa.Integer(), sa.ForeignKey('multi_collections.id'), nullable=True))
    op.add_column('block_items', sa.Column('smart_collection_id', sa.Integer(), sa.ForeignKey('smart_collections.id'), nullable=True))
    op.add_column('block_items', sa.Column('search_query', sa.Text(), nullable=True))
    op.add_column('block_items', sa.Column('search_title', sa.String(500), nullable=True))
    op.add_column('block_items', sa.Column('disable_watermarks', sa.Boolean(), nullable=False, server_default='0'))
    
    # Make collection_id nullable
    op.alter_column('block_items', 'collection_id', existing_type=sa.Integer(), nullable=True)
    
    # ========================================
    # Playout updates
    # ========================================
    op.add_column('playouts', sa.Column('deco_id', sa.Integer(), sa.ForeignKey('decos.id'), nullable=True))
    op.add_column('playouts', sa.Column('schedule_kind', sa.String(20), nullable=False, server_default='flood'))
    op.add_column('playouts', sa.Column('schedule_file', sa.Text(), nullable=True))
    op.add_column('playouts', sa.Column('seed', sa.Integer(), nullable=True))
    
    # ========================================
    # FillerPreset updates
    # ========================================
    op.add_column('filler_presets', sa.Column('filler_kind', sa.String(20), nullable=True))
    op.add_column('filler_presets', sa.Column('expression', sa.Text(), nullable=True))
    op.add_column('filler_presets', sa.Column('allow_watermarks', sa.Boolean(), nullable=False, server_default='1'))
    op.add_column('filler_presets', sa.Column('collection_id', sa.Integer(), sa.ForeignKey('playlists.id'), nullable=True))
    op.add_column('filler_presets', sa.Column('smart_collection_id', sa.Integer(), sa.ForeignKey('smart_collections.id'), nullable=True))
    op.add_column('filler_presets', sa.Column('multi_collection_id', sa.Integer(), sa.ForeignKey('multi_collections.id'), nullable=True))
    
    # ========================================
    # MediaItem updates (source-specific)
    # ========================================
    # Archive.org
    op.add_column('media_items', sa.Column('archive_org_identifier', sa.String(255), nullable=True))
    op.add_column('media_items', sa.Column('archive_org_filename', sa.String(500), nullable=True))
    op.add_column('media_items', sa.Column('archive_org_creator', sa.String(255), nullable=True))
    op.add_column('media_items', sa.Column('archive_org_collection', sa.String(255), nullable=True))
    op.add_column('media_items', sa.Column('archive_org_subject', sa.Text(), nullable=True))
    
    # YouTube
    op.add_column('media_items', sa.Column('youtube_video_id', sa.String(20), nullable=True))
    op.add_column('media_items', sa.Column('youtube_channel_id', sa.String(50), nullable=True))
    op.add_column('media_items', sa.Column('youtube_channel_name', sa.String(255), nullable=True))
    op.add_column('media_items', sa.Column('youtube_tags', sa.Text(), nullable=True))
    op.add_column('media_items', sa.Column('youtube_category', sa.String(100), nullable=True))
    op.add_column('media_items', sa.Column('youtube_like_count', sa.Integer(), nullable=True))
    
    # Plex
    op.add_column('media_items', sa.Column('plex_rating_key', sa.String(50), nullable=True))
    op.add_column('media_items', sa.Column('plex_guid', sa.String(255), nullable=True))
    op.add_column('media_items', sa.Column('plex_library_section_id', sa.Integer(), nullable=True))
    op.add_column('media_items', sa.Column('plex_library_section_title', sa.String(255), nullable=True))
    
    # Jellyfin/Emby
    op.add_column('media_items', sa.Column('jellyfin_item_id', sa.String(50), nullable=True))
    op.add_column('media_items', sa.Column('emby_item_id', sa.String(50), nullable=True))
    
    # External IDs
    op.add_column('media_items', sa.Column('tvdb_id', sa.Integer(), nullable=True))
    op.add_column('media_items', sa.Column('tmdb_id', sa.Integer(), nullable=True))
    op.add_column('media_items', sa.Column('imdb_id', sa.String(20), nullable=True))
    
    # AI enhancement
    op.add_column('media_items', sa.Column('ai_enhanced_title', sa.String(500), nullable=True))
    op.add_column('media_items', sa.Column('ai_enhanced_description', sa.Text(), nullable=True))
    op.add_column('media_items', sa.Column('ai_enhanced_at', sa.DateTime(), nullable=True))
    op.add_column('media_items', sa.Column('ai_enhancement_model', sa.String(50), nullable=True))
    
    # Create indexes for common lookups
    op.create_index('ix_media_items_youtube_video_id', 'media_items', ['youtube_video_id'])
    op.create_index('ix_media_items_plex_rating_key', 'media_items', ['plex_rating_key'])
    op.create_index('ix_media_items_archive_org_identifier', 'media_items', ['archive_org_identifier'])
    op.create_index('ix_media_items_imdb_id', 'media_items', ['imdb_id'])
    op.create_index('ix_media_items_tmdb_id', 'media_items', ['tmdb_id'])
    
    # ========================================
    # New tables: Deco (expanded)
    # ========================================
    # First, we need to handle the existing decos table
    # The new Deco structure is different, so we'll add new columns
    op.add_column('decos', sa.Column('watermark_mode', sa.String(20), nullable=False, server_default='inherit'))
    op.add_column('decos', sa.Column('watermark_id', sa.Integer(), sa.ForeignKey('channel_watermarks.id'), nullable=True))
    op.add_column('decos', sa.Column('graphics_elements_mode', sa.String(20), nullable=False, server_default='inherit'))
    op.add_column('decos', sa.Column('break_content_mode', sa.String(20), nullable=False, server_default='inherit'))
    op.add_column('decos', sa.Column('default_filler_mode', sa.String(20), nullable=False, server_default='inherit'))
    op.add_column('decos', sa.Column('default_filler_collection_id', sa.Integer(), sa.ForeignKey('playlists.id'), nullable=True))
    op.add_column('decos', sa.Column('default_filler_trim_to_fit', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('decos', sa.Column('dead_air_fallback_mode', sa.String(20), nullable=False, server_default='inherit'))
    op.add_column('decos', sa.Column('dead_air_fallback_collection_id', sa.Integer(), sa.ForeignKey('playlists.id'), nullable=True))
    
    # ========================================
    # New table: deco_break_contents
    # ========================================
    op.create_table(
        'deco_break_contents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('deco_id', sa.Integer(), sa.ForeignKey('decos.id'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('collection_id', sa.Integer(), sa.ForeignKey('playlists.id'), nullable=True),
        sa.Column('target_duration_seconds', sa.Integer(), nullable=True),
        sa.Column('frequency_minutes', sa.Integer(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # ========================================
    # New table: deco_templates
    # ========================================
    op.create_table(
        'deco_templates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('deco_groups.id'), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('deco_type', sa.String(50), nullable=False, server_default='bumper'),
        sa.Column('media_item_id', sa.Integer(), sa.ForeignKey('media_items.id'), nullable=True),
        sa.Column('file_path', sa.Text(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('static_duration_seconds', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('weight', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # ========================================
    # New table: smart_collections
    # ========================================
    op.create_table(
        'smart_collections',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('query_type', sa.String(20), nullable=False, server_default='json'),
        sa.Column('source_filter', sa.String(50), nullable=True),
        sa.Column('library_ids', sa.Text(), nullable=True),
        sa.Column('order_by', sa.String(50), nullable=False, server_default='title'),
        sa.Column('order_direction', sa.String(10), nullable=False, server_default='asc'),
        sa.Column('max_items', sa.Integer(), nullable=True),
        sa.Column('cache_duration_minutes', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('last_refreshed', sa.DateTime(), nullable=True),
        sa.Column('cached_item_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # ========================================
    # New table: smart_collection_items
    # ========================================
    op.create_table(
        'smart_collection_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('smart_collection_id', sa.Integer(), sa.ForeignKey('smart_collections.id'), nullable=False),
        sa.Column('media_item_id', sa.Integer(), sa.ForeignKey('media_items.id'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cached_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_smart_collection_items_smart_collection_id', 'smart_collection_items', ['smart_collection_id'])
    
    # ========================================
    # New table: rerun_collections
    # ========================================
    op.create_table(
        'rerun_collections',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('channel_id', sa.Integer(), sa.ForeignKey('channels.id'), nullable=True),
        sa.Column('playout_id', sa.Integer(), sa.ForeignKey('playouts.id'), nullable=True),
        sa.Column('minimum_rerun_window_hours', sa.Integer(), nullable=False, server_default='24'),
        sa.Column('max_history_items', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # ========================================
    # New table: rerun_history_items
    # ========================================
    op.create_table(
        'rerun_history_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('collection_id', sa.Integer(), sa.ForeignKey('rerun_collections.id'), nullable=False),
        sa.Column('media_item_id', sa.Integer(), sa.ForeignKey('media_items.id'), nullable=False),
        sa.Column('played_at', sa.DateTime(), nullable=False),
        sa.Column('playout_item_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_rerun_history_items_collection_id', 'rerun_history_items', ['collection_id'])
    op.create_index('ix_rerun_history_items_media_item_id', 'rerun_history_items', ['media_item_id'])
    op.create_index('ix_rerun_history_items_played_at', 'rerun_history_items', ['played_at'])


def downgrade() -> None:
    """Remove ErsatzTV and StreamTV compatibility fields."""
    
    # Drop new tables in reverse order
    op.drop_index('ix_rerun_history_items_played_at', table_name='rerun_history_items')
    op.drop_index('ix_rerun_history_items_media_item_id', table_name='rerun_history_items')
    op.drop_index('ix_rerun_history_items_collection_id', table_name='rerun_history_items')
    op.drop_table('rerun_history_items')
    op.drop_table('rerun_collections')
    op.drop_index('ix_smart_collection_items_smart_collection_id', table_name='smart_collection_items')
    op.drop_table('smart_collection_items')
    op.drop_table('smart_collections')
    op.drop_table('deco_templates')
    op.drop_table('deco_break_contents')
    
    # Drop Deco expansion columns
    op.drop_column('decos', 'dead_air_fallback_collection_id')
    op.drop_column('decos', 'dead_air_fallback_mode')
    op.drop_column('decos', 'default_filler_trim_to_fit')
    op.drop_column('decos', 'default_filler_collection_id')
    op.drop_column('decos', 'default_filler_mode')
    op.drop_column('decos', 'break_content_mode')
    op.drop_column('decos', 'graphics_elements_mode')
    op.drop_column('decos', 'watermark_id')
    op.drop_column('decos', 'watermark_mode')
    
    # Drop MediaItem indexes and columns
    op.drop_index('ix_media_items_tmdb_id', table_name='media_items')
    op.drop_index('ix_media_items_imdb_id', table_name='media_items')
    op.drop_index('ix_media_items_archive_org_identifier', table_name='media_items')
    op.drop_index('ix_media_items_plex_rating_key', table_name='media_items')
    op.drop_index('ix_media_items_youtube_video_id', table_name='media_items')
    
    op.drop_column('media_items', 'ai_enhancement_model')
    op.drop_column('media_items', 'ai_enhanced_at')
    op.drop_column('media_items', 'ai_enhanced_description')
    op.drop_column('media_items', 'ai_enhanced_title')
    op.drop_column('media_items', 'imdb_id')
    op.drop_column('media_items', 'tmdb_id')
    op.drop_column('media_items', 'tvdb_id')
    op.drop_column('media_items', 'emby_item_id')
    op.drop_column('media_items', 'jellyfin_item_id')
    op.drop_column('media_items', 'plex_library_section_title')
    op.drop_column('media_items', 'plex_library_section_id')
    op.drop_column('media_items', 'plex_guid')
    op.drop_column('media_items', 'plex_rating_key')
    op.drop_column('media_items', 'youtube_like_count')
    op.drop_column('media_items', 'youtube_category')
    op.drop_column('media_items', 'youtube_tags')
    op.drop_column('media_items', 'youtube_channel_name')
    op.drop_column('media_items', 'youtube_channel_id')
    op.drop_column('media_items', 'youtube_video_id')
    op.drop_column('media_items', 'archive_org_subject')
    op.drop_column('media_items', 'archive_org_collection')
    op.drop_column('media_items', 'archive_org_creator')
    op.drop_column('media_items', 'archive_org_filename')
    op.drop_column('media_items', 'archive_org_identifier')
    
    # Drop FillerPreset columns
    op.drop_column('filler_presets', 'multi_collection_id')
    op.drop_column('filler_presets', 'smart_collection_id')
    op.drop_column('filler_presets', 'collection_id')
    op.drop_column('filler_presets', 'allow_watermarks')
    op.drop_column('filler_presets', 'expression')
    op.drop_column('filler_presets', 'filler_kind')
    
    # Drop Playout columns
    op.drop_column('playouts', 'seed')
    op.drop_column('playouts', 'schedule_file')
    op.drop_column('playouts', 'schedule_kind')
    op.drop_column('playouts', 'deco_id')
    
    # Drop BlockItem columns
    op.drop_column('block_items', 'disable_watermarks')
    op.drop_column('block_items', 'search_title')
    op.drop_column('block_items', 'search_query')
    op.drop_column('block_items', 'smart_collection_id')
    op.drop_column('block_items', 'multi_collection_id')
    
    # Drop Block columns
    op.drop_column('blocks', 'stop_scheduling')
    op.drop_column('blocks', 'minutes')
    
    # Drop ProgramScheduleItem columns
    op.drop_column('program_schedule_items', 'subtitle_mode')
    op.drop_column('program_schedule_items', 'preferred_subtitle_language_code')
    op.drop_column('program_schedule_items', 'preferred_audio_title')
    op.drop_column('program_schedule_items', 'preferred_audio_language_code')
    op.drop_column('program_schedule_items', 'marathon_group_by')
    op.drop_column('program_schedule_items', 'marathon_batch_size')
    op.drop_column('program_schedule_items', 'search_title')
    op.drop_column('program_schedule_items', 'search_query')
    op.drop_column('program_schedule_items', 'smart_collection_id')
    op.drop_column('program_schedule_items', 'multi_collection_id')
    
    # Drop ProgramSchedule columns
    op.drop_column('program_schedules', 'fixed_start_time_behavior')
    
    # Drop Channel columns
    op.drop_index('ix_channels_unique_id', table_name='channels')
    op.drop_column('channels', 'categories')
    op.drop_column('channels', 'sort_number')
    op.drop_column('channels', 'unique_id')
    
    # Drop FFmpegProfile columns
    op.drop_column('ffmpeg_profiles', 'global_watermark_id')
    op.drop_column('ffmpeg_profiles', 'gop_size')
    op.drop_column('ffmpeg_profiles', 'deinterlace_video')
    op.drop_column('ffmpeg_profiles', 'normalize_framerate')
    op.drop_column('ffmpeg_profiles', 'qsv_extra_hardware_frames')
    op.drop_column('ffmpeg_profiles', 'vaapi_device')
    op.drop_column('ffmpeg_profiles', 'vaapi_driver')
    op.drop_column('ffmpeg_profiles', 'target_loudness')
    op.drop_column('ffmpeg_profiles', 'normalize_loudness_mode')
    op.drop_column('ffmpeg_profiles', 'tonemap_algorithm')
    op.drop_column('ffmpeg_profiles', 'scaling_behavior')
    op.drop_column('ffmpeg_profiles', 'audio_buffer_size')
    op.drop_column('ffmpeg_profiles', 'audio_format')
    op.drop_column('ffmpeg_profiles', 'bit_depth')
    op.drop_column('ffmpeg_profiles', 'allow_b_frames')
    op.drop_column('ffmpeg_profiles', 'video_profile')
    op.drop_column('ffmpeg_profiles', 'video_format')
