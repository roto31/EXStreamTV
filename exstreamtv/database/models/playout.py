"""
Playout Database Models

Defines Playout, PlayoutItem, PlayoutAnchor, and related models.
Core ErsatzTV feature: manages the continuous timeline for channels.
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Interval, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from exstreamtv.database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from exstreamtv.database.models.channel import Channel
    from exstreamtv.database.models.media import MediaItem
    from exstreamtv.database.models.schedule import ProgramSchedule
    from exstreamtv.database.models.template import Template


class Playout(Base, TimestampMixin):
    """
    Playout model representing a channel's scheduled content timeline.
    
    ErsatzTV core concept: each channel has playouts that define
    what plays and when.
    """
    
    __tablename__ = "playouts"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Channel association
    channel_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("channels.id"),
        nullable=False,
    )
    
    # Schedule reference
    program_schedule_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("program_schedules.id"),
        nullable=True,
    )
    
    # Template reference (alternative to program schedule)
    template_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("templates.id"),
        nullable=True,
    )
    
    # ErsatzTV: Deco configuration reference
    deco_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("decos.id"),
        nullable=True,
    )
    
    # Playout mode: "continuous", "daily", "weekly"
    playout_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="continuous",
    )
    
    # ErsatzTV: Schedule kind (flood, block, external)
    schedule_kind: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="flood",  # "flood", "block", "external", "yaml"
    )
    
    # ErsatzTV: External schedule file path (for "external" kind)
    schedule_file: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # ErsatzTV: Random seed for reproducible shuffling
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Daily reset time (for "daily" type)
    daily_reset_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # State
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    channel: Mapped["Channel"] = relationship(
        "Channel",
        back_populates="playouts",
    )
    program_schedule: Mapped[Optional["ProgramSchedule"]] = relationship(
        "ProgramSchedule",
        back_populates="playouts",
    )
    template: Mapped[Optional["Template"]] = relationship(
        "Template",
        back_populates="playouts",
    )
    anchor: Mapped[Optional["PlayoutAnchor"]] = relationship(
        "PlayoutAnchor",
        back_populates="playout",
        uselist=False,
        cascade="all, delete-orphan",
    )
    items: Mapped[list["PlayoutItem"]] = relationship(
        "PlayoutItem",
        back_populates="playout",
        cascade="all, delete-orphan",
        order_by="PlayoutItem.start_time",
    )
    history: Mapped[list["PlayoutHistory"]] = relationship(
        "PlayoutHistory",
        back_populates="playout",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<Playout {self.id} for Channel {self.channel_id}>"


class PlayoutAnchor(Base, TimestampMixin):
    """
    Anchor point for playout scheduling.
    
    ErsatzTV: Tracks the current position in collections/schedules
    for continuous playback.
    """
    
    __tablename__ = "playout_anchors"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    playout_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("playouts.id"),
        nullable=False,
        unique=True,
    )
    
    # Anchor time (next item starts here)
    next_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Collection/schedule state for each item type
    # Stored as JSON: {"collection_id": {"index": 5, "state": "shuffled_order"}}
    collection_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Relationships
    playout: Mapped["Playout"] = relationship(
        "Playout",
        back_populates="anchor",
    )
    
    def __repr__(self) -> str:
        return f"<PlayoutAnchor for Playout {self.playout_id}>"


class PlayoutItem(Base, TimestampMixin):
    """
    Individual item in a playout timeline.
    
    Represents a scheduled media item with start/finish times.
    """
    
    __tablename__ = "playout_items"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    playout_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("playouts.id"),
        nullable=False,
    )
    
    # Media item reference
    media_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("media_items.id"),
        nullable=True,
    )
    
    # For online sources (alternative to media_item)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Timing
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finish_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # In/Out points (for trimming)
    in_point: Mapped[timedelta | None] = mapped_column(Interval, nullable=True)
    out_point: Mapped[timedelta | None] = mapped_column(Interval, nullable=True)
    
    # Item metadata (cached)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    episode_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Filler type: null=regular, "pre_roll", "mid_roll", "post_roll", "tail", "fallback"
    filler_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    
    # Guide information
    guide_group: Mapped[int | None] = mapped_column(Integer, nullable=True)  # For multi-episode
    custom_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Block reference (if part of a block)
    block_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("blocks.id"),
        nullable=True,
    )
    
    # Relationships
    playout: Mapped["Playout"] = relationship(
        "Playout",
        back_populates="items",
    )
    media_item: Mapped[Optional["MediaItem"]] = relationship("MediaItem")
    
    def __repr__(self) -> str:
        return f"<PlayoutItem {self.title} at {self.start_time}>"
    
    @property
    def duration(self) -> timedelta:
        """Get item duration."""
        return self.finish_time - self.start_time
    
    @property
    def is_filler(self) -> bool:
        """Check if this is a filler item."""
        return self.filler_kind is not None


class PlayoutHistory(Base, TimestampMixin):
    """
    History of played items for analytics and debugging.
    """
    
    __tablename__ = "playout_history"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    playout_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("playouts.id"),
        nullable=False,
    )
    
    # Item that was played
    media_item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    
    # When it played
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Status: "completed", "interrupted", "skipped", "error"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    
    # Error details if applicable
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Relationships
    playout: Mapped["Playout"] = relationship(
        "Playout",
        back_populates="history",
    )
    
    def __repr__(self) -> str:
        return f"<PlayoutHistory {self.title} at {self.started_at}>"


class PlayoutTemplate(Base, TimestampMixin):
    """
    Association between playouts and templates.
    
    ErsatzTV feature: allows applying templates to playouts.
    """
    
    __tablename__ = "playout_templates"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    playout_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("playouts.id"),
        nullable=False,
    )
    template_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("templates.id"),
        nullable=False,
    )
    
    # Day of week (0=Sunday, 1=Monday, etc.) or null for all days
    day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Priority (lower = higher priority)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    def __repr__(self) -> str:
        return f"<PlayoutTemplate playout={self.playout_id} template={self.template_id}>"


class PlayoutBuildSession(Base, TimestampMixin):
    """
    Active playout build session for scripted schedule API.
    
    ErsatzTV feature: programmatic playout building with persistent state.
    """
    
    __tablename__ = "playout_build_sessions"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    playout_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("playouts.id"),
        nullable=False,
    )
    
    # Current build time position
    current_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Build state as JSON
    state_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    
    # Content buffer as JSON (items pending commit)
    content_buffer: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    
    # Build state flags
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="building",
    )  # "building", "committed", "cancelled"
    
    # Feature flags
    watermark_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    graphics_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    pre_roll_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # EPG grouping
    epg_group_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    epg_group_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Session expiration
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Relationships
    playout: Mapped["Playout"] = relationship("Playout")
    
    def __repr__(self) -> str:
        return f"<PlayoutBuildSession {self.id} for playout {self.playout_id}>"
