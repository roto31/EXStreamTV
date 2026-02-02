"""API authentication checker for StreamTV"""

from fastapi import Header, HTTPException, Query, Request, status

from ..config import config


async def verify_api_key(
    request: Request,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    access_token: str | None = Query(None, alias="access_token"),
)-> bool:
    """Verify API key for protected endpoints.

    Supports both header (X-API-Key) and query parameter (access_token) authentication
    as specified in docs/API.md.

    Usage:
        @router.post("/endpoint", dependencies=[Depends(verify_api_key)])
    """
    if config.security.api_key_required:
        if not config.security.access_token:
            # If API key required but not configured, allow access with warning
            # In production, this should be an error
            return True

        # Check header first (preferred), then query parameter
        provided_token = x_api_key or access_token

        if not provided_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key required. Provide X-API-Key header or access_token query parameter.",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        if provided_token != config.security.access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "ApiKey"},
            )

    return True
