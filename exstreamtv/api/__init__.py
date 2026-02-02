"""API routes and controllers for EXStreamTV"""

from fastapi import APIRouter

# Core routers that are working
from .auth import router as auth_router
from .dashboard import router as dashboard_router
from .health import router as health_router
from .settings import router as settings_router

# Create the main API router
api_router = APIRouter(prefix="/api")

# Include core routers
api_router.include_router(auth_router, tags=["Authentication"])
api_router.include_router(dashboard_router, tags=["Dashboard"])
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(settings_router, tags=["Settings"])

# Try to include optional routers (some may have import issues)
try:
    from .channels import router as channels_router
    api_router.include_router(channels_router, tags=["Channels"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Channels router not available: {e}")

try:
    from .media import router as media_router
    api_router.include_router(media_router, tags=["Media"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Media router not available: {e}")

try:
    from .playlists import router as playlists_router
    api_router.include_router(playlists_router, tags=["Playlists"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Playlists router not available: {e}")

try:
    from .schedules import router as schedules_router
    api_router.include_router(schedules_router, tags=["Schedules"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Schedules router not available: {e}")

try:
    from .schedule_items import router as schedule_items_router
    api_router.include_router(schedule_items_router, tags=["Schedule Items"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Schedule Items router not available: {e}")

try:
    from .libraries import router as libraries_router
    api_router.include_router(libraries_router, tags=["Libraries"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Libraries router not available: {e}")

try:
    from .ffmpeg_profiles import router as ffmpeg_profiles_router
    api_router.include_router(ffmpeg_profiles_router, tags=["FFmpeg Profiles"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"FFmpeg profiles router not available: {e}")

try:
    from .resolutions import router as resolutions_router
    api_router.include_router(resolutions_router, tags=["Resolutions"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Resolutions router not available: {e}")

try:
    from .playouts import router as playouts_router
    api_router.include_router(playouts_router, tags=["Playouts"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Playouts router not available: {e}")

try:
    from .ollama import router as ollama_router
    api_router.include_router(ollama_router, tags=["Ollama"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Ollama router not available: {e}")

try:
    from .validation import router as validation_router
    api_router.include_router(validation_router, tags=["Validation"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Validation router not available: {e}")

try:
    from .import_api import router as import_router
    api_router.include_router(import_router, tags=["Import"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Import router not available: {e}")

try:
    from .export_api import router as export_router
    api_router.include_router(export_router, tags=["Export"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Export router not available: {e}")

try:
    from .watermarks import router as watermarks_router
    api_router.include_router(watermarks_router, tags=["Watermarks"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Watermarks router not available: {e}")

try:
    from .logs import router as logs_router
    api_router.include_router(logs_router, tags=["Logs"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Logs router not available: {e}")

try:
    from .collections import router as collections_router
    api_router.include_router(collections_router, tags=["Collections"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Collections router not available: {e}")

# IPTV router is mounted at root level (not under /api) for compatibility with StreamTV
# It's exported separately and mounted in main.py
try:
    from .iptv import router as iptv_router
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"IPTV router not available: {e}")
    iptv_router = None

try:
    from .m3u_service_api import router as m3u_service_router
    api_router.include_router(m3u_service_router, tags=["M3U Service"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"M3U Service router not available: {e}")

try:
    from .media_sources import router as media_sources_router
    api_router.include_router(media_sources_router, tags=["Media Sources"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Media Sources router not available: {e}")

# Player API for React Player control
try:
    from .player import router as player_router
    api_router.include_router(player_router, tags=["Player"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Player router not available: {e}")

# ErsatzTV-compatible APIs
try:
    from .blocks import router as blocks_router
    api_router.include_router(blocks_router, tags=["Blocks"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Blocks router not available: {e}")

try:
    from .filler_presets import router as filler_presets_router
    api_router.include_router(filler_presets_router, tags=["Filler Presets"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Filler Presets router not available: {e}")

try:
    from .templates import router as templates_router
    api_router.include_router(templates_router, tags=["Templates"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Templates router not available: {e}")

try:
    from .deco import router as deco_router
    api_router.include_router(deco_router, tags=["Deco"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Deco router not available: {e}")

try:
    from .scripted import router as scripted_router
    api_router.include_router(scripted_router, tags=["Scripted Schedule"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Scripted Schedule router not available: {e}")

# Export the main router and IPTV router (mounted separately at root level)
__all__ = ["api_router", "iptv_router"]
