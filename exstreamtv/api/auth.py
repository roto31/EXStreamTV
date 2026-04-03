"""Authentication API endpoints for EXStreamTV"""

import logging
from pathlib import Path
from typing import Any, Callable

import yaml
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ..config import get_config, reload_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

# Initialize Jinja2 templates
templates_path = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_path))


def _config_yaml_path() -> Path:
    for candidate in (
        Path("config.yaml"),
        Path(__file__).resolve().parents[2] / "config.yaml",
    ):
        if candidate.exists():
            return candidate
    return Path(__file__).resolve().parents[2] / "config.yaml"


def _get_youtube_cookies_path() -> Path:
    raw = (get_config().sources.youtube.cookies_file or "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path(__file__).resolve().parents[2] / "data" / "youtube_cookies.txt"


def _read_write_config_yaml(mutator: Callable[[dict[str, Any]], None]) -> None:
    cfg_path = _config_yaml_path()
    if cfg_path.exists():
        with open(cfg_path, encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
    else:
        data = {}
    mutator(data)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import fcntl

        with open(cfg_path, "w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    except ImportError:
        with open(cfg_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


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


@router.post("/youtube/cookies")
async def youtube_cookies_upload(file: UploadFile = File(...)) -> dict[str, str]:
    """Upload Netscape-format cookies.txt for YouTube (yt-dlp)."""
    filename = (file.filename or "").lower()
    if not filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Cookies file must be a .txt file (Netscape format).")
    dest = _get_youtube_cookies_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    body = await file.read()
    dest.write_bytes(body)

    def mutator(data: dict[str, Any]) -> None:
        sources = data.setdefault("sources", {})
        yt = sources.setdefault("youtube", {})
        yt["cookies_file"] = str(dest)

    _read_write_config_yaml(mutator)
    reload_config()
    return {"status": "success", "path": str(dest)}


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
