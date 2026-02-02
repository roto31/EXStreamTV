"""
Retry logic with different configurations for error recovery.

Ported from StreamTV with all retry strategies preserved.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypeVar

import httpx

from exstreamtv.streaming.error_handler import ErrorHandler, StreamError

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry attempts."""

    max_retries: int = 3
    backoff_base: float = 1.0
    backoff_max: float = 60.0
    timeout_multiplier: float = 1.5
    use_exponential_backoff: bool = True


@dataclass
class RetryAttempt:
    """Represents a single retry attempt."""

    attempt_number: int
    timestamp: datetime
    config_changes: dict[str, Any]
    success: bool = False
    error: Exception | None = None


class RetryManager:
    """Manages retry logic with different configurations."""

    def __init__(
        self,
        error_handler: ErrorHandler,
        config: RetryConfig | None = None,
    ):
        """
        Initialize retry manager.

        Args:
            error_handler: Error handler instance for classification.
            config: Retry configuration.
        """
        self.error_handler = error_handler
        self.config = config or RetryConfig()
        self.attempt_history: list[RetryAttempt] = []

    async def execute_with_retry(
        self,
        operation: Callable[[], Awaitable[T]],
        operation_name: str = "operation",
        context: dict[str, Any] | None = None,
        retry_strategies: list[str] | None = None,
    ) -> T:
        """
        Execute an operation with automatic retry using different strategies.

        Args:
            operation: Async function to execute.
            operation_name: Name of the operation for logging.
            context: Additional context for error handling.
            retry_strategies: List of retry strategies to try (auto-detected if None).

        Returns:
            Result of the operation.

        Raises:
            Exception: If all retry attempts fail.
        """
        if context is None:
            context = {}

        last_error = None
        last_stream_error = None

        for attempt in range(self.config.max_retries + 1):
            try:
                result = await operation()

                if attempt > 0:
                    logger.info(
                        f"{operation_name} succeeded after {attempt} retry attempt(s)"
                    )

                return result

            except Exception as e:
                last_error = e

                attempt_context = {**context, "attempt": attempt}
                stream_error = self.error_handler.handle_error(e, attempt_context, attempt)
                last_stream_error = stream_error

                if not self.error_handler.should_retry(stream_error):
                    logger.exception(
                        f"{operation_name} failed after {attempt} attempts: "
                        f"{stream_error.message}"
                    )
                    break

                if retry_strategies is None:
                    retry_strategies = self.error_handler.get_recovery_strategies(
                        stream_error
                    )

                if attempt < len(retry_strategies):
                    strategy = retry_strategies[attempt]
                    logger.info(
                        f"{operation_name} failed "
                        f"(attempt {attempt + 1}/{self.config.max_retries + 1}), "
                        f"trying strategy: {strategy}"
                    )

                    await self._apply_retry_strategy(strategy, context, stream_error)

                if attempt < self.config.max_retries:
                    delay = self._calculate_backoff(attempt, context)
                    logger.debug(f"Waiting {delay:.2f}s before retry...")
                    await asyncio.sleep(delay)

        if last_stream_error:
            logger.error(
                f"{operation_name} failed after {self.config.max_retries + 1} attempts. "
                f"Last error: {last_stream_error.error_type.value} - "
                f"{last_stream_error.message}"
            )

        if last_error:
            raise last_error
        raise Exception(f"{operation_name} failed after retries")

    async def _apply_retry_strategy(
        self,
        strategy: str,
        context: dict[str, Any],
        stream_error: StreamError,
    ) -> None:
        """
        Apply a retry strategy by modifying context.

        Args:
            strategy: Strategy name to apply.
            context: Context dictionary to modify.
            stream_error: The error that triggered the retry.
        """
        if strategy == "retry_without_cookies":
            context["use_cookies"] = False
            context["headers"] = context.get("headers", {}).copy()
            context["headers"].pop("Cookie", None)
            logger.debug("Retry strategy: Removing cookies from request")

        elif strategy == "retry_with_refreshed_cookies":
            context["reload_cookies"] = True
            logger.debug("Retry strategy: Reloading cookies")

        elif strategy == "retry_with_different_user_agent":
            context["headers"] = context.get("headers", {}).copy()
            context["headers"]["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            logger.debug("Retry strategy: Changing User-Agent")

        elif strategy == "retry_with_minimal_headers":
            context["headers"] = {}
            context["use_cookies"] = False
            logger.debug("Retry strategy: Using minimal headers")

        elif strategy == "retry_with_backoff":
            pass  # Handled separately

        elif strategy == "retry_with_long_backoff":
            context["long_backoff"] = True
            logger.debug("Retry strategy: Using long backoff for rate limiting")

        elif strategy == "retry_with_longer_timeout":
            context["timeout"] = context.get("timeout", 30) * self.config.timeout_multiplier
            logger.debug(f"Retry strategy: Increasing timeout to {context['timeout']}s")

        elif strategy == "try_alternative_url_format":
            context["try_alternative_url"] = True
            logger.debug("Retry strategy: Trying alternative URL format")

        elif strategy == "try_alternative_cdn":
            context["try_next_cdn"] = True
            logger.debug("Retry strategy: Trying alternative CDN")

        elif strategy == "refresh_authentication":
            context["refresh_auth"] = True
            logger.debug("Retry strategy: Refreshing authentication")

        elif strategy == "reload_cookies":
            context["reload_cookies"] = True
            logger.debug("Retry strategy: Reloading cookies")

        elif strategy == "try_different_codec":
            context["try_different_codec"] = True
            logger.debug("Retry strategy: Trying different codec")

        elif strategy == "try_alternative_format":
            context["try_alternative_format"] = True
            logger.debug("Retry strategy: Trying alternative format")

        else:
            logger.debug(f"Unknown retry strategy: {strategy}, using default backoff")

    def _calculate_backoff(
        self,
        attempt: int,
        context: dict[str, Any] | None = None,
    ) -> float:
        """Calculate backoff delay for retry attempt."""
        if not self.config.use_exponential_backoff:
            return self.config.backoff_base

        delay = self.config.backoff_base * (2**attempt)

        # For HTTP 464 (rate limiting), use longer backoff (5x multiplier)
        if context and context.get("long_backoff"):
            delay = delay * 5.0

        return min(delay, self.config.backoff_max)

    async def retry_with_config_changes(
        self,
        operation: Callable[[dict[str, Any]], Awaitable[T]],
        config_changes: list[dict[str, Any]],
        operation_name: str = "operation",
    ) -> T:
        """
        Retry an operation with different configuration changes.

        Args:
            operation: Async function that accepts a config dict.
            config_changes: List of configuration dictionaries to try.
            operation_name: Name of the operation for logging.

        Returns:
            Result of the operation.

        Raises:
            Exception: If all configurations fail.
        """
        last_error = None

        for idx, config in enumerate(config_changes):
            try:
                logger.debug(
                    f"{operation_name} attempt {idx + 1}/{len(config_changes)} "
                    f"with config: {config}"
                )
                result = await operation(config)

                if idx > 0:
                    logger.info(
                        f"{operation_name} succeeded with config change {idx + 1}"
                    )

                return result

            except Exception as e:
                last_error = e
                logger.warning(f"{operation_name} failed with config {idx + 1}: {e}")

                if idx < len(config_changes) - 1:
                    await asyncio.sleep(self._calculate_backoff(idx, None))

        if last_error:
            raise last_error
        raise Exception(f"{operation_name} failed with all configurations")


class HTTPRetryManager(RetryManager):
    """Specialized retry manager for HTTP requests."""

    async def execute_http_request(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Execute HTTP request with automatic retry.

        Args:
            client: HTTP client to use.
            method: HTTP method (GET, POST, etc.).
            url: Request URL.
            context: Additional context for error handling.
            **kwargs: Additional arguments for httpx request.

        Returns:
            HTTP response.

        Raises:
            httpx.HTTPError: If all retry attempts fail.
        """
        if context is None:
            context = {}

        async def make_request() -> httpx.Response:
            headers = kwargs.get("headers", {}).copy()
            if context.get("headers"):
                headers.update(context["headers"])

            cookies = kwargs.get("cookies")
            if context.get("use_cookies") is False:
                cookies = None
            elif context.get("reload_cookies") and "cookie_loader" in context:
                cookies = await context["cookie_loader"]()

            timeout = kwargs.get("timeout")
            if "timeout" in context:
                timeout = context["timeout"]

            request_kwargs = {
                **kwargs,
                "headers": headers,
                "cookies": cookies,
                "timeout": timeout,
            }

            response = await client.request(method, url, **request_kwargs)

            if response.status_code >= 400:
                error_context = {
                    **context,
                    "http_status_code": response.status_code,
                    "url": url,
                }

                error = httpx.HTTPStatusError(
                    f"HTTP {response.status_code}",
                    request=response.request,
                    response=response,
                )
                stream_error = self.error_handler.handle_error(error, error_context)

                if not self.error_handler.should_retry(stream_error):
                    raise error

                raise error

            return response

        return await self.execute_with_retry(
            make_request,
            operation_name=f"HTTP {method} {url}",
            context=context,
        )
