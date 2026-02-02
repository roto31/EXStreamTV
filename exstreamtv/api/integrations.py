"""
Integration API endpoints.

Provides endpoints for:
- IPTV source management
- HDHomeRun tuner control
- Notification services
- Home Assistant
- Cloud storage
- Plugin management
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

router = APIRouter(prefix="/integrations", tags=["Integrations"])


# ============================================================================
# Request/Response Models
# ============================================================================

class IPTVSourceCreate(BaseModel):
    """Create IPTV source request."""
    name: str
    source_type: str  # "m3u" or "xtream"
    m3u_url: Optional[str] = None
    xtream_url: Optional[str] = None
    xtream_username: Optional[str] = None
    xtream_password: Optional[str] = None
    auto_refresh: bool = True
    refresh_interval_hours: int = 24


class NotificationServiceCreate(BaseModel):
    """Create notification service request."""
    name: str
    service_type: str  # "discord", "telegram", "pushover", "slack"
    config: Dict[str, Any]


class HomeAssistantSetup(BaseModel):
    """Home Assistant setup request."""
    ha_url: str
    access_token: str


class CloudStorageCreate(BaseModel):
    """Create cloud storage request."""
    name: str
    provider: str  # "google_drive", "dropbox", "s3"
    config: Dict[str, Any]


# ============================================================================
# IPTV Sources
# ============================================================================

@router.get("/iptv/sources")
async def list_iptv_sources() -> List[Dict[str, Any]]:
    """List all IPTV sources."""
    from exstreamtv.integration import iptv_source_manager
    
    sources = iptv_source_manager.get_all_sources()
    return [
        {
            "id": s.id,
            "name": s.name,
            "source_type": s.source_type.value,
            "is_enabled": s.is_enabled,
            "channel_count": s.channel_count,
            "last_refresh": s.last_refresh.isoformat() if s.last_refresh else None,
            "last_error": s.last_error,
        }
        for s in sources
    ]


@router.post("/iptv/sources")
async def create_iptv_source(data: IPTVSourceCreate) -> Dict[str, Any]:
    """Create a new IPTV source."""
    from exstreamtv.integration import (
        iptv_source_manager,
        IPTVSourceConfig,
        SourceType,
    )
    
    source_type = SourceType(data.source_type)
    
    config = IPTVSourceConfig(
        id=len(iptv_source_manager.get_all_sources()) + 1,
        name=data.name,
        source_type=source_type,
        m3u_url=data.m3u_url,
        xtream_url=data.xtream_url,
        xtream_username=data.xtream_username,
        xtream_password=data.xtream_password,
        auto_refresh=data.auto_refresh,
        refresh_interval_hours=data.refresh_interval_hours,
    )
    
    iptv_source_manager.add_source(config)
    
    return {"id": config.id, "name": config.name, "message": "Source created"}


@router.post("/iptv/sources/{source_id}/refresh")
async def refresh_iptv_source(
    source_id: int,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """Refresh an IPTV source."""
    from exstreamtv.integration import iptv_source_manager
    
    source = iptv_source_manager.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Refresh in background
    background_tasks.add_task(iptv_source_manager.refresh_source, source_id)
    
    return {"message": "Refresh started", "source_id": source_id}


@router.get("/iptv/sources/{source_id}/channels")
async def get_iptv_channels(source_id: int) -> List[Dict[str, Any]]:
    """Get channels from an IPTV source."""
    from exstreamtv.integration import iptv_source_manager
    
    channels = iptv_source_manager.get_channels(source_id)
    return [c.to_dict() for c in channels]


@router.post("/iptv/sources/{source_id}/test")
async def test_iptv_source(source_id: int) -> Dict[str, Any]:
    """Test an IPTV source connection."""
    from exstreamtv.integration import iptv_source_manager
    
    success, message = await iptv_source_manager.test_source(source_id)
    return {"success": success, "message": message}


# ============================================================================
# HDHomeRun
# ============================================================================

@router.get("/hdhomerun/devices")
async def list_hdhomerun_devices() -> List[Dict[str, Any]]:
    """List discovered HDHomeRun devices."""
    from exstreamtv.integration import hdhomerun_manager
    
    return hdhomerun_manager.get_devices()


@router.post("/hdhomerun/discover")
async def discover_hdhomerun_devices() -> Dict[str, Any]:
    """Discover HDHomeRun devices on network."""
    from exstreamtv.integration import hdhomerun_manager
    
    devices = await hdhomerun_manager.discover()
    return {
        "discovered": len(devices),
        "devices": [d.to_dict() for d in devices],
    }


@router.post("/hdhomerun/devices")
async def add_hdhomerun_device(ip_address: str) -> Dict[str, Any]:
    """Add an HDHomeRun device manually."""
    from exstreamtv.integration import hdhomerun_manager
    
    device = await hdhomerun_manager.add_device(ip_address)
    if device:
        return device.to_dict()
    raise HTTPException(status_code=400, detail="Failed to add device")


@router.post("/hdhomerun/devices/{device_id}/scan")
async def scan_hdhomerun_channels(device_id: str) -> Dict[str, Any]:
    """Scan channels on an HDHomeRun device."""
    from exstreamtv.integration import hdhomerun_manager
    
    channels = await hdhomerun_manager.scan_channels(device_id)
    return {
        "device_id": device_id,
        "channel_count": len(channels),
        "channels": [c.to_dict() for c in channels],
    }


@router.get("/hdhomerun/devices/{device_id}/channels")
async def get_hdhomerun_channels(device_id: str) -> List[Dict[str, Any]]:
    """Get cached channels for a device."""
    from exstreamtv.integration import hdhomerun_manager
    
    return hdhomerun_manager.get_channels(device_id)


# ============================================================================
# Notifications
# ============================================================================

@router.get("/notifications/services")
async def list_notification_services() -> List[str]:
    """List configured notification services."""
    from exstreamtv.integration import notification_manager
    
    return notification_manager.get_services()


@router.post("/notifications/services")
async def add_notification_service(data: NotificationServiceCreate) -> Dict[str, Any]:
    """Add a notification service."""
    from exstreamtv.integration import (
        notification_manager,
        DiscordService,
        DiscordConfig,
        TelegramService,
        TelegramConfig,
        PushoverService,
        PushoverConfig,
        SlackService,
        SlackConfig,
    )
    
    if data.service_type == "discord":
        config = DiscordConfig(
            name=data.name,
            webhook_url=data.config.get("webhook_url", ""),
        )
        service = DiscordService(config)
    
    elif data.service_type == "telegram":
        config = TelegramConfig(
            name=data.name,
            bot_token=data.config.get("bot_token", ""),
            chat_id=data.config.get("chat_id", ""),
        )
        service = TelegramService(config)
    
    elif data.service_type == "pushover":
        config = PushoverConfig(
            name=data.name,
            user_key=data.config.get("user_key", ""),
            api_token=data.config.get("api_token", ""),
        )
        service = PushoverService(config)
    
    elif data.service_type == "slack":
        config = SlackConfig(
            name=data.name,
            webhook_url=data.config.get("webhook_url", ""),
        )
        service = SlackService(config)
    
    else:
        raise HTTPException(status_code=400, detail="Unknown service type")
    
    notification_manager.add_service(data.name, service)
    return {"name": data.name, "type": data.service_type, "message": "Service added"}


@router.post("/notifications/services/{name}/test")
async def test_notification_service(name: str) -> Dict[str, Any]:
    """Test a notification service."""
    from exstreamtv.integration import notification_manager
    
    success, message = await notification_manager.test_service(name)
    return {"success": success, "message": message}


@router.post("/notifications/send")
async def send_notification(
    title: str,
    message: str,
    priority: str = "normal",
) -> Dict[str, Any]:
    """Send a test notification to all services."""
    from exstreamtv.integration import (
        notification_manager,
        Notification,
        NotificationType,
        NotificationPriority,
    )
    
    notification = Notification(
        title=title,
        message=message,
        notification_type=NotificationType.INFO,
        priority=NotificationPriority(priority),
    )
    
    results = await notification_manager.send(notification)
    return {"results": results}


@router.get("/notifications/history")
async def get_notification_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Get notification history."""
    from exstreamtv.integration import notification_manager
    
    return notification_manager.get_history(limit)


