"""
Rate limiting wrapper for exporters.

Provides token bucket rate limiting for export operations.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

from tracecraft.exporters.base import BaseExporter

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun

logger = logging.getLogger(__name__)


class TokenBucket:
    """
    Token bucket rate limiter implementation.

    Allows a burst of operations up to 'burst' tokens, then limits
    operations to 'rate' per second. Tokens refill continuously.
    """

    def __init__(self, rate: float, burst: int) -> None:
        """
        Initialize the token bucket.

        Args:
            rate: Number of tokens to add per second.
            burst: Maximum number of tokens (bucket capacity).
        """
        self._rate = rate
        self._burst = burst
        self._tokens = float(burst)
        self._last_update = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, blocking: bool = True) -> bool:
        """
        Acquire a token from the bucket.

        Args:
            blocking: If True, wait for a token. If False, return immediately.

        Returns:
            True if token acquired, False if non-blocking and no token available.
        """
        with self._lock:
            return self._acquire_unlocked(blocking)

    def _acquire_unlocked(self, blocking: bool) -> bool:
        """Acquire without lock (caller must hold lock)."""
        self._refill()

        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True

        if not blocking:
            return False

        # Calculate wait time for next token
        tokens_needed = 1.0 - self._tokens
        wait_time = tokens_needed / self._rate

        # Release lock while waiting
        self._lock.release()
        try:
            time.sleep(wait_time)
        finally:
            self._lock.acquire()

        # Refill and try again
        self._refill()
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True

        return False

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_update
        self._last_update = now

        # Add tokens based on elapsed time
        self._tokens = min(
            self._burst,
            self._tokens + elapsed * self._rate,
        )


class RateLimitedExporter(BaseExporter):
    """
    Exporter wrapper that applies rate limiting.

    Uses a token bucket algorithm to limit export rate.

    Usage:
        ```python
        from tracecraft.exporters.otlp import OTLPExporter
        from tracecraft.exporters.rate_limited import RateLimitedExporter

        otlp = OTLPExporter(endpoint="http://localhost:4317")
        rate_limited = RateLimitedExporter(
            exporter=otlp,
            rate=100.0,  # 100 exports per second
            burst=10,    # Allow burst of 10
        )

        rate_limited.export(run)
        ```
    """

    def __init__(
        self,
        exporter: BaseExporter,
        rate: float = 100.0,
        burst: int = 10,
        blocking: bool = True,
    ) -> None:
        """
        Initialize the rate-limited exporter.

        Args:
            exporter: The underlying exporter to wrap.
            rate: Maximum exports per second.
            burst: Maximum burst size (bucket capacity).
            blocking: If True, wait for rate limit. If False, drop excess.
        """
        self._exporter = exporter
        self._bucket = TokenBucket(rate=rate, burst=burst)
        self._blocking = blocking
        self._dropped_count = 0
        self._lock = threading.Lock()

    @property
    def dropped_count(self) -> int:
        """Number of exports dropped due to rate limiting."""
        with self._lock:
            return self._dropped_count

    def export(self, run: AgentRun) -> None:
        """
        Export a run, respecting rate limits.

        Args:
            run: The AgentRun to export.
        """
        acquired = self._bucket.acquire(blocking=self._blocking)

        if not acquired:
            with self._lock:
                self._dropped_count += 1
            logger.warning(
                "Export dropped due to rate limiting (run: %s)",
                run.id,
            )
            return

        self._exporter.export(run)

    def shutdown(self) -> None:
        """Shutdown the underlying exporter."""
        if hasattr(self._exporter, "shutdown"):
            self._exporter.shutdown()
