"""M3U metadata enrichment using iptv-org API"""

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from .m3u_importer import M3UEntry

logger = logging.getLogger(__name__)

# iptv-org API base URL
IPTV_ORG_API_BASE = "https://iptv-org.github.io/api"


class M3UMetadataEnricher:
    """Fetch additional metadata from iptv-org API"""

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_expiry: dict[str, datetime] = {}
        self._cache_ttl = timedelta(hours=24)  # Cache for 24 hours

    async def _fetch_channels_data(self) -> dict[str, Any] | None:
        """Fetch channels data from iptv-org API"""
        try:
            url = f"{IPTV_ORG_API_BASE}/channels.json"
            response = await self._client.get(url)
            response.raise_for_status()
            channels = response.json()

            # Convert to dict keyed by channel ID for fast lookup
            channels_dict = {}
            for channel in channels:
                channel_id = channel.get("id")
                if channel_id:
                    channels_dict[channel_id] = channel

            return channels_dict
        except Exception as e:
            logger.warning(f"Could not fetch iptv-org channels data: {e}")
            return None

    async def _get_channel_metadata(self, tvg_id: str) -> dict[str, Any] | None:
        """Get metadata for a specific channel by tvg-id"""
        # Check cache first
        if tvg_id in self._cache:
            expiry = self._cache_expiry.get(tvg_id)
            if expiry and datetime.now() < expiry:
                return self._cache[tvg_id]

        try:
            # Fetch channels data (will be cached internally)
            channels_data = await self._fetch_channels_data()
            if not channels_data:
                return None

            # Look up channel
            channel_data = channels_data.get(tvg_id)
            if not channel_data:
                return None

            # Extract relevant metadata
            metadata = {
                "country": channel_data.get("country"),
                "categories": channel_data.get("categories", []),
                "name": channel_data.get("name"),
                "network": channel_data.get("network"),
                "language": channel_data.get("language"),
                "website": channel_data.get("website"),
                "is_nsfw": channel_data.get("is_nsfw", False),
                "launched": channel_data.get("launched"),
                "closed": channel_data.get("closed"),
            }

            # Cache the result
            self._cache[tvg_id] = metadata
            self._cache_expiry[tvg_id] = datetime.now() + self._cache_ttl

            return metadata
        except Exception as e:
            logger.debug(f"Error fetching metadata for {tvg_id}: {e}")
            return None

    async def enrich_entry(self, entry: "M3UEntry") -> "M3UEntry":
        """
        Enrich M3U entry with metadata from iptv-org API

        Args:
            entry: M3UEntry to enrich

        Returns:
            Enriched M3UEntry (same object, modified in place)
        """
        if not entry.tvg_id:
            return entry

        metadata = await self._get_channel_metadata(entry.tvg_id)
        if not metadata:
            return entry

        # Add metadata to extra_attrs if not already present
        if metadata.get("country") and "country" not in entry.extra_attrs:
            entry.extra_attrs["country"] = metadata["country"]

        if metadata.get("categories") and "categories" not in entry.extra_attrs:
            entry.extra_attrs["categories"] = ",".join(metadata["categories"])

        if metadata.get("network") and "network" not in entry.extra_attrs:
            entry.extra_attrs["network"] = metadata["network"]

        if metadata.get("language") and "language" not in entry.extra_attrs:
            entry.extra_attrs["language"] = metadata["language"]

        return entry

    async def enrich_entries(self, entries: list["M3UEntry"]) -> list["M3UEntry"]:
        """
        Enrich multiple M3U entries with metadata

        Args:
            entries: List of M3UEntry objects

        Returns:
            List of enriched M3UEntry objects
        """
        # Enrich entries that have tvg_id
        enriched = []
        for entry in entries:
            if entry.tvg_id:
                enriched_entry = await self.enrich_entry(entry)
                enriched.append(enriched_entry)
            else:
                enriched.append(entry)

        return enriched

    async def close(self):
        """Close HTTP client"""
        await self._client.aclose()