# ============================================================================
# Home Assistant
# ============================================================================

@router.get("/homeassistant/status")
async def get_homeassistant_status() -> Dict[str, Any]:
    """Get Home Assistant integration status."""
    from exstreamtv.integration.homeassistant import ha_integration
    
    if ha_integration:
        return {
            "connected": True,
            "ha_url": ha_integration.config.ha_url,
        }
    return {"connected": False}


@router.post("/homeassistant/setup")
async def setup_homeassistant_integration(data: HomeAssistantSetup) -> Dict[str, Any]:
    """Setup Home Assistant integration."""
    from exstreamtv.integration import (
        HAConfig,
        setup_homeassistant,
    )
    
    config = HAConfig(
        ha_url=data.ha_url,
        access_token=data.access_token,
    )
    
    integration = await setup_homeassistant(config)
    
    if integration:
        return {"success": True, "message": "Home Assistant connected"}
    return {"success": False, "message": "Failed to connect"}


@router.post("/homeassistant/disconnect")
async def disconnect_homeassistant() -> Dict[str, Any]:
    """Disconnect Home Assistant integration."""
    from exstreamtv.integration import shutdown_homeassistant
    
    await shutdown_homeassistant()
    return {"message": "Disconnected"}


# ============================================================================
# Cloud Storage
# ============================================================================

@router.get("/cloud/providers")
async def list_cloud_providers() -> List[str]:
    """List configured cloud storage providers."""
    from exstreamtv.integration import cloud_storage_manager
    
    return cloud_storage_manager.get_providers()


