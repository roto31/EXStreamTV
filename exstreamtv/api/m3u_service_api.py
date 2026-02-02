"""API endpoints for M3U module service management"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import get_config
config = get_config()
from ..database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/m3u/service", tags=["M3U Service"])


@router.get("/status")
async def get_service_status() -> dict[str, Any]:
    """
    Get M3U module service status.

    Returns:
        Dictionary with enabled flags for M3U module and sub-features
    """
    return {
        "enabled": config.m3u.enabled,
        "library_enabled": config.m3u.enable_library,
        "testing_enabled": config.m3u.enable_testing_service,
    }


@router.post("/enable")
async def enable_service(
    enable: bool = True,
    enable_library: bool = False,
    enable_testing: bool = False,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Enable M3U module.

    Args:
        enable: Enable M3U module
        enable_library: Enable stream library feature
        enable_testing: Enable background testing service

    Returns:
        Dictionary with success status and restart_required flag
    """
    try:
        from ..utils.config_updater import ConfigUpdater

        updater = ConfigUpdater()
        updater.update_m3u_config(
            enabled=enable, enable_library=enable_library, enable_testing=enable_testing
        )

        logger.info(f"M3U module {'enabled' if enable else 'disabled'}")

        return {
            "success": True,
            "restart_required": True,
            "message": "M3U module configuration updated. StreamTV must be restarted for changes to take effect.",
        }
    except Exception as e:
        logger.error(f"Error enabling M3U module: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating configuration: {e!s}")


@router.post("/disable")
async def disable_service(db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Disable M3U module.

    Returns:
        Dictionary with success status and restart_required flag
    """
    try:
        from ..utils.config_updater import ConfigUpdater

        updater = ConfigUpdater()
        updater.update_m3u_config(enabled=False, enable_library=False, enable_testing=False)

        logger.info("M3U module disabled")

        return {
            "success": True,
            "restart_required": True,
            "message": "M3U module disabled. StreamTV must be restarted for changes to take effect.",
        }
    except Exception as e:
        logger.error(f"Error disabling M3U module: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating configuration: {e!s}")


@router.post("/restart")
async def restart_service() -> dict[str, Any]:
    """
    Trigger StreamTV restart.

    This sets a flag that will cause StreamTV to restart gracefully.

    Returns:
        Dictionary with success status and message
    """
    try:
        # Set restart flag in app state
        from ..main import app

        app.state.restart_requested = True

        logger.warning("Restart requested via API")

        return {"success": True, "message": "StreamTV will restart in 3 seconds..."}
    except Exception as e:
        logger.error(f"Error triggering restart: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error triggering restart: {e!s}")
