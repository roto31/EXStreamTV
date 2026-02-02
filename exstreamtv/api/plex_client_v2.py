"""Plex API client v2 - Proper authentication, library browsing, and EPG generation"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any

import httpx

from ..config import config
from ..constants import DEFAULT_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


class PlexClientV2:
    """
    Plex API client v2 - Proper authentication and library browsing

    Reference: Plex Media Server API documentation
    """

    def __init__(self, base_url: str | None = None, token: str | None = None):
        """
        Initialize Plex client v2

        Args:
            base_url: Plex Media Server base URL
            token: Plex authentication token
        """
        self.base_url = (
            (base_url or config.plex.base_url).rstrip("/")
            if base_url or (hasattr(config, "plex") and config.plex.base_url)
            else None
        )
        self.token = token or (config.plex.token if hasattr(config, "plex") else None)

        if not self.base_url:
            raise ValueError("Plex base_url is required")
        if not self.token:
            raise ValueError("Plex token is required")

        self._http_client: httpx.AsyncClient = httpx.AsyncClient(
            timeout=httpx.Timeout(DEFAULT_TIMEOUT_SECONDS * 6), follow_redirects=True
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._http_client.aclose()

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with authentication"""
        return {
            "Accept": "application/json",
            "X-Plex-Product": "StreamTV",
            "X-Plex-Version": "2.0.0",
            "X-Plex-Client-Identifier": "streamtv-plex-client-v2",
            "X-Plex-Token": self.token,
        }

    async def get_libraries(self) -> list[dict[str, Any]]:
        """Get all libraries from Plex server"""
        try:
            url = f"{self.base_url}/library/sections"
            headers = self._get_headers()

            response = await self._http_client.get(url, headers=headers)
            response.raise_for_status()

            # Plex returns XML by default
            if response.headers.get("content-type", "").startswith("application/json"):
                data = response.json()
                return data.get("MediaContainer", {}).get("Directory", [])
            else:
                # Parse XML
                root = ET.fromstring(response.text)
                libraries = []
                for directory in root.findall("Directory"):
                    libraries.append(
                        {
                            "key": directory.get("key"),
                            "type": directory.get("type"),
                            "title": directory.get("title"),
                        }
                    )
                return libraries

        except Exception as e:
            logger.exception(f"Error getting Plex libraries: {e}")
            return []

    async def get_library_items(
        self, library_key: str, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Get items from a library"""
        try:
            url = f"{self.base_url}/library/sections/{library_key}/all"
            params = {}
            if limit:
                params["X-Plex-Container-Size"] = str(limit)

            headers = self._get_headers()
            response = await self._http_client.get(url, params=params, headers=headers)
            response.raise_for_status()

            # Parse response (XML or JSON)
            if response.headers.get("content-type", "").startswith("application/json"):
                data = response.json()
                return data.get("MediaContainer", {}).get("Metadata", [])
            else:
                root = ET.fromstring(response.text)
                items = []
                for metadata in (
                    root.findall("Video") + root.findall("Movie") + root.findall("Episode")
                ):
                    items.append(
                        {
                            "ratingKey": metadata.get("ratingKey"),
                            "title": metadata.get("title"),
                            "type": metadata.tag.lower(),
                        }
                    )
                return items

        except Exception as e:
            logger.exception(f"Error getting Plex library items: {e}")
            return []

    async def generate_epg_data(
        self,
        channels: list[dict[str, Any]],
        start_time: datetime | None = None,
        duration_hours: int = 24,
    ) -> dict[str, Any]:
        """
        Generate EPG data from Plex library items

        Args:
            channels: List of channels with Plex library mappings
            start_time: Start time for EPG
            duration_hours: Duration in hours

        Returns:
            EPG data structure
        """
        start_time = start_time or datetime.utcnow()
        epg_data = {
            "channels": [],
            "programs": [],
        }

        # Get libraries
        await self.get_libraries()

        for channel in channels:
            library_key = channel.get("plex_library_key")
            if not library_key:
                continue

            # Get library items
            items = await self.get_library_items(library_key)

            # Create EPG entries
            current_time = start_time
            for item in items:
                duration = int(item.get("duration", 0)) // 1000 if item.get("duration") else 3600

                epg_data["programs"].append(
                    {
                        "channel": channel.get("number"),
                        "start": current_time,
                        "stop": current_time + timedelta(seconds=duration),
                        "title": item.get("title", ""),
                        "description": item.get("summary", ""),
                    }
                )

                current_time += timedelta(seconds=duration)

        return epg_data
