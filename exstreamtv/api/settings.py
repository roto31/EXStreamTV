"""Settings API endpoints for EXStreamTV"""

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from ..config import get_config

router = APIRouter(prefix="/settings", tags=["Settings"])



class FFmpegSettings(BaseModel):
    """FFmpeg settings response model."""
    path: str
    ffprobe_path: str
    hardware_acceleration_enabled: bool
    hardware_acceleration_preferred: str
    video_bitrate: str
    audio_bitrate: str
    video_codec: str
    audio_codec: str


class HDHomeRunSettings(BaseModel):
    """HDHomeRun settings response model."""
    enabled: bool
    device_id: str
    tuner_count: int


class ServerSettings(BaseModel):
    """Server settings response model."""
    host: str
    port: int
    debug: bool
    log_level: str


class StreamingSettings(BaseModel):
    """Streaming settings response model."""
    buffer_size: int
    read_size: int


class FFmpegSettingsUpdate(BaseModel):
    """FFmpeg settings update model - matches frontend payload."""
    ffmpeg_path: Optional[str] = None
    ffprobe_path: Optional[str] = None
    log_level: Optional[str] = None
    threads: Optional[int] = None
    hwaccel: Optional[str] = None
    hwaccel_device: Optional[str] = None
    extra_flags: Optional[str] = None
    # Per-source overrides
    youtube_hwaccel: Optional[str] = None
    archive_org_hwaccel: Optional[str] = None
    plex_hwaccel: Optional[str] = None
    youtube_video_encoder: Optional[str] = None
    archive_org_video_encoder: Optional[str] = None
    plex_video_encoder: Optional[str] = None


class FFmpegSettingsResponse(BaseModel):
    """FFmpeg settings response model - matches what frontend expects."""
    ffmpeg_path: str
    ffprobe_path: str
    log_level: str = "info"
    threads: int = 0
    hwaccel: str = ""
    hwaccel_device: Optional[str] = None
    extra_flags: Optional[str] = None


@router.get("/ffmpeg")
async def get_ffmpeg_settings() -> FFmpegSettingsResponse:
    """Return current FFmpeg settings.
    
    Returns:
        FFmpegSettingsResponse: Current FFmpeg configuration
    """
    config = get_config()
    hwaccel_value = ""
    if config.ffmpeg.hardware_acceleration.enabled:
        hwaccel_value = config.ffmpeg.hardware_acceleration.preferred or "auto"
    response = FFmpegSettingsResponse(
        ffmpeg_path=config.ffmpeg.path,
        ffprobe_path=config.ffmpeg.ffprobe_path,
        log_level=config.ffmpeg.log_level,
        threads=config.ffmpeg.threads,
        hwaccel=hwaccel_value,
        hwaccel_device=config.ffmpeg.hwaccel_device,
        extra_flags=config.ffmpeg.extra_flags,
    )
    return response


@router.put("/ffmpeg")
async def update_ffmpeg_settings(settings: FFmpegSettingsUpdate):
    """Update FFmpeg settings.
    
    Args:
        settings: New FFmpeg settings to apply
        
    Returns:
        dict: Success message
    """
    import yaml
    
    # Load existing config
    config_path = Path("config.yaml")
    if config_path.exists():
        with open(config_path) as f:
            config_data = yaml.safe_load(f) or {}
    else:
        config_data = {}
    
    # Initialize ffmpeg section if needed
    if "ffmpeg" not in config_data:
        config_data["ffmpeg"] = {}
    
    # Update all values
    if settings.ffmpeg_path is not None:
        config_data["ffmpeg"]["path"] = settings.ffmpeg_path
    if settings.ffprobe_path is not None:
        config_data["ffmpeg"]["ffprobe_path"] = settings.ffprobe_path
    if settings.log_level is not None:
        config_data["ffmpeg"]["log_level"] = settings.log_level
    if settings.threads is not None:
        config_data["ffmpeg"]["threads"] = settings.threads
    if settings.hwaccel_device is not None:
        config_data["ffmpeg"]["hwaccel_device"] = settings.hwaccel_device if settings.hwaccel_device else None
    if settings.extra_flags is not None:
        config_data["ffmpeg"]["extra_flags"] = settings.extra_flags if settings.extra_flags else None
    
    # Handle hardware acceleration
    if "hardware_acceleration" not in config_data["ffmpeg"]:
        config_data["ffmpeg"]["hardware_acceleration"] = {}
    
    if settings.hwaccel is not None:
        if settings.hwaccel == "":
            config_data["ffmpeg"]["hardware_acceleration"]["enabled"] = False
            config_data["ffmpeg"]["hardware_acceleration"]["preferred"] = ""
        else:
            config_data["ffmpeg"]["hardware_acceleration"]["enabled"] = True
            config_data["ffmpeg"]["hardware_acceleration"]["preferred"] = settings.hwaccel
    
    # Per-source overrides
    if settings.youtube_hwaccel is not None:
        config_data["ffmpeg"]["youtube_hwaccel"] = settings.youtube_hwaccel if settings.youtube_hwaccel else None
    if settings.archive_org_hwaccel is not None:
        config_data["ffmpeg"]["archive_org_hwaccel"] = settings.archive_org_hwaccel if settings.archive_org_hwaccel else None
    if settings.plex_hwaccel is not None:
        config_data["ffmpeg"]["plex_hwaccel"] = settings.plex_hwaccel if settings.plex_hwaccel else None
    if settings.youtube_video_encoder is not None:
        config_data["ffmpeg"]["youtube_video_encoder"] = settings.youtube_video_encoder if settings.youtube_video_encoder else None
    if settings.archive_org_video_encoder is not None:
        config_data["ffmpeg"]["archive_org_video_encoder"] = settings.archive_org_video_encoder if settings.archive_org_video_encoder else None
    if settings.plex_video_encoder is not None:
        config_data["ffmpeg"]["plex_video_encoder"] = settings.plex_video_encoder if settings.plex_video_encoder else None
    
    # Write back to file
    with open(config_path, "w") as f:
        yaml.safe_dump(config_data, f, sort_keys=False, default_flow_style=False, allow_unicode=True)
    
    return {"message": "FFmpeg settings saved successfully. Restart EXStreamTV to apply changes."}


