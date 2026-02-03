"""
Retry and buffering wrappers for exporters.

Provides RetryingExporter for automatic retry with exponential backoff
and BufferingExporter for batching exports.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from typing import TYPE_CHECKING

from tracecraft.exporters.base import BaseExporter

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun

logger = logging.getLogger(__name__)


class RetryingExporter(BaseExporter):
    """
    Exporter wrapper that retries failed exports with exponential backoff.

    Wraps another exporter and automatically retries on transient failures
    using exponential backoff with jitter.

    Usage:
        ```python
        from tracecraft.exporters.otlp import OTLPExporter
        from tracecraft.exporters.retry import RetryingExporter

        otlp = OTLPExporter(endpoint="http://localhost:4317")
        retrying = RetryingExporter(
            exporter=otlp,
            max_retries=3,
            base_delay_ms=100,
        )

        # Use retrying exporter - will auto-retry on failures
        retrying.export(run)
        ```
    """

    def __init__(
        self,
        exporter: BaseExporter,
        max_retries: int = 3,
        base_delay_ms: int = 100,
        max_delay_ms: int = 30000,
        retryable_exceptions: tuple[type[Exception], ...] | None = None,
    ) -> None:
        """
        Initialize the retrying exporter.

        Args:
            exporter: The underlying exporter to wrap.
            max_retries: Maximum number of retry attempts.
            base_delay_ms: Initial delay between retries in milliseconds.
            max_delay_ms: Maximum delay between retries in milliseconds.
            retryable_exceptions: Exception types that trigger retry.
                Defaults to (ConnectionError, TimeoutError, OSError).
        """
        self._exporter = exporter
        self._max_retries = max_retries
        self._base_delay_ms = base_delay_ms
        self._max_delay_ms = max_delay_ms
        self._retryable_exceptions = retryable_exceptions or (
            ConnectionError,
            TimeoutError,
            OSError,
        )

    def export(self, run: AgentRun) -> None:
        """
        Export a run with automatic retry on failure.

        Args:
            run: The AgentRun to export.

        Raises:
            Exception: The last exception if all retries fail.
        """
        last_exception: Exception | None = None
        attempt = 0

        while attempt <= self._max_retries:
            try:
                self._exporter.export(run)
                return  # Success
            except self._retryable_exceptions as e:
                last_exception = e
                attempt += 1

                if attempt > self._max_retries:
                    logger.error(
                        "Export failed after %d retries: %s",
                        self._max_retries,
                        e,
                    )
                    raise

                # Calculate delay with exponential backoff and jitter
                delay_ms = min(
                    self._base_delay_ms * (2 ** (attempt - 1)),
                    self._max_delay_ms,
                )
                # Add jitter (50-100% of delay) - not for security
                jitter = random.uniform(0.5, 1.0)  # nosec B311
                delay_seconds = (delay_ms * jitter) / 1000

                logger.warning(
                    "Export failed (attempt %d/%d), retrying in %.2fs: %s",
                    attempt,
                    self._max_retries + 1,
                    delay_seconds,
                    e,
                )
                time.sleep(delay_seconds)
            except Exception:
                # Non-retryable exception - raise immediately
                raise

        # Should not reach here, but raise last exception if we do
        if last_exception:
            raise last_exception

    def shutdown(self) -> None:
        """Shutdown the underlying exporter."""
        if hasattr(self._exporter, "shutdown"):
            self._exporter.shutdown()


class BufferingExporter(BaseExporter):
    """
    Exporter wrapper that buffers runs before flushing.

    Collects runs in a buffer and exports them in batches when the
    buffer reaches capacity or when explicitly flushed.

    Usage:
        ```python
        from tracecraft.exporters.otlp import OTLPExporter
        from tracecraft.exporters.retry import BufferingExporter

        otlp = OTLPExporter(endpoint="http://localhost:4317")
        buffering = BufferingExporter(
            exporter=otlp,
            buffer_size=10,
        )

        # Runs are buffered
        buffering.export(run1)
        buffering.export(run2)

        # Manually flush or wait for buffer to fill
        buffering.flush()

        # Always flush on shutdown
        buffering.shutdown()
        ```
    """

    def __init__(
        self,
        exporter: BaseExporter,
        buffer_size: int = 10,
    ) -> None:
        """
        Initialize the buffering exporter.

        Args:
            exporter: The underlying exporter to wrap.
            buffer_size: Number of runs to buffer before flushing.
        """
        self._exporter = exporter
        self._buffer_size = buffer_size
        self._buffer: list[AgentRun] = []
        self._lock = threading.Lock()

    def export(self, run: AgentRun) -> None:
        """
        Add a run to the buffer, flushing if full.

        Args:
            run: The AgentRun to buffer.
        """
        with self._lock:
            self._buffer.append(run)

            if len(self._buffer) >= self._buffer_size:
                self._flush_unlocked()

    def flush(self) -> None:
        """Flush all buffered runs to the underlying exporter."""
        with self._lock:
            self._flush_unlocked()

    def _flush_unlocked(self) -> None:
        """Flush without acquiring lock (caller must hold lock)."""
        for run in self._buffer:
            try:
                self._exporter.export(run)
            except Exception as e:
                logger.error("Failed to export buffered run %s: %s", run.id, e)

        self._buffer.clear()

    def shutdown(self) -> None:
        """Flush remaining runs and shutdown."""
        self.flush()
        if hasattr(self._exporter, "shutdown"):
            self._exporter.shutdown()

    def __len__(self) -> int:
        """Return the number of buffered runs."""
        with self._lock:
            return len(self._buffer)
