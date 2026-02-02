"""
Database session compatibility module.

Provides SessionLocal and legacy imports for modules expecting
the old session pattern. This wrapper ensures backward compatibility
with code that imports from database.session.
"""

from exstreamtv.database.connection import (
    get_db,
    get_sync_session,
    get_sync_session_factory,
    init_db,
)


def SessionLocal():
    """
    Get a synchronous database session.
    
    This is a factory function that returns a new session.
    The caller is responsible for closing the session.
    
    Returns:
        SQLAlchemy Session instance
    """
    factory = get_sync_session_factory()
    if factory is None:
        # Initialize if not already done
        from exstreamtv.database.connection import init_sync_db
        init_sync_db()
        factory = get_sync_session_factory()
    return factory()


__all__ = ["SessionLocal", "get_db", "init_db"]
