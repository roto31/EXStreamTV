"""
HDHomeRun Tuner Input Integration

Allows using physical HDHomeRun tuners as channel sources:
- Auto-discovery via SSDP
- Channel scanning
- Live TV streaming
- Signal quality monitoring
"""

import asyncio
import socket
import struct
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import logging
import httpx

logger = logging.getLogger(__name__)


class TunerStatus(str, Enum):
    """Status of a tuner."""
    IDLE = "idle"
    SCANNING = "scanning"
    STREAMING = "streaming"
    ERROR = "error"


@dataclass
class TunerChannel:
    """A channel from an HDHomeRun tuner."""
    
    number: str
    name: str
    frequency: int
    program_number: int
    modulation: str
    
    # Virtual channel info
    virtual_major: Optional[int] = None
    virtual_minor: Optional[int] = None
    
    # Stream info
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    is_hd: bool = False
    is_encrypted: bool = False
    
    # Signal
    signal_strength: Optional[int] = None
    signal_quality: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "number": self.number,
            "name": self.name,
            "frequency": self.frequency,
            "program_number": self.program_number,
            "is_hd": self.is_hd,
            "is_encrypted": self.is_encrypted,
            "signal_strength": self.signal_strength,
        }


@dataclass
class HDHomeRunDevice:
    """An HDHomeRun device."""
    
    device_id: str
    ip_address: str
    
    # Device info
    model: Optional[str] = None
    firmware: Optional[str] = None
    tuner_count: int = 2
    
    # Status
    is_online: bool = True
    last_seen: Optional[datetime] = None
    
    # Tuner states
    tuner_status: Dict[int, TunerStatus] = field(default_factory=dict)
    
    # Channels
    channels: List[TunerChannel] = field(default_factory=list)
    
    @property
    def base_url(self) -> str:
        return f"http://{self.ip_address}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "ip_address": self.ip_address,
            "model": self.model,
            "firmware": self.firmware,
            "tuner_count": self.tuner_count,
            "is_online": self.is_online,
            "channel_count": len(self.channels),
        }


