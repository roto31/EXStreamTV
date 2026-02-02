"""
IPTV Source Provider System

Supports importing channels from external IPTV sources:
- M3U/M3U8 playlists with auto-refresh
- Xtream Codes API
- Custom providers
"""

import asyncio
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import logging
import httpx

logger = logging.getLogger(__name__)


class SourceType(str, Enum):
    """Type of IPTV source."""
    M3U = "m3u"
    M3U_URL = "m3u_url"
    XTREAM = "xtream"
    CUSTOM = "custom"


class ChannelType(str, Enum):
    """Type of channel content."""
    LIVE = "live"
    MOVIE = "movie"
    SERIES = "series"
    VOD = "vod"


@dataclass
class IPTVChannel:
    """An IPTV channel from an external source."""
    
    id: str
    name: str
    stream_url: str
    logo_url: Optional[str] = None
    group: Optional[str] = None
    epg_id: Optional[str] = None
    channel_type: ChannelType = ChannelType.LIVE
    
    # Xtream-specific
    stream_id: Optional[int] = None
    category_id: Optional[int] = None
    
    # Quality/format info
    is_hd: bool = False
    codec: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "stream_url": self.stream_url,
            "logo_url": self.logo_url,
            "group": self.group,
            "epg_id": self.epg_id,
            "channel_type": self.channel_type.value,
            "is_hd": self.is_hd,
        }


@dataclass
class IPTVSourceConfig:
    """Configuration for an IPTV source."""
    
    id: int
    name: str
    source_type: SourceType
    is_enabled: bool = True
    
    # M3U source
    m3u_url: Optional[str] = None
    m3u_content: Optional[str] = None
    
    # Xtream Codes
    xtream_url: Optional[str] = None
    xtream_username: Optional[str] = None
    xtream_password: Optional[str] = None
    
    # EPG
    epg_url: Optional[str] = None
    
    # Auto-refresh
    auto_refresh: bool = True
    refresh_interval_hours: int = 24
    last_refresh: Optional[datetime] = None
    
    # Filtering
    include_groups: Optional[List[str]] = None
    exclude_groups: Optional[List[str]] = None
    name_filter: Optional[str] = None  # Regex pattern
    
    # Status
    channel_count: int = 0
    last_error: Optional[str] = None


