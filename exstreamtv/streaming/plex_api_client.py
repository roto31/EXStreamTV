"""Plex API client for DVR and EPG integration"""

import logging
import time
from typing import Any

import httpx

from ..config import get_config
from ..constants import DEFAULT_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

# Throttle for Plex guide reload (avoid hammering Plex on rapid EPG edits)
RELOAD_THROTTLE_SECONDS = 60
_last_reload_time: float = 0.0


class PlexAPIClient:
    """
    Plex API client for DVR and EPG integration.
    
    This client provides access to Plex DVR features for channel mapping
    and EPG integration with EXStreamTV.
    """
    
    def __init__(self, base_url: str | None = None, token: str | None = None):
        """
        Initialize Plex API client.
        
        Args:
            base_url: Plex Media Server base URL
            token: Plex authentication token
        """
        config = get_config()
        plex_url = base_url or (getattr(getattr(config, "plex", None), "url", None) or getattr(getattr(config, "plex", None), "base_url", None))
        self.base_url = plex_url.rstrip("/") if plex_url else None
        self.token = token or (getattr(getattr(config, "plex", None), "token", None) or None)
        
        if not self.base_url:
            raise ValueError("Plex base_url is required")
        if not self.token:
            raise ValueError("Plex token is required")
        
        self._http_client: httpx.AsyncClient | None = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(DEFAULT_TIMEOUT_SECONDS * 3),
            follow_redirects=True
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
    
    def _get_headers(self) -> dict[str, str]:
        """Get request headers with authentication."""
        return {
            "Accept": "application/json",
            "X-Plex-Product": "EXStreamTV",
            "X-Plex-Version": "2.0.0",
            "X-Plex-Client-Identifier": "exstreamtv-plex-client",
            "X-Plex-Token": self.token,
        }
    
    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure HTTP client is initialized."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(DEFAULT_TIMEOUT_SECONDS * 3),
                follow_redirects=True
            )
        return self._http_client
    
    async def get_dvrs(self) -> list[dict[str, Any]]:
        """
        Get all DVR configurations from Plex server.
        
        Returns:
            List of DVR configurations with channel information
        """
        try:
            client = await self._ensure_client()
            url = f"{self.base_url}/livetv/dvrs"
            headers = self._get_headers()
            
            response = await client.get(url, headers=headers)
            
            if response.status_code == 404:
                # DVR not configured
                logger.debug("Plex DVR not configured (404)")
                return []
            
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            dvrs = data.get("MediaContainer", {}).get("Dvr", [])
            
            # Ensure it's a list
            if isinstance(dvrs, dict):
                dvrs = [dvrs]
            
            return dvrs
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.warning("Plex authentication failed - check your token")
            elif e.response.status_code == 404:
                logger.debug("Plex DVR endpoint not found - DVR may not be enabled")
            else:
                logger.warning(f"Error getting Plex DVRs: {e}")
            return []
        except Exception as e:
            logger.warning(f"Error getting Plex DVRs: {e}")
            return []
    
    async def get_dvr_channels(self, dvr_key: str | None = None) -> list[dict[str, Any]]:
        """
        Get channels from a specific DVR or all DVRs.
        
        Args:
            dvr_key: Specific DVR key, or None for all DVRs
            
        Returns:
            List of channel configurations
        """
        try:
            dvrs = await self.get_dvrs()
            if not dvrs:
                return []
            
            channels = []
            for dvr in dvrs:
                if dvr_key and dvr.get("key") != dvr_key:
                    continue
                
                # Get channels for this DVR
                dvr_channels = dvr.get("Channel", [])
                if isinstance(dvr_channels, dict):
                    dvr_channels = [dvr_channels]
                
                channels.extend(dvr_channels)
            
            return channels
            
        except Exception as e:
            logger.warning(f"Error getting Plex DVR channels: {e}")
            return []
    
    async def reload_guide(self, force: bool = False) -> bool:
        """
        Tell Plex DVR to reload the program guide (POST livetv/dvrs/{dvrId}/reloadGuide).
        Uses the first DVR returned by GET livetv/dvrs. Throttled unless force=True.
        
        Args:
            force: If True, skip throttle (e.g. for manual "Refresh guide" button).
        
        Returns:
            True if reload was sent (or skipped by throttle), False on error.
        """
        global _last_reload_time
        now = time.monotonic()
        if not force and (now - _last_reload_time) < RELOAD_THROTTLE_SECONDS:
            logger.debug("Plex guide reload skipped (throttled)")
            return True
        try:
            dvrs = await self.get_dvrs()
            if not dvrs:
                logger.debug("No Plex DVR found; cannot reload guide")
                return False
            dvr = dvrs[0]
            key = dvr.get("key") or ""
            dvr_id = key.strip("/").split("/")[-1] if key else dvr.get("id")
            if not dvr_id:
                logger.warning("Plex DVR has no key/id for reloadGuide")
                return False
            client = await self._ensure_client()
            url = f"{self.base_url}/livetv/dvrs/{dvr_id}/reloadGuide"
            headers = self._get_headers()
            response = await client.post(url, headers=headers)
            if response.status_code in (200, 204):
                _last_reload_time = time.monotonic()
                logger.info("Plex DVR guide reload requested")
                return True
            logger.warning(f"Plex reloadGuide returned {response.status_code}")
            return False
        except Exception as e:
            logger.warning(f"Plex guide reload failed: {e}")
            return False

    async def test_connection(self) -> bool:
        """
        Test connection to Plex server.
        
        Returns:
            True if connection successful
        """
        try:
            client = await self._ensure_client()
            url = f"{self.base_url}/"
            headers = self._get_headers()
            
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            return True
        except Exception as e:
            logger.warning(f"Plex connection test failed: {e}")
            return False


async def request_plex_guide_reload(force: bool = False) -> bool:
    """
    Request Plex to reload its program guide (uses config base_url/token).
    Safe to call when Plex is not configured; returns False without raising.
    
    Args:
        force: If True, skip throttle (e.g. manual "Refresh guide in Plex" button).
    
    Returns:
        True if reload was requested (or skipped by throttle), False on error or no config.
    """
    try:
        client = PlexAPIClient()
    except ValueError:
        return False
    try:
        async with client:
            return await client.reload_guide(force=force)
    except Exception as e:
        logger.debug(f"Plex guide reload not available: {e}")
        return False
