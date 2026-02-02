"""
Balance Scheduler for weighted content distribution.

Ported from Tunarr's balance scheduling with enhancements:
- Weight-based content distribution
- Cooldown periods to avoid repetition
- Distribution tracking and reporting

This enables fair distribution of content across multiple
collections based on configured weights.
"""

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ContentSource:
    """A content source with weight and cooldown settings."""
    
    source_id: str
    name: str
    collection_id: int
    
    # Weight (higher = more frequent)
    weight: float = 1.0
    
    # Cooldown settings
    cooldown_minutes: int = 0  # Minimum time between plays
    max_consecutive: int = 0  # Max items in a row (0 = unlimited)
    
    # State tracking
    last_played_at: Optional[datetime] = None
    consecutive_count: int = 0
    total_plays: int = 0
    
    @property
    def effective_weight(self) -> float:
        """Get effective weight considering cooldown."""
        if self.cooldown_minutes <= 0:
            return self.weight
        
        if self.last_played_at is None:
            return self.weight
        
        elapsed = (datetime.utcnow() - self.last_played_at).total_seconds() / 60
        
        if elapsed < self.cooldown_minutes:
            # Reduce weight during cooldown
            return self.weight * (elapsed / self.cooldown_minutes)
        
        return self.weight
    
    @property
    def is_on_cooldown(self) -> bool:
        """Check if source is on cooldown."""
        if self.cooldown_minutes <= 0:
            return False
        
        if self.last_played_at is None:
            return False
        
        elapsed = (datetime.utcnow() - self.last_played_at).total_seconds() / 60
        return elapsed < self.cooldown_minutes
    
    @property
    def at_consecutive_limit(self) -> bool:
        """Check if source is at consecutive limit."""
        if self.max_consecutive <= 0:
            return False
        return self.consecutive_count >= self.max_consecutive
    
    def record_play(self) -> None:
        """Record that content from this source was played."""
        self.last_played_at = datetime.utcnow()
        self.consecutive_count += 1
        self.total_plays += 1
    
    def reset_consecutive(self) -> None:
        """Reset consecutive count (when other source played)."""
        self.consecutive_count = 0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source_id": self.source_id,
            "name": self.name,
            "collection_id": self.collection_id,
            "weight": self.weight,
            "effective_weight": self.effective_weight,
            "cooldown_minutes": self.cooldown_minutes,
            "max_consecutive": self.max_consecutive,
            "is_on_cooldown": self.is_on_cooldown,
            "at_consecutive_limit": self.at_consecutive_limit,
            "consecutive_count": self.consecutive_count,
            "total_plays": self.total_plays,
            "last_played_at": self.last_played_at.isoformat() if self.last_played_at else None,
        }


@dataclass
class BalanceConfig:
    """Configuration for balance scheduling."""
    
    config_id: str
    name: str
    channel_id: int
    sources: list[ContentSource] = field(default_factory=list)
    
    # Balance settings
    use_effective_weights: bool = True  # Consider cooldowns
    allow_consecutive: bool = True  # Allow same source consecutively
    
    # Filler
    filler_collection_id: Optional[int] = None
    
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def total_weight(self) -> float:
        """Get total weight of all sources."""
        if self.use_effective_weights:
            return sum(s.effective_weight for s in self.sources if not s.at_consecutive_limit)
        return sum(s.weight for s in self.sources)
    
    def add_source(self, source: ContentSource) -> None:
        """Add a content source."""
        self.sources.append(source)
    
    def remove_source(self, source_id: str) -> bool:
        """Remove a content source."""
        for i, source in enumerate(self.sources):
            if source.source_id == source_id:
                del self.sources[i]
                return True
        return False
    
    def get_source(self, source_id: str) -> Optional[ContentSource]:
        """Get a content source by ID."""
        for source in self.sources:
            if source.source_id == source_id:
                return source
        return None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "config_id": self.config_id,
            "name": self.name,
            "channel_id": self.channel_id,
            "enabled": self.enabled,
            "sources": [s.to_dict() for s in self.sources],
            "total_weight": self.total_weight,
            "use_effective_weights": self.use_effective_weights,
            "allow_consecutive": self.allow_consecutive,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class BalanceStats:
    """Statistics for balance distribution."""
    
    total_selections: int = 0
    selections_by_source: dict[str, int] = field(default_factory=dict)
    target_distribution: dict[str, float] = field(default_factory=dict)
    actual_distribution: dict[str, float] = field(default_factory=dict)
    
    def record_selection(self, source_id: str) -> None:
        """Record a source selection."""
        self.total_selections += 1
        self.selections_by_source[source_id] = (
            self.selections_by_source.get(source_id, 0) + 1
        )
        
        # Recalculate distribution
        for sid, count in self.selections_by_source.items():
            self.actual_distribution[sid] = count / self.total_selections
    
    def calculate_imbalance(self) -> dict[str, float]:
        """Calculate imbalance (difference from target)."""
        return {
            sid: self.actual_distribution.get(sid, 0) - target
            for sid, target in self.target_distribution.items()
        }
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_selections": self.total_selections,
            "selections_by_source": self.selections_by_source,
            "target_distribution": self.target_distribution,
            "actual_distribution": self.actual_distribution,
            "imbalance": self.calculate_imbalance(),
        }