@router.get("/hdhomerun")
async def get_hdhomerun_settings() -> HDHomeRunSettings:
    """Return current HDHomeRun settings.
    
    Returns:
        HDHomeRunSettings: Current HDHomeRun configuration
    """
    config = get_config()
    return HDHomeRunSettings(
        enabled=config.hdhomerun.enabled,
        device_id=config.hdhomerun.device_id,
        tuner_count=config.hdhomerun.tuner_count,
    )


@router.get("/server")
async def get_server_settings() -> ServerSettings:
    """Return current server settings.
    
    Returns:
        ServerSettings: Current server configuration
    """
    config = get_config()
    return ServerSettings(
        host=config.server.host,
        port=config.server.port,
        debug=config.server.debug,
        log_level=config.server.log_level,
    )


@router.get("/streaming")
async def get_streaming_settings() -> StreamingSettings:
    """Return current streaming settings.
    
    Returns:
        StreamingSettings: Current streaming configuration
    """
    config = get_config()
    return StreamingSettings(
        buffer_size=config.streaming.buffer_size,
        read_size=config.streaming.read_size,
    )


@router.get("/hdhr")
async def get_hdhr_settings() -> HDHomeRunSettings:
    """Return current HDHomeRun settings (alias).
    
    Returns:
        HDHomeRunSettings: Current HDHomeRun configuration
    """
    return await get_hdhomerun_settings()


class PlayoutSettings(BaseModel):
    """Playout settings response model."""
    days_to_build: int = 2
    rebuild_interval_hours: int = 24


@router.get("/playout")
async def get_playout_settings() -> PlayoutSettings:
    """Return current playout settings.
    
    Returns:
        PlayoutSettings: Current playout configuration
    """
    config = get_config()
    days = getattr(getattr(config, 'playout', None), 'days_to_build', 2)
    interval = getattr(getattr(config, 'playout', None), 'rebuild_interval_hours', 24)
    return PlayoutSettings(
        days_to_build=days,
        rebuild_interval_hours=interval,
    )


class PlexSettings(BaseModel):
    """Plex settings response model."""
    enabled: bool = False
    base_url: str = ""
    token: str = ""
    use_for_epg: bool = False


class PlexSettingsUpdate(BaseModel):
    """Plex settings update model."""
    enabled: Optional[bool] = None
    base_url: Optional[str] = None
    token: Optional[str] = None
    use_for_epg: Optional[bool] = None


@router.get("/plex")
async def get_plex_settings() -> PlexSettings:
    """Return current Plex settings.
    
    Returns:
        PlexSettings: Current Plex configuration
    """
    config = get_config()
    plex_config = getattr(config, 'plex', None)
    libraries_plex = getattr(getattr(config, 'libraries', None), 'plex', None)
    
    # Try both config locations (plex and libraries.plex)
    enabled = False
    base_url = ""
    token = ""
    use_for_epg = False
    
    if plex_config:
        enabled = getattr(plex_config, 'enabled', False)
        base_url = getattr(plex_config, 'url', '') or getattr(plex_config, 'base_url', '')
        token = getattr(plex_config, 'token', '')
        use_for_epg = getattr(plex_config, 'use_for_epg', False)
    
    if libraries_plex and not base_url:
        enabled = enabled or getattr(libraries_plex, 'enabled', False)
        base_url = getattr(libraries_plex, 'url', '') or base_url
        token = getattr(libraries_plex, 'token', '') or token
    
    return PlexSettings(
        enabled=enabled,
        base_url=base_url,
        token=token,
        use_for_epg=use_for_epg,
    )


@router.put("/plex")
async def update_plex_settings(settings: PlexSettingsUpdate):
    """Update Plex settings.
    
    Args:
        settings: New Plex settings to apply
        
    Returns:
        dict: Success message
    """
    import yaml
    
    # Load existing config
    config_path = Path("config.yaml")
    if config_path.exists():
        with open(config_path) as f:
            config_data = yaml.safe_load(f) or {}
    else:
        config_data = {}
    
    # Initialize plex section if needed
    if "plex" not in config_data:
        config_data["plex"] = {}
    
    # Also update libraries.plex for compatibility
    if "libraries" not in config_data:
        config_data["libraries"] = {}
    if "plex" not in config_data["libraries"]:
        config_data["libraries"]["plex"] = {}
    
    # Update values
    if settings.enabled is not None:
        config_data["plex"]["enabled"] = settings.enabled
        config_data["libraries"]["plex"]["enabled"] = settings.enabled
    if settings.base_url is not None:
        config_data["plex"]["url"] = settings.base_url
        config_data["libraries"]["plex"]["url"] = settings.base_url
    if settings.token is not None:
        config_data["plex"]["token"] = settings.token
        config_data["libraries"]["plex"]["token"] = settings.token
    if settings.use_for_epg is not None:
        config_data["plex"]["use_for_epg"] = settings.use_for_epg
    
    # Write back to file
    with open(config_path, "w") as f:
        yaml.safe_dump(config_data, f, sort_keys=False, default_flow_style=False, allow_unicode=True)
    
    # Reload config to pick up new settings immediately
    from exstreamtv.config import reload_config
    reload_config()
    
    return {"message": "Plex settings saved successfully"}


