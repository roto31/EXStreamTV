"""M3U stream discovery, testing, and curation"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

import httpx

from ..database.models import M3UStreamSource
from ..database.session import SessionLocal
from .m3u_importer import M3UEntry, M3UParser

logger = logging.getLogger(__name__)


class M3UStreamDiscoverer:
    """Discover M3U streams from various sources"""

    def __init__(self, db_session=None):
        self.db = db_session or SessionLocal()
        self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    async def discover_from_iptv_org(self) -> list[dict[str, Any]]:
        """
        Discover M3U streams from iptv-org API.

        Returns:
            List of discovered stream metadata
        """
        streams = []

        try:
            # iptv-org provides playlists by country
            # We'll fetch the main index
            url = "https://iptv-org.github.io/iptv/index.m3u"

            # Parse the M3U to get basic info
            entries = await M3UParser.parse_file(url)

            # Group by country/genre from metadata
            streams.append(
                {
                    "name": "iptv-org Global",
                    "url": url,
                    "description": "Global IPTV playlist from iptv-org",
                    "source_type": "curated",
                    "total_channels": len(entries),
                }
            )

        except Exception as e:
            logger.error(f"Error discovering from iptv-org: {e}", exc_info=True)

        return streams

    async def discover_from_github(self, query: str = "m3u playlist") -> list[dict[str, Any]]:
        """
        Search GitHub for M3U repositories.

        Args:
            query: Search query

        Returns:
            List of discovered stream metadata
        """
        streams = []

        try:
            # GitHub API search
            url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc"

            async with self._client.get(url) as response:
                if response.status_code == 200:
                    data = response.json()
                    for repo in data.get("items", [])[:10]:  # Top 10
                        # Look for M3U files in repository
                        # This is a simplified version - in production, you'd search the repo contents
                        streams.append(
                            {
                                "name": repo["name"],
                                "url": repo["html_url"],
                                "description": repo.get("description", ""),
                                "source_type": "dynamic",
                            }
                        )
        except Exception as e:
            logger.error(f"Error discovering from GitHub: {e}", exc_info=True)

        return streams

    async def discover_from_known_sources(self) -> list[dict[str, Any]]:
        """
        Discover from curated list of known reliable sources.

        Returns:
            List of known stream sources
        """
        # Known reliable M3U sources
        known_sources = [
            {
                "name": "iptv-org Global",
                "url": "https://iptv-org.github.io/iptv/index.m3u",
                "description": "Comprehensive global IPTV playlist",
                "country": None,
                "genre": "Mixed",
                "source_type": "curated",
            },
            {
                "name": "iptv-org Countries",
                "url": "https://iptv-org.github.io/iptv/countries/",
                "description": "Country-specific playlists",
                "country": None,
                "genre": "Mixed",
                "source_type": "curated",
            },
        ]

        return known_sources

    def categorize_stream(
        self, entry: M3UEntry, metadata: dict | None = None
    ) -> tuple[str | None, str | None]:
        """
        Extract country and genre from stream metadata.

        Args:
            entry: M3U entry
            metadata: Additional metadata from enrichment

        Returns:
            Tuple of (country, genre)
        """
        country = None
        genre = None

        # Try metadata first
        if metadata:
            country = metadata.get("country")
            categories = metadata.get("categories", [])
            if categories:
                genre = categories[0] if isinstance(categories, list) else str(categories)

        # Fall back to group-title
        if not genre and entry.group_title:
            genre = entry.group_title

        return country, genre

    async def close(self):
        """Close HTTP client"""
        await self._client.aclose()


class M3UStreamTester:
    """Test M3U stream reliability"""

    def __init__(self, db_session=None):
        self.db = db_session or SessionLocal()
        self._client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)

    async def test_stream(self, m3u_url: str, sample_size: int = 10) -> dict[str, Any]:
        """
        Test individual M3U stream for reliability.

        Args:
            m3u_url: URL to M3U file
            sample_size: Number of channels to test

        Returns:
            Test results dictionary
        """
        start_time = time.time()

        try:
            # Verify URL is reachable
            async with self._client.head(m3u_url) as response:
                if response.status_code >= 400:
                    return {
                        "success": False,
                        "error_message": f"HTTP {response.status_code}",
                        "reliability_percentage": 0,
                        "total_channels": 0,
                        "working_channels": 0,
                        "channels_tested": 0,
                        "test_duration": time.time() - start_time,
                    }

            # Parse M3U format
            entries = await M3UParser.parse_file(m3u_url)

            if not entries:
                return {
                    "success": False,
                    "error_message": "No channels found in M3U",
                    "reliability_percentage": 0,
                    "total_channels": 0,
                    "working_channels": 0,
                    "channels_tested": 0,
                    "test_duration": time.time() - start_time,
                }

            total_channels = len(entries)

            # Test sample channels
            sample_entries = entries[: min(sample_size, len(entries))]
            working_channels = 0
            channels_tested = len(sample_entries)

            for entry in sample_entries:
                if await self.validate_channel_stream(entry.url):
                    working_channels += 1

            # Calculate reliability
            reliability = (working_channels / channels_tested * 100) if channels_tested > 0 else 0

            return {
                "success": True,
                "reliability_percentage": round(reliability, 2),
                "total_channels": total_channels,
                "working_channels": working_channels,
                "channels_tested": channels_tested,
                "test_duration": round(time.time() - start_time, 2),
            }

        except Exception as e:
            logger.error(f"Error testing stream {m3u_url}: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e),
                "reliability_percentage": 0,
                "total_channels": 0,
                "working_channels": 0,
                "channels_tested": 0,
                "test_duration": time.time() - start_time,
            }

    async def validate_channel_stream(self, stream_url: str) -> bool:
        """
        Validate individual channel stream URL.

        Args:
            stream_url: Channel stream URL

        Returns:
            True if stream is accessible
        """
        try:
            # Try HEAD request first (faster)
            async with self._client.head(stream_url, timeout=5.0) as response:
                if response.status_code < 400:
                    return True

            # Fall back to GET with small timeout
            async with self._client.get(stream_url, timeout=5.0) as response:
                return response.status_code < 400

        except Exception:
            return False

    async def test_stream_batch(self, m3u_urls: list[str]) -> list[dict[str, Any]]:
        """
        Test multiple streams in parallel.

        Args:
            m3u_urls: List of M3U URLs to test

        Returns:
            List of test results
        """
        tasks = [self.test_stream(url) for url in m3u_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        return [
            result
            if isinstance(result, dict)
            else {"success": False, "error_message": str(result), "reliability_percentage": 0}
            for result in results
        ]

    async def close(self):
        """Close HTTP client"""
        await self._client.aclose()


class M3UStreamCurator:
    """Manage curated stream library"""

    def __init__(self, db_session=None):
        self.db = db_session or SessionLocal()

    def add_stream(
        self,
        name: str,
        url: str,
        description: str | None = None,
        country: str | None = None,
        genre: str | None = None,
        category: str | None = None,
        source_type: str = "curated",
    ) -> M3UStreamSource:
        """
        Add new stream to library.

        Args:
            name: Stream name
            url: Stream URL
            description: Description
            country: Country code
            genre: Genre
            category: Category
            source_type: Source type (curated/dynamic)

        Returns:
            Created M3UStreamSource
        """
        # Check if stream already exists
        existing = self.db.query(M3UStreamSource).filter(M3UStreamSource.url == url).first()
        if existing:
            # Update existing
            existing.name = name
            existing.description = description
            existing.country = country
            existing.genre = genre
            existing.category = category
            existing.is_active = True
            self.db.commit()
            return existing

        # Create new
        stream = M3UStreamSource(
            name=name,
            url=url,
            description=description,
            country=country,
            genre=genre,
            category=category,
            source_type=source_type,
            is_active=True,
        )

        self.db.add(stream)
        self.db.commit()
        self.db.refresh(stream)

        return stream

    def update_reliability(
        self, stream_id: int, reliability_score: float, total_channels: int, working_channels: int
    ) -> None:
        """
        Update reliability scores for a stream.

        Args:
            stream_id: Stream source ID
            reliability_score: Reliability percentage (0-100)
            total_channels: Total number of channels
            working_channels: Number of working channels
        """
        stream = self.db.query(M3UStreamSource).filter(M3UStreamSource.id == stream_id).first()
        if stream:
            stream.reliability_score = reliability_score
            stream.total_channels = total_channels
            stream.working_channels = working_channels
            stream.last_tested = datetime.utcnow()
            self.db.commit()

    def get_streams_by_country(self, country: str) -> list[M3UStreamSource]:
        """Get streams filtered by country"""
        return (
            self.db.query(M3UStreamSource)
            .filter(M3UStreamSource.country == country, M3UStreamSource.is_active)
            .all()
        )

    def get_streams_by_genre(self, genre: str) -> list[M3UStreamSource]:
        """Get streams filtered by genre"""
        return (
            self.db.query(M3UStreamSource)
            .filter(M3UStreamSource.genre == genre, M3UStreamSource.is_active)
            .all()
        )

    def get_reliable_streams(self, min_reliability: float = 70.0) -> list[M3UStreamSource]:
        """Get streams above reliability threshold"""
        return (
            self.db.query(M3UStreamSource)
            .filter(M3UStreamSource.reliability_score >= min_reliability, M3UStreamSource.is_active)
            .all()
        )

    def close(self):
        """Close database session"""
        if self.db:
            self.db.close()
