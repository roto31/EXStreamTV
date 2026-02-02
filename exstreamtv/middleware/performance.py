"""
Performance middleware for FastAPI.

Provides:
- Response compression (gzip/brotli)
- ETag support for conditional requests
- Request timing and logging
- Rate limiting
"""

import gzip
import hashlib
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


# ============================================================================
# Compression Middleware
# ============================================================================

class CompressionMiddleware(BaseHTTPMiddleware):
    """
    Middleware that compresses responses using gzip.
    
    Features:
    - Automatic gzip compression for text responses
    - Minimum size threshold
    - Content-type filtering
    - Respects Accept-Encoding header
    """
    
    COMPRESSIBLE_TYPES = {
        "text/html",
        "text/plain",
        "text/css",
        "text/javascript",
        "application/json",
        "application/javascript",
        "application/xml",
        "application/xhtml+xml",
        "image/svg+xml",
    }
    
    def __init__(
        self,
        app: ASGIApp,
        minimum_size: int = 500,
        compression_level: int = 6,
    ):
        super().__init__(app)
        self.minimum_size = minimum_size
        self.compression_level = compression_level
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if client accepts gzip
        accept_encoding = request.headers.get("accept-encoding", "")
        if "gzip" not in accept_encoding.lower():
            return await call_next(request)
        
        # Get response
        response = await call_next(request)
        
        # Skip streaming responses
        if isinstance(response, StreamingResponse):
            return response
        
        # Check content type
        content_type = response.headers.get("content-type", "")
        base_type = content_type.split(";")[0].strip()
        if base_type not in self.COMPRESSIBLE_TYPES:
            return response
        
        # Get body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        
        # Check minimum size
        if len(body) < self.minimum_size:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        
        # Compress
        compressed = gzip.compress(body, compresslevel=self.compression_level)
        
        # Only use if actually smaller
        if len(compressed) >= len(body):
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        
        # Return compressed response
        headers = dict(response.headers)
        headers["content-encoding"] = "gzip"
        headers["content-length"] = str(len(compressed))
        headers["vary"] = "Accept-Encoding"
        
        return Response(
            content=compressed,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )


# ============================================================================
# ETag Middleware
# ============================================================================

class ETagMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds ETag support for conditional requests.
    
    Features:
    - Automatic ETag generation
    - If-None-Match handling (304 responses)
    - Configurable paths
    """
    
    def __init__(
        self,
        app: ASGIApp,
        include_paths: Optional[List[str]] = None,
        exclude_paths: Optional[List[str]] = None,
    ):
        super().__init__(app)
        self.include_paths = include_paths or ["/api/"]
        self.exclude_paths = exclude_paths or ["/api/stream", "/api/iptv"]
    
    def _should_process(self, path: str) -> bool:
        """Check if path should have ETag processing."""
        # Check exclusions first
        for exclude in self.exclude_paths:
            if path.startswith(exclude):
                return False
        
        # Check inclusions
        for include in self.include_paths:
            if path.startswith(include):
                return True
        
        return False
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only process GET requests
        if request.method != "GET":
            return await call_next(request)
        
        # Check if path should be processed
        if not self._should_process(request.url.path):
            return await call_next(request)
        
        # Get response
        response = await call_next(request)
        
        # Skip non-200 responses
        if response.status_code != 200:
            return response
        
        # Skip streaming responses
        if isinstance(response, StreamingResponse):
            return response
        
        # Get body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        
        # Generate ETag
        etag = f'"{hashlib.md5(body).hexdigest()}"'
        
        # Check If-None-Match
        if_none_match = request.headers.get("if-none-match")
        if if_none_match and if_none_match == etag:
            return Response(
                status_code=304,
                headers={"etag": etag},
            )
        
        # Add ETag to response
        headers = dict(response.headers)
        headers["etag"] = etag
        
        return Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )


# ============================================================================
# Timing Middleware
# ============================================================================

@dataclass
class RequestTiming:
    """Timing information for a request."""
    path: str
    method: str
    status_code: int
    duration_ms: float
    timestamp: float


class TimingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that tracks request timing.
    
    Features:
    - Request duration tracking
    - Slow request logging
    - Timing metrics collection
    """
    
    def __init__(
        self,
        app: ASGIApp,
        slow_request_threshold_ms: float = 1000,
        enable_header: bool = True,
        max_history: int = 1000,
    ):
        super().__init__(app)
        self.slow_request_threshold_ms = slow_request_threshold_ms
        self.enable_header = enable_header
        self.max_history = max_history
        
        # Timing history
        self._history: List[RequestTiming] = []
        
        # Aggregate stats
        self._stats = {
            "total_requests": 0,
            "total_duration_ms": 0.0,
            "slow_requests": 0,
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        response = await call_next(request)
        
        duration_ms = (time.time() - start_time) * 1000
        
        # Update stats
        self._stats["total_requests"] += 1
        self._stats["total_duration_ms"] += duration_ms
        
        # Log slow requests
        if duration_ms > self.slow_request_threshold_ms:
            self._stats["slow_requests"] += 1
            logger.warning(
                f"Slow request: {request.method} {request.url.path} "
                f"took {duration_ms:.2f}ms"
            )
        
        # Add to history
        timing = RequestTiming(
            path=request.url.path,
            method=request.method,
            status_code=response.status_code,
            duration_ms=duration_ms,
            timestamp=start_time,
        )
        self._history.append(timing)
        
        # Trim history
        if len(self._history) > self.max_history:
            self._history = self._history[-self.max_history:]
        
        # Add timing header
        if self.enable_header:
            response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        
        return response
    
    def get_stats(self) -> Dict:
        """Get timing statistics."""
        total = self._stats["total_requests"]
        avg = (
            self._stats["total_duration_ms"] / total 
            if total > 0 else 0
        )
        
        return {
            "total_requests": total,
            "average_duration_ms": round(avg, 2),
            "slow_requests": self._stats["slow_requests"],
            "slow_request_threshold_ms": self.slow_request_threshold_ms,
        }
    
    def get_recent_slow_requests(self, limit: int = 10) -> List[Dict]:
        """Get recent slow requests."""
        slow = [
            {
                "path": t.path,
                "method": t.method,
                "status_code": t.status_code,
                "duration_ms": round(t.duration_ms, 2),
            }
            for t in self._history
            if t.duration_ms > self.slow_request_threshold_ms
        ]
        return slow[-limit:]


# ============================================================================
# Rate Limiting Middleware
# ============================================================================

@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_minute: int = 100
    burst_size: int = 20
    enabled: bool = False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Token bucket rate limiting middleware.
    
    Features:
    - Per-client rate limiting
    - Token bucket algorithm
    - Configurable limits
    - Rate limit headers
    """
    
    def __init__(
        self,
        app: ASGIApp,
        config: Optional[RateLimitConfig] = None,
    ):
        super().__init__(app)
        self.config = config or RateLimitConfig()
        
        # Token buckets per client
        self._buckets: Dict[str, Dict] = {}
        
        # Tokens refill rate (per second)
        self._refill_rate = self.config.requests_per_minute / 60.0
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier."""
        # Use X-Forwarded-For if behind proxy
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        # Use client host
        return request.client.host if request.client else "unknown"
    
    def _get_bucket(self, client_id: str) -> Dict:
        """Get or create token bucket for client."""
        now = time.time()
        
        if client_id not in self._buckets:
            self._buckets[client_id] = {
                "tokens": self.config.burst_size,
                "last_update": now,
            }
        
        bucket = self._buckets[client_id]
        
        # Refill tokens
        elapsed = now - bucket["last_update"]
        bucket["tokens"] = min(
            self.config.burst_size,
            bucket["tokens"] + elapsed * self._refill_rate,
        )
        bucket["last_update"] = now
        
        return bucket
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.config.enabled:
            return await call_next(request)
        
        client_id = self._get_client_id(request)
        bucket = self._get_bucket(client_id)
        
        # Check if request allowed
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            response = await call_next(request)
            
            # Add rate limit headers
            response.headers["X-RateLimit-Limit"] = str(self.config.requests_per_minute)
            response.headers["X-RateLimit-Remaining"] = str(int(bucket["tokens"]))
            
            return response
        else:
            # Rate limited
            retry_after = int((1 - bucket["tokens"]) / self._refill_rate) + 1
            
            return Response(
                content='{"detail": "Rate limit exceeded"}',
                status_code=429,
                headers={
                    "Content-Type": "application/json",
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.config.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                },
            )


# ============================================================================
# Performance Metrics Collection
# ============================================================================

class PerformanceMetrics:
    """
    Collects and aggregates performance metrics.
    """
    
    def __init__(self):
        self._request_timings: List[RequestTiming] = []
        self._endpoint_stats: Dict[str, Dict] = {}
        self._max_history = 10000
    
    def record_request(
        self,
        path: str,
        method: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        """Record a request timing."""
        timing = RequestTiming(
            path=path,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms,
            timestamp=time.time(),
        )
        
        self._request_timings.append(timing)
        if len(self._request_timings) > self._max_history:
            self._request_timings = self._request_timings[-self._max_history:]
        
        # Update endpoint stats
        key = f"{method} {path}"
        if key not in self._endpoint_stats:
            self._endpoint_stats[key] = {
                "count": 0,
                "total_ms": 0,
                "min_ms": float("inf"),
                "max_ms": 0,
            }
        
        stats = self._endpoint_stats[key]
        stats["count"] += 1
        stats["total_ms"] += duration_ms
        stats["min_ms"] = min(stats["min_ms"], duration_ms)
        stats["max_ms"] = max(stats["max_ms"], duration_ms)
    
    def get_endpoint_stats(self) -> List[Dict]:
        """Get statistics per endpoint."""
        result = []
        for key, stats in self._endpoint_stats.items():
            avg_ms = stats["total_ms"] / stats["count"] if stats["count"] > 0 else 0
            result.append({
                "endpoint": key,
                "count": stats["count"],
                "avg_ms": round(avg_ms, 2),
                "min_ms": round(stats["min_ms"], 2) if stats["min_ms"] != float("inf") else 0,
                "max_ms": round(stats["max_ms"], 2),
            })
        
        return sorted(result, key=lambda x: x["count"], reverse=True)
    
    def get_summary(self) -> Dict:
        """Get performance summary."""
        if not self._request_timings:
            return {"message": "No data available"}
        
        durations = [t.duration_ms for t in self._request_timings]
        
        return {
            "total_requests": len(durations),
            "avg_duration_ms": round(sum(durations) / len(durations), 2),
            "min_duration_ms": round(min(durations), 2),
            "max_duration_ms": round(max(durations), 2),
            "p50_duration_ms": round(sorted(durations)[len(durations) // 2], 2),
            "p95_duration_ms": round(sorted(durations)[int(len(durations) * 0.95)], 2),
            "p99_duration_ms": round(sorted(durations)[int(len(durations) * 0.99)], 2),
        }


# Global metrics instance
performance_metrics = PerformanceMetrics()