@router.post("/plex/test")
async def test_plex_connection():
    """Test connection to Plex server.
    
    Returns:
        dict: Connection test result
    """
    import httpx
    
    config = get_config()
    plex_config = getattr(config, 'plex', None)
    libraries_plex = getattr(getattr(config, 'libraries', None), 'plex', None)
    
    # Get URL and token from config
    base_url = ""
    token = ""
    
    if plex_config:
        base_url = getattr(plex_config, 'url', '') or getattr(plex_config, 'base_url', '')
        token = getattr(plex_config, 'token', '')
    
    if libraries_plex and not base_url:
        base_url = getattr(libraries_plex, 'url', '') or base_url
        token = getattr(libraries_plex, 'token', '') or token
    
    if not base_url or not token:
        return {
            "success": False,
            "error": "Plex server URL or token not configured. Please save settings first."
        }
    
    try:
        # Test connection to Plex server
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {
                "X-Plex-Token": token,
                "Accept": "application/json"
            }
            response = await client.get(f"{base_url.rstrip('/')}/", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                media_container = data.get("MediaContainer", {})
                
                # Try to get DVR count
                dvrs_count = 0
                try:
                    dvr_response = await client.get(f"{base_url.rstrip('/')}/livetv/dvrs", headers=headers)
                    if dvr_response.status_code == 200:
                        dvr_data = dvr_response.json()
                        dvrs_count = len(dvr_data.get("MediaContainer", {}).get("Dvr", []))
                except Exception:
                    pass
                
                return {
                    "success": True,
                    "server_info": {
                        "friendlyName": media_container.get("friendlyName", "Unknown"),
                        "version": media_container.get("version", "Unknown"),
                        "machineIdentifier": media_container.get("machineIdentifier", ""),
                    },
                    "dvrs_count": dvrs_count
                }
            else:
                return {
                    "success": False,
                    "error": f"Plex server returned status {response.status_code}"
                }
    except httpx.ConnectError:
        return {
            "success": False,
            "error": f"Could not connect to Plex server at {base_url}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/plex/reload-guide")
async def reload_plex_guide():
    """Tell Plex DVR to reload the program guide (e.g. after EPG changes). Safe to call; returns success/error."""
    from ..streaming.plex_api_client import request_plex_guide_reload
    ok = await request_plex_guide_reload(force=True)
    if ok:
        return {"success": True, "message": "Plex guide reload requested."}
    return {"success": False, "error": "Plex not configured or reload failed. Check server URL and token."}


@router.get("/plex/test-channel/{channel_id}")
async def test_plex_channel(channel_id: int):
    """Test Plex URL resolution for a specific channel.
    
    Resolves the first media item's URL and tests if it's accessible.
    
    Args:
        channel_id: The channel ID to test
        
    Returns:
        dict: Test result with URL info
    """
    import httpx
    from sqlalchemy import select
    from ..database import get_sync_session
    from ..database.models import Channel, Playout, PlayoutItem, MediaItem
    
    result = {
        "channel_id": channel_id,
        "success": False,
        "steps": []
    }
    
    session = get_sync_session()
    try:
        # Step 1: Get channel
        channel = session.query(Channel).filter(Channel.id == channel_id).first()
        if not channel:
            result["error"] = f"Channel {channel_id} not found"
            return result
        result["steps"].append(f"Found channel: {channel.name} (#{channel.number})")
        
        # Step 2: Get active playout
        playout = session.query(Playout).filter(
            Playout.channel_id == channel_id,
            Playout.is_active == True
        ).first()
        if not playout:
            result["error"] = "No active playout for channel"
            return result
        result["steps"].append(f"Found active playout: {playout.id}")
        
        # Step 3: Get first playout item with media
        stmt = select(PlayoutItem, MediaItem).outerjoin(
            MediaItem, PlayoutItem.media_item_id == MediaItem.id
        ).where(
            PlayoutItem.playout_id == playout.id
        ).order_by(PlayoutItem.start_time).limit(1)
        
        items_result = session.execute(stmt)
        row = items_result.first()
        
        if not row:
            result["error"] = "No playout items found"
            return result
        
        playout_item, media_item = row
        result["steps"].append(f"Found playout item: {playout_item.title or 'untitled'}")
        
        if not media_item:
            result["error"] = "Playout item has no associated media"
            result["source_url"] = playout_item.source_url
            return result
        
        result["media_item"] = {
            "id": media_item.id,
            "title": media_item.title,
            "source": str(media_item.source),
            "url": media_item.url[:100] + "..." if media_item.url and len(media_item.url) > 100 else media_item.url,
        }
        result["steps"].append(f"Media item: {media_item.title} (source: {media_item.source})")
        
        # Step 4: Try to resolve URL
        try:
            from ..streaming.url_resolver import get_url_resolver
            resolver = get_url_resolver()
            resolved = await resolver.resolve(media_item, force_refresh=True)
            
            result["resolved_url"] = resolved.url[:150] + "..." if len(resolved.url) > 150 else resolved.url
            result["expires_at"] = str(resolved.expires_at) if resolved.expires_at else None
            result["steps"].append(f"URL resolved successfully")
            
            # Step 5: Test if URL is accessible
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                try:
                    head_resp = await client.head(
                        resolved.url,
                        headers=resolved.headers or {}
                    )
                    result["http_status"] = head_resp.status_code
                    result["content_length"] = head_resp.headers.get("content-length")
                    result["content_type"] = head_resp.headers.get("content-type")
                    
                    if head_resp.status_code == 200:
                        result["success"] = True
                        result["steps"].append(f"URL accessible: HTTP {head_resp.status_code}")
                    else:
                        result["steps"].append(f"URL returned: HTTP {head_resp.status_code}")
                        result["error"] = f"HTTP {head_resp.status_code}"
                except Exception as e:
                    result["steps"].append(f"URL test failed: {str(e)}")
                    result["error"] = f"Connection error: {str(e)}"
                    
        except Exception as e:
            result["steps"].append(f"URL resolution failed: {str(e)}")
            result["error"] = f"Resolution error: {str(e)}"
        
        return result
        
    except Exception as e:
        result["error"] = str(e)
        return result
    finally:
        session.close()


@router.post("/plex/refresh-urls")
async def refresh_plex_urls():
    """Refresh all Plex media URLs.
    
    Clears the URL cache for Plex items and forces re-resolution
    of all Plex media URLs on next access.
    
    Returns:
        dict: Refresh operation result
    """
    import logging
    from sqlalchemy import select, update
    from ..database import get_sync_session
    from ..database.models import MediaItem
    
    logger = logging.getLogger(__name__)
    
    stats = {
        "urls_cleared": 0,
        "cache_cleared": False,
        "errors": []
    }
    
    try:
        # 1. Clear the URL resolver cache for Plex items
        try:
            from ..streaming.url_resolver import get_url_resolver
            resolver = get_url_resolver()
            
            # Clear Plex entries from global cache
            plex_keys_to_remove = []
            for key in list(resolver._global_cache.keys()):
                if "plex" in key.lower():
                    plex_keys_to_remove.append(key)
            
            for key in plex_keys_to_remove:
                del resolver._global_cache[key]
                stats["urls_cleared"] += 1
            
            stats["cache_cleared"] = True
            logger.info(f"Cleared {len(plex_keys_to_remove)} Plex URLs from resolver cache")
        except Exception as e:
            stats["errors"].append(f"Cache clear error: {str(e)}")
            logger.warning(f"Error clearing URL cache: {e}")
        
        # 2. Optionally clear cached URLs in database (if stored there)
        try:
            session = get_sync_session()
            
            # Update media items with Plex source to clear any cached URLs
            # This forces re-resolution on next access
            stmt = select(MediaItem).where(
                MediaItem.source.ilike("%plex%")
            )
            result = session.execute(stmt)
            plex_items = result.scalars().all()
            
            for item in plex_items:
                # Clear any cached/resolved URL fields if they exist
                if hasattr(item, 'resolved_url'):
                    item.resolved_url = None
                if hasattr(item, 'url_expires_at'):
                    item.url_expires_at = None
            
            session.commit()
            logger.info(f"Found {len(plex_items)} Plex media items")
            session.close()
        except Exception as e:
            stats["errors"].append(f"Database update error: {str(e)}")
            logger.warning(f"Error updating database: {e}")
        
        return {
            "success": True,
            "message": f"Refreshed {stats['urls_cleared']} Plex URLs. URLs will be re-resolved on next playback.",
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"Error refreshing Plex URLs: {e}")
        return {
            "success": False,
            "error": str(e),
            "stats": stats
        }


# =============================================================================
# Plex OAuth Sign-in
# =============================================================================

@router.get("/plex/oauth/pin")
async def get_plex_oauth_pin():
    """Get a Plex PIN for OAuth authentication.
    
    User should visit https://plex.tv/link and enter the PIN code.
    Then poll /settings/plex/oauth/poll with the pin_id.
    
    Returns:
        dict: Contains pin_id, pin_code, and auth_url
    """
    import httpx
    
    headers = {
        "Accept": "application/json",
        "X-Plex-Product": "EXStreamTV",
        "X-Plex-Version": "2.0.0",
        "X-Plex-Client-Identifier": "exstreamtv-oauth",
        "X-Plex-Platform": "EXStreamTV",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://plex.tv/api/v2/pins",
                headers=headers,
                data={"strong": "true"},
            )
            
            if response.status_code != 201:
                return {
                    "success": False,
                    "error": f"Failed to get PIN: {response.status_code}"
                }
            
            data = response.json()
            return {
                "success": True,
                "pin_id": data["id"],
                "pin_code": data["code"],
                "auth_url": f"https://app.plex.tv/auth#?clientID=exstreamtv-oauth&code={data['code']}&context%5Bdevice%5D%5Bproduct%5D=EXStreamTV",
                "expires_at": data.get("expiresAt"),
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/plex/oauth/poll/{pin_id}")
async def poll_plex_oauth(pin_id: int):
    """Poll for Plex OAuth completion.
    
    Call this periodically after user visits plex.tv/link.
    
    Args:
        pin_id: The PIN ID from /settings/plex/oauth/pin
        
    Returns:
        dict: Contains auth_token if completed, or waiting status
    """
    import httpx
    
    headers = {
        "Accept": "application/json",
        "X-Plex-Client-Identifier": "exstreamtv-oauth",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"https://plex.tv/api/v2/pins/{pin_id}",
                headers=headers,
            )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Failed to poll PIN: {response.status_code}"
                }
            
            data = response.json()
            
            if data.get("authToken"):
                # User completed auth!
                return {
                    "success": True,
                    "completed": True,
                    "auth_token": data["authToken"],
                    "message": "Authentication successful! Token obtained."
                }
            else:
                return {
                    "success": True,
                    "completed": False,
                    "message": "Waiting for user to authenticate..."
                }
                
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/plex/oauth/discover")
async def discover_plex_servers(auth_token: str = None):
    """Discover Plex servers available to the authenticated user.
    
    After OAuth, use this to find the user's Plex servers.
    
    Args:
        auth_token: Optional token (uses config if not provided)
        
    Returns:
        dict: List of available servers with connection details
    """
    import httpx
    
    config = get_config()
    token = auth_token or getattr(config.plex, "token", None)
    
    if not token:
        return {"success": False, "error": "No auth token provided"}
    
    headers = {
        "Accept": "application/json",
        "X-Plex-Token": token,
        "X-Plex-Client-Identifier": "exstreamtv-oauth",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                "https://plex.tv/api/v2/resources",
                headers=headers,
                params={"includeHttps": 1, "includeRelay": 0},
            )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Failed to get resources: {response.status_code}"
                }
            
            resources = response.json()
            servers = []
            
            for resource in resources:
                if resource.get("provides") == "server":
                    connections = resource.get("connections", [])
                    # Prefer local connections
                    local_conns = [c for c in connections if c.get("local")]
                    remote_conns = [c for c in connections if not c.get("local")]
                    
                    best_conn = (local_conns + remote_conns)[0] if connections else None
                    
                    servers.append({
                        "name": resource.get("name"),
                        "product": resource.get("product"),
                        "clientIdentifier": resource.get("clientIdentifier"),
                        "accessToken": resource.get("accessToken"),
                        "connection": {
                            "uri": best_conn.get("uri") if best_conn else None,
                            "local": best_conn.get("local") if best_conn else None,
                        } if best_conn else None,
                        "allConnections": [
                            {"uri": c.get("uri"), "local": c.get("local")}
                            for c in connections
                        ],
                    })
            
            return {
                "success": True,
                "servers": servers,
                "message": f"Found {len(servers)} Plex server(s)"
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Plex Library Rebuild
# =============================================================================

@router.get("/plex/libraries")
async def list_plex_libraries():
    """List all Plex libraries with item counts.
    
    Returns:
        dict: List of Plex libraries
    """
    import httpx
    from sqlalchemy import func
    from ..database import get_sync_session
    from ..database.models import MediaItem
    
    config = get_config()
    plex_url = getattr(config.plex, "url", None) or getattr(config.plex, "base_url", None)
    plex_token = getattr(config.plex, "token", None)
    
    if not plex_url or not plex_token:
        return {
            "success": False,
            "error": "Plex not configured. Please set URL and token in settings."
        }
    
    headers = {
        "Accept": "application/json",
        "X-Plex-Token": plex_token,
    }
    
    # Get existing item counts from database
    session = get_sync_session()
    existing_counts = {}
    try:
        counts = session.query(
            MediaItem.plex_library_section_id,
            func.count()
        ).filter(
            MediaItem.plex_library_section_id.isnot(None)
        ).group_by(MediaItem.plex_library_section_id).all()
        
        for lib_id, count in counts:
            existing_counts[str(lib_id)] = count
    except Exception:
        pass
    finally:
        session.close()
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{plex_url.rstrip('/')}/library/sections",
                headers=headers,
            )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Failed to get libraries: {response.status_code}"
                }
            
            data = response.json()
            libraries = []
            
            for lib in data.get("MediaContainer", {}).get("Directory", []):
                lib_key = lib.get("key")
                libraries.append({
                    "key": lib_key,
                    "title": lib.get("title"),
                    "type": lib.get("type"),  # movie, show, artist, photo
                    "agent": lib.get("agent"),
                    "scanner": lib.get("scanner"),
                    "uuid": lib.get("uuid"),
                    "imported_count": existing_counts.get(str(lib_key), 0),
                })
            
            return {
                "success": True,
                "libraries": libraries,
                "server_url": plex_url,
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/plex/scan-library/{library_key}")
async def scan_plex_library(library_key: str):
    """Scan a specific Plex library and import media items.
    
    Args:
        library_key: The Plex library key to scan
        
    Returns:
        dict: Scan result with import counts
    """
    import logging
    import httpx
    from ..database import get_sync_session
    from ..database.models import MediaItem
    
    logger = logging.getLogger(__name__)
    config = get_config()
    plex_url = getattr(config.plex, "url", None) or getattr(config.plex, "base_url", None)
    plex_token = getattr(config.plex, "token", None)
    
    if not plex_url or not plex_token:
        return {
            "success": False,
            "error": "Plex not configured"
        }
    
    headers = {
        "Accept": "application/json",
        "X-Plex-Token": plex_token,
    }
    
    items_imported = 0
    items_skipped = 0
    
    session = get_sync_session()
    
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            # Get library info
            lib_response = await client.get(
                f"{plex_url.rstrip('/')}/library/sections/{library_key}",
                headers=headers,
            )
            
            if lib_response.status_code != 200:
                return {"success": False, "error": f"Failed to get library info: {lib_response.status_code}"}
            
            lib_data = lib_response.json()
            library_info = lib_data.get("MediaContainer", {}).get("Directory", [{}])[0]
            library_title = library_info.get("title", "Unknown")
            library_type = library_info.get("type", "movie")
            
            logger.info(f"Scanning Plex library: {library_title} (type: {library_type})")
            
            # Get all items from library
            items_response = await client.get(
                f"{plex_url.rstrip('/')}/library/sections/{library_key}/all",
                headers=headers,
            )
            
            if items_response.status_code != 200:
                return {"success": False, "error": f"Failed to get library items: {items_response.status_code}"}
            
            items_data = items_response.json()
            items = items_data.get("MediaContainer", {}).get("Metadata", [])
            
            for item in items:
                rating_key = str(item.get("ratingKey", ""))
                
                if library_type == "show":
                    # For TV shows, fetch all episodes
                    episodes_response = await client.get(
                        f"{plex_url.rstrip('/')}/library/metadata/{rating_key}/allLeaves",
                        headers=headers,
                    )
                    
                    if episodes_response.status_code == 200:
                        episodes_data = episodes_response.json()
                        episodes = episodes_data.get("MediaContainer", {}).get("Metadata", [])
                        show_title = item.get("title", "Unknown Show")
                        
                        for episode in episodes:
                            ep_rating_key = str(episode.get("ratingKey", ""))
                            
                            # Check if already exists
                            existing = session.query(MediaItem).filter(
                                MediaItem.plex_rating_key == ep_rating_key
                            ).first()
                            
                            if existing:
                                items_skipped += 1
                                continue
                            
                            # Get duration from Media array
                            duration = episode.get("duration")
                            if not duration:
                                media_list = episode.get("Media", [])
                                if media_list:
                                    duration = media_list[0].get("duration")
                            
                            media_item = MediaItem(
                                title=episode.get("title", "Unknown Episode"),
                                media_type="episode",
                                source="plex",
                                show_title=show_title,
                                season_number=episode.get("parentIndex"),
                                episode_number=episode.get("index"),
                                duration=int(duration / 1000) if duration else None,
                                description=episode.get("summary"),
                                year=episode.get("year"),
                                thumbnail=episode.get("thumb"),
                                plex_rating_key=ep_rating_key,
                                plex_guid=episode.get("guid"),
                                plex_library_section_id=library_key,
                                plex_library_section_title=library_title,
                            )
                            session.add(media_item)
                            items_imported += 1
                else:
                    # Movies
                    # Check if already exists
                    existing = session.query(MediaItem).filter(
                        MediaItem.plex_rating_key == rating_key
                    ).first()
                    
                    if existing:
                        items_skipped += 1
                        continue
                    
                    # Get duration from Media array
                    duration = item.get("duration")
                    if not duration:
                        media_list = item.get("Media", [])
                        if media_list:
                            duration = media_list[0].get("duration")
                    
                    media_item = MediaItem(
                        title=item.get("title", "Unknown"),
                        media_type="movie",
                        source="plex",
                        duration=int(duration / 1000) if duration else None,
                        description=item.get("summary"),
                        year=item.get("year"),
                        thumbnail=item.get("thumb"),
                        plex_rating_key=rating_key,
                        plex_guid=item.get("guid"),
                        plex_library_section_id=library_key,
                        plex_library_section_title=library_title,
                    )
                    session.add(media_item)
                    items_imported += 1
                
                # Commit in batches
                if items_imported > 0 and items_imported % 100 == 0:
                    session.commit()
                    logger.info(f"Imported {items_imported} items so far...")
            
            session.commit()
            logger.info(f"Scan complete: {items_imported} imported, {items_skipped} skipped")
            
            return {
                "success": True,
                "library": library_title,
                "library_type": library_type,
                "items_imported": items_imported,
                "items_skipped": items_skipped,
            }
            
    except Exception as e:
        session.rollback()
        logger.error(f"Error scanning library: {e}")
        return {"success": False, "error": str(e)}
    finally:
        session.close()


@router.post("/plex/fix-library-ids")
async def fix_plex_library_ids():
    """Fix library_id for existing Plex media items.
    
    Maps MediaItem.plex_library_section_id to PlexLibrary.plex_library_key
    and updates MediaItem.library_id accordingly.
    
    Returns:
        dict: Summary of items updated
    """
    import traceback
    
    try:
        from ..database import get_sync_session
        from ..database.models import MediaItem
        from ..database.models.library import PlexLibrary
    except Exception as e:
        return {"success": False, "error": f"Import error: {str(e)}", "traceback": traceback.format_exc()}
    
    try:
        session = get_sync_session()
    except Exception as e:
        return {"success": False, "error": f"Session error: {str(e)}", "traceback": traceback.format_exc()}
    
    try:
        # Get all PlexLibrary records
        plex_libraries = session.query(PlexLibrary).all()
        
        # Build mapping: plex_library_key (as int) -> PlexLibrary.id
        key_to_id = {}
        for lib in plex_libraries:
            try:
                # plex_library_key is stored as string, plex_library_section_id as int
                key_to_id[int(lib.plex_library_key)] = lib.id
                logger.info(f"Mapping: plex_library_key={lib.plex_library_key} -> library_id={lib.id} ({lib.plex_library_name})")
            except (ValueError, TypeError):
                logger.warning(f"Could not parse plex_library_key for library {lib.id}: {lib.plex_library_key}")
        
        logger.info(f"Found {len(key_to_id)} Plex library mappings")
        
        # Query all Plex media items with NULL library_id
        items = session.query(MediaItem).filter(
            MediaItem.source == "plex",
            MediaItem.library_id == None,
            MediaItem.plex_library_section_id != None
        ).all()
        
        logger.info(f"Found {len(items)} Plex media items with NULL library_id")
        
        # Update each item
        total_updated = 0
        for item in items:
            section_id = item.plex_library_section_id
            if section_id in key_to_id:
                item.library_id = key_to_id[section_id]
                total_updated += 1
        
        session.commit()
        
        logger.info(f"Fix complete: updated {total_updated} media items")
        
        return {
            "success": True,
            "items_checked": len(items),
            "items_updated": total_updated,
            "library_mappings": {str(k): v for k, v in key_to_id.items()},
        }
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error fixing library IDs: {e}")
        import traceback
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}
    finally:
        session.close()


