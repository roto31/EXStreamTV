"""API endpoints for M3U stream library"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import config
from ..database import get_db
from ..database.models import M3UStreamSource, M3UStreamTest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/m3u/library", tags=["M3U Library"])


@router.get("")
async def get_stream_library(
    country: str | None = Query(None, description="Filter by country"),
    genre: str | None = Query(None, description="Filter by genre"),
    min_reliability: float | None = Query(None, description="Minimum reliability percentage"),
    sort_by: str = Query("name", description="Sort by: country, genre, reliability, name"),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """
    Get all curated M3U streams with optional filtering.

    Args:
        country: Filter by country code
        genre: Filter by genre
        min_reliability: Minimum reliability percentage (0-100)
        sort_by: Sort field (country, genre, reliability, name)

    Returns:
        List of stream sources with metadata
    """
    # If M3U module is not enabled, return empty list (don't error)
    # This allows the UI to check status without errors
    if not config.m3u.enabled:
        return []

    query = db.query(M3UStreamSource).filter(M3UStreamSource.is_active)

    # Apply filters
    if country:
        query = query.filter(M3UStreamSource.country == country)
    if genre:
        query = query.filter(M3UStreamSource.genre == genre)
    if min_reliability is not None:
        query = query.filter(M3UStreamSource.reliability_score >= min_reliability)

    # Sort
    if sort_by == "country":
        query = query.order_by(M3UStreamSource.country, M3UStreamSource.name)
    elif sort_by == "genre":
        query = query.order_by(M3UStreamSource.genre, M3UStreamSource.name)
    elif sort_by == "reliability":
        query = query.order_by(M3UStreamSource.reliability_score.desc(), M3UStreamSource.name)
    else:  # name
        query = query.order_by(M3UStreamSource.name)

    streams = query.all()

    return [
        {
            "id": stream.id,
            "name": stream.name,
            "url": stream.url,
            "description": stream.description,
            "country": stream.country,
            "genre": stream.genre,
            "category": stream.category,
            "source_type": stream.source_type,
            "is_active": stream.is_active,
            "last_tested": stream.last_tested.isoformat() if stream.last_tested else None,
            "reliability_score": stream.reliability_score,
            "total_channels": stream.total_channels,
            "working_channels": stream.working_channels,
            "created_at": stream.created_at.isoformat() if stream.created_at else None,
            "updated_at": stream.updated_at.isoformat() if stream.updated_at else None,
        }
        for stream in streams
    ]


@router.get("/stats")
async def get_library_stats(db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Get library statistics.

    Returns:
        Statistics about the stream library
    """
    # If M3U module is not enabled, return empty stats
    if not config.m3u.enabled:
        return {"total_streams": 0, "by_country": {}, "by_genre": {}, "average_reliability": None}

    total_streams = db.query(M3UStreamSource).filter(M3UStreamSource.is_active).count()

    # Count by country
    countries = (
        db.query(M3UStreamSource.country, func.count(M3UStreamSource.id).label("count"))
        .filter(M3UStreamSource.is_active, M3UStreamSource.country.isnot(None))
        .group_by(M3UStreamSource.country)
        .all()
    )

    # Count by genre
    genres = (
        db.query(M3UStreamSource.genre, func.count(M3UStreamSource.id).label("count"))
        .filter(M3UStreamSource.is_active, M3UStreamSource.genre.isnot(None))
        .group_by(M3UStreamSource.genre)
        .all()
    )

    # Average reliability
    avg_reliability = (
        db.query(func.avg(M3UStreamSource.reliability_score))
        .filter(M3UStreamSource.is_active, M3UStreamSource.reliability_score.isnot(None))
        .scalar()
        or 0
    )

    return {
        "total_streams": total_streams,
        "by_country": dict(countries),
        "by_genre": dict(genres),
        "average_reliability": round(avg_reliability, 2) if avg_reliability else None,
    }


@router.get("/{stream_id}")
async def get_stream_details(stream_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Get detailed information about a specific stream source.

    Args:
        stream_id: Stream source ID

    Returns:
        Stream source details with test history
    """
    # If M3U module is not enabled, return 403
    if not config.m3u.enabled:
        raise HTTPException(status_code=403, detail="M3U module is not enabled")

    stream = db.query(M3UStreamSource).filter(M3UStreamSource.id == stream_id).first()

    if not stream:
        raise HTTPException(status_code=404, detail="Stream source not found")

    # Get test history
    tests = (
        db.query(M3UStreamTest)
        .filter(M3UStreamTest.stream_source_id == stream_id)
        .order_by(M3UStreamTest.test_date.desc())
        .limit(10)
        .all()
    )

    return {
        "id": stream.id,
        "name": stream.name,
        "url": stream.url,
        "description": stream.description,
        "country": stream.country,
        "genre": stream.genre,
        "category": stream.category,
        "source_type": stream.source_type,
        "is_active": stream.is_active,
        "last_tested": stream.last_tested.isoformat() if stream.last_tested else None,
        "reliability_score": stream.reliability_score,
        "total_channels": stream.total_channels,
        "working_channels": stream.working_channels,
        "created_at": stream.created_at.isoformat() if stream.created_at else None,
        "updated_at": stream.updated_at.isoformat() if stream.updated_at else None,
        "test_history": [
            {
                "id": test.id,
                "test_date": test.test_date.isoformat(),
                "test_result": test.test_result,
                "channels_tested": test.channels_tested,
                "channels_working": test.channels_working,
                "reliability_percentage": test.reliability_percentage,
                "test_duration": test.test_duration,
                "error_message": test.error_message,
            }
            for test in tests
        ],
    }


@router.post("/test")
async def test_stream(
    stream_id: int | None = Query(None, description="Stream source ID"),
    stream_url: str | None = Query(None, description="Stream URL to test"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Manually trigger a stream test.

    Args:
        stream_id: Stream source ID (if testing existing stream)
        stream_url: Stream URL (if testing new stream)

    Returns:
        Test results
    """
    # Check if M3U module is enabled
    if not config.m3u.enabled:
        raise HTTPException(status_code=403, detail="M3U module is not enabled")

    try:
        from ..importers.m3u_discovery import M3UStreamTester

        tester = M3UStreamTester(db)

        if stream_id:
            stream = db.query(M3UStreamSource).filter(M3UStreamSource.id == stream_id).first()
            if not stream:
                raise HTTPException(status_code=404, detail="Stream source not found")
            url = stream.url
        elif stream_url:
            url = stream_url
        else:
            raise HTTPException(
                status_code=400, detail="Either stream_id or stream_url must be provided"
            )

        # Run test
        result = await tester.test_stream(url)

        # Update stream source if it exists
        if stream_id:
            stream = db.query(M3UStreamSource).filter(M3UStreamSource.id == stream_id).first()
            if stream:
                stream.last_tested = datetime.utcnow()
                stream.reliability_score = result.get("reliability_percentage")
                stream.total_channels = result.get("total_channels", 0)
                stream.working_channels = result.get("working_channels", 0)

                # Create test record
                test_record = M3UStreamTest(
                    stream_source_id=stream_id,
                    test_result="success" if result.get("success") else "failure",
                    channels_tested=result.get("channels_tested", 0),
                    channels_working=result.get("working_channels", 0),
                    reliability_percentage=result.get("reliability_percentage"),
                    test_duration=result.get("test_duration"),
                    error_message=result.get("error_message"),
                )
                db.add(test_record)
                db.commit()

        return result

    except Exception as e:
        logger.error(f"Error testing stream: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error testing stream: {e!s}")
