"""Base HTTP client with rate limiting, retry logic, and error handling."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Status codes that trigger automatic retry
RETRY_STATUS_CODES = {429, 502, 503, 504}


class APIClientError(Exception):
    """Base exception for API client errors."""


class RateLimitError(APIClientError):
    """Raised when rate limit is exceeded."""


class BaseAPIClient:
    """Async HTTP client with token-bucket rate limiting and exponential backoff retry.

    Attributes:
        base_url: API base URL.
        requests_per_minute: Max requests per minute (token bucket rate).
        max_retries: Maximum number of retry attempts for transient errors.
        timeout: Request timeout in seconds.
        headers: Default HTTP headers (includes User-Agent).
    """

    def __init__(
        self,
        base_url: str,
        *,
        requests_per_minute: int = 60,
        max_retries: int = 3,
        timeout: float = 30.0,
        user_agent: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.requests_per_minute = requests_per_minute
        self.max_retries = max_retries
        self.timeout = timeout

        # Token bucket state
        self._min_interval = 60.0 / requests_per_minute if requests_per_minute > 0 else 0
        self._last_request_time: float = 0.0
        self._lock: asyncio.Lock | None = None  # Set lazily in async context

        # Headers
        self.headers: dict[str, str] = {
            "user-agent": user_agent or "ps5-hk-scraper/1.0.0",
            "accept": "application/json",
            "content-type": "application/json",
        }

    async def _get_lock(self) -> asyncio.Lock:
        """Lazily create the event loop lock."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def _wait_rate_limit(self) -> None:
        """Token-bucket rate limiting: ensure minimum interval between requests."""
        lock = await self._get_lock()
        async with lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self._min_interval:
                wait_time = self._min_interval - elapsed
                logger.debug("Rate limiting: sleeping %.2fs", wait_time)
                await asyncio.sleep(wait_time)
            self._last_request_time = time.monotonic()

    async def _retry_with_backoff(
        self,
        func,
        *args: Any,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute func with exponential backoff retry on transient errors.

        Args:
            func: Async callable that returns httpx.Response.
            *args, **kwargs: Passed to func.

        Returns:
            Successful httpx.Response.

        Raises:
            APIClientError: After exhausting all retries.
        """
        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await func(*args, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                if status_code in RETRY_STATUS_CODES and attempt < self.max_retries:
                    sleep_time = (2**attempt) * 0.5 + 0.1  # 0.6, 1.1, 2.1 seconds
                    logger.warning(
                        "HTTP %d on attempt %d/%d, retrying in %.1fs",
                        status_code,
                        attempt + 1,
                        self.max_retries + 1,
                        sleep_time,
                    )
                    await asyncio.sleep(sleep_time)
                    last_exception = e
                    continue
                raise APIClientError(
                    f"HTTP error {status_code} after {attempt + 1} attempt(s): {e}"
                ) from e
            except httpx.TimeoutException as e:
                if attempt < self.max_retries:
                    sleep_time = (2**attempt) * 0.5 + 0.1
                    logger.warning(
                        "Timeout on attempt %d/%d, retrying in %.1fs",
                        attempt + 1,
                        self.max_retries + 1,
                        sleep_time,
                    )
                    await asyncio.sleep(sleep_time)
                    last_exception = e
                    continue
                raise APIClientError(
                    f"Request timeout after {attempt + 1} attempt(s): {e}"
                ) from e
            except Exception as e:
                # Non-retryable errors
                raise APIClientError(f"Request failed: {e}") from e

        # Should not reach here, but just in case
        raise APIClientError(f"Max retries ({self.max_retries}) exceeded") from last_exception

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request with rate limiting and retry.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: URL path (appended to base_url).
            params: Query parameters.
            json: JSON body for POST/PUT.
            headers: Additional headers (merged with defaults).
            timeout: Override default timeout.

        Returns:
            Parsed JSON response as dict.

        Raises:
            APIClientError: On request failure after retries.
        """
        await self._wait_rate_limit()

        if path:
            url = f"{self.base_url}{path}" if path.startswith("/") else f"{self.base_url}/{path}"
        else:
            url = self.base_url
        req_headers = {**self.headers, **(headers or {})}

        req_timeout = timeout or self.timeout

        async with httpx.AsyncClient(timeout=req_timeout) as http_client:
            if method.upper() == "GET":
                func = http_client.get
            elif method.upper() == "POST":
                func = http_client.post
            else:
                func = getattr(http_client, method.lower())

            response = await self._retry_with_backoff(
                func,
                url,
                params=params,
                json=json,
                headers=req_headers,
            )
            return response.json()
