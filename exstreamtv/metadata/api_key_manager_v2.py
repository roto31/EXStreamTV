"""API key management system v2 - Centralized API key management with validation, token refresh, and rate limiting"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any

import httpx

from ..config import config
from ..database.models_v2 import APIKeyToken
from ..database.session import SessionLocal

logger = logging.getLogger(__name__)


class APIKeyManagerV2:
    """Centralized API key management for all metadata sources"""

    def __init__(self, db_session=None):
        """
        Initialize API key manager

        Args:
            db_session: Optional database session (creates new if not provided)
        """
        self.db = db_session or SessionLocal()
        self._http_client = httpx.AsyncClient(timeout=30.0)

        # Rate limiting state per service
        self._rate_limits: dict[str, dict[str, Any]] = {}

        # Load API keys from config
        self._load_api_keys()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._http_client.aclose()
        if not hasattr(self, "_db_provided") or not self._db_provided:
            self.db.close()

    def _load_api_keys(self):
        """Load API keys from config and environment variables"""
        self.tvdb_api_key = config.metadata.tvdb_api_key or os.getenv(
            "STREAMTV_METADATA_TVDB_API_KEY"
        )
        self.tvdb_pin = config.metadata.tvdb_pin or os.getenv("STREAMTV_METADATA_TVDB_PIN")
        self.tmdb_api_key = config.metadata.tmdb_api_key or os.getenv(
            "STREAMTV_METADATA_TMDB_API_KEY"
        )
        self.omdb_api_key = config.metadata.omdb_api_key or os.getenv(
            "STREAMTV_METADATA_OMDB_API_KEY"
        )
        self.fanart_api_key = config.metadata.fanart_api_key or os.getenv(
            "STREAMTV_METADATA_FANART_API_KEY"
        )
        self.musicbrainz_user_agent = config.metadata.musicbrainz_user_agent or os.getenv(
            "STREAMTV_METADATA_MUSICBRAINZ_USER_AGENT"
        )

    async def validate_api_key(self, service: str, api_key: str | None = None) -> bool:
        """
        Validate API key for a service

        Args:
            service: Service name ("tvdb", "tmdb", "omdb", "fanart")
            api_key: Optional API key (uses configured key if not provided)

        Returns:
            True if valid, False otherwise
        """
        if service == "tvdb":
            key = api_key or self.tvdb_api_key
            if not key:
                return False
            # TVDB validation requires login (API key + PIN)
            return await self._validate_tvdb_key(key)

        elif service == "tmdb":
            key = api_key or self.tmdb_api_key
            if not key:
                return False
            return await self._validate_tmdb_key(key)

        elif service == "omdb":
            key = api_key or self.omdb_api_key
            if not key:
                return False
            return await self._validate_omdb_key(key)

        elif service == "fanart":
            key = api_key or self.fanart_api_key
            if not key:
                return False
            return await self._validate_fanart_key(key)

        return False

    async def _validate_tvdb_key(self, api_key: str) -> bool:
        """Validate TVDB API key (requires PIN for full validation)"""
        try:
            # TVDB v4 requires login to get read token
            # For validation, we can check if API key format is valid
            # Full validation requires PIN
            if not api_key or len(api_key) < 10:
                return False

            # If PIN is available, try login
            if self.tvdb_pin:
                token = await self.get_tvdb_token(api_key, self.tvdb_pin)
                return token is not None

            return True  # Assume valid if format looks correct
        except Exception as e:
            logger.exception(f"TVDB API key validation failed: {e}")
            return False

    async def _validate_tmdb_key(self, api_key: str) -> bool:
        """Validate TMDB API key"""
        try:
            url = "https://api.themoviedb.org/3/configuration"
            params = {"api_key": api_key}

            response = await self._http_client.get(url, params=params)
            return response.status_code == 200
        except Exception as e:
            logger.exception(f"TMDB API key validation failed: {e}")
            return False

    async def _validate_omdb_key(self, api_key: str) -> bool:
        """Validate OMDb API key"""
        try:
            url = "http://www.omdbapi.com/"
            params = {"apikey": api_key, "t": "test"}

            response = await self._http_client.get(url, params=params)
            data = response.json()
            # OMDb returns error if key is invalid, success if valid
            return "Error" not in data or "Invalid API key" not in data.get("Error", "")
        except Exception as e:
            logger.exception(f"OMDb API key validation failed: {e}")
            return False

    async def _validate_fanart_key(self, api_key: str) -> bool:
        """Validate Fanart.tv API key"""
        try:
            # Fanart.tv doesn't have a simple validation endpoint
            # We can try a simple request to check if key is valid
            url = "https://webservice.fanart.tv/v3/movies/tt0111161"
            headers = {"api-key": api_key}

            response = await self._http_client.get(url, headers=headers)
            # Fanart.tv returns 200 even for invalid keys, but with error message
            if response.status_code == 200:
                data = response.json()
                return "error" not in data or "Invalid API key" not in str(data.get("error", ""))

            return False
        except Exception as e:
            logger.exception(f"Fanart.tv API key validation failed: {e}")
            return False

    async def get_tvdb_token(
        self, api_key: str | None = None, pin: str | None = None
    ) -> str | None:
        """
        Get TVDB read token (with auto-refresh if expired)

        TVDB API v4 requires:
        1. API key + PIN to login
        2. Get read token (valid for 30 days)
        3. Auto-refresh before expiry

        Args:
            api_key: Optional API key (uses configured if not provided)
            pin: Optional PIN (uses configured if not provided)

        Returns:
            Read token or None if error
        """
        api_key = api_key or self.tvdb_api_key
        pin = pin or self.tvdb_pin

        if not api_key:
            logger.warning("TVDB API key not configured")
            return None

        # Check for cached token in database
        cached_token = (
            self.db.query(APIKeyToken)
            .filter(APIKeyToken.service_name == "tvdb", APIKeyToken.token_type == "read_token")
            .first()
        )

        if cached_token:
            # Check if token is still valid
            if cached_token.expires_at and cached_token.expires_at > datetime.utcnow():
                logger.debug("Using cached TVDB read token")
                return cached_token.token_value

            # Token expired, need to refresh
            logger.info("TVDB read token expired, refreshing...")

        # Login to get new token
        if not pin:
            logger.warning("TVDB PIN not configured - cannot get read token")
            return None

        try:
            url = "https://api4.thetvdb.com/v4/login"
            data = {
                "apikey": api_key,
                "pin": pin,
            }

            response = await self._http_client.post(url, json=data)
            response.raise_for_status()

            token_data = response.json()
            read_token = token_data.get("data", {}).get("token")

            if not read_token:
                logger.error("TVDB login succeeded but no token returned")
                return None

            # Store token in database
            if cached_token:
                cached_token.token_value = read_token
                cached_token.expires_at = datetime.utcnow() + timedelta(days=30)
                cached_token.updated_at = datetime.utcnow()
            else:
                new_token = APIKeyToken(
                    service_name="tvdb",
                    token_type="read_token",
                    token_value=read_token,
                    expires_at=datetime.utcnow() + timedelta(days=30),
                )
                self.db.add(new_token)

            self.db.commit()

            logger.info("TVDB read token obtained and cached")
            return read_token

        except Exception as e:
            logger.exception(f"TVDB login failed: {e}")
            return None

    def get_api_key(self, service: str) -> str | None:
        """Get API key for a service"""
        key_map = {
            "tvdb": self.tvdb_api_key,
            "tmdb": self.tmdb_api_key,
            "omdb": self.omdb_api_key,
            "fanart": self.fanart_api_key,
        }
        return key_map.get(service.lower())

    def get_user_agent(self, service: str) -> str | None:
        """Get user agent for a service (e.g., MusicBrainz)"""
        if service.lower() == "musicbrainz":
            return self.musicbrainz_user_agent or "StreamTV/2.0 (contact@streamtv.example.com)"
        return None

    def is_service_enabled(self, service: str) -> bool:
        """Check if a service is enabled in config"""
        enabled_map = {
            "tvdb": config.metadata.enable_tvdb,
            "tmdb": config.metadata.enable_tmdb,
            "tvmaze": config.metadata.enable_tvmaze,
            "musicbrainz": config.metadata.musicbrainz_enabled,
            "omdb": config.metadata.enable_omdb,
            "fanart": config.metadata.enable_fanart,
        }
        return enabled_map.get(service.lower(), False)

    async def check_rate_limit(self, service: str) -> bool:
        """Check if service is currently rate limited"""
        if service not in self._rate_limits:
            return False

        rate_limit_info = self._rate_limits[service]
        limited_until = rate_limit_info.get("limited_until")

        return bool(limited_until and datetime.utcnow() < limited_until)

    def set_rate_limit(self, service: str, retry_after: int | None = None):
        """Set rate limit for a service"""
        if retry_after:
            limited_until = datetime.utcnow() + timedelta(seconds=retry_after)
        else:
            # Default backoff based on service
            backoff_map = {
                "tvdb": 3600,  # 1 hour
                "tmdb": 600,  # 10 minutes
                "tvmaze": 60,  # 1 minute
                "musicbrainz": 60,  # 1 minute
                "omdb": 3600,  # 1 hour
                "fanart": 600,  # 10 minutes
            }
            limited_until = datetime.utcnow() + timedelta(seconds=backoff_map.get(service, 300))

        self._rate_limits[service] = {
            "limited_until": limited_until,
            "set_at": datetime.utcnow(),
        }

        logger.warning(f"Rate limit set for {service} until {limited_until}")

    async def validate_all_keys(self) -> dict[str, bool]:
        """Validate all configured API keys"""
        results = {}

        if config.metadata.enable_tvdb and self.tvdb_api_key:
            results["tvdb"] = await self.validate_api_key("tvdb")

        if config.metadata.enable_tmdb and self.tmdb_api_key:
            results["tmdb"] = await self.validate_api_key("tmdb")

        if config.metadata.enable_omdb and self.omdb_api_key:
            results["omdb"] = await self.validate_api_key("omdb")

        if config.metadata.enable_fanart and self.fanart_api_key:
            results["fanart"] = await self.validate_api_key("fanart")

        # TVMaze and MusicBrainz don't require keys
        results["tvmaze"] = True  # Free, no key required
        results["musicbrainz"] = bool(self.musicbrainz_user_agent)  # Requires user-agent

        return results
