"""
Filler Database Models

Defines FillerPreset and FillerPresetItem for filler content.
ErsatzTV feature: fill gaps between scheduled content.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from exstreamtv.database.models.base import Base, TimestampMixin


class FillerPreset(Base, TimestampMixin):
    """
    Filler preset defining a collection of filler content.
    
    ErsatzTV feature: used for pre-roll, mid-roll, post-roll,
    tail filler, and fallback content.
    """
    
    __tablename__ = "filler_presets"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # ErsatzTV: Filler kind (type of filler usage)
    # "pre_roll", "mid_roll", "post_roll", "tail", "fallback", "dead_air"
    filler_kind: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    
    # Filler behavior
    # "count" - play N items
    # "duration" - fill for N minutes
    # "pad" - pad to next time boundary
    filler_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="duration",
    )
    
    # For "count" mode
    count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # For "duration" mode (seconds)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # For "pad" mode (minutes boundary)
    pad_to_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # ErsatzTV: Expression for dynamic filler selection
    # Used for complex filler logic (e.g., "duration < 120 AND genre='comedy'")
    expression: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Playback order: "chronological", "shuffled", "random"
    playback_order: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="shuffled",
    )
    
    # Allow repeats within same filler slot
    allow_repeats: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # ErsatzTV: Allow watermarks during filler playback
    allow_watermarks: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # ErsatzTV: Collection reference for filler content
    collection_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("playlists.id"),
        nullable=True,
    )
    
    # ErsatzTV: Smart collection reference
    smart_collection_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("smart_collections.id"),
        nullable=True,
    )
    
    # ErsatzTV: Multi-collection reference
    multi_collection_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("multi_collections.id"),
        nullable=True,
    )
    
    # Relationships
    items: Mapped[list["FillerPresetItem"]] = relationship(
        "FillerPresetItem",
        back_populates="preset",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<FillerPreset {self.name}>"


class FillerPresetItem(Base, TimestampMixin):
    """
    Item within a filler preset.
    
    Can reference a collection or a single media item.
    """
    
    __tablename__ = "filler_preset_items"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    preset_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("filler_presets.id"),
        nullable=False,
    )
    
    # Collection reference (for multiple items)
    collection_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    collection_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Single media item reference
    media_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("media_items.id"),
        nullable=True,
    )
    
    # Weight for selection (higher = more likely)
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    # Duration constraints
    min_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Relationships
    preset: Mapped["FillerPreset"] = relationship(
        "FillerPreset",
        back_populates="items",
    )
    
    def __repr__(self) -> str:
        if self.media_item_id:
            return f"<FillerPresetItem media={self.media_item_id}>"
        return f"<FillerPresetItem {self.collection_type}:{self.collection_id}>"
