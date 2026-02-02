"""
Home Assistant Integration

Provides:
- Media player entity for EXStreamTV
- Sensor entities for server status
- Service calls for control
- Automation support
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import logging
import json
import httpx

logger = logging.getLogger(__name__)


class HAEntityType(str, Enum):
    """Home Assistant entity types."""
    MEDIA_PLAYER = "media_player"
    SENSOR = "sensor"
    BINARY_SENSOR = "binary_sensor"
    SWITCH = "switch"


class HAMediaPlayerState(str, Enum):
    """Media player states."""
    OFF = "off"
    ON = "on"
    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"
    STANDBY = "standby"
    UNAVAILABLE = "unavailable"


@dataclass
class HAEntity:
    """A Home Assistant entity."""
    
    entity_id: str
    entity_type: HAEntityType
    name: str
    state: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": f"{self.entity_type.value}.{self.entity_id}",
            "state": self.state,
            "attributes": {
                "friendly_name": self.name,
                **self.attributes,
            },
        }


@dataclass
class HAConfig:
    """Home Assistant integration configuration."""
    
    # Home Assistant instance
    ha_url: str = ""
    access_token: str = ""
    
    # Entity configuration
    entity_prefix: str = "exstreamtv"
    
    # Features
    create_media_player: bool = True
    create_sensors: bool = True
    enable_websocket: bool = False
    
    # Update interval
    update_interval_seconds: int = 30


class HomeAssistantClient:
    """
    Client for Home Assistant REST API.
    
    Supports:
    - State updates
    - Service calls
    - Entity registration
    """
    
    def __init__(self, config: HAConfig):
        self.config = config
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        headers = {
            "Authorization": f"Bearer {self.config.access_token}",
            "Content-Type": "application/json",
        }
        self._http_client = httpx.AsyncClient(
            base_url=self.config.ha_url.rstrip("/"),
            headers=headers,
            timeout=30.0,
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._http_client:
            await self._http_client.aclose()
    
    async def test_connection(self) -> tuple[bool, str]:
        """Test connection to Home Assistant."""
        try:
            response = await self._http_client.get("/api/")
            
            if response.status_code == 200:
                data = response.json()
                return True, f"Connected to HA {data.get('version', 'unknown')}"
            elif response.status_code == 401:
                return False, "Invalid access token"
            else:
                return False, f"HTTP {response.status_code}"
        
        except Exception as e:
            return False, str(e)
    
    async def set_state(
        self,
        entity_id: str,
        state: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Set entity state."""
        try:
            payload = {
                "state": state,
                "attributes": attributes or {},
            }
            
            response = await self._http_client.post(
                f"/api/states/{entity_id}",
                json=payload,
            )
            
            return response.status_code in (200, 201)
        
        except Exception as e:
            logger.error(f"Failed to set state: {e}")
            return False
    
    async def get_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get entity state."""
        try:
            response = await self._http_client.get(f"/api/states/{entity_id}")
            
            if response.status_code == 200:
                return response.json()
            return None
        
        except Exception as e:
            logger.error(f"Failed to get state: {e}")
            return None
    
    async def call_service(
        self,
        domain: str,
        service: str,
        data: Optional[Dict[str, Any]] = None,
        target: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Call a Home Assistant service."""
        try:
            payload = {}
            if data:
                payload.update(data)
            if target:
                payload["target"] = target
            
            response = await self._http_client.post(
                f"/api/services/{domain}/{service}",
                json=payload,
            )
            
            return response.status_code == 200
        
        except Exception as e:
            logger.error(f"Failed to call service: {e}")
            return False
    
    async def fire_event(
        self,
        event_type: str,
        event_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Fire a Home Assistant event."""
        try:
            response = await self._http_client.post(
                f"/api/events/{event_type}",
                json=event_data or {},
            )
            
            return response.status_code == 200
        
        except Exception as e:
            logger.error(f"Failed to fire event: {e}")
            return False


class HomeAssistantIntegration:
    """
    Full Home Assistant integration for EXStreamTV.
    
    Creates and manages:
    - Media player entity for channels
    - Server status sensor
    - Stream count sensor
    - Channel list as attributes
    """
    
    def __init__(self, config: HAConfig):
        self.config = config
        self._client = HomeAssistantClient(config)
        self._update_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Current state
        self._current_channel: Optional[str] = None
        self._is_playing: bool = False
        self._channels: List[Dict] = []
    
    async def start(self) -> bool:
        """Start the integration."""
        async with self._client:
            success, message = await self._client.test_connection()
            if not success:
                logger.error(f"Home Assistant connection failed: {message}")
                return False
        
        self._running = True
        
        # Initial entity setup
        await self._setup_entities()
        
        # Start update loop
        self._update_task = asyncio.create_task(self._update_loop())
        
        logger.info("Home Assistant integration started")
        return True
    
    async def stop(self) -> None:
        """Stop the integration."""
        self._running = False
        
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Home Assistant integration stopped")
    
    async def _setup_entities(self) -> None:
        """Create initial entities."""
        async with self._client:
            # Media player entity
            if self.config.create_media_player:
                await self._client.set_state(
                    f"media_player.{self.config.entity_prefix}",
                    HAMediaPlayerState.IDLE.value,
                    {
                        "friendly_name": "EXStreamTV",
                        "supported_features": 152463,  # Play, pause, stop, volume, etc.
                        "device_class": "tv",
                    },
                )
            
            # Server status sensor
            if self.config.create_sensors:
                await self._client.set_state(
                    f"sensor.{self.config.entity_prefix}_status",
                    "online",
                    {
                        "friendly_name": "EXStreamTV Status",
                        "icon": "mdi:television-box",
                    },
                )
                
                # Stream count sensor
                await self._client.set_state(
                    f"sensor.{self.config.entity_prefix}_streams",
                    "0",
                    {
                        "friendly_name": "EXStreamTV Active Streams",
                        "icon": "mdi:video",
                        "unit_of_measurement": "streams",
                    },
                )
    
    async def update_media_player(
        self,
        state: HAMediaPlayerState,
        channel_name: Optional[str] = None,
        channel_number: Optional[int] = None,
        channel_logo: Optional[str] = None,
        program_title: Optional[str] = None,
    ) -> None:
        """Update media player state."""
        attributes = {
            "friendly_name": "EXStreamTV",
            "device_class": "tv",
        }
        
        if channel_name:
            attributes["media_title"] = channel_name
            self._current_channel = channel_name
        
        if channel_number:
            attributes["media_channel"] = channel_number
        
        if channel_logo:
            attributes["entity_picture"] = channel_logo
        
        if program_title:
            attributes["media_content_id"] = program_title
        
        if self._channels:
            attributes["source_list"] = [c.get("name") for c in self._channels]
        
        if channel_name:
            attributes["source"] = channel_name
        
        async with self._client:
            await self._client.set_state(
                f"media_player.{self.config.entity_prefix}",
                state.value,
                attributes,
            )
        
        self._is_playing = state == HAMediaPlayerState.PLAYING
    
    async def update_stream_count(self, count: int) -> None:
        """Update active stream count sensor."""
        async with self._client:
            await self._client.set_state(
                f"sensor.{self.config.entity_prefix}_streams",
                str(count),
                {
                    "friendly_name": "EXStreamTV Active Streams",
                    "icon": "mdi:video",
                    "unit_of_measurement": "streams",
                },
            )
    
    async def update_server_status(
        self,
        status: str,
        cpu_percent: Optional[float] = None,
        memory_percent: Optional[float] = None,
        channel_count: Optional[int] = None,
    ) -> None:
        """Update server status sensor."""
        attributes = {
            "friendly_name": "EXStreamTV Status",
            "icon": "mdi:television-box",
        }
        
        if cpu_percent is not None:
            attributes["cpu_percent"] = cpu_percent
        
        if memory_percent is not None:
            attributes["memory_percent"] = memory_percent
        
        if channel_count is not None:
            attributes["channel_count"] = channel_count
        
        async with self._client:
            await self._client.set_state(
                f"sensor.{self.config.entity_prefix}_status",
                status,
                attributes,
            )
    
    def set_channels(self, channels: List[Dict]) -> None:
        """Update channel list."""
        self._channels = channels
    
    async def fire_event(
        self,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Fire an EXStreamTV event in Home Assistant."""
        async with self._client:
            await self._client.fire_event(
                f"exstreamtv_{event_type}",
                data,
            )
    
    async def notify_channel_changed(
        self,
        channel_name: str,
        channel_number: int,
    ) -> None:
        """Notify HA that the channel changed."""
        await self.fire_event("channel_changed", {
            "channel_name": channel_name,
            "channel_number": channel_number,
        })
        
        await self.update_media_player(
            HAMediaPlayerState.PLAYING,
            channel_name=channel_name,
            channel_number=channel_number,
        )
    
    async def notify_stream_started(self, channel_name: str) -> None:
        """Notify HA that a stream started."""
        await self.fire_event("stream_started", {
            "channel_name": channel_name,
        })
    
    async def notify_stream_stopped(self, channel_name: str) -> None:
        """Notify HA that a stream stopped."""
        await self.fire_event("stream_stopped", {
            "channel_name": channel_name,
        })
        
        if self._current_channel == channel_name:
            await self.update_media_player(HAMediaPlayerState.IDLE)
    
    async def _update_loop(self) -> None:
        """Periodic update loop."""
        while self._running:
            try:
                await asyncio.sleep(self.config.update_interval_seconds)
                
                # Update server status (would fetch real data in production)
                await self.update_server_status("online")
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"HA update error: {e}")


# Global integration instance
ha_integration: Optional[HomeAssistantIntegration] = None


async def setup_homeassistant(config: HAConfig) -> Optional[HomeAssistantIntegration]:
    """Setup Home Assistant integration."""
    global ha_integration
    
    ha_integration = HomeAssistantIntegration(config)
    
    if await ha_integration.start():
        return ha_integration
    
    ha_integration = None
    return None


async def shutdown_homeassistant() -> None:
    """Shutdown Home Assistant integration."""
    global ha_integration
    
    if ha_integration:
        await ha_integration.stop()
        ha_integration = None
