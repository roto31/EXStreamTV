"""
Template Database Models

Defines Template, TemplateGroup, and TemplateItem for scheduling templates.
ErsatzTV feature: reusable schedule patterns.
"""

from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from exstreamtv.database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from exstreamtv.database.models.playout import Playout


class TemplateGroup(Base, TimestampMixin):
    """
    Group for organizing templates.
    """
    
    __tablename__ = "template_groups"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Relationships
    templates: Mapped[list["Template"]] = relationship(
        "Template",
        back_populates="group",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<TemplateGroup {self.name}>"


class Template(Base, TimestampMixin):
    """
    Schedule template for reusable programming patterns.
    
    ErsatzTV feature: define a day's programming once, apply to multiple days.
    """
    
    __tablename__ = "templates"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("template_groups.id"),
        nullable=True,
    )
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # State
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    group: Mapped["TemplateGroup"] = relationship(
        "TemplateGroup",
        back_populates="templates",
    )
    items: Mapped[list["TemplateItem"]] = relationship(
        "TemplateItem",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="TemplateItem.start_time",
    )
    playouts: Mapped[list["Playout"]] = relationship(
        "Playout",
        back_populates="template",
    )
    
    def __repr__(self) -> str:
        return f"<Template {self.name}>"


class TemplateItem(Base, TimestampMixin):
    """
    Item within a template defining a time slot.
    """
    
    __tablename__ = "template_items"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("templates.id"),
        nullable=False,
    )
    
    # Start time for this slot
    start_time: Mapped[time] = mapped_column(Integer, nullable=False)
    
    # Block reference (if using a block)
    block_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("blocks.id"),
        nullable=True,
    )
    
    # Or inline definition
    collection_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    collection_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Playback mode
    playback_order: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="chronological",
    )
    
    # Relationships
    template: Mapped["Template"] = relationship(
        "Template",
        back_populates="items",
    )
    
    def __repr__(self) -> str:
        return f"<TemplateItem at {self.start_time}>"
