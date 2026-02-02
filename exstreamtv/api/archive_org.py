"""Archive.org API client for proper authentication and metadata fetching."""

import logging
from pathlib import Path
from typing import Any

import httpx

from ..constants import DEFAULT_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


class ArchiveOrgAPIClient:
    """Client for Archive.org API with authentication and metadata fetching."""

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        cookies_file: str | None = None,
        base_url: str = "https://archive.org",
    ) -> None:
        """Initialize Archive.org API client.

        Args:
            username: Archive.org username
            password: Archive.org password
            cookies_file: Path to cookies file (Netscape format)
            base_url: Base URL for Archive.org API
        """
        self.base_url = base_url
        self.api_url = f"{base_url}/metadata"
        self.username = username
        self.password = password
        self.cookies_file = cookies_file
        self._session_cookies: dict[str, str] | None = None
        self._authenticated = False

        # Load cookies from file if provided
        if cookies_file:
            self._load_cookies_from_file()

    def _load_cookies_from_file(self) -> None:
        """Load cookies from a Netscape-format cookies file."""
        try:
            cookies_path = Path(self.cookies_file)
            if not cookies_path.exists():
                logger.warning(f"Archive.org cookies file not found: {self.cookies_file}")
                return

            cookies = {}
            with open(cookies_path, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    # Netscape format: domain flag path secure expiration name value
                    parts = line.split("\t")
                    if len(parts) >= 7:
                        name = parts[5]
                        value = parts[6]
                        cookies[name] = value

            if cookies:
                self._session_cookies = cookies
                self._authenticated = True
                logger.info(f"Loaded {len(cookies)} cookies from {self.cookies_file}")
        except Exception as e:
            logger.exception(f"Error loading Archive.org cookies from file: {e}")

    async def _ensure_authenticated(self) -> httpx.AsyncClient:
        """Create an HTTP client configured for authenticated access (if possible)."""
        client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS * 3, follow_redirects=True)

        if self.cookies_file:
            # Reload cookies from file to ensure they're fresh
            self._load_cookies_from_file()

            if self._session_cookies:
                for name, value in self._session_cookies.items():
                    client.cookies.set(name, value)
                return client

        # Try programmatic login if credentials provided
        if self.username and self.password and not self._authenticated:
            if await self._login(client):
                return client

        return client

    async def _login(self, client: httpx.AsyncClient) -> bool:
        """Login to Archive.org programmatically"""
        try:
            login_url = f"{self.base_url}/account/login"

            # Get login page to get CSRF token
            login_page = await client.get(login_url)
            if login_page.status_code != 200:
                logger.error(f"Failed to get Archive.org login page: {login_page.status_code}")
                return False

            # Extract CSRF token if present
            csrf_token = None
            page_content = login_page.text
            # Look for CSRF token in various formats
            import re

            csrf_match = re.search(
                r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', page_content
            )
            if csrf_match:
                csrf_token = csrf_match.group(1)

            # Prepare login data
            login_data = {
                "username": self.username,
                "password": self.password,
            }
            if csrf_token:
                login_data["csrf_token"] = csrf_token

            # Submit login
            login_response = await client.post(login_url, data=login_data, follow_redirects=True)

            # Check if login was successful
            cookies = dict(login_response.cookies)
            if cookies:
                self._session_cookies = cookies
                self._authenticated = True
                logger.info("Successfully authenticated with Archive.org")
                return True

            return False
        except Exception as e:
            logger.exception(f"Error during Archive.org login: {e}")
            return False

    async def get_item_metadata(self, identifier: str) -> dict[str, Any] | None:
        """
        Get metadata for an Archive.org item

        Args:
            identifier: Archive.org item identifier

        Returns:
            Item metadata dictionary or None if not found
        """
        try:
            async with await self._ensure_authenticated() as client:
                metadata_url = f"{self.api_url}/{identifier}"
                response = await client.get(metadata_url)

                if response.status_code == 200:
                    return response.json()
                if response.status_code == 404:
                    logger.warning(f"Archive.org item not found: {identifier}")
                    return None

                logger.error(f"Failed to get metadata for {identifier}: {response.status_code}")
                return None
        except Exception as e:
            logger.exception(f"Error fetching metadata for {identifier}: {e}")
            return None

    async def search(
        self,
        query: str,
        collection: str | None = None,
        mediatype: str | None = None,
        rows: int = 50,
        page: int = 1,
    ) -> dict[str, Any]:
        """
        Search Archive.org items

        Args:
            query: Search query
            collection: Collection identifier to search within
            mediatype: Media type filter (e.g., "movies", "videos")
            rows: Number of results per page
            page: Page number

        Returns:
            Search results dictionary
        """
        try:
            async with await self._ensure_authenticated() as client:
                search_url = f"{self.base_url}/advancedsearch.php"
                params = {"q": query, "output": "json", "rows": rows, "page": page}

                if collection:
                    params["collection"] = collection
                if mediatype:
                    params["mediatype"] = mediatype

                response = await client.get(search_url, params=params)

                if response.status_code == 200:
                    return response.json()

                logger.error(f"Archive.org search failed: {response.status_code}")
                return {"response": {"docs": [], "numFound": 0}}
        except Exception as e:
            logger.exception(f"Error searching Archive.org: {e}")
            return {"response": {"docs": [], "numFound": 0}}

    async def browse_collection(self, collection_id: str, page: int = 1) -> dict[str, Any]:
        """
        Browse items in a collection

        Args:
            collection_id: Collection identifier
            page: Page number

        Returns:
            Collection items dictionary
        """
        try:
            # Use search API to browse collection
            return await self.search(
                query=f"collection:{collection_id}", collection=collection_id, page=page
            )
        except Exception as e:
            logger.exception(f"Error browsing collection {collection_id}: {e}")
            return {"response": {"docs": [], "numFound": 0}}

    async def get_item_files(self, identifier: str) -> list[dict[str, Any]]:
        """
        Get file list for an Archive.org item

        Args:
            identifier: Archive.org item identifier

        Returns:
            List of file metadata dictionaries
        """
        metadata = await self.get_item_metadata(identifier)
        if metadata and "files" in metadata:
            return metadata["files"]
        return []

    async def get_stream_url(
        self, identifier: str, filename: str | None = None, preferred_format: str = "h264"
    ) -> str | None:
        """
        Get streaming URL for an Archive.org item file

        Args:
            identifier: Archive.org item identifier
            filename: Specific filename to stream (optional)
            preferred_format: Preferred video format

        Returns:
            Stream URL or None if not found
        """
        try:
            files = await self.get_item_files(identifier)
            if not files:
                logger.warning(f"No files found for Archive.org item: {identifier}")
                return None

            # Filter video files
            video_files = [
                f
                for f in files
                if f.get("format") in ["h264", "MPEG4", "h.264"]
                or f.get("name", "").endswith((".mp4", ".mpeg", ".mov", ".avi"))
            ]

            if not video_files:
                logger.warning(f"No video files found for Archive.org item: {identifier}")
                return None

            # If filename specified, try to find exact match
            if filename:
                for file_info in video_files:
                    if file_info.get("name") == filename:
                        return f"{self.base_url}/download/{identifier}/{filename}"

            # Prefer specified format
            preferred_files = [
                f for f in video_files if preferred_format.lower() in f.get("format", "").lower()
            ]
            file_info = preferred_files[0] if preferred_files else video_files[0]

            file_name = file_info.get("name")
            if file_name:
                return f"{self.base_url}/download/{identifier}/{file_name}"

            return None
        except Exception as e:
            logger.exception(f"Error getting stream URL for {identifier}: {e}")
            return None
