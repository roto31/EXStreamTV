"""
Library Database Models

Defines library sources: Plex, Jellyfin, Emby, and local folders.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from exstreamtv.database.models.base import Base, TimestampMixin


class PlexLibrary(Base, TimestampMixin):
    """
    Plex media server library.
    """
    
    __tablename__ = "plex_libraries"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Connection info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    server_url: Mapped[str] = mapped_column(Text, nullable=False)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Plex-specific
    plex_library_key: Mapped[str] = mapped_column(String(50), nullable=False)
    plex_library_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Library type: "movie", "show", "music"
    library_type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Scan state
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_scan: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scan_interval_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    # Stats
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    def __repr__(self) -> str:
        return f"<PlexLibrary {self.name}: {self.plex_library_name}>"


class JellyfinLibrary(Base, TimestampMixin):
    """
    Jellyfin media server library.
    """
    
    __tablename__ = "jellyfin_libraries"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Connection info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    server_url: Mapped[str] = mapped_column(Text, nullable=False)
    api_key: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Jellyfin-specific
    jellyfin_library_id: Mapped[str] = mapped_column(String(50), nullable=False)
    jellyfin_library_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Library type
    library_type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Scan state
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_scan: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scan_interval_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    # Stats
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    def __repr__(self) -> str:
        return f"<JellyfinLibrary {self.name}: {self.jellyfin_library_name}>"


class EmbyLibrary(Base, TimestampMixin):
    """
    Emby media server library.
    """
    
    __tablename__ = "emby_libraries"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Connection info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    server_url: Mapped[str] = mapped_column(Text, nullable=False)
    api_key: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Emby-specific
    emby_library_id: Mapped[str] = mapped_column(String(50), nullable=False)
    emby_library_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Library type
    library_type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Scan state
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_scan: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scan_interval_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    # Stats
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    def __repr__(self) -> str:
        return f"<EmbyLibrary {self.name}: {self.emby_library_name}>"


class LocalLibrary(Base, TimestampMixin):
    """
    Local folder library.
    """
    
    __tablename__ = "local_libraries"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Library type: "movie", "show", "music", "other"
    library_type: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    
    # Scan settings
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_scan: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scan_interval_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    recursive: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Stats
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # File extensions to include (comma-separated)
    file_extensions: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default=".mp4,.mkv,.avi,.mov,.wmv,.flv,.webm,.m4v,.ts,.m2ts",
    )
    
    def __repr__(self) -> str:
        return f"<LocalLibrary {self.name}: {self.path}>"