@router.get("/plex/preview-filter")
async def preview_filter(
    title: str = None,
    type: str = None,
    genre: str = None,
    year: str = None,
    show_title: str = None,
):
    """Preview how many media items match the given filters.
    
    Returns:
        dict: Count of matching items and sample titles
    """
    from sqlalchemy import and_
    from ..database import get_sync_session
    from ..database.models import MediaItem
    
    session = get_sync_session()
    
    try:
        # Build filter conditions
        conditions = [MediaItem.source.ilike("%plex%")]
        
        if type:
            conditions.append(MediaItem.media_type == type)
        
        if genre:
            conditions.append(MediaItem.genres.ilike(f"%{genre}%"))
        
        if year:
            if "-" in year:
                start, end = year.split("-")
                conditions.append(and_(
                    MediaItem.year >= int(start),
                    MediaItem.year <= int(end)
                ))
            else:
                conditions.append(MediaItem.year == int(year))
        
        if title:
            conditions.append(MediaItem.title.ilike(f"%{title}%"))
        
        if show_title:
            conditions.append(MediaItem.show_title.ilike(f"%{show_title}%"))
        
        # Get count and samples
        query = session.query(MediaItem).filter(and_(*conditions))
        count = query.count()
        samples = [item.title for item in query.limit(5).all()]
        
        return {
            "success": True,
            "count": count,
            "samples": samples,
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        session.close()


@router.post("/plex/rebuild-playlist/{playlist_id}")
async def rebuild_playlist_from_plex(
    playlist_id: int,
    library_key: str = None,
    filter_type: str = None,  # "movie", "episode", etc.
    filter_genre: str = None,
    filter_year: str = None,  # "1980-1999" or "2020"
    filter_title: str = None,  # Title contains
    filter_show_title: str = None,  # TV show title contains
    clear_existing: bool = True,
):
    """Rebuild a playlist from Plex library content.
    
    Args:
        playlist_id: The playlist to populate
        library_key: Plex library key (optional, uses all if not specified)
        filter_type: Filter by content type
        filter_genre: Filter by genre (contains)
        filter_year: Filter by year (exact or range like "1980-1999")
        filter_title: Filter by title (contains)
        clear_existing: Clear existing items before adding
        
    Returns:
        dict: Rebuild result with item counts
    """
    import logging
    from sqlalchemy import and_
    from ..database import get_sync_session
    from ..database.models import Playlist, PlaylistItem, MediaItem
    
    logger = logging.getLogger(__name__)
    session = get_sync_session()
    
    try:
        # Get playlist
        playlist = session.query(Playlist).filter(Playlist.id == playlist_id).first()
        if not playlist:
            return {"success": False, "error": f"Playlist {playlist_id} not found"}
        
        # Build filter conditions
        conditions = [MediaItem.source.ilike("%plex%")]
        
        if filter_type:
            conditions.append(MediaItem.media_type == filter_type)
        
        if filter_genre:
            # Genres stored as JSON array or comma-separated
            conditions.append(MediaItem.genres.ilike(f"%{filter_genre}%"))
        
        if filter_year:
            if "-" in filter_year:
                start, end = filter_year.split("-")
                conditions.append(and_(
                    MediaItem.year >= int(start),
                    MediaItem.year <= int(end)
                ))
            else:
                conditions.append(MediaItem.year == int(filter_year))
        
        if filter_title:
            conditions.append(MediaItem.title.ilike(f"%{filter_title}%"))
        
        if filter_show_title:
            conditions.append(MediaItem.show_title.ilike(f"%{filter_show_title}%"))
        
        # Get matching media items
        media_items = session.query(MediaItem).filter(and_(*conditions)).all()
        
        if not media_items:
            return {
                "success": False,
                "error": "No matching media items found"
            }
        
        # Clear existing items if requested
        items_removed = 0
        if clear_existing:
            items_removed = session.query(PlaylistItem).filter(
                PlaylistItem.playlist_id == playlist_id
            ).delete()
            session.flush()
        
        # Add new items
        items_added = 0
        for i, media in enumerate(media_items):
            item = PlaylistItem(
                playlist_id=playlist_id,
                media_item_id=media.id,
                title=media.title,
                duration_seconds=media.duration,
                thumbnail_url=media.thumbnail,
                position=i + 1,
                is_enabled=True,
            )
            session.add(item)
            items_added += 1
        
        session.commit()
        
        logger.info(f"Rebuilt playlist {playlist.name}: removed {items_removed}, added {items_added}")
        
        return {
            "success": True,
            "playlist_name": playlist.name,
            "items_removed": items_removed,
            "items_added": items_added,
            "message": f"Playlist '{playlist.name}' rebuilt with {items_added} items"
        }
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error rebuilding playlist: {e}")
        return {"success": False, "error": str(e)}
    finally:
        session.close()


@router.post("/plex/auto-populate-playlists")
async def auto_populate_playlists():
    """Auto-populate empty playlists from Plex media based on name matching.
    
    Attempts to find media items that match playlist names (by title keywords)
    and populate the playlists.
    
    Returns:
        dict: Summary of populated playlists
    """
    import logging
    from sqlalchemy import func
    from ..database import get_sync_session
    from ..database.models import Playlist, PlaylistItem, MediaItem
    
    logger = logging.getLogger(__name__)
    session = get_sync_session()
    
    results = {
        "success": True,
        "playlists_processed": 0,
        "playlists_populated": 0,
        "total_items_added": 0,
        "details": []
    }
    
    try:
        # Find empty playlists
        empty_playlists = session.query(Playlist).outerjoin(
            PlaylistItem, Playlist.id == PlaylistItem.playlist_id
        ).group_by(Playlist.id).having(func.count(PlaylistItem.id) == 0).all()
        
        for playlist in empty_playlists:
            results["playlists_processed"] += 1
            
            # Try to find matching media based on playlist name
            # Common patterns: "Disney Afternoon" -> search for Disney titles
            # "Bluey" -> search for Bluey show
            # "Comedy Movies" -> search for comedy genre
            
            search_terms = playlist.name.lower().split()
            items_added = 0
            
            # Try exact title match first
            media_items = session.query(MediaItem).filter(
                MediaItem.source.ilike("%plex%"),
                MediaItem.title.ilike(f"%{playlist.name}%")
            ).limit(500).all()
            
            # If no exact match, try search terms
            if not media_items:
                for term in search_terms:
                    if len(term) >= 4:  # Skip short words
                        media_items = session.query(MediaItem).filter(
                            MediaItem.source.ilike("%plex%"),
                            MediaItem.title.ilike(f"%{term}%")
                        ).limit(500).all()
                        if media_items:
                            break
            
            # Add items to playlist
            for i, media in enumerate(media_items):
                item = PlaylistItem(
                    playlist_id=playlist.id,
                    media_item_id=media.id,
                    title=media.title,
                    duration_seconds=media.duration,
                    thumbnail_url=media.thumbnail,
                    position=i + 1,
                    is_enabled=True,
                )
                session.add(item)
                items_added += 1
            
            if items_added > 0:
                results["playlists_populated"] += 1
                results["total_items_added"] += items_added
                results["details"].append({
                    "playlist": playlist.name,
                    "items_added": items_added,
                })
                logger.info(f"Populated playlist '{playlist.name}' with {items_added} items")
        
        session.commit()
        
        results["message"] = f"Populated {results['playlists_populated']} of {results['playlists_processed']} empty playlists"
        return results
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error auto-populating playlists: {e}")
        return {"success": False, "error": str(e)}
    finally:
        session.close()


@router.post("/plex/rebuild-channel-playout/{channel_id}")
async def rebuild_channel_playout(channel_id: int):
    """Rebuild a channel's playout from its schedule/playlist.
    
    This creates new PlayoutItems from the channel's configured schedule.
    
    Args:
        channel_id: The channel to rebuild
        
    Returns:
        dict: Rebuild result
    """
    import logging
    from datetime import datetime, timedelta
    from ..database import get_sync_session
    from ..database.models import Channel, Playout, PlayoutItem, ProgramSchedule, ProgramScheduleItem, Playlist, PlaylistItem
    
    logger = logging.getLogger(__name__)
    session = get_sync_session()
    
    try:
        # Get channel
        channel = session.query(Channel).filter(Channel.id == channel_id).first()
        if not channel:
            return {"success": False, "error": f"Channel {channel_id} not found"}
        
        # Get active playout
        playout = session.query(Playout).filter(
            Playout.channel_id == channel_id,
            Playout.is_active == True
        ).first()
        
        if not playout:
            return {"success": False, "error": "No active playout for channel"}
        
        # Clear existing playout items
        items_removed = session.query(PlayoutItem).filter(
            PlayoutItem.playout_id == playout.id
        ).delete()
        session.flush()
        
        # Get schedule
        schedule = None
        if hasattr(playout, 'program_schedule_id') and playout.program_schedule_id:
            schedule = session.query(ProgramSchedule).filter(
                ProgramSchedule.id == playout.program_schedule_id
            ).first()
        
        items_added = 0
        current_time = datetime.now()
        
        if schedule:
            # Get schedule items
            schedule_items = session.query(ProgramScheduleItem).filter(
                ProgramScheduleItem.schedule_id == schedule.id
            ).order_by(ProgramScheduleItem.position).all()
            
            for sched_item in schedule_items:
                # Get playlist/collection items
                if sched_item.collection_id:
                    playlist_items = session.query(PlaylistItem).filter(
                        PlaylistItem.playlist_id == sched_item.collection_id
                    ).order_by(PlaylistItem.position).all()
                    
                    for pl_item in playlist_items:
                        duration = pl_item.duration_seconds or 1800
                        finish_time = current_time + timedelta(seconds=duration)
                        playout_item = PlayoutItem(
                            playout_id=playout.id,
                            media_item_id=pl_item.media_item_id,
                            title=pl_item.title,
                            start_time=current_time,
                            finish_time=finish_time,
                            source_url=pl_item.source_url,
                        )
                        session.add(playout_item)
                        current_time = finish_time
                        items_added += 1
        
        # If no schedule or empty schedule, try to use playlist name matching
        if items_added == 0:
            # Find playlist by channel name
            playlist = session.query(Playlist).filter(
                Playlist.name.ilike(f"%{channel.name}%")
            ).first()
            
            if playlist:
                playlist_items = session.query(PlaylistItem).filter(
                    PlaylistItem.playlist_id == playlist.id
                ).order_by(PlaylistItem.position).all()
                
                for pl_item in playlist_items:
                    duration = pl_item.duration_seconds or 1800
                    finish_time = current_time + timedelta(seconds=duration)
                    playout_item = PlayoutItem(
                        playout_id=playout.id,
                        media_item_id=pl_item.media_item_id,
                        title=pl_item.title,
                        start_time=current_time,
                        finish_time=finish_time,
                        source_url=pl_item.source_url,
                    )
                    session.add(playout_item)
                    current_time = finish_time
                    items_added += 1
        
        session.commit()
        
        logger.info(f"Rebuilt channel {channel.name} playout: removed {items_removed}, added {items_added}")
        
        return {
            "success": True,
            "channel_name": channel.name,
            "items_removed": items_removed,
            "items_added": items_added,
            "message": f"Channel '{channel.name}' playout rebuilt with {items_added} items"
        }
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error rebuilding channel playout: {e}")
        return {"success": False, "error": str(e)}
    finally:
        session.close()


@router.post("/plex/rebuild-all-playouts")
async def rebuild_all_playouts():
    """Rebuild all channel playouts.
    
    Iterates through all channels and rebuilds their playouts.
    
    Returns:
        dict: Summary of rebuilt channels
    """
    import logging
    from ..database import get_sync_session
    from ..database.models import Channel
    
    logger = logging.getLogger(__name__)
    session = get_sync_session()
    
    results = {
        "success": True,
        "channels_processed": 0,
        "channels_rebuilt": 0,
        "total_items_added": 0,
        "details": []
    }
    
    try:
        channels = session.query(Channel).all()
        session.close()
        
        for channel in channels:
            results["channels_processed"] += 1
            
            # Rebuild each channel (reuses the single channel rebuild)
            result = await rebuild_channel_playout(channel.id)
            
            if result.get("success") and result.get("items_added", 0) > 0:
                results["channels_rebuilt"] += 1
                results["total_items_added"] += result.get("items_added", 0)
                results["details"].append({
                    "channel": channel.name,
                    "items_added": result.get("items_added", 0),
                })
        
        results["message"] = f"Rebuilt {results['channels_rebuilt']} of {results['channels_processed']} channels"
        return results
        
    except Exception as e:
        logger.error(f"Error rebuilding all playouts: {e}")
        return {"success": False, "error": str(e)}


@router.post("/plex/cleanup-duplicates")
async def cleanup_duplicate_media():
    """Remove duplicate media items, keeping the best version.
    
    Best version = has plex_rating_key and artwork.
    Updates playlist items to point to the best version before deleting duplicates.
    
    Returns:
        dict: Cleanup statistics
    """
    import logging
    from sqlalchemy import func
    from ..database import get_sync_session
    from ..database.models import MediaItem, PlaylistItem, PlayoutItem
    
    logger = logging.getLogger(__name__)
    session = get_sync_session()
    
    stats = {
        "duplicates_found": 0,
        "items_deleted": 0,
        "playlist_items_updated": 0,
        "playout_items_updated": 0,
        "errors": [],
    }
    
    try:
        # Find duplicate titles
        duplicate_titles = session.query(
            MediaItem.title
        ).group_by(MediaItem.title).having(func.count() > 1).all()
        
        stats["duplicates_found"] = len(duplicate_titles)
        logger.info(f"Found {len(duplicate_titles)} titles with duplicates")
        
        for (title,) in duplicate_titles:
            # Get all items with this title
            items = session.query(MediaItem).filter(MediaItem.title == title).all()
            
            if len(items) <= 1:
                continue
            
            # Score each item: rating_key=10, artwork=5, duration=2
            def score_item(item):
                score = 0
                if item.plex_rating_key:
                    score += 10
                if item.thumbnail or item.poster_path:
                    score += 5
                if item.duration:
                    score += 2
                return score
            
            # Sort by score descending, keep the best
            items_sorted = sorted(items, key=score_item, reverse=True)
            best_item = items_sorted[0]
            duplicates_to_delete = items_sorted[1:]
            
            # Update playlist items to point to best item
            for dup in duplicates_to_delete:
                # Update PlaylistItems
                updated = session.query(PlaylistItem).filter(
                    PlaylistItem.media_item_id == dup.id
                ).update({PlaylistItem.media_item_id: best_item.id})
                stats["playlist_items_updated"] += updated
                
                # Update PlayoutItems
                updated = session.query(PlayoutItem).filter(
                    PlayoutItem.media_item_id == dup.id
                ).update({PlayoutItem.media_item_id: best_item.id})
                stats["playout_items_updated"] += updated
                
                # Delete the duplicate
                session.delete(dup)
                stats["items_deleted"] += 1
            
            # Commit in batches
            if stats["items_deleted"] % 100 == 0:
                session.commit()
                logger.info(f"Deleted {stats['items_deleted']} duplicates so far...")
        
        session.commit()
        logger.info(f"Cleanup complete: {stats['items_deleted']} items deleted")
        
        return {
            "success": True,
            "message": f"Removed {stats['items_deleted']} duplicate items",
            "stats": stats,
        }
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error during cleanup: {e}")
        return {"success": False, "error": str(e)}
    finally:
        session.close()


@router.get("")
async def get_all_settings() -> dict[str, Any]:
    """Return all settings.
    
    Returns:
        dict: All configuration settings
    """
    config = get_config()
    return {
        "server": {
            "host": config.server.host,
            "port": config.server.port,
            "debug": config.server.debug,
            "log_level": config.server.log_level,
        },
        "database": {
            "url": config.database.url,
            "echo": config.database.echo,
        },
        "ffmpeg": {
            "path": config.ffmpeg.path,
            "ffprobe_path": config.ffmpeg.ffprobe_path,
            "hardware_acceleration": {
                "enabled": config.ffmpeg.hardware_acceleration.enabled,
                "preferred": config.ffmpeg.hardware_acceleration.preferred,
            },
            "defaults": {
                "video_bitrate": config.ffmpeg.defaults.video_bitrate,
                "audio_bitrate": config.ffmpeg.defaults.audio_bitrate,
                "video_codec": config.ffmpeg.defaults.video_codec,
                "audio_codec": config.ffmpeg.defaults.audio_codec,
            },
        },
        "hdhomerun": {
            "enabled": config.hdhomerun.enabled,
            "device_id": config.hdhomerun.device_id,
            "tuner_count": config.hdhomerun.tuner_count,
        },
        "streaming": {
            "buffer_size": config.streaming.buffer_size,
            "read_size": config.streaming.read_size,
        },
    }
