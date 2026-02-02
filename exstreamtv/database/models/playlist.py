"""
Playlist Database Models

Defines Playlist, PlaylistGroup, and PlaylistItem models.
Compatible with ErsatzTV playlist structure.
"""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from exstreamtv.database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from exstreamtv.database.models.media import MediaItem


class PlaylistGroup(Base, TimestampMixin):
    """
    Group for organizing playlists.
    
    ErsatzTV feature: organize playlists into logical groups.
    """
    
    __tablename__ = "playlist_groups"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Relationships
    playlists: Mapped[list["Playlist"]] = relationship(
        "Playlist",
        back_populates="group",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<PlaylistGroup {self.name}>"


class Playlist(Base, TimestampMixin):
    """
    Playlist model for organizing media content.
    
    Combines StreamTV playlist with ErsatzTV features.
    """
    
    __tablename__ = "playlists"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Group association
    group_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("playlist_groups.id"),
        nullable=True,
    )
    
    # Source type: "youtube", "archive_org", "local", "plex", "jellyfin", "emby", "mixed"
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="mixed")
    
    # For online playlists
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Thumbnail/preview
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Playlist settings
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    shuffle: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    loop: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Collection/Smart playlist fields (v2.5.0)
    # collection_type: "static", "smart", "manual"
    collection_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="static",
    )
    
    # For smart collections: query string to find matching content
    # Format: "genres:Action,Comedy AND year:1980-1999 AND source:plex"
    search_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Relationships
    group: Mapped[Optional["PlaylistGroup"]] = relationship(
        "PlaylistGroup",
        back_populates="playlists",
    )
    items: Mapped[list["PlaylistItem"]] = relationship(
        "PlaylistItem",
        back_populates="playlist",
        cascade="all, delete-orphan",
        order_by="PlaylistItem.position",
    )
    
    def __repr__(self) -> str:
        return f"<Playlist {self.name}>"
    
    @property
    def item_count(self) -> int:
        """Get number of items in playlist."""
        return len(self.items)


class PlaylistItem(Base, TimestampMixin):
    """
    Item within a playlist.
    
    Can reference either a media item or an online source URL.
    """
    
    __tablename__ = "playlist_items"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Playlist association
    playlist_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("playlists.id"),
        nullable=False,
    )
    
    # Optional media item reference (for local/library content)
    media_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("media_items.id"),
        nullable=True,
    )
    
    # For online sources (YouTube, Archive.org)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Item metadata (cached for performance)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Position in playlist (1-based)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    # ErsatzTV: In/Out points for trimming
    in_point_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    out_point_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Item state
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    playlist: Mapped["Playlist"] = relationship(
        "Playlist",
        back_populates="items",
    )
    media_item: Mapped[Optional["MediaItem"]] = relationship(
        "MediaItem",
        back_populates="playlist_items",
    )
    
    def __repr__(self) -> str:
        return f"<PlaylistItem {self.position}: {self.title[:30]}>"
    
    @property
    def effective_duration(self) -> int | None:
        """Get effective duration considering in/out points."""
        if self.duration_seconds is None:
            return None
        
        start = self.in_point_seconds or 0
        end = self.out_point_seconds or self.duration_seconds
        
        return max(0, end - start)
