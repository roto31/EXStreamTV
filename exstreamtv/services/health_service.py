"""Stream / probe health helpers and async retry decorator."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar

import httpx

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def with_retry(
    max_attempts: int = 3,
    backoff_base: float = 1.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[F], F]:
    """Async retry with exponential backoff (per-call state, not shared)."""

    def decorator(fn: F) -> F:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None
            for attempt in range(max_attempts):
                try:
                    return await fn(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    wait = backoff_base * (2**attempt)
                    logger.warning(
                        "%s: attempt %s/%s failed (%s), retrying in %.1fs",
                        getattr(fn, "__qualname__", str(fn)),
                        attempt + 1,
                        max_attempts,
                        e,
                        wait,
                    )
                    await asyncio.sleep(wait)
            logger.error(
                "%s: all %s attempts failed",
                getattr(fn, "__qualname__", str(fn)),
                max_attempts,
            )
            assert last_exc is not None
            raise last_exc

        return wrapper  # type: ignore[return-value]

    return decorator


@with_retry(
    max_attempts=3,
    backoff_base=0.5,
    exceptions=(httpx.HTTPError, httpx.RequestError, TimeoutError, OSError),
)
async def check_stream_health(url: str, timeout: float = 5.0) -> bool:
    """Return True if URL responds with a non-error HTTP status (HEAD, then GET)."""
    headers = {"User-Agent": "EXStreamTV-Health/1.0"}
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            r = await client.head(url, headers=headers)
            if r.status_code < 400:
                return True
        except httpx.HTTPError:
            pass
        r = await client.get(url, headers=headers)
        return r.status_code < 400
