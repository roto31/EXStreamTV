"""
Dashboard API endpoints - Async version.

Provides dashboard statistics, system info, and activity feeds.
"""

import logging
import os
import platform
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import psutil
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from exstreamtv.database.connection import get_db
from exstreamtv.database.models.channel import Channel
from exstreamtv.database.models.playlist import Playlist, PlaylistItem
from exstreamtv.database.models.library import (
    LocalLibrary,
    PlexLibrary,
    JellyfinLibrary,
    EmbyLibrary,
)
from exstreamtv.database.models.playout import Playout, PlayoutItem
from exstreamtv.database.models.schedule import ProgramSchedule

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# ============ Schemas ============


class QuickStat(BaseModel):
    """Quick stat card data."""

    label: str
    value: int | str
    change: Optional[str] = None  # e.g., "+5 this week"
    icon: str = "📊"
    color: str = "blue"


class SystemInfo(BaseModel):
    """System information."""

    hostname: str
    platform: str
    python_version: str
    cpu_count: int
    memory_total_gb: float
    disk_total_gb: float
    uptime_hours: float


class ResourceUsage(BaseModel):
    """Current resource usage."""

    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    disk_percent: float
    disk_used_gb: float
    network_sent_mb: float
    network_recv_mb: float


class ActiveStream(BaseModel):
    """Active stream information."""

    channel_id: int
    channel_name: str
    channel_number: str
    current_item: Optional[str] = None
    viewers: int = 0
    uptime_minutes: float = 0.0
    bitrate_kbps: Optional[int] = None


class ActivityItem(BaseModel):
    """Activity feed item."""

    id: str
    type: str  # "stream_start", "stream_end", "scan_complete", "error", "info"
    message: str
    timestamp: datetime
    icon: str = "📌"
    color: str = "gray"


class DashboardStats(BaseModel):
    """Complete dashboard statistics."""

    quick_stats: List[QuickStat]
    system_info: SystemInfo
    resource_usage: ResourceUsage
    active_streams: List[ActiveStream]
    recent_activity: List[ActivityItem]
    storage_breakdown: Dict[str, float]


class ChartData(BaseModel):
    """Chart data point."""

    label: str
    value: float


class StreamHistory(BaseModel):
    """Stream history for charts."""

    hourly_viewers: List[ChartData]
    daily_streams: List[ChartData]
    weekly_bandwidth: List[ChartData]


# ============ In-Memory State ============

# Track active streams (would be populated by streaming module)
_active_streams: Dict[int, Dict[str, Any]] = {}

# Track activity feed
_activity_feed: List[ActivityItem] = []

# Network baseline for delta calculation
_network_baseline: Optional[Dict[str, int]] = None


def add_activity(
    activity_type: str,
    message: str,
    icon: str = "📌",
    color: str = "gray",
) -> None:
    """Add an activity item to the feed."""
    global _activity_feed

    activity = ActivityItem(
        id=f"act_{datetime.now().timestamp()}",
        type=activity_type,
        message=message,
        timestamp=datetime.now(),
        icon=icon,
        color=color,
    )

    _activity_feed.insert(0, activity)

    # Keep only last 100 items
    if len(_activity_feed) > 100:
        _activity_feed = _activity_feed[:100]


def register_stream(
    channel_id: int,
    channel_name: str,
    channel_number: str,
) -> None:
    """Register an active stream."""
    _active_streams[channel_id] = {
        "channel_name": channel_name,
        "channel_number": channel_number,
        "started_at": datetime.now(),
        "current_item": None,
        "viewers": 1,
    }
    add_activity(
        "stream_start",
        f"Channel {channel_number} ({channel_name}) started streaming",
        icon="▶️",
        color="green",
    )


def unregister_stream(channel_id: int) -> None:
    """Unregister an active stream."""
    if channel_id in _active_streams:
        stream = _active_streams.pop(channel_id)
        add_activity(
            "stream_end",
            f"Channel {stream['channel_number']} ({stream['channel_name']}) stopped",
            icon="⏹️",
            color="gray",
        )