class IPTVSourceProvider(ABC):
    """Abstract base for IPTV source providers."""
    
    def __init__(self, config: IPTVSourceConfig):
        self.config = config
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        self._http_client = httpx.AsyncClient(timeout=60.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._http_client:
            await self._http_client.aclose()
    
    @abstractmethod
    async def fetch_channels(self) -> List[IPTVChannel]:
        """Fetch channels from the source."""
        pass
    
    @abstractmethod
    async def test_connection(self) -> Tuple[bool, str]:
        """Test if the source is accessible."""
        pass
    
    def _apply_filters(self, channels: List[IPTVChannel]) -> List[IPTVChannel]:
        """Apply configured filters to channels."""
        filtered = channels
        
        # Group inclusion filter
        if self.config.include_groups:
            filtered = [
                c for c in filtered
                if c.group and c.group in self.config.include_groups
            ]
        
        # Group exclusion filter
        if self.config.exclude_groups:
            filtered = [
                c for c in filtered
                if not c.group or c.group not in self.config.exclude_groups
            ]
        
        # Name filter (regex)
        if self.config.name_filter:
            try:
                pattern = re.compile(self.config.name_filter, re.IGNORECASE)
                filtered = [c for c in filtered if pattern.search(c.name)]
            except re.error:
                pass
        
        return filtered


class M3USourceProvider(IPTVSourceProvider):
    """Provider for M3U/M3U8 playlist sources."""
    
    async def fetch_channels(self) -> List[IPTVChannel]:
        """Parse M3U playlist and return channels."""
        content = await self._get_m3u_content()
        if not content:
            return []
        
        channels = self._parse_m3u(content)
        return self._apply_filters(channels)
    
    async def test_connection(self) -> Tuple[bool, str]:
        """Test if M3U URL is accessible."""
        if self.config.m3u_content:
            return True, "Static M3U content configured"
        
        if not self.config.m3u_url:
            return False, "No M3U URL configured"
        
        try:
            response = await self._http_client.head(
                self.config.m3u_url,
                follow_redirects=True,
            )
            if response.status_code == 200:
                return True, "M3U URL accessible"
            return False, f"HTTP {response.status_code}"
        except Exception as e:
            return False, str(e)
    
    async def _get_m3u_content(self) -> Optional[str]:
        """Get M3U content from URL or static config."""
        if self.config.m3u_content:
            return self.config.m3u_content
        
        if not self.config.m3u_url:
            return None
        
        try:
            response = await self._http_client.get(
                self.config.m3u_url,
                follow_redirects=True,
            )
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Failed to fetch M3U: {e}")
            self.config.last_error = str(e)
            return None
    
    def _parse_m3u(self, content: str) -> List[IPTVChannel]:
        """Parse M3U content into channels."""
        channels = []
        lines = content.strip().split("\n")
        
        current_info = {}
        
        for line in lines:
            line = line.strip()
            
            if line.startswith("#EXTM3U"):
                continue
            
            if line.startswith("#EXTINF:"):
                current_info = self._parse_extinf(line)
            
            elif line.startswith("#EXTVLCOPT:") or line.startswith("#EXTGRP:"):
                # Parse additional tags
                if line.startswith("#EXTGRP:"):
                    current_info["group"] = line.split(":", 1)[1].strip()
            
            elif line and not line.startswith("#"):
                # This is the URL
                if current_info:
                    channel = IPTVChannel(
                        id=current_info.get("tvg-id", str(len(channels) + 1)),
                        name=current_info.get("name", f"Channel {len(channels) + 1}"),
                        stream_url=line,
                        logo_url=current_info.get("tvg-logo"),
                        group=current_info.get("group-title") or current_info.get("group"),
                        epg_id=current_info.get("tvg-id"),
                        is_hd="HD" in current_info.get("name", "").upper(),
                    )
                    channels.append(channel)
                    current_info = {}
        
        return channels
    
    def _parse_extinf(self, line: str) -> Dict[str, str]:
        """Parse #EXTINF line for metadata."""
        info = {}
        
        # Extract attributes like tvg-id="xxx" tvg-logo="xxx"
        attr_pattern = r'(\w+[-\w]*)\s*=\s*"([^"]*)"'
        for match in re.finditer(attr_pattern, line):
            key = match.group(1).lower().replace("-", "_")
            info[match.group(1).lower()] = match.group(2)
        
        # Extract channel name (after the comma)
        if "," in line:
            info["name"] = line.split(",", 1)[1].strip()
        
        return info


class XtreamCodesProvider(IPTVSourceProvider):
    """Provider for Xtream Codes API sources."""
    
    async def fetch_channels(self) -> List[IPTVChannel]:
        """Fetch channels from Xtream Codes API."""
        if not self._validate_config():
            return []
        
        channels = []
        
        # Fetch live streams
        live_streams = await self._fetch_live_streams()
        channels.extend(live_streams)
        
        return self._apply_filters(channels)
    
    async def test_connection(self) -> Tuple[bool, str]:
        """Test Xtream Codes API connection."""
        if not self._validate_config():
            return False, "Missing Xtream Codes configuration"
        
        try:
            auth_url = self._build_url("player_api.php", action="")
            response = await self._http_client.get(auth_url)
            response.raise_for_status()
            
            data = response.json()
            if data.get("user_info", {}).get("auth") == 1:
                exp_date = data.get("user_info", {}).get("exp_date")
                return True, f"Connected (expires: {exp_date})"
            
            return False, "Authentication failed"
        except Exception as e:
            return False, str(e)
    
    def _validate_config(self) -> bool:
        """Validate Xtream configuration."""
        return all([
            self.config.xtream_url,
            self.config.xtream_username,
            self.config.xtream_password,
        ])
    
    def _build_url(self, endpoint: str, **params) -> str:
        """Build Xtream API URL."""
        base = self.config.xtream_url.rstrip("/")
        url = f"{base}/{endpoint}"
        
        query_params = {
            "username": self.config.xtream_username,
            "password": self.config.xtream_password,
            **params,
        }
        
        query = "&".join(f"{k}={v}" for k, v in query_params.items() if v)
        return f"{url}?{query}"
    
    async def _fetch_live_streams(self) -> List[IPTVChannel]:
        """Fetch live TV streams."""
        try:
            # Get categories first
            categories = await self._fetch_categories("live")
            category_map = {c["category_id"]: c["category_name"] for c in categories}
            
            # Get streams
            url = self._build_url("player_api.php", action="get_live_streams")
            response = await self._http_client.get(url)
            response.raise_for_status()
            
            streams = response.json()
            channels = []
            
            for stream in streams:
                stream_id = stream.get("stream_id")
                cat_id = stream.get("category_id")
                
                # Build stream URL
                stream_url = self._build_stream_url(stream_id, "live")
                
                channel = IPTVChannel(
                    id=str(stream_id),
                    name=stream.get("name", ""),
                    stream_url=stream_url,
                    logo_url=stream.get("stream_icon"),
                    group=category_map.get(cat_id),
                    epg_id=stream.get("epg_channel_id"),
                    channel_type=ChannelType.LIVE,
                    stream_id=stream_id,
                    category_id=cat_id,
                    is_hd=stream.get("is_hd", False),
                )
                channels.append(channel)
            
            return channels
        except Exception as e:
            logger.error(f"Failed to fetch live streams: {e}")
            return []
    
    async def _fetch_categories(self, stream_type: str) -> List[Dict]:
        """Fetch categories for a stream type."""
        try:
            action = f"get_{stream_type}_categories"
            url = self._build_url("player_api.php", action=action)
            response = await self._http_client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception:
            return []
    
    def _build_stream_url(self, stream_id: int, stream_type: str) -> str:
        """Build stream URL for a channel."""
        base = self.config.xtream_url.rstrip("/")
        username = self.config.xtream_username
        password = self.config.xtream_password
        
        if stream_type == "live":
            return f"{base}/live/{username}/{password}/{stream_id}.ts"
        elif stream_type == "movie":
            return f"{base}/movie/{username}/{password}/{stream_id}.mkv"
        else:
            return f"{base}/{stream_type}/{username}/{password}/{stream_id}"


class IPTVSourceManager:
    """
    Manages multiple IPTV sources.
    
    Features:
    - Multiple source registration
    - Auto-refresh scheduling
    - Channel aggregation
    - Source health monitoring
    """
    
    def __init__(self):
        self._sources: Dict[int, IPTVSourceConfig] = {}
        self._providers: Dict[int, IPTVSourceProvider] = {}
        self._channels_cache: Dict[int, List[IPTVChannel]] = {}
        self._refresh_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start the source manager with auto-refresh."""
        self._refresh_task = asyncio.create_task(self._refresh_loop())
        logger.info("IPTV source manager started")
    
    async def stop(self) -> None:
        """Stop the source manager."""
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        logger.info("IPTV source manager stopped")
    
    def add_source(self, config: IPTVSourceConfig) -> None:
        """Add an IPTV source."""
        self._sources[config.id] = config
        self._providers[config.id] = self._create_provider(config)
        logger.info(f"Added IPTV source: {config.name} ({config.source_type.value})")
    
    def remove_source(self, source_id: int) -> bool:
        """Remove an IPTV source."""
        if source_id in self._sources:
            del self._sources[source_id]
            del self._providers[source_id]
            self._channels_cache.pop(source_id, None)
            return True
        return False
    
    def get_source(self, source_id: int) -> Optional[IPTVSourceConfig]:
        """Get a source configuration."""
        return self._sources.get(source_id)
    
    def get_all_sources(self) -> List[IPTVSourceConfig]:
        """Get all source configurations."""
        return list(self._sources.values())
    
    async def refresh_source(self, source_id: int) -> List[IPTVChannel]:
        """Refresh channels from a specific source."""
        config = self._sources.get(source_id)
        provider = self._providers.get(source_id)
        
        if not config or not provider:
            return []
        
        try:
            async with provider:
                channels = await provider.fetch_channels()
            
            config.channel_count = len(channels)
            config.last_refresh = datetime.now()
            config.last_error = None
            
            self._channels_cache[source_id] = channels
            
            logger.info(f"Refreshed source {config.name}: {len(channels)} channels")
            return channels
        
        except Exception as e:
            config.last_error = str(e)
            logger.error(f"Failed to refresh source {config.name}: {e}")
            return []
    
    async def refresh_all(self) -> Dict[int, int]:
        """Refresh all sources."""
        results = {}
        for source_id in self._sources:
            channels = await self.refresh_source(source_id)
            results[source_id] = len(channels)
        return results
    
    async def test_source(self, source_id: int) -> Tuple[bool, str]:
        """Test a source connection."""
        provider = self._providers.get(source_id)
        if not provider:
            return False, "Source not found"
        
        async with provider:
            return await provider.test_connection()
    
    def get_channels(
        self,
        source_id: Optional[int] = None,
    ) -> List[IPTVChannel]:
        """Get cached channels, optionally filtered by source."""
        if source_id:
            return self._channels_cache.get(source_id, [])
        
        # Return all channels
        all_channels = []
        for channels in self._channels_cache.values():
            all_channels.extend(channels)
        return all_channels
    
    def get_channel_groups(self) -> List[str]:
        """Get all unique channel groups."""
        groups = set()
        for channels in self._channels_cache.values():
            for channel in channels:
                if channel.group:
                    groups.add(channel.group)
        return sorted(groups)
    
    def _create_provider(self, config: IPTVSourceConfig) -> IPTVSourceProvider:
        """Create appropriate provider for source type."""
        if config.source_type in (SourceType.M3U, SourceType.M3U_URL):
            return M3USourceProvider(config)
        elif config.source_type == SourceType.XTREAM:
            return XtreamCodesProvider(config)
        else:
            raise ValueError(f"Unknown source type: {config.source_type}")
    
    async def _refresh_loop(self) -> None:
        """Background refresh loop."""
        while True:
            try:
                await asyncio.sleep(3600)  # Check every hour
                
                now = datetime.now()
                
                for config in self._sources.values():
                    if not config.auto_refresh or not config.is_enabled:
                        continue
                    
                    if config.last_refresh:
                        next_refresh = config.last_refresh + timedelta(
                            hours=config.refresh_interval_hours
                        )
                        if now < next_refresh:
                            continue
                    
                    await self.refresh_source(config.id)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Refresh loop error: {e}")


# Global source manager
iptv_source_manager = IPTVSourceManager()