class BalanceScheduler:
    """
    Scheduler that balances content from multiple sources.
    
    Features:
    - Weighted random selection
    - Cooldown management
    - Consecutive limits
    - Distribution tracking
    
    Usage:
        scheduler = BalanceScheduler()
        scheduler.add_config(config)
        
        # Select next source
        source = scheduler.select_source(channel_id)
        
        # Get distribution stats
        stats = scheduler.get_stats(channel_id)
    """
    
    def __init__(self):
        """Initialize the scheduler."""
        self._configs: dict[int, BalanceConfig] = {}  # channel_id -> config
        self._stats: dict[int, BalanceStats] = {}  # channel_id -> stats
        self._last_source: dict[int, str] = {}  # channel_id -> last source_id
    
    def add_config(self, config: BalanceConfig) -> None:
        """
        Add or update a balance configuration.
        
        Args:
            config: BalanceConfig to add
        """
        self._configs[config.channel_id] = config
        
        # Initialize stats
        stats = BalanceStats()
        total_weight = config.total_weight
        
        if total_weight > 0:
            for source in config.sources:
                stats.target_distribution[source.source_id] = (
                    source.weight / total_weight
                )
        
        self._stats[config.channel_id] = stats
        
        logger.info(
            f"Added balance config '{config.name}' for channel {config.channel_id} "
            f"with {len(config.sources)} sources"
        )
    
    def get_config(self, channel_id: int) -> Optional[BalanceConfig]:
        """Get configuration for a channel."""
        return self._configs.get(channel_id)
    
    def remove_config(self, channel_id: int) -> bool:
        """Remove configuration for a channel."""
        if channel_id in self._configs:
            del self._configs[channel_id]
            if channel_id in self._stats:
                del self._stats[channel_id]
            return True
        return False
    
    def select_source(self, channel_id: int) -> Optional[ContentSource]:
        """
        Select the next content source based on weights.
        
        Uses weighted random selection with cooldown and
        consecutive limit considerations.
        
        Args:
            channel_id: Channel ID
            
        Returns:
            Selected ContentSource or None
        """
        config = self._configs.get(channel_id)
        if not config or not config.enabled or not config.sources:
            return None
        
        # Get eligible sources
        eligible = []
        
        for source in config.sources:
            # Skip if at consecutive limit
            if source.at_consecutive_limit:
                continue
            
            # Skip if same source and not allowed
            if not config.allow_consecutive:
                last = self._last_source.get(channel_id)
                if last == source.source_id:
                    continue
            
            # Get weight
            weight = (
                source.effective_weight
                if config.use_effective_weights
                else source.weight
            )
            
            if weight > 0:
                eligible.append((source, weight))
        
        if not eligible:
            # All sources at limit - reset and try again
            for source in config.sources:
                source.reset_consecutive()
            return self.select_source(channel_id)
        
        # Weighted random selection
        total_weight = sum(w for _, w in eligible)
        
        if total_weight <= 0:
            return eligible[0][0] if eligible else None
        
        rand = random.uniform(0, total_weight)
        cumulative = 0
        
        for source, weight in eligible:
            cumulative += weight
            if rand <= cumulative:
                # Selected this source
                self._record_selection(channel_id, source)
                return source
        
        # Fallback to last (shouldn't happen)
        return eligible[-1][0]
    
    def _record_selection(
        self,
        channel_id: int,
        source: ContentSource,
    ) -> None:
        """Record a source selection."""
        # Update source state
        source.record_play()
        
        # Reset other sources' consecutive counts
        config = self._configs.get(channel_id)
        if config:
            for other in config.sources:
                if other.source_id != source.source_id:
                    other.reset_consecutive()
        
        # Update stats
        stats = self._stats.get(channel_id)
        if stats:
            stats.record_selection(source.source_id)
        
        # Track last source
        self._last_source[channel_id] = source.source_id
    
    async def get_next_item(
        self,
        channel_id: int,
        get_media_items: Optional[callable] = None,
    ) -> Optional[tuple[int, ContentSource]]:
        """
        Get the next media item using balanced selection.
        
        Args:
            channel_id: Channel ID
            get_media_items: Async function to get media items for collection
            
        Returns:
            Tuple of (media_item_id, source) or None
        """
        source = self.select_source(channel_id)
        if not source:
            return None
        
        if get_media_items:
            items = await get_media_items(source.collection_id)
            if items:
                item_id = random.choice(items)
                return (item_id, source)
        
        return None
    
    def get_distribution(self, channel_id: int) -> dict[str, float]:
        """
        Get current distribution of plays.
        
        Args:
            channel_id: Channel ID
            
        Returns:
            Dictionary of source_id -> percentage
        """
        stats = self._stats.get(channel_id)
        if stats:
            return dict(stats.actual_distribution)
        return {}
    
    def get_stats(self, channel_id: int) -> Optional[BalanceStats]:
        """Get stats for a channel."""
        return self._stats.get(channel_id)
    
    def reset_stats(self, channel_id: int) -> None:
        """Reset stats for a channel."""
        if channel_id in self._stats:
            config = self._configs.get(channel_id)
            if config:
                stats = BalanceStats()
                total_weight = config.total_weight
                
                if total_weight > 0:
                    for source in config.sources:
                        stats.target_distribution[source.source_id] = (
                            source.weight / total_weight
                        )
                
                self._stats[channel_id] = stats
    
    def get_all_stats(self) -> dict[str, Any]:
        """Get statistics for all channels."""
        return {
            "configs_count": len(self._configs),
            "channels": {
                ch_id: {
                    "config": config.name,
                    "sources_count": len(config.sources),
                    "stats": self._stats.get(ch_id).to_dict() if ch_id in self._stats else None,
                }
                for ch_id, config in self._configs.items()
            },
        }


# Global scheduler instance
_balance_scheduler: Optional[BalanceScheduler] = None


def get_balance_scheduler() -> BalanceScheduler:
    """Get the global BalanceScheduler instance."""
    global _balance_scheduler
    if _balance_scheduler is None:
        _balance_scheduler = BalanceScheduler()
    return _balance_scheduler
