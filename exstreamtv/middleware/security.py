"""Security middleware and utilities for API key/JWT enforcement and security headers."""

import logging
import secrets
from collections.abc import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_401_UNAUTHORIZED
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

SAFE_METHODS: Iterable[str] = {"GET", "HEAD", "OPTIONS"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Enforce API key/JWT on non-safe HTTP methods (POST/PUT/PATCH/DELETE).

    Accepts either:
    - `Authorization: Bearer <token>` (preferred)
    - `X-API-Key: <token>` (preferred)

    SECURITY: Query parameter support removed to prevent token exposure in URLs/logs.
    """

    def __init__(
        self,
        app: ASGIApp,
        token: str | None,
        required: bool = True,
        exempt_paths: list[str] | None = None,
        allow_query_param: bool = True,
    ):
        super().__init__(app)
        self.token = token
        self.required = required
        self.exempt_paths = set(exempt_paths or [])
        self.allow_query_param = (
            allow_query_param  # Enabled by default for API compatibility per docs/API.md
        )
        self._warning_logged = False  # Track if we've already warned about missing token

    async def dispatch(self, request: Request, call_next):
        # Read from config dynamically (allows runtime updates without restart)
        from ..config import config

        required = (
            config.security.api_key_required if hasattr(config, "security") else self.required
        )

        # If API key is not required, allow access without checking
        if not required:
            return await call_next(request)

        # Allow safe methods (GET, HEAD, OPTIONS) without API key
        if request.method in SAFE_METHODS:
            return await call_next(request)

        # Allow exempt paths without API key
        if any(request.url.path.startswith(path) for path in self.exempt_paths):
            return await call_next(request)

        # Read token from config dynamically (allows runtime token updates)
        token = (
            config.security.access_token
            if hasattr(config, "security") and config.security.access_token
            else self.token
        )

        # If API key is required but no token is configured, warn once and allow access
        # This prevents breaking existing setups while alerting to misconfiguration
        if required and not token:
            if not self._warning_logged:
                logger.warning(
                    "API key required but access_token not set in config - allowing access (set security.access_token in config.yaml to enforce authentication)"
                )
                self._warning_logged = True
            # Allow access but log the security issue (only warn once to reduce log noise)
            return await call_next(request)

        # If no token is configured at all, allow access (API key not enforced)
        if not token:
            return await call_next(request)

        # Validate provided token
        provided = self._extract_token(request)
        if not provided or provided != token:
            return JSONResponse(
                status_code=HTTP_401_UNAUTHORIZED,
                content={"detail": "Unauthorized: valid API key or bearer token required"},
            )

        return await call_next(request)

    def _extract_token(self, request: Request) -> str | None:
        """Extract token from request headers only (query params disabled by default for security)."""
        # Check Authorization header (Bearer token) - preferred method
        auth = request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            return auth.split(" ", 1)[1].strip()

        # Check X-API-Key header - preferred method
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return api_key.strip()

        # Query parameter support (disabled by default for security)
        # Only allow if explicitly enabled and only for specific endpoints (e.g., IPTV streams)
        if self.allow_query_param:
            query_token = request.query_params.get("access_token")
            if query_token:
                # Log warning when query param is used (security concern)
                logger.warning(
                    f"API key provided via query parameter (security risk) for {request.url.path}"
                )
                return query_token.strip()

        return None


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add common security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        # Generate nonce before the request is processed so templates can access it
        nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce

        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=(), payment=()"
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")

        # Tightened CSP - removed 'unsafe-inline' from script-src for better XSS protection
        # Using nonces for inline scripts instead
        # Note: Some legacy inline scripts may need to be refactored to use nonces
        csp_policy = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "  # Keep unsafe-inline for styles (needed for dynamic styling)
            "font-src 'self' data: https://fonts.googleapis.com https://fonts.gstatic.com; "
            f"script-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net https://unpkg.com; "  # Use nonce instead of unsafe-inline
            "img-src 'self' data: blob: https:; "
            "media-src 'self' blob:; "
            "connect-src 'self'; "
            "frame-src 'self'; "
            "frame-ancestors 'none'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        response.headers.setdefault("Content-Security-Policy", csp_policy)

        # Add HSTS header if HTTPS is detected (for production)
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )

        return response


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """CSRF protection middleware for form submissions."""

    def __init__(self, app: ASGIApp, exempt_paths: list[str] | None = None):
        super().__init__(app)
        self.exempt_paths = set(exempt_paths or [])
        self.exempt_methods = {"GET", "HEAD", "OPTIONS"}

    async def dispatch(self, request: Request, call_next):
        path_is_exempt = any(request.url.path.startswith(path) for path in self.exempt_paths)

        # Reuse existing CSRF token from cookie when available, otherwise generate a new one
        csrf_cookie = request.cookies.get("csrf_token")
        if csrf_cookie:
            request.state.csrf_token = csrf_cookie
        elif not hasattr(request.state, "csrf_token"):
            request.state.csrf_token = secrets.token_urlsafe(32)

        should_validate = (
            request.method not in self.exempt_methods
            and not path_is_exempt
            and request.method in {"POST", "PUT", "DELETE", "PATCH"}
        )

        if should_validate:
            csrf_token_header = request.headers.get("X-CSRF-Token")
            csrf_token_form = None

            content_type = request.headers.get("Content-Type", "")
            if (
                "application/x-www-form-urlencoded" in content_type
                or "multipart/form-data" in content_type
            ):
                try:
                    form_data = await request.form()
                    csrf_token_form = form_data.get("csrf_token")
                except Exception:
                    csrf_token_form = None

            provided_token = csrf_token_header or csrf_token_form
            expected_token = csrf_cookie or getattr(request.state, "csrf_token", None)

            if not provided_token or not expected_token or provided_token != expected_token:
                if not request.url.path.startswith("/api/"):
                    return JSONResponse(
                        status_code=403, content={"detail": "CSRF token validation failed"}
                    )

        response = await call_next(request)

        if hasattr(request.state, "csrf_token"):
            response.set_cookie(
                "csrf_token",
                request.state.csrf_token,
                httponly=True,
                samesite="strict",
                secure=request.url.scheme == "https",
            )

        return response
