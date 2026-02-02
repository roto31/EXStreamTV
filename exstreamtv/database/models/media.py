"""
Media Database Models

Defines MediaItem, MediaFile, and MediaVersion models.
Represents local media library content and streaming sources.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from exstreamtv.database.models.base import Base, TimestampMixin


class CollectionTypeEnum(str, Enum):
    """
    Enum for collection types.
    
    - STATIC: Manual collection with fixed items
    - SMART: Dynamic collection based on search query
    - MANUAL: User-curated collection
    """
    
    STATIC = "static"
    SMART = "smart"
    MANUAL = "manual"

if TYPE_CHECKING:
    from exstreamtv.database.models.playlist import PlaylistItem


class MediaItem(Base, TimestampMixin):
    """
    Media item representing a video/show/movie.
    
    Supports both local library media and streaming sources
    (YouTube, Archive.org, Plex, etc.)
    """
    
    __tablename__ = "media_items"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Type: "movie", "episode", "music_video", "other_video", "song"
    media_type: Mapped[str] = mapped_column(String(50), nullable=False, default="other_video")
    
    # Source type: "local", "plex", "jellyfin", "emby", "youtube", "archive_org"
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="local")
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # URL for streaming sources
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Library source (for local/plex/jellyfin/emby)
    library_source: Mapped[str] = mapped_column(String(50), nullable=False, default="local")
    library_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # External IDs (for library integrations)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Basic metadata
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    original_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Description (alias for plot for streaming sources)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Duration in seconds
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Thumbnail URL
    thumbnail: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # For streaming sources
    uploader: Mapped[str | None] = mapped_column(String(255), nullable=True)
    upload_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    view_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meta_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    
    # For episodes
    show_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    season_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    episode_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # For multi-episode files
    episode_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    # Description for library items
    plot: Mapped[str | None] = mapped_column(Text, nullable=True)
    tagline: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Dates
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    release_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    added_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    
    # Ratings
    content_rating: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "TV-MA", "PG-13"
    rating: Mapped[float | None] = mapped_column(Integer, nullable=True)  # 0-100
    
    # Genres (JSON array)
    genres: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Studios/Networks (JSON array)
    studios: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Artwork
    poster_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    fanart_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # === Source-specific metadata (StreamTV compatibility) ===
    
    # Archive.org metadata
    archive_org_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    archive_org_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    archive_org_creator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    archive_org_collection: Mapped[str | None] = mapped_column(String(255), nullable=True)
    archive_org_subject: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    
    # YouTube metadata
    youtube_video_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    youtube_channel_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    youtube_channel_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    youtube_tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    youtube_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    youtube_like_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Plex metadata
    plex_rating_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    plex_guid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    plex_library_section_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    plex_library_section_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Jellyfin/Emby metadata
    jellyfin_item_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    emby_item_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # External database IDs (for metadata enrichment)
    tvdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    imdb_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    
    # AI-enhanced metadata (StreamTV feature)
    ai_enhanced_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ai_enhanced_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_enhanced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ai_enhancement_model: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # State
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    versions: Mapped[list["MediaVersion"]] = relationship(
        "MediaVersion",
        back_populates="media_item",
        cascade="all, delete-orphan",
    )
    files: Mapped[list["MediaFile"]] = relationship(
        "MediaFile",
        back_populates="media_item",
        cascade="all, delete-orphan",
    )
    playlist_items: Mapped[list["PlaylistItem"]] = relationship(
        "PlaylistItem",
        back_populates="media_item",
    )
    
    def __repr__(self) -> str:
        if self.media_type == "episode":
            return f"<MediaItem {self.show_title} S{self.season_number}E{self.episode_number}>"
        return f"<MediaItem {self.title}>"


class MediaVersion(Base, TimestampMixin):
    """
    Version/quality variant of a media item.
    
    Allows multiple quality versions of the same content.
    """
    
    __tablename__ = "media_versions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    media_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("media_items.id"),
        nullable=False,
    )
    
    # Version name (e.g., "1080p", "4K", "SD")
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="Default")
    
    # Duration in milliseconds
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Video info
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_codec: Mapped[str | None] = mapped_column(String(50), nullable=True)
    video_bitrate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    framerate: Mapped[float | None] = mapped_column(Integer, nullable=True)
    
    # Audio info
    audio_codec: Mapped[str | None] = mapped_column(String(50), nullable=True)
    audio_channels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    audio_bitrate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Chapter markers (JSON array)
    chapters: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Relationships
    media_item: Mapped["MediaItem"] = relationship(
        "MediaItem",
        back_populates="versions",
    )
    
    def __repr__(self) -> str:
        return f"<MediaVersion {self.name} ({self.width}x{self.height})>"
    
    @property
    def duration_seconds(self) -> int:
        """Get duration in seconds."""
        return self.duration_ms // 1000


class MultiCollection(Base, TimestampMixin):
    """
    Multi-collection grouping multiple collections together.
    
    ErsatzTV feature: combine multiple collections for scheduling.
    """
    
    __tablename__ = "multi_collections"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Relationships
    collection_links: Mapped[list["MultiCollectionLink"]] = relationship(
        "MultiCollectionLink",
        back_populates="multi_collection",
        cascade="all, delete-orphan",
        order_by="MultiCollectionLink.position",
    )
    
    def __repr__(self) -> str:
        return f"<MultiCollection {self.name}>"


class MultiCollectionLink(Base, TimestampMixin):
    """
    Link between a multi-collection and a collection.
    """
    
    __tablename__ = "multi_collection_links"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    multi_collection_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("multi_collections.id"),
        nullable=False,
    )
    collection_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("playlists.id"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Relationships
    multi_collection: Mapped["MultiCollection"] = relationship(
        "MultiCollection",
        back_populates="collection_links",
    )
    
    def __repr__(self) -> str:
        return f"<MultiCollectionLink multi={self.multi_collection_id} coll={self.collection_id}>"


class MediaFile(Base, TimestampMixin):
    """
    Physical file location for a media item.
    """
    
    __tablename__ = "media_files"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    media_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("media_items.id"),
        nullable=False,
    )
    
    # File path
    path: Mapped[str] = mapped_column(Text, nullable=False)
    
    # File info
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA-256
    
    # Last modified time
    file_modified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # State
    is_accessible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    media_item: Mapped["MediaItem"] = relationship(
        "MediaItem",
        back_populates="files",
    )
    
    def __repr__(self) -> str:
        return f"<MediaFile {self.path}>"
