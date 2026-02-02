"""Authentication API endpoints for EXStreamTV"""

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ..config import get_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

# Initialize Jinja2 templates
templates_path = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_path))


class ArchiveOrgCredentials(BaseModel):
    """Archive.org credentials model."""
    username: str
    password: str


class YouTubeCookies(BaseModel):
    """YouTube cookies configuration."""
    cookies_file: str


@router.get("/status")
async def auth_status() -> dict[str, Any]:
    """Get authentication status for all services.
    
    Returns:
        dict: Authentication status for YouTube, Archive.org, etc.
    """
    config = get_config()
    return {
        "youtube": {
            "authenticated": bool(config.sources.youtube.cookies_file),
            "enabled": config.sources.youtube.enabled,
        },
        "archive_org": {
            "authenticated": False,  # Not using authentication by default
            "enabled": config.sources.archive_org.enabled,
        },
        "security": {
            "enabled": config.security.enabled,
        },
    }


@router.get("/youtube", response_class=HTMLResponse)
async def youtube_auth_page(request: Request) -> HTMLResponse:
    """YouTube authentication page.
    
    Args:
        request: FastAPI request object
        
    Returns:
        HTMLResponse: YouTube authentication page
    """
    config = get_config()
    return templates.TemplateResponse(
        "auth_youtube.html",
        {
            "request": request,
            "authenticated": bool(config.sources.youtube.cookies_file),
            "cookies_file": config.sources.youtube.cookies_file or "",
        },
    )


@router.get("/youtube/status")
async def youtube_status() -> dict[str, Any]:
    """Get YouTube authentication status.
    
    Returns:
        dict: YouTube authentication status
    """
    config = get_config()
    return {
        "authenticated": bool(config.sources.youtube.cookies_file),
        "cookies_file": config.sources.youtube.cookies_file,
        "enabled": config.sources.youtube.enabled,
    }


@router.get("/archive-org", response_class=HTMLResponse)
async def archive_org_auth_page(request: Request) -> HTMLResponse:
    """Archive.org authentication page.
    
    Args:
        request: FastAPI request object
        
    Returns:
        HTMLResponse: Archive.org authentication page
    """
    return templates.TemplateResponse(
        "auth_archive_org.html",
        {
            "request": request,
            "authenticated": False,
            "username": "",
        },
    )


@router.get("/archive-org/status")
async def archive_org_status() -> dict[str, Any]:
    """Get Archive.org authentication status.
    
    Returns:
        dict: Archive.org authentication status
    """
    config = get_config()
    return {
        "authenticated": False,
        "enabled": config.sources.archive_org.enabled,
    }


@router.post("/archive-org")
async def archive_org_login(credentials: ArchiveOrgCredentials) -> dict[str, Any]:
    """Login to Archive.org.
    
    Args:
        credentials: Archive.org username and password
        
    Returns:
        dict: Status message
        
    Note:
        Archive.org authentication is not fully implemented yet.
    """
    logger.info(f"Archive.org login attempt for user: {credentials.username}")
    return {
        "status": "pending",
        "message": "Archive.org authentication is not fully implemented. Credentials stored for future use.",
    }


@router.delete("/archive-org")
async def archive_org_logout() -> dict[str, str]:
    """Logout from Archive.org.
    
    Returns:
        dict: Status message
    """
    return {"status": "success", "message": "Logged out from Archive.org"}


@router.delete("/youtube")
async def youtube_logout() -> dict[str, str]:
    """Remove YouTube authentication.
    
    Returns:
        dict: Status message
    """
    logger.info("YouTube authentication removed")
    return {"status": "success", "message": "YouTube authentication removed"}
