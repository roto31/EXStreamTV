"""
Schedule Database Models

Defines ProgramSchedule, Block, and related scheduling models.
Core ErsatzTV scheduling features.
"""

from datetime import time
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from exstreamtv.database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from exstreamtv.database.models.playout import Playout


class ProgramSchedule(Base, TimestampMixin):
    """
    Program schedule defining content ordering and behavior.
    
    ErsatzTV core concept: controls how content is selected and ordered.
    """
    
    __tablename__ = "program_schedules"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Schedule behavior flags
    keep_multi_part_episodes: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    treat_collections_as_shows: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    shuffle_schedule_items: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    random_start_point: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    # ErsatzTV: Fixed start time behavior
    # Options: "skip", "fill", "skip_and_fill"
    fixed_start_time_behavior: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="fill",
    )
    
    # Relationships
    items: Mapped[list["ProgramScheduleItem"]] = relationship(
        "ProgramScheduleItem",
        back_populates="schedule",
        cascade="all, delete-orphan",
        order_by="ProgramScheduleItem.position",
    )
    playouts: Mapped[list["Playout"]] = relationship(
        "Playout",
        back_populates="program_schedule",
    )
    
    def __repr__(self) -> str:
        return f"<ProgramSchedule {self.name}>"


class ProgramScheduleItem(Base, TimestampMixin):
    """
    Item within a program schedule.
    
    References collections/playlists with playback mode settings.
    Supports ErsatzTV-compatible collection types and marathon mode.
    """
    
    __tablename__ = "program_schedule_items"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("program_schedules.id"),
        nullable=False,
    )
    
    # Position in schedule (1-based)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    # Collection/playlist reference
    collection_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # "playlist", "collection", "show", "season", "multi_collection", "smart_collection", "search"
    collection_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # ErsatzTV: Multi-collection reference
    multi_collection_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("multi_collections.id"),
        nullable=True,
    )
    
    # ErsatzTV: Smart collection reference
    smart_collection_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("smart_collections.id"),
        nullable=True,
    )
    
    # ErsatzTV: Search-based content (dynamic query)
    search_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Custom title for EPG
    custom_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Playback mode: "one", "multiple", "duration", "flood"
    playback_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="flood",
    )
    
    # For "multiple" mode
    multiple_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # For "duration" mode (minutes)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    playout_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Time settings
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    
    # Playback order: "chronological", "shuffled", "random", "shuffle_in_order"
    playback_order: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="chronological",
    )
    
    # === Marathon Mode Settings (ErsatzTV) ===
    # Marathon mode groups related content (e.g., same show episodes)
    marathon_batch_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    marathon_group_by: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,  # "show", "season", "collection"
    )
    
    # === Audio/Subtitle Overrides (ErsatzTV) ===
    preferred_audio_language_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    preferred_audio_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preferred_subtitle_language_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    subtitle_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    
    # Guide settings
    guide_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="normal",  # "normal", "filler"
    )
    
    # Pre/mid/post roll filler
    pre_roll_filler_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("filler_presets.id"),
        nullable=True,
    )
    mid_roll_filler_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("filler_presets.id"),
        nullable=True,
    )
    post_roll_filler_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("filler_presets.id"),
        nullable=True,
    )
    tail_filler_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("filler_presets.id"),
        nullable=True,
    )
    fallback_filler_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("filler_presets.id"),
        nullable=True,
    )
    
    # Relationships
    schedule: Mapped["ProgramSchedule"] = relationship(
        "ProgramSchedule",
        back_populates="items",
    )
    
    def __repr__(self) -> str:
        return f"<ProgramScheduleItem {self.position}: {self.collection_type}>"


class BlockGroup(Base, TimestampMixin):
    """
    Group of blocks for organizing time-based programming.
    """
    
    __tablename__ = "block_groups"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Relationships
    blocks: Mapped[list["Block"]] = relationship(
        "Block",
        back_populates="group",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<BlockGroup {self.name}>"


class Block(Base, TimestampMixin):
    """
    Time-based programming block.
    
    ErsatzTV feature: schedule content for specific time slots.
    """
    
    __tablename__ = "blocks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("block_groups.id"),
        nullable=True,
    )
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Block timing
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # ErsatzTV: Alternative duration in minutes (for flexible scheduling)
    minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Days of week (bitmask: 1=Sun, 2=Mon, 4=Tue, 8=Wed, 16=Thu, 32=Fri, 64=Sat)
    days_of_week: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=127,  # All days
    )
    
    # ErsatzTV: Stop scheduling flag (block terminates schedule building)
    stop_scheduling: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Relationships
    group: Mapped[Optional["BlockGroup"]] = relationship(
        "BlockGroup",
        back_populates="blocks",
    )
    items: Mapped[list["BlockItem"]] = relationship(
        "BlockItem",
        back_populates="block",
        cascade="all, delete-orphan",
        order_by="BlockItem.position",
    )
    
    def __repr__(self) -> str:
        return f"<Block {self.name} at {self.start_time}>"
    
    def active_on_day(self, day: int) -> bool:
        """Check if block is active on given day (0=Sun, 1=Mon, etc.)."""
        return bool(self.days_of_week & (1 << day))


class BlockItem(Base, TimestampMixin):
    """
    Item within a block.
    
    References collections/playlists to play during the block.
    Supports ErsatzTV-compatible search and smart collection features.
    """
    
    __tablename__ = "block_items"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    block_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("blocks.id"),
        nullable=False,
    )
    
    # Position in block (1-based)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    # Collection reference
    collection_type: Mapped[str] = mapped_column(String(50), nullable=False)
    collection_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # ErsatzTV: Multi-collection reference
    multi_collection_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("multi_collections.id"),
        nullable=True,
    )
    
    # ErsatzTV: Smart collection reference
    smart_collection_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("smart_collections.id"),
        nullable=True,
    )
    
    # ErsatzTV: Search-based content
    search_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Playback mode
    playback_order: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="chronological",
    )
    
    # Include in guide
    include_in_guide: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # ErsatzTV: Disable watermarks for this block item
    disable_watermarks: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Relationships
    block: Mapped["Block"] = relationship(
        "Block",
        back_populates="items",
    )
    
    def __repr__(self) -> str:
        return f"<BlockItem {self.position} in Block {self.block_id}>"
