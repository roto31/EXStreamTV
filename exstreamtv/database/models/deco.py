"""
Deco Database Models

Defines Deco, DecoGroup, and related models for channel decoration.
ErsatzTV feature: watermarks, bumpers, breaks, graphics, dead air fallback.

This module provides full ErsatzTV-compatible Deco configuration including:
- Watermark mode and configuration
- Graphics elements mode
- Break content mode and items
- Default filler mode and collection
- Dead air fallback mode and collection
"""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from exstreamtv.database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from exstreamtv.database.models.channel import ChannelWatermark


class DecoGroup(Base, TimestampMixin):
    """
    Group for organizing deco content.
    """
    
    __tablename__ = "deco_groups"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Relationships
    decos: Mapped[list["DecoTemplate"]] = relationship(
        "DecoTemplate",
        back_populates="group",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<DecoGroup {self.name}>"


class Deco(Base, TimestampMixin):
    """
    Deco configuration for a channel/playout.
    
    ErsatzTV-compatible: Full decoration configuration including
    watermarks, graphics, breaks, filler, and dead air fallback.
    
    This is the main Deco entity that is referenced by Playout.
    """
    
    __tablename__ = "decos"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # === Watermark Configuration ===
    # Mode: "none", "inherit", "override"
    watermark_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="inherit",
    )
    # Watermark to use when mode is "override"
    watermark_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("channel_watermarks.id"),
        nullable=True,
    )
    
    # === Graphics Elements Configuration ===
    # Mode: "none", "inherit", "override"
    graphics_elements_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="inherit",
    )
    
    # === Break Content Configuration ===
    # Mode: "none", "inherit", "override"
    break_content_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="inherit",
    )
    
    # === Default Filler Configuration ===
    # Mode: "none", "inherit", "override"
    default_filler_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="inherit",
    )
    # Collection ID for filler content when mode is "override"
    default_filler_collection_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("playlists.id"),
        nullable=True,
    )
    # Trim filler to fit exactly
    default_filler_trim_to_fit: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    # === Dead Air Fallback Configuration ===
    # Mode: "none", "inherit", "override"
    dead_air_fallback_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="inherit",
    )
    # Collection ID for dead air fallback when mode is "override"
    dead_air_fallback_collection_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("playlists.id"),
        nullable=True,
    )
    
    # Relationships
    watermark: Mapped[Optional["ChannelWatermark"]] = relationship(
        "ChannelWatermark",
        foreign_keys=[watermark_id],
    )
    break_items: Mapped[list["DecoBreakContent"]] = relationship(
        "DecoBreakContent",
        back_populates="deco",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<Deco {self.name}>"


class DecoBreakContent(Base, TimestampMixin):
    """
    Break content item within a Deco configuration.
    
    ErsatzTV feature: content to play during breaks (commercials, PSAs, etc.)
    """
    
    __tablename__ = "deco_break_contents"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deco_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("decos.id"),
        nullable=False,
    )
    
    # Position in break content list
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Collection reference for break content
    collection_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("playlists.id"),
        nullable=True,
    )
    
    # Duration settings
    target_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Frequency: how often to include this break content
    frequency_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Enabled flag
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    deco: Mapped["Deco"] = relationship(
        "Deco",
        back_populates="break_items",
    )
    
    def __repr__(self) -> str:
        return f"<DecoBreakContent {self.id} for Deco {self.deco_id}>"


class DecoTemplate(Base, TimestampMixin):
    """
    Deco template/preset for reusable deco content.
    
    Legacy model for bumpers, station IDs, etc.
    Kept for backward compatibility and simpler use cases.
    """
    
    __tablename__ = "deco_templates"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("deco_groups.id"),
        nullable=True,
    )
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Deco type: "bumper", "commercial", "station_id", "promo", "credits"
    deco_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="bumper",
    )
    
    # Media reference
    media_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("media_items.id"),
        nullable=True,
    )
    
    # Or direct file path
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Duration in seconds (cached or for static images)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # For static images, show duration
    static_duration_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
    )
    
    # Weight for random selection
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    # Relationships
    group: Mapped[Optional["DecoGroup"]] = relationship(
        "DecoGroup",
        back_populates="decos",
    )
    
    def __repr__(self) -> str:
        return f"<DecoTemplate {self.name} ({self.deco_type})>"