@router.post("/cloud/providers")
async def add_cloud_provider(data: CloudStorageCreate) -> Dict[str, Any]:
    """Add a cloud storage provider."""
    from exstreamtv.integration import (
        cloud_storage_manager,
        CloudProvider,
        GoogleDriveProvider,
        GoogleDriveConfig,
        DropboxProvider,
        DropboxConfig,
        S3Provider,
        S3Config,
    )
    
    if data.provider == "google_drive":
        config = GoogleDriveConfig(
            name=data.name,
            client_id=data.config.get("client_id", ""),
            client_secret=data.config.get("client_secret", ""),
            refresh_token=data.config.get("refresh_token", ""),
        )
        provider = GoogleDriveProvider(config)
    
    elif data.provider == "dropbox":
        config = DropboxConfig(
            name=data.name,
            access_token=data.config.get("access_token", ""),
        )
        provider = DropboxProvider(config)
    
    elif data.provider == "s3":
        config = S3Config(
            name=data.name,
            endpoint_url=data.config.get("endpoint_url", ""),
            bucket_name=data.config.get("bucket_name", ""),
            access_key=data.config.get("access_key", ""),
            secret_key=data.config.get("secret_key", ""),
            region=data.config.get("region", "us-east-1"),
        )
        provider = S3Provider(config)
    
    else:
        raise HTTPException(status_code=400, detail="Unknown provider type")
    
    cloud_storage_manager.add_provider(data.name, provider)
    return {"name": data.name, "provider": data.provider, "message": "Provider added"}


@router.post("/cloud/providers/{name}/scan")
async def scan_cloud_provider(name: str) -> Dict[str, Any]:
    """Scan a cloud storage provider for files."""
    from exstreamtv.integration import cloud_storage_manager
    
    files = await cloud_storage_manager.scan_provider(name)
    return {
        "provider": name,
        "file_count": len(files),
        "files": [f.to_dict() for f in files[:100]],  # Limit response
    }


@router.post("/cloud/providers/{name}/test")
async def test_cloud_provider(name: str) -> Dict[str, Any]:
    """Test a cloud storage provider."""
    from exstreamtv.integration import cloud_storage_manager
    
    success, message = await cloud_storage_manager.test_provider(name)
    return {"success": success, "message": message}


@router.get("/cloud/files")
async def get_cloud_files(provider: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get cached cloud files."""
    from exstreamtv.integration import cloud_storage_manager
    
    files = cloud_storage_manager.get_files(provider)
    return [f.to_dict() for f in files]


# ============================================================================
# Plugins
# ============================================================================

@router.get("/plugins")
async def list_plugins() -> List[Dict[str, Any]]:
    """List all plugins."""
    from exstreamtv.integration import get_plugin_manager
    
    manager = get_plugin_manager()
    if not manager:
        return []
    
    plugins = manager.get_plugins()
    return [
        {
            "id": p.info.id,
            "name": p.info.name,
            "version": p.info.version,
            "type": p.info.plugin_type.value,
            "state": p.state.value,
            "author": p.info.author,
            "description": p.info.description,
        }
        for p in plugins
    ]


@router.post("/plugins/{plugin_id}/enable")
async def enable_plugin(plugin_id: str) -> Dict[str, Any]:
    """Enable a plugin."""
    from exstreamtv.integration import get_plugin_manager
    
    manager = get_plugin_manager()
    if not manager:
        raise HTTPException(status_code=503, detail="Plugin system not initialized")
    
    # Load if not loaded
    loaded = manager.get_plugin(plugin_id)
    if not loaded:
        if not await manager.load_plugin(plugin_id):
            raise HTTPException(status_code=400, detail="Failed to load plugin")
    
    if await manager.enable_plugin(plugin_id):
        return {"message": f"Plugin {plugin_id} enabled"}
    
    raise HTTPException(status_code=400, detail="Failed to enable plugin")


@router.post("/plugins/{plugin_id}/disable")
async def disable_plugin(plugin_id: str) -> Dict[str, Any]:
    """Disable a plugin."""
    from exstreamtv.integration import get_plugin_manager
    
    manager = get_plugin_manager()
    if not manager:
        raise HTTPException(status_code=503, detail="Plugin system not initialized")
    
    if await manager.disable_plugin(plugin_id):
        return {"message": f"Plugin {plugin_id} disabled"}
    
    raise HTTPException(status_code=400, detail="Failed to disable plugin")


@router.post("/plugins/discover")
async def discover_plugins() -> Dict[str, Any]:
    """Discover available plugins."""
    from exstreamtv.integration import get_plugin_manager
    
    manager = get_plugin_manager()
    if not manager:
        raise HTTPException(status_code=503, detail="Plugin system not initialized")
    
    plugins = await manager.discover_plugins()
    return {
        "discovered": len(plugins),
        "plugins": [p.to_dict() for p in plugins],
    }