# ============ Endpoints ============


@router.get("")
async def dashboard_root(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Get dashboard summary.
    
    Returns a summary of key dashboard metrics for quick access.
    For full stats, use /dashboard/stats.
    """
    quick_stats = await _get_quick_stats(db)
    active_streams = _get_active_streams()
    
    return {
        "message": "Dashboard API",
        "endpoints": [
            {"path": "/api/dashboard/stats", "description": "Complete dashboard statistics"},
            {"path": "/api/dashboard/quick-stats", "description": "Quick stat cards"},
            {"path": "/api/dashboard/system-info", "description": "System information"},
            {"path": "/api/dashboard/resource-usage", "description": "Current resource usage"},
            {"path": "/api/dashboard/active-streams", "description": "Active streams list"},
            {"path": "/api/dashboard/activity", "description": "Recent activity feed"},
            {"path": "/api/dashboard/stream-history", "description": "Stream history charts"},
            {"path": "/api/dashboard/library-stats", "description": "Library statistics"},
        ],
        "summary": {
            "channels": next((s.value for s in quick_stats if s.label == "Channels"), 0),
            "active_streams": len(active_streams),
            "playlists": next((s.value for s in quick_stats if s.label == "Playlists"), 0),
        }
    }


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)) -> DashboardStats:
    """Get complete dashboard statistics."""

    # Quick stats
    quick_stats = await _get_quick_stats(db)

    # System info
    system_info = _get_system_info()

    # Resource usage
    resource_usage = _get_resource_usage()

    # Active streams
    active_streams = _get_active_streams()

    # Recent activity
    recent_activity = _activity_feed[:20]

    # Storage breakdown
    storage_breakdown = await _get_storage_breakdown(db)

    return DashboardStats(
        quick_stats=quick_stats,
        system_info=system_info,
        resource_usage=resource_usage,
        active_streams=active_streams,
        recent_activity=recent_activity,
        storage_breakdown=storage_breakdown,
    )


@router.get("/quick-stats", response_model=List[QuickStat])
async def get_quick_stats(db: AsyncSession = Depends(get_db)) -> List[QuickStat]:
    """Get quick stat cards."""
    return await _get_quick_stats(db)


@router.get("/system-info", response_model=SystemInfo)
async def get_system_info() -> SystemInfo:
    """Get system information."""
    return _get_system_info()


@router.get("/resource-usage", response_model=ResourceUsage)
async def get_resource_usage() -> ResourceUsage:
    """Get current resource usage."""
    return _get_resource_usage()


@router.get("/active-streams", response_model=List[ActiveStream])
async def get_active_streams() -> List[ActiveStream]:
    """Get list of active streams."""
    return _get_active_streams()


@router.get("/activity", response_model=List[ActivityItem])
async def get_activity(limit: int = 20) -> List[ActivityItem]:
    """Get recent activity feed."""
    return _activity_feed[:limit]


@router.get("/stream-history", response_model=StreamHistory)
async def get_stream_history() -> StreamHistory:
    """Get streaming history for charts."""
    # Generate sample data (would be from actual metrics in production)
    now = datetime.now()

    hourly_viewers = [
        ChartData(label=f"{(now - timedelta(hours=i)).strftime('%H:00')}", value=0)
        for i in range(23, -1, -1)
    ]

    daily_streams = [
        ChartData(
            label=(now - timedelta(days=i)).strftime("%a"),
            value=0,
        )
        for i in range(6, -1, -1)
    ]

    weekly_bandwidth = [
        ChartData(
            label=f"Week {i+1}",
            value=0,
        )
        for i in range(4)
    ]

    return StreamHistory(
        hourly_viewers=hourly_viewers,
        daily_streams=daily_streams,
        weekly_bandwidth=weekly_bandwidth,
    )


@router.get("/library-stats")
async def get_library_stats(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Get library statistics breakdown."""
    stats: Dict[str, Any] = {
        "local": {"count": 0, "items": 0},
        "plex": {"count": 0, "items": 0},
        "jellyfin": {"count": 0, "items": 0},
        "emby": {"count": 0, "items": 0},
    }

    # Local libraries
    result = await db.execute(select(LocalLibrary))
    for lib in result.scalars().all():
        stats["local"]["count"] += 1
        stats["local"]["items"] += getattr(lib, "item_count", 0) or 0

    # Plex libraries
    result = await db.execute(select(PlexLibrary))
    for lib in result.scalars().all():
        stats["plex"]["count"] += 1
        stats["plex"]["items"] += getattr(lib, "item_count", 0) or 0

    # Jellyfin libraries
    result = await db.execute(select(JellyfinLibrary))
    for lib in result.scalars().all():
        stats["jellyfin"]["count"] += 1
        stats["jellyfin"]["items"] += getattr(lib, "item_count", 0) or 0

    # Emby libraries
    result = await db.execute(select(EmbyLibrary))
    for lib in result.scalars().all():
        stats["emby"]["count"] += 1
        stats["emby"]["items"] += getattr(lib, "item_count", 0) or 0

    stats["total_libraries"] = sum(s["count"] for s in stats.values() if isinstance(s, dict))
    stats["total_items"] = sum(s["items"] for s in stats.values() if isinstance(s, dict))

    return stats


# ============ Helper Functions ============


async def _get_quick_stats(db: AsyncSession) -> List[QuickStat]:
    """Get quick stat cards."""
    # Count channels
    result = await db.execute(select(func.count(Channel.id)))
    channel_count = result.scalar() or 0

    # Count playlists
    result = await db.execute(select(func.count(Playlist.id)))
    playlist_count = result.scalar() or 0

    # Count total media items in playlists
    result = await db.execute(select(func.count(PlaylistItem.id)))
    media_count = result.scalar() or 0

    # Count libraries
    local_count_result = await db.execute(select(func.count(LocalLibrary.id)))
    plex_count_result = await db.execute(select(func.count(PlexLibrary.id)))
    jellyfin_count_result = await db.execute(select(func.count(JellyfinLibrary.id)))
    emby_count_result = await db.execute(select(func.count(EmbyLibrary.id)))
    
    library_count = (
        (local_count_result.scalar() or 0)
        + (plex_count_result.scalar() or 0)
        + (jellyfin_count_result.scalar() or 0)
        + (emby_count_result.scalar() or 0)
    )

    # Count schedules
    result = await db.execute(select(func.count(ProgramSchedule.id)))
    schedule_count = result.scalar() or 0

    # Active streams
    active_count = len(_active_streams)

    return [
        QuickStat(
            label="Channels",
            value=channel_count,
            icon="📺",
            color="blue",
        ),
        QuickStat(
            label="Playlists",
            value=playlist_count,
            icon="📋",
            color="purple",
        ),
        QuickStat(
            label="Media Items",
            value=media_count,
            icon="🎬",
            color="green",
        ),
        QuickStat(
            label="Libraries",
            value=library_count,
            icon="📚",
            color="orange",
        ),
        QuickStat(
            label="Schedules",
            value=schedule_count,
            icon="📅",
            color="teal",
        ),
        QuickStat(
            label="Active Streams",
            value=active_count,
            icon="▶️",
            color="red" if active_count > 0 else "gray",
        ),
    ]


def _get_system_info() -> SystemInfo:
    """Get system information."""
    try:
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        uptime_hours = uptime.total_seconds() / 3600
    except Exception:
        uptime_hours = 0.0

    try:
        memory = psutil.virtual_memory()
        memory_total = memory.total / (1024**3)
    except Exception:
        memory_total = 0.0

    try:
        disk = psutil.disk_usage("/")
        disk_total = disk.total / (1024**3)
    except Exception:
        disk_total = 0.0

    return SystemInfo(
        hostname=platform.node(),
        platform=f"{platform.system()} {platform.release()}",
        python_version=platform.python_version(),
        cpu_count=os.cpu_count() or 1,
        memory_total_gb=round(memory_total, 1),
        disk_total_gb=round(disk_total, 1),
        uptime_hours=round(uptime_hours, 1),
    )


def _get_resource_usage() -> ResourceUsage:
    """Get current resource usage."""
    global _network_baseline

    try:
        cpu = psutil.cpu_percent(interval=0.1)
    except Exception:
        cpu = 0.0

    try:
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used = memory.used / (1024**3)
    except Exception:
        memory_percent = 0.0
        memory_used = 0.0

    try:
        disk = psutil.disk_usage("/")
        disk_percent = disk.percent
        disk_used = disk.used / (1024**3)
    except Exception:
        disk_percent = 0.0
        disk_used = 0.0

    try:
        net = psutil.net_io_counters()
        if _network_baseline is None:
            _network_baseline = {"sent": net.bytes_sent, "recv": net.bytes_recv}

        net_sent = (net.bytes_sent - _network_baseline["sent"]) / (1024**2)
        net_recv = (net.bytes_recv - _network_baseline["recv"]) / (1024**2)
    except Exception:
        net_sent = 0.0
        net_recv = 0.0

    return ResourceUsage(
        cpu_percent=round(cpu, 1),
        memory_percent=round(memory_percent, 1),
        memory_used_gb=round(memory_used, 2),
        disk_percent=round(disk_percent, 1),
        disk_used_gb=round(disk_used, 1),
        network_sent_mb=round(net_sent, 2),
        network_recv_mb=round(net_recv, 2),
    )


def _get_active_streams() -> List[ActiveStream]:
    """Get active streams."""
    streams = []

    for channel_id, data in _active_streams.items():
        started = data.get("started_at", datetime.now())
        uptime = (datetime.now() - started).total_seconds() / 60

        streams.append(
            ActiveStream(
                channel_id=channel_id,
                channel_name=data.get("channel_name", "Unknown"),
                channel_number=data.get("channel_number", "0"),
                current_item=data.get("current_item"),
                viewers=data.get("viewers", 1),
                uptime_minutes=round(uptime, 1),
                bitrate_kbps=data.get("bitrate"),
            )
        )

    return streams


async def _get_storage_breakdown(db: AsyncSession) -> Dict[str, float]:
    """Get storage breakdown by library type."""
    breakdown = {}

    # Count items by type
    local_items = 0
    plex_items = 0
    jellyfin_items = 0
    emby_items = 0

    result = await db.execute(select(LocalLibrary))
    for lib in result.scalars().all():
        local_items += getattr(lib, "item_count", 0) or 0

    result = await db.execute(select(PlexLibrary))
    for lib in result.scalars().all():
        plex_items += getattr(lib, "item_count", 0) or 0

    result = await db.execute(select(JellyfinLibrary))
    for lib in result.scalars().all():
        jellyfin_items += getattr(lib, "item_count", 0) or 0

    result = await db.execute(select(EmbyLibrary))
    for lib in result.scalars().all():
        emby_items += getattr(lib, "item_count", 0) or 0

    total = local_items + plex_items + jellyfin_items + emby_items

    if total > 0:
        breakdown["Local"] = round(local_items / total * 100, 1)
        breakdown["Plex"] = round(plex_items / total * 100, 1)
        breakdown["Jellyfin"] = round(jellyfin_items / total * 100, 1)
        breakdown["Emby"] = round(emby_items / total * 100, 1)
    else:
        breakdown["No Data"] = 100.0

    return breakdown


# Add initial activity on module load
add_activity("info", "EXStreamTV server started", icon="🚀", color="blue")
