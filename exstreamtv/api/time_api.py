"""Authoritative time API. Zero wall-clock dependency."""

from fastapi import APIRouter

from exstreamtv.scheduling.authoritative_time import now_epoch

router = APIRouter(prefix="/time", tags=["Time"])


@router.get("/authoritative")
async def get_authoritative_time() -> dict:
    """Return monotonic-derived now. Use for all EPG/playout verification."""
    return {"now_epoch": now_epoch()}
