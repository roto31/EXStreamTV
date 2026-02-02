"""
Smart Collection Database Models

Defines SmartCollection and related models for dynamic content selection.
ErsatzTV feature: collections based on search queries/expressions.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from exstreamtv.database.models.base import Base, TimestampMixin


class SmartCollection(Base, TimestampMixin):
    """
    Smart collection with dynamic content based on search query.
    
    ErsatzTV feature: collections that automatically update based on
    search criteria (genre, year, studio, etc.)
    """
    
    __tablename__ = "smart_collections"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Search query (JSON or expression string)
    # Example: {"genre": "comedy", "year": {"$gte": 1980, "$lte": 1989}}
    query: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Query type: "json", "expression", "lucene"
    query_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="json",
    )
    
    # Media source filter (limit to specific sources)
    # "all", "plex", "jellyfin", "emby", "local", "archive_org", "youtube"
    source_filter: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Library filter (limit to specific library IDs)
    library_ids: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    
    # Ordering
    order_by: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="title",  # title, year, added_date, random, shuffle
    )
    order_direction: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="asc",  # asc, desc
    )
    
    # Limits
    max_items: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Cache settings
    cache_duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=60,
    )
    last_refreshed: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cached_item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # State
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    def __repr__(self) -> str:
        return f"<SmartCollection {self.name}>"


class SmartCollectionItem(Base, TimestampMixin):
    """
    Cached item in a smart collection.
    
    Represents the resolved items from a smart collection query.
    """
    
    __tablename__ = "smart_collection_items"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    smart_collection_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("smart_collections.id"),
        nullable=False,
    )
    media_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("media_items.id"),
        nullable=False,
    )
    
    # Position in collection (for ordered collections)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # When this item was added to cache
    cached_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    
    def __repr__(self) -> str:
        return f"<SmartCollectionItem smart={self.smart_collection_id} media={self.media_item_id}>"


class RerunCollection(Base, TimestampMixin):
    """
    Rerun tracking collection.
    
    ErsatzTV feature: tracks what content has been played to avoid
    immediate repeats and implement rerun windows.
    """
    
    __tablename__ = "rerun_collections"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Associated channel or playout
    channel_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("channels.id"),
        nullable=True,
    )
    playout_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("playouts.id"),
        nullable=True,
    )
    
    # Rerun window settings
    # Minimum time before content can be replayed (in hours)
    minimum_rerun_window_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=24,
    )
    
    # Maximum history to track (number of items)
    max_history_items: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1000,
    )
    
    # Relationships
    history_items: Mapped[list["RerunHistoryItem"]] = relationship(
        "RerunHistoryItem",
        back_populates="collection",
        cascade="all, delete-orphan",
        order_by="RerunHistoryItem.played_at.desc()",
    )
    
    def __repr__(self) -> str:
        return f"<RerunCollection {self.name}>"


class RerunHistoryItem(Base, TimestampMixin):
    """
    History item for rerun tracking.
    
    Records when content was played for rerun window calculations.
    """
    
    __tablename__ = "rerun_history_items"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rerun_collections.id"),
        nullable=False,
    )
    media_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("media_items.id"),
        nullable=False,
    )
    
    # When this item was played
    played_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Optional: which playout item triggered this
    playout_item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Relationships
    collection: Mapped["RerunCollection"] = relationship(
        "RerunCollection",
        back_populates="history_items",
    )
    
    def __repr__(self) -> str:
        return f"<RerunHistoryItem media={self.media_item_id} at {self.played_at}>"
