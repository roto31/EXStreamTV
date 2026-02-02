"""
Collection Executor for AI Channel Creation

Persists CollectionConfig objects from BuildPlan to the database,
creating Collection entities that can be linked to Block schedules.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from exstreamtv.ai_agent.build_plan_generator import BuildPlan, CollectionConfig
from exstreamtv.ai_agent.source_selector import SourceType

logger = logging.getLogger(__name__)


@dataclass
class CollectionInfo:
    """Information about a created collection."""
    
    id: int
    name: str
    source_type: str
    item_count: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "source_type": self.source_type,
            "item_count": self.item_count,
        }


@dataclass
class CollectionExecutionResult:
    """Result of collection execution."""
    
    collections: list[CollectionInfo] = field(default_factory=list)
    name_to_id: dict[str, int] = field(default_factory=dict)
    
    @property
    def collection_count(self) -> int:
        return len(self.collections)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "collections": [c.to_dict() for c in self.collections],
            "collection_count": self.collection_count,
        }


class CollectionExecutor:
    """
    Executes AI-generated collection configurations into the database.
    
    Takes CollectionConfig objects from a BuildPlan and creates:
    - Collection entities (smart or static collections)
    - Search queries for smart collections
    - Returns a mapping of collection names to IDs for block linking
    """
    
    def __init__(self):
        """Initialize the collection executor."""
        logger.info("CollectionExecutor initialized")
    
    async def execute(
        self,
        plan: BuildPlan,
        db: AsyncSession,
    ) -> CollectionExecutionResult:
        """
        Execute collection creation from a build plan.
        
        Args:
            plan: The BuildPlan containing collection configurations
            db: Database session
            
        Returns:
            CollectionExecutionResult with created collections and name->id mapping
        """
        from exstreamtv.database.models import Collection
        from exstreamtv.database.models.media import CollectionTypeEnum
        
        if not plan.collections:
            logger.warning("No collections in plan, returning empty result")
            return CollectionExecutionResult()
        
        created_collections: list[CollectionInfo] = []
        name_to_id: dict[str, int] = {}
        
        for config in plan.collections:
            try:
                # Check if collection with same name already exists
                existing = await self._find_existing_collection(config.name, db)
                
                if existing:
                    logger.info(f"Using existing collection '{config.name}' (id={existing.id})")
                    name_to_id[config.name] = existing.id
                    created_collections.append(CollectionInfo(
                        id=existing.id,
                        name=existing.name,
                        source_type=config.source_type.value if isinstance(config.source_type, SourceType) else str(config.source_type),
                        item_count=0,
                    ))
                    continue
                
                # Build search query from config
                search_query = self._build_search_query(config)
                
                # Determine collection type (store as string value)
                collection_type = CollectionTypeEnum.SMART if search_query else CollectionTypeEnum.STATIC
                
                # Create collection (Collection is an alias for Playlist)
                # collection_type is stored as string, not enum
                collection = Collection(
                    name=config.name,
                    description=self._build_description(config),
                    collection_type=collection_type.value,
                    search_query=search_query,
                )
                
                db.add(collection)
                await db.flush()
                
                name_to_id[config.name] = collection.id
                
                created_collections.append(CollectionInfo(
                    id=collection.id,
                    name=collection.name,
                    source_type=config.source_type.value if isinstance(config.source_type, SourceType) else str(config.source_type),
                    item_count=0,
                ))
                
                logger.info(f"Created collection '{config.name}' (id={collection.id}, type={collection_type.value})")
                
            except Exception as e:
                logger.exception(f"Error creating collection '{config.name}': {e}")
        
        return CollectionExecutionResult(
            collections=created_collections,
            name_to_id=name_to_id,
        )
    
    async def _find_existing_collection(
        self,
        name: str,
        db: AsyncSession,
    ):
        """Find an existing collection by name."""
        from exstreamtv.database.models import Collection
        
        stmt = select(Collection).where(Collection.name == name)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    def _build_search_query(self, config: CollectionConfig) -> str | None:
        """
        Build a search query string from collection config.
        
        Creates a query that can be used by smart collections
        to dynamically find matching content.
        """
        parts = []
        
        # Add genres
        if config.genres:
            genre_str = ",".join(config.genres)
            parts.append(f"genres:{genre_str}")
        
        # Add year range
        if config.year_min or config.year_max:
            year_min = config.year_min or 1900
            year_max = config.year_max or 2030
            parts.append(f"year:{year_min}-{year_max}")
        
        # Add keywords
        if config.keywords:
            keywords_str = ",".join(config.keywords)
            parts.append(f"keywords:{keywords_str}")
        
        # Add source type
        if config.source_type:
            source_str = config.source_type.value if isinstance(config.source_type, SourceType) else str(config.source_type)
            parts.append(f"source:{source_str}")
        
        # Add content type
        if config.content_type:
            parts.append(f"type:{config.content_type}")
        
        # Add Archive.org collection if specified
        if config.archive_collection:
            parts.append(f"archive_collection:{config.archive_collection}")
        
        # Add Plex library if specified
        if config.plex_library:
            parts.append(f"plex_library:{config.plex_library}")
        
        return " AND ".join(parts) if parts else None
    
    def _build_description(self, config: CollectionConfig) -> str:
        """Build a human-readable description from collection config."""
        parts = [f"AI-generated collection from {config.source_name}"]
        
        if config.genres:
            parts.append(f"Genres: {', '.join(config.genres)}")
        
        if config.year_min or config.year_max:
            year_range = f"{config.year_min or '?'}-{config.year_max or '?'}"
            parts.append(f"Years: {year_range}")
        
        if config.content_type:
            parts.append(f"Type: {config.content_type}")
        
        return ". ".join(parts)
    
    async def populate_collection(
        self,
        collection_id: int,
        config: CollectionConfig,
        db: AsyncSession,
    ) -> int:
        """
        Populate a collection with media items based on config.
        
        This is an optional step that can be called after collection creation
        to actually add media items to the collection.
        
        Args:
            collection_id: Database collection ID
            config: Collection configuration
            db: Database session
            
        Returns:
            Number of items added
        """
        from exstreamtv.database.models import MediaItem, CollectionItem
        
        items_added = 0
        
        try:
            # Build query based on config
            stmt = select(MediaItem)
            conditions = []
            
            # Filter by source
            if config.source_type:
                source_str = config.source_type.value if isinstance(config.source_type, SourceType) else str(config.source_type)
                conditions.append(MediaItem.source == source_str)
            
            # Filter by year range
            if config.year_min:
                conditions.append(MediaItem.year >= config.year_min)
            if config.year_max:
                conditions.append(MediaItem.year <= config.year_max)
            
            # Filter by content type
            if config.content_type:
                conditions.append(MediaItem.media_type == config.content_type)
            
            if conditions:
                stmt = stmt.where(*conditions)
            
            stmt = stmt.limit(500)  # Limit for safety
            
            result = await db.execute(stmt)
            media_items = result.scalars().all()
            
            # Add items to collection (CollectionItem is alias for PlaylistItem)
            for idx, item in enumerate(media_items):
                collection_item = CollectionItem(
                    playlist_id=collection_id,  # Uses playlist_id (Collection = Playlist)
                    media_item_id=item.id,
                    title=item.title or f"Item {idx + 1}",
                    position=idx + 1,  # 1-based position
                    duration_seconds=item.duration_seconds if hasattr(item, 'duration_seconds') else None,
                )
                db.add(collection_item)
                items_added += 1
            
            await db.flush()
            
            logger.info(f"Added {items_added} items to collection {collection_id}")
            
        except Exception as e:
            logger.exception(f"Error populating collection {collection_id}: {e}")
        
        return items_added
