"""
Media Source Aggregator for AI Channel Creation

Provides a unified interface to query all media sources (Plex, Archive.org, YouTube)
and build collections from query results.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MediaQueryResult:
    """Result from a media query."""
    
    source: str  # "plex", "archive_org", "youtube"
    items: list[dict[str, Any]] = field(default_factory=list)
    total_count: int = 0
    query: str = ""
    filters: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    
    @property
    def success(self) -> bool:
        return self.error is None


@dataclass
class MediaSourceInfo:
    """Information about an available media source."""
    
    source: str
    name: str
    available: bool = True
    libraries: list[dict[str, Any]] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    years: list[int] = field(default_factory=list)
    item_count: int = 0
    error: str | None = None


class MediaAggregator:
    """
    Unified interface for querying multiple media sources.
    
    Aggregates results from Plex, Archive.org, and YouTube to support
    AI-powered channel creation with mixed content sources.
    """
    
    def __init__(
        self,
        plex_client: Any | None = None,
        archive_org_client: Any | None = None,
        youtube_client: Any | None = None,
        db_session: Any | None = None,
    ):
        """
        Initialize media aggregator.
        
        Args:
            plex_client: PlexMediaSource instance
            archive_org_client: ArchiveOrgAPIClient instance
            youtube_client: YouTube client (future)
            db_session: Database session for querying local media
        """
        self.plex_client = plex_client
        self.archive_org_client = archive_org_client
        self.youtube_client = youtube_client
        self.db_session = db_session
        
        # Cache for source info
        self._source_cache: dict[str, MediaSourceInfo] = {}
        self._cache_expires_at: datetime | None = None
    
    async def get_available_sources(self, force_refresh: bool = False) -> dict[str, Any]:
        """
        Get information about all available media sources.
        
        Args:
            force_refresh: Force refresh of cached data
            
        Returns:
            Dict with source information
        """
        # Check cache
        if not force_refresh and self._cache_expires_at:
            if datetime.utcnow() < self._cache_expires_at:
                return self._format_source_info()
        
        sources = {}
        
        # Query Plex
        if self.plex_client:
            try:
                plex_info = await self._get_plex_info()
                sources["plex"] = plex_info
                self._source_cache["plex"] = plex_info
            except Exception as e:
                logger.exception(f"Error getting Plex info: {e}")
                sources["plex"] = MediaSourceInfo(
                    source="plex",
                    name="Plex",
                    available=False,
                    error=str(e),
                )
        
        # Archive.org is always available (public)
        sources["archive_org"] = MediaSourceInfo(
            source="archive_org",
            name="Archive.org",
            available=True,
            genres=["classic_tv", "commercials", "movies", "documentaries", "animation"],
        )
        self._source_cache["archive_org"] = sources["archive_org"]
        
        # YouTube (future)
        if self.youtube_client:
            sources["youtube"] = MediaSourceInfo(
                source="youtube",
                name="YouTube",
                available=True,
            )
            self._source_cache["youtube"] = sources["youtube"]
        
        # Also query local database for existing media
        if self.db_session:
            try:
                local_info = await self._get_local_media_info()
                sources["local"] = local_info
                self._source_cache["local"] = local_info
            except Exception as e:
                logger.warning(f"Error getting local media info: {e}")
        
        # Update cache expiration (5 minutes)
        from datetime import timedelta
        self._cache_expires_at = datetime.utcnow() + timedelta(minutes=5)
        
        return self._format_source_info()
    
    def _format_source_info(self) -> dict[str, Any]:
        """Format cached source info for API response."""
        result = {}
        
        for source, info in self._source_cache.items():
            result[source] = {
                "name": info.name,
                "available": info.available,
                "libraries": info.libraries,
                "genres": info.genres,
                "years": info.years,
                "item_count": info.item_count,
                "error": info.error,
            }
        
        return result
    
    async def _get_plex_info(self) -> MediaSourceInfo:
        """Get Plex library information."""
        if not self.plex_client:
            return MediaSourceInfo(
                source="plex",
                name="Plex",
                available=False,
                error="Plex client not configured",
            )
        
        # Connect if needed
        if not self.plex_client.is_connected:
            await self.plex_client.connect()
        
        # Get libraries
        libraries = await self.plex_client.get_libraries()
        
        library_info = []
        all_genres: set[str] = set()
        all_years: set[int] = set()
        total_items = 0
        
        for lib in libraries:
            lib_dict = {
                "id": lib.id,
                "name": lib.name,
                "type": lib.type,
                "item_count": lib.item_count or 0,
            }
            library_info.append(lib_dict)
            total_items += lib.item_count or 0
            
            # Get genres and years from metadata if available
            if hasattr(lib, "metadata") and lib.metadata:
                if "genres" in lib.metadata:
                    all_genres.update(lib.metadata["genres"])
        
        return MediaSourceInfo(
            source="plex",
            name=self.plex_client._server_name or "Plex",
            available=True,
            libraries=library_info,
            genres=sorted(list(all_genres)),
            years=sorted(list(all_years)),
            item_count=total_items,
        )
    
    async def _get_local_media_info(self) -> MediaSourceInfo:
        """Get local database media information."""
        from sqlalchemy import select, func, distinct
        from exstreamtv.database.models import MediaItem
        
        # Get count
        stmt = select(func.count(MediaItem.id))
        result = await self.db_session.execute(stmt)
        total_count = result.scalar() or 0
        
        # Get distinct years
        stmt = select(distinct(MediaItem.year)).where(MediaItem.year.isnot(None))
        result = await self.db_session.execute(stmt)
        years = [row[0] for row in result.all() if row[0]]
        
        # Get sources breakdown
        stmt = select(
            MediaItem.source,
            func.count(MediaItem.id).label("count")
        ).group_by(MediaItem.source)
        result = await self.db_session.execute(stmt)
        sources = {str(row[0]): row[1] for row in result.all()}
        
        return MediaSourceInfo(
            source="local",
            name="Local Database",
            available=True,
            years=sorted(years),
            item_count=total_count,
            libraries=[
                {"name": source, "item_count": count}
                for source, count in sources.items()
            ],
        )
    
    async def search(
        self,
        query: str | None = None,
        sources: list[str] | None = None,
        genres: list[str] | None = None,
        year_start: int | None = None,
        year_end: int | None = None,
        media_type: str | None = None,
        limit: int = 50,
    ) -> dict[str, MediaQueryResult]:
        """
        Search across multiple media sources.
        
        Args:
            query: Search query string
            sources: List of sources to search (default: all)
            genres: Filter by genres
            year_start: Minimum year
            year_end: Maximum year
            media_type: Filter by type (movie, episode, etc.)
            limit: Maximum results per source
            
        Returns:
            Dict of source -> MediaQueryResult
        """
        if sources is None:
            sources = ["plex", "archive_org"]
        
        results = {}
        
        # Search each source in parallel
        import asyncio
        
        tasks = []
        source_names = []
        
        if "plex" in sources and self.plex_client:
            tasks.append(self._search_plex(
                query=query,
                genres=genres,
                year_start=year_start,
                year_end=year_end,
                media_type=media_type,
                limit=limit,
            ))
            source_names.append("plex")
        
        if "archive_org" in sources and self.archive_org_client:
            tasks.append(self._search_archive_org(
                query=query,
                genres=genres,
                year_start=year_start,
                year_end=year_end,
                limit=limit,
            ))
            source_names.append("archive_org")
        
        if "local" in sources and self.db_session:
            tasks.append(self._search_local(
                query=query,
                genres=genres,
                year_start=year_start,
                year_end=year_end,
                media_type=media_type,
                limit=limit,
            ))
            source_names.append("local")
        
        if tasks:
            search_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for source, result in zip(source_names, search_results):
                if isinstance(result, Exception):
                    results[source] = MediaQueryResult(
                        source=source,
                        error=str(result),
                    )
                else:
                    results[source] = result
        
        return results
    
    async def _search_plex(
        self,
        query: str | None = None,
        genres: list[str] | None = None,
        year_start: int | None = None,
        year_end: int | None = None,
        media_type: str | None = None,
        limit: int = 50,
    ) -> MediaQueryResult:
        """Search Plex library."""
        if not self.plex_client:
            return MediaQueryResult(
                source="plex",
                error="Plex client not available",
            )
        
        try:
            # Get all libraries
            libraries = await self.plex_client.get_libraries()
            
            all_items = []
            
            for lib in libraries:
                # Scan library if needed
                items = await self.plex_client.scan_library(lib.id)
                
                for item in items:
                    # Apply filters
                    if media_type and item.type != media_type:
                        continue
                    
                    if year_start and (item.year or 0) < year_start:
                        continue
                    
                    if year_end and (item.year or 9999) > year_end:
                        continue
                    
                    if query and query.lower() not in (item.title or "").lower():
                        continue
                    
                    if genres:
                        item_genres = getattr(item, "genres", []) or []
                        if not any(g.lower() in [ig.lower() for ig in item_genres] for g in genres):
                            continue
                    
                    all_items.append({
                        "id": item.id,
                        "title": item.title,
                        "type": item.type,
                        "year": item.year,
                        "duration_ms": item.duration_ms,
                        "thumbnail_url": item.thumbnail_url,
                        "source": "plex",
                        "show_title": item.show_title,
                        "season_number": item.season_number,
                        "episode_number": item.episode_number,
                    })
                    
                    if len(all_items) >= limit:
                        break
                
                if len(all_items) >= limit:
                    break
            
            return MediaQueryResult(
                source="plex",
                items=all_items[:limit],
                total_count=len(all_items),
                query=query or "",
                filters={
                    "genres": genres,
                    "year_start": year_start,
                    "year_end": year_end,
                    "media_type": media_type,
                },
            )
            
        except Exception as e:
            logger.exception(f"Error searching Plex: {e}")
            return MediaQueryResult(
                source="plex",
                error=str(e),
            )
    
    async def _search_archive_org(
        self,
        query: str | None = None,
        genres: list[str] | None = None,
        year_start: int | None = None,
        year_end: int | None = None,
        limit: int = 50,
    ) -> MediaQueryResult:
        """Search Archive.org."""
        if not self.archive_org_client:
            return MediaQueryResult(
                source="archive_org",
                error="Archive.org client not available",
            )
        
        try:
            # Build search query
            search_parts = []
            
            if query:
                search_parts.append(query)
            
            if year_start and year_end:
                search_parts.append(f"date:[{year_start} TO {year_end}]")
            elif year_start:
                search_parts.append(f"date:[{year_start} TO *]")
            elif year_end:
                search_parts.append(f"date:[* TO {year_end}]")
            
            # Map genres to collections
            if genres:
                collection_map = {
                    "commercials": "prelinger",
                    "classic_tv": "classic_tv",
                    "animation": "classic_cartoons",
                    "movies": "feature_films",
                    "documentaries": "documentaries",
                }
                for genre in genres:
                    if genre.lower() in collection_map:
                        search_parts.append(f"collection:{collection_map[genre.lower()]}")
            
            search_query = " AND ".join(search_parts) if search_parts else "mediatype:movies"
            
            # Search Archive.org
            result = await self.archive_org_client.search(
                query=search_query,
                mediatype="movies",
                rows=limit,
            )
            
            items = []
            docs = result.get("response", {}).get("docs", [])
            
            for doc in docs:
                items.append({
                    "id": doc.get("identifier"),
                    "title": doc.get("title", "Unknown"),
                    "type": "video",
                    "year": doc.get("year"),
                    "description": doc.get("description"),
                    "source": "archive_org",
                    "collection": doc.get("collection"),
                    "url": f"https://archive.org/details/{doc.get('identifier')}",
                })
            
            return MediaQueryResult(
                source="archive_org",
                items=items,
                total_count=result.get("response", {}).get("numFound", 0),
                query=search_query,
                filters={
                    "genres": genres,
                    "year_start": year_start,
                    "year_end": year_end,
                },
            )
            
        except Exception as e:
            logger.exception(f"Error searching Archive.org: {e}")
            return MediaQueryResult(
                source="archive_org",
                error=str(e),
            )
    
    async def _search_local(
        self,
        query: str | None = None,
        genres: list[str] | None = None,
        year_start: int | None = None,
        year_end: int | None = None,
        media_type: str | None = None,
        limit: int = 50,
    ) -> MediaQueryResult:
        """Search local database."""
        try:
            from sqlalchemy import select, or_
            from exstreamtv.database.models import MediaItem
            
            stmt = select(MediaItem)
            conditions = []
            
            if query:
                search_term = f"%{query}%"
                conditions.append(or_(
                    MediaItem.title.ilike(search_term),
                    MediaItem.description.ilike(search_term),
                    MediaItem.show_title.ilike(search_term),
                ))
            
            if media_type:
                conditions.append(MediaItem.media_type == media_type)
            
            if year_start:
                conditions.append(MediaItem.year >= year_start)
            
            if year_end:
                conditions.append(MediaItem.year <= year_end)
            
            if genres:
                # Genres are stored as JSON array or comma-separated
                for genre in genres:
                    conditions.append(MediaItem.genres.ilike(f"%{genre}%"))
            
            if conditions:
                stmt = stmt.where(*conditions)
            
            stmt = stmt.limit(limit)
            result = await self.db_session.execute(stmt)
            media_items = result.scalars().all()
            
            items = []
            for item in media_items:
                items.append({
                    "id": item.id,
                    "title": item.title,
                    "type": item.media_type,
                    "year": item.year,
                    "duration": item.duration,
                    "thumbnail": item.thumbnail,
                    "source": str(item.source),
                    "show_title": item.show_title,
                    "season_number": item.season_number,
                    "episode_number": item.episode_number,
                })
            
            return MediaQueryResult(
                source="local",
                items=items,
                total_count=len(items),
                query=query or "",
                filters={
                    "genres": genres,
                    "year_start": year_start,
                    "year_end": year_end,
                    "media_type": media_type,
                },
            )
            
        except Exception as e:
            logger.exception(f"Error searching local database: {e}")
            return MediaQueryResult(
                source="local",
                error=str(e),
            )
    
    async def get_commercials(
        self,
        era_start: int | None = None,
        era_end: int | None = None,
        limit: int = 100,
    ) -> MediaQueryResult:
        """
        Get period-appropriate commercials from Archive.org.
        
        Args:
            era_start: Start year for commercials
            era_end: End year for commercials
            limit: Maximum results
            
        Returns:
            MediaQueryResult with commercial items
        """
        if not self.archive_org_client:
            return MediaQueryResult(
                source="archive_org",
                error="Archive.org client not available",
            )
        
        # Use the Prelinger collection for vintage commercials
        return await self._search_archive_org(
            query="commercials OR advertisements OR commercial",
            genres=["commercials"],
            year_start=era_start,
            year_end=era_end,
            limit=limit,
        )
    
    async def build_collection(
        self,
        name: str,
        source: str,
        filters: dict[str, Any],
        db_session: Any,
    ) -> int | None:
        """
        Build a collection from search results.
        
        Args:
            name: Collection name
            source: Source to search
            filters: Search filters
            db_session: Database session
            
        Returns:
            Created collection ID or None
        """
        try:
            from exstreamtv.database.models import Collection, CollectionItem, MediaItem
            from exstreamtv.database.models.media import CollectionTypeEnum
            
            # Search for matching content
            results = await self.search(
                sources=[source],
                **filters,
            )
            
            source_result = results.get(source)
            if not source_result or not source_result.success:
                logger.warning(f"No results from {source} for collection {name}")
                return None
            
            # Create collection
            collection = Collection(
                name=name,
                description=f"AI-generated collection from {source}",
                collection_type=CollectionTypeEnum.SMART,
                search_query=str(filters),
            )
            db_session.add(collection)
            await db_session.flush()
            
            # Add items to collection
            for idx, item in enumerate(source_result.items):
                # First ensure media item exists in database
                existing = await db_session.execute(
                    select(MediaItem).where(
                        MediaItem.source_id == str(item.get("id")),
                        MediaItem.source == source,
                    )
                )
                media_item = existing.scalar_one_or_none()
                
                if not media_item:
                    # Create media item
                    media_item = MediaItem(
                        source=source,
                        source_id=str(item.get("id")),
                        title=item.get("title", "Unknown"),
                        url=item.get("url", ""),
                        duration=item.get("duration"),
                        thumbnail=item.get("thumbnail"),
                        year=item.get("year"),
                        media_type=item.get("type"),
                        show_title=item.get("show_title"),
                        season_number=item.get("season_number"),
                        episode_number=item.get("episode_number"),
                    )
                    db_session.add(media_item)
                    await db_session.flush()
                
                # Add to collection
                collection_item = CollectionItem(
                    collection_id=collection.id,
                    media_item_id=media_item.id,
                    order=idx,
                )
                db_session.add(collection_item)
            
            await db_session.commit()
            
            logger.info(f"Created collection '{name}' with {len(source_result.items)} items")
            return collection.id
            
        except Exception as e:
            logger.exception(f"Error building collection: {e}")
            await db_session.rollback()
            return None