class HDHomeRunClient:
    """
    Client for communicating with HDHomeRun devices.
    
    Supports:
    - Device discovery
    - Channel scanning
    - Stream URL generation
    - Status monitoring
    """
    
    DISCOVERY_PORT = 65001
    DISCOVERY_TIMEOUT = 5.0
    
    def __init__(self):
        self._http_client: Optional[httpx.AsyncClient] = None
        self._devices: Dict[str, HDHomeRunDevice] = {}
    
    async def __aenter__(self):
        self._http_client = httpx.AsyncClient(timeout=30.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._http_client:
            await self._http_client.aclose()
    
    async def discover_devices(self) -> List[HDHomeRunDevice]:
        """
        Discover HDHomeRun devices on the network.
        
        Uses UDP broadcast to find devices.
        """
        devices = []
        
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(self.DISCOVERY_TIMEOUT)
        
        try:
            # HDHomeRun discovery packet
            # Type: 0x0002 (discover request)
            # Tag: 0x01 (device type: tuner)
            # Tag: 0x02 (device ID: wildcard)
            discover_packet = bytes([
                0x00, 0x02,  # Type: discover
                0x00, 0x0c,  # Length: 12
                0x01,        # Tag: device type
                0x04,        # Length
                0xff, 0xff, 0xff, 0xff,  # Wildcard
                0x02,        # Tag: device ID
                0x04,        # Length
                0xff, 0xff, 0xff, 0xff,  # Wildcard
            ])
            
            # Send discovery
            sock.sendto(discover_packet, ("255.255.255.255", self.DISCOVERY_PORT))
            
            # Receive responses
            while True:
                try:
                    data, addr = sock.recvfrom(1024)
                    device = self._parse_discovery_response(data, addr[0])
                    if device:
                        devices.append(device)
                        self._devices[device.device_id] = device
                except socket.timeout:
                    break
        
        finally:
            sock.close()
        
        # Also try HTTP discovery for known devices
        for device in devices:
            await self._update_device_info(device)
        
        logger.info(f"Discovered {len(devices)} HDHomeRun devices")
        return devices
    
    async def add_device_by_ip(self, ip_address: str) -> Optional[HDHomeRunDevice]:
        """Manually add a device by IP address."""
        try:
            response = await self._http_client.get(f"http://{ip_address}/discover.json")
            response.raise_for_status()
            
            data = response.json()
            device = HDHomeRunDevice(
                device_id=data.get("DeviceID", ip_address),
                ip_address=ip_address,
                model=data.get("ModelNumber"),
                firmware=data.get("FirmwareVersion"),
                tuner_count=data.get("TunerCount", 2),
            )
            
            self._devices[device.device_id] = device
            return device
        
        except Exception as e:
            logger.error(f"Failed to add device at {ip_address}: {e}")
            return None
    
    async def scan_channels(self, device_id: str) -> List[TunerChannel]:
        """
        Scan for channels on a device.
        
        This retrieves the channel lineup from the device.
        """
        device = self._devices.get(device_id)
        if not device:
            return []
        
        try:
            # Get lineup
            response = await self._http_client.get(
                f"{device.base_url}/lineup.json"
            )
            response.raise_for_status()
            
            lineup = response.json()
            channels = []
            
            for item in lineup:
                channel = TunerChannel(
                    number=item.get("GuideNumber", ""),
                    name=item.get("GuideName", ""),
                    frequency=0,  # Not in lineup
                    program_number=0,
                    modulation="",
                    is_hd=item.get("HD", 0) == 1,
                )
                
                # Store stream URL in metadata
                channel.video_codec = item.get("VideoCodec")
                channel.audio_codec = item.get("AudioCodec")
                
                channels.append(channel)
            
            device.channels = channels
            logger.info(f"Scanned {len(channels)} channels from {device_id}")
            return channels
        
        except Exception as e:
            logger.error(f"Failed to scan channels: {e}")
            return []
    
    def get_stream_url(
        self,
        device_id: str,
        channel_number: str,
        tuner: int = 0,
    ) -> Optional[str]:
        """Get stream URL for a channel."""
        device = self._devices.get(device_id)
        if not device:
            return None
        
        return f"{device.base_url}/auto/v{channel_number}"
    
    async def get_tuner_status(self, device_id: str) -> Dict[int, Dict]:
        """Get status of all tuners on a device."""
        device = self._devices.get(device_id)
        if not device:
            return {}
        
        status = {}
        
        for tuner_num in range(device.tuner_count):
            try:
                response = await self._http_client.get(
                    f"{device.base_url}/tuners.html",
                    params={"tuner": tuner_num},
                )
                
                # Parse status (simplified)
                status[tuner_num] = {
                    "status": TunerStatus.IDLE.value,
                    "channel": None,
                }
            except Exception:
                status[tuner_num] = {
                    "status": TunerStatus.ERROR.value,
                    "channel": None,
                }
        
        return status
    
    async def get_signal_status(
        self,
        device_id: str,
        tuner: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """Get signal status for a tuner."""
        device = self._devices.get(device_id)
        if not device:
            return None
        
        try:
            response = await self._http_client.get(
                f"{device.base_url}/tuner{tuner}/status"
            )
            
            # Parse status page
            text = response.text
            
            # Extract signal info (format varies by device)
            return {
                "tuner": tuner,
                "signal_present": "sig" in text.lower(),
                "raw_status": text[:500],
            }
        except Exception as e:
            logger.error(f"Failed to get signal status: {e}")
            return None
    
    def get_device(self, device_id: str) -> Optional[HDHomeRunDevice]:
        """Get a device by ID."""
        return self._devices.get(device_id)
    
    def get_all_devices(self) -> List[HDHomeRunDevice]:
        """Get all known devices."""
        return list(self._devices.values())
    
    def _parse_discovery_response(
        self,
        data: bytes,
        ip_address: str,
    ) -> Optional[HDHomeRunDevice]:
        """Parse a discovery response packet."""
        if len(data) < 4:
            return None
        
        # Check packet type (0x0003 = discover reply)
        pkt_type = struct.unpack(">H", data[0:2])[0]
        if pkt_type != 0x0003:
            return None
        
        # Parse TLV tags
        device_id = None
        offset = 4
        
        while offset < len(data):
            if offset + 2 > len(data):
                break
            
            tag = data[offset]
            length = data[offset + 1]
            offset += 2
            
            if offset + length > len(data):
                break
            
            value = data[offset:offset + length]
            offset += length
            
            if tag == 0x02:  # Device ID
                device_id = value.hex().upper()
        
        if device_id:
            return HDHomeRunDevice(
                device_id=device_id,
                ip_address=ip_address,
                last_seen=datetime.now(),
            )
        
        return None
    
    async def _update_device_info(self, device: HDHomeRunDevice) -> None:
        """Update device info via HTTP."""
        try:
            response = await self._http_client.get(
                f"{device.base_url}/discover.json"
            )
            response.raise_for_status()
            
            data = response.json()
            device.model = data.get("ModelNumber")
            device.firmware = data.get("FirmwareVersion")
            device.tuner_count = data.get("TunerCount", 2)
            device.is_online = True
            device.last_seen = datetime.now()
        
        except Exception as e:
            logger.warning(f"Failed to update device info for {device.device_id}: {e}")


class HDHomeRunManager:
    """
    Manages HDHomeRun devices as channel sources.
    
    Features:
    - Device discovery and management
    - Channel lineup import
    - Stream management
    - Health monitoring
    """
    
    def __init__(self):
        self._client = HDHomeRunClient()
        self._devices: Dict[str, HDHomeRunDevice] = {}
        self._monitor_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start the manager."""
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("HDHomeRun manager started")
    
    async def stop(self) -> None:
        """Stop the manager."""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
    
    async def discover(self) -> List[HDHomeRunDevice]:
        """Discover HDHomeRun devices."""
        async with self._client:
            devices = await self._client.discover_devices()
            for device in devices:
                self._devices[device.device_id] = device
            return devices
    
    async def add_device(self, ip_address: str) -> Optional[HDHomeRunDevice]:
        """Add a device manually."""
        async with self._client:
            device = await self._client.add_device_by_ip(ip_address)
            if device:
                self._devices[device.device_id] = device
            return device
    
    async def scan_channels(self, device_id: str) -> List[TunerChannel]:
        """Scan channels on a device."""
        async with self._client:
            return await self._client.scan_channels(device_id)
    
    def get_stream_url(
        self,
        device_id: str,
        channel_number: str,
    ) -> Optional[str]:
        """Get stream URL for a channel."""
        return self._client.get_stream_url(device_id, channel_number)
    
    def get_devices(self) -> List[Dict[str, Any]]:
        """Get all devices."""
        return [d.to_dict() for d in self._devices.values()]
    
    def get_channels(self, device_id: Optional[str] = None) -> List[Dict]:
        """Get channels, optionally filtered by device."""
        if device_id:
            device = self._devices.get(device_id)
            if device:
                return [c.to_dict() for c in device.channels]
            return []
        
        all_channels = []
        for device in self._devices.values():
            all_channels.extend([c.to_dict() for c in device.channels])
        return all_channels
    
    async def _monitor_loop(self) -> None:
        """Monitor device health."""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                async with self._client:
                    for device_id, device in self._devices.items():
                        try:
                            response = await self._client._http_client.get(
                                f"{device.base_url}/discover.json",
                                timeout=5.0,
                            )
                            device.is_online = response.status_code == 200
                            device.last_seen = datetime.now()
                        except Exception:
                            device.is_online = False
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}")


# Global manager instance
hdhomerun_manager = HDHomeRunManager()
