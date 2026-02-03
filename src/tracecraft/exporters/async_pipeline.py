"""
Async export pipeline for TraceCraft.

Provides non-blocking export capabilities using background threads
and async queues for high-throughput production deployments.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import queue
import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from tracecraft.exporters.base import BaseExporter

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun

logger = logging.getLogger(__name__)


class AsyncExporter(BaseExporter):
    """
    Exporter wrapper that exports asynchronously in a background thread.

    Runs don't block the main thread - they're queued and exported
    by a background worker. Useful for high-throughput scenarios where
    export latency shouldn't impact application performance.

    Example:
        from tracecraft.exporters.otlp import OTLPExporter
        from tracecraft.exporters.async_pipeline import AsyncExporter

        otlp = OTLPExporter(endpoint="http://localhost:4317")
        async_otlp = AsyncExporter(
            exporter=otlp,
            queue_size=1000,
            num_workers=2,
        )

        # Exports are now non-blocking
        async_otlp.export(run)  # Returns immediately

        # Ensure cleanup on shutdown
        async_otlp.shutdown()
    """

    def __init__(
        self,
        exporter: BaseExporter,
        queue_size: int = 1000,
        num_workers: int = 1,
        on_error: Callable[[AgentRun, Exception], None] | None = None,
        on_drop: Callable[[AgentRun], None] | None = None,
    ) -> None:
        """
        Initialize the async exporter.

        Args:
            exporter: The underlying exporter to wrap.
            queue_size: Maximum queue size. Exports are dropped if full.
            num_workers: Number of background worker threads.
            on_error: Callback when export fails (run, exception).
            on_drop: Callback when a run is dropped due to full queue.
        """
        self._exporter = exporter
        self._queue: queue.Queue[AgentRun | None] = queue.Queue(maxsize=queue_size)
        self._num_workers = num_workers
        self._on_error = on_error
        self._on_drop = on_drop
        self._shutdown_event = threading.Event()
        self._workers: list[threading.Thread] = []

        # Statistics
        self._stats = {
            "exported": 0,
            "dropped": 0,
            "errors": 0,
        }
        self._stats_lock = threading.Lock()

        # Start worker threads
        self._start_workers()

    def _start_workers(self) -> None:
        """Start background worker threads."""
        for i in range(self._num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"tracecraft-async-exporter-{i}",
                daemon=True,
            )
            worker.start()
            self._workers.append(worker)

        logger.debug(
            "Started %d async export workers",
            self._num_workers,
        )

    def _worker_loop(self) -> None:
        """Worker thread main loop."""
        while not self._shutdown_event.is_set():
            try:
                # Get with timeout to allow checking shutdown event
                run = self._queue.get(timeout=0.5)

                if run is None:
                    # Shutdown signal
                    break

                try:
                    self._exporter.export(run)
                    with self._stats_lock:
                        self._stats["exported"] += 1
                except Exception as e:
                    with self._stats_lock:
                        self._stats["errors"] += 1

                    logger.error(
                        "Async export failed for run '%s': %s",
                        run.name,
                        e,
                    )

                    if self._on_error:
                        try:
                            self._on_error(run, e)
                        except Exception:
                            logger.exception("Error in on_error callback")

                finally:
                    self._queue.task_done()

            except queue.Empty:
                # Timeout, check shutdown event and continue
                continue

    def export(self, run: AgentRun) -> None:
        """
        Queue a run for async export.

        Returns immediately. If the queue is full, the run is dropped
        and on_drop callback is called if configured.

        Args:
            run: The AgentRun to export.
        """
        try:
            self._queue.put_nowait(run)
        except queue.Full:
            with self._stats_lock:
                self._stats["dropped"] += 1

            logger.warning(
                "Export queue full, dropping run '%s'",
                run.name,
            )

            if self._on_drop:
                try:
                    self._on_drop(run)
                except Exception:
                    logger.exception("Error in on_drop callback")

    def shutdown(self, timeout: float = 10.0) -> None:
        """
        Shutdown the async exporter.

        Waits for the queue to drain and workers to finish.

        Args:
            timeout: Maximum time to wait for shutdown.
        """
        logger.debug("Shutting down async exporter...")

        # Signal shutdown
        self._shutdown_event.set()

        # Send stop signals to workers
        for _ in self._workers:
            with contextlib.suppress(queue.Full):
                self._queue.put_nowait(None)

        # Wait for workers to finish
        deadline = time.time() + timeout
        for worker in self._workers:
            remaining = max(0, deadline - time.time())
            worker.join(timeout=remaining)

            if worker.is_alive():
                logger.warning(
                    "Worker %s did not finish within timeout",
                    worker.name,
                )

        # Shutdown underlying exporter
        if hasattr(self._exporter, "shutdown"):
            self._exporter.shutdown()
        elif hasattr(self._exporter, "close"):
            self._exporter.close()

        logger.info(
            "Async exporter shutdown complete. Stats: %s",
            self._stats,
        )

    def close(self) -> None:
        """Alias for shutdown."""
        self.shutdown()

    def get_stats(self) -> dict[str, int]:
        """Get export statistics."""
        with self._stats_lock:
            return self._stats.copy()

    def queue_size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()

    def is_healthy(self) -> bool:
        """Check if the exporter is healthy (workers running, queue not full)."""
        # Check if any worker is alive and queue is not too full (> 90%)
        workers_alive = any(w.is_alive() for w in self._workers)
        queue_healthy = self._queue.qsize() <= self._queue.maxsize * 0.9
        return workers_alive and queue_healthy


class AsyncBatchExporter(BaseExporter):
    """
    Async exporter that batches runs before exporting.

    Combines batching and async export for maximum efficiency.
    Exports when batch is full OR after a timeout, whichever comes first.

    Example:
        from tracecraft.exporters.otlp import OTLPExporter
        from tracecraft.exporters.async_pipeline import AsyncBatchExporter

        otlp = OTLPExporter(endpoint="http://localhost:4317")
        batch_exporter = AsyncBatchExporter(
            exporter=otlp,
            batch_size=50,
            flush_interval_seconds=5.0,
        )

        # Non-blocking, batched exports
        batch_exporter.export(run)

        # Ensure cleanup
        batch_exporter.shutdown()
    """

    def __init__(
        self,
        exporter: BaseExporter,
        batch_size: int = 50,
        flush_interval_seconds: float = 5.0,
        max_queue_size: int = 1000,
        on_error: Callable[[list[AgentRun], Exception], None] | None = None,
    ) -> None:
        """
        Initialize the async batch exporter.

        Args:
            exporter: The underlying exporter to wrap.
            batch_size: Number of runs to batch before exporting.
            flush_interval_seconds: Max time before forcing a flush.
            max_queue_size: Maximum queue size before dropping.
            on_error: Callback when batch export fails.
        """
        self._exporter = exporter
        self._batch_size = batch_size
        self._flush_interval = flush_interval_seconds
        self._max_queue_size = max_queue_size
        self._on_error = on_error

        self._queue: queue.Queue[AgentRun | None] = queue.Queue(maxsize=max_queue_size)
        self._batch: list[AgentRun] = []
        self._batch_lock = threading.Lock()
        self._last_flush = time.time()
        self._shutdown_event = threading.Event()

        # Statistics
        self._stats = {
            "batches_exported": 0,
            "runs_exported": 0,
            "dropped": 0,
            "errors": 0,
        }
        self._stats_lock = threading.Lock()

        # Start worker thread
        self._worker = threading.Thread(
            target=self._worker_loop,
            name="tracecraft-batch-exporter",
            daemon=True,
        )
        self._worker.start()

    def _worker_loop(self) -> None:
        """Worker thread main loop."""
        while not self._shutdown_event.is_set():
            try:
                # Get with timeout for periodic flush check
                run = self._queue.get(timeout=0.1)

                if run is None:
                    # Shutdown signal, flush remaining (must hold lock)
                    with self._batch_lock:
                        self._flush()
                    break

                with self._batch_lock:
                    self._batch.append(run)

                    # Check if batch is full
                    if len(self._batch) >= self._batch_size:
                        self._flush()

                self._queue.task_done()

            except queue.Empty:
                # Check if we should flush based on time
                with self._batch_lock:
                    if self._batch and (time.time() - self._last_flush) >= self._flush_interval:
                        self._flush()

    def _flush(self) -> None:
        """Flush the current batch (must hold batch_lock)."""
        if not self._batch:
            return

        batch = self._batch[:]
        self._batch.clear()
        self._last_flush = time.time()

        # Export each run in the batch
        errors = []
        for run in batch:
            try:
                self._exporter.export(run)
            except Exception as e:
                errors.append((run, e))

        with self._stats_lock:
            self._stats["batches_exported"] += 1
            self._stats["runs_exported"] += len(batch) - len(errors)
            self._stats["errors"] += len(errors)

        if errors:
            logger.error(
                "Batch export had %d errors out of %d runs",
                len(errors),
                len(batch),
            )

            if self._on_error:
                try:
                    self._on_error([r for r, _ in errors], errors[0][1])
                except Exception:
                    logger.exception("Error in on_error callback")

    def export(self, run: AgentRun) -> None:
        """
        Queue a run for batched async export.

        Args:
            run: The AgentRun to export.
        """
        try:
            self._queue.put_nowait(run)
        except queue.Full:
            with self._stats_lock:
                self._stats["dropped"] += 1

            logger.warning(
                "Export queue full, dropping run '%s'",
                run.name,
            )

    def flush(self) -> None:
        """Force a flush of the current batch."""
        with self._batch_lock:
            self._flush()

    def shutdown(self, timeout: float = 10.0) -> None:
        """
        Shutdown the batch exporter.

        Args:
            timeout: Maximum time to wait for shutdown.
        """
        logger.debug("Shutting down batch exporter...")

        # Signal shutdown
        self._shutdown_event.set()

        # Send stop signal
        with contextlib.suppress(queue.Full):
            self._queue.put_nowait(None)

        # Wait for worker
        self._worker.join(timeout=timeout)

        if self._worker.is_alive():
            logger.warning("Batch worker did not finish within timeout")

        # Shutdown underlying exporter
        if hasattr(self._exporter, "shutdown"):
            self._exporter.shutdown()
        elif hasattr(self._exporter, "close"):
            self._exporter.close()

        logger.info(
            "Batch exporter shutdown complete. Stats: %s",
            self._stats,
        )

    def close(self) -> None:
        """Alias for shutdown."""
        self.shutdown()

    def get_stats(self) -> dict[str, int]:
        """Get export statistics."""
        with self._stats_lock:
            return self._stats.copy()

    def pending_count(self) -> int:
        """Get number of runs waiting to be exported."""
        with self._batch_lock:
            return self._queue.qsize() + len(self._batch)


class AsyncioExporter(BaseExporter):
    """
    Exporter wrapper for asyncio-based applications.

    Uses asyncio queues and tasks for non-blocking export in
    async applications. Must be used within an asyncio event loop.

    Example:
        import asyncio
        from tracecraft.exporters.otlp import OTLPExporter
        from tracecraft.exporters.async_pipeline import AsyncioExporter

        async def main():
            otlp = OTLPExporter(endpoint="http://localhost:4317")
            async_exporter = AsyncioExporter(otlp)

            await async_exporter.start()

            # Export asynchronously
            await async_exporter.export_async(run)

            # Shutdown
            await async_exporter.shutdown_async()

        asyncio.run(main())
    """

    def __init__(
        self,
        exporter: BaseExporter,
        queue_size: int = 1000,
    ) -> None:
        """
        Initialize the asyncio exporter.

        Args:
            exporter: The underlying exporter to wrap.
            queue_size: Maximum queue size.
        """
        self._exporter = exporter
        self._queue_size = queue_size
        self._queue: asyncio.Queue[AgentRun | None] | None = None
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        """Start the async export worker."""
        if self._running:
            return

        self._queue = asyncio.Queue(maxsize=self._queue_size)
        self._task = asyncio.create_task(self._worker_loop())
        self._running = True

    async def _worker_loop(self) -> None:
        """Async worker loop."""
        while self._running:
            try:
                run = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=0.5,
                )

                if run is None:
                    self._queue.task_done()
                    break

                try:
                    # Export in thread pool to avoid blocking
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(
                        None,
                        self._exporter.export,
                        run,
                    )
                finally:
                    self._queue.task_done()

            except TimeoutError:
                continue
            except Exception:
                logger.exception("Async export error")

    def export(self, run: AgentRun) -> None:
        """
        Synchronous export interface.

        For sync code, use export_async() instead when possible.
        This method blocks until the run is queued.
        """
        if self._queue is None:
            raise RuntimeError("Exporter not started. Call start() first.")

        # Try to queue async, fall back to sync export if no event loop
        try:
            asyncio.get_running_loop()  # Raises RuntimeError if no loop running
            # We're inside an async context, schedule the put
            asyncio.create_task(self._queue.put(run))
        except RuntimeError:
            # No running event loop, fall back to sync export
            self._exporter.export(run)

    async def export_async(self, run: AgentRun) -> None:
        """
        Queue a run for async export.

        Args:
            run: The AgentRun to export.
        """
        if self._queue is None:
            raise RuntimeError("Exporter not started. Call start() first.")

        await self._queue.put(run)

    async def shutdown_async(self, timeout: float = 10.0) -> None:
        """
        Shutdown the async exporter.

        Args:
            timeout: Maximum time to wait for shutdown.
        """
        if not self._running:
            return

        self._running = False

        # Send stop signal
        if self._queue:
            await self._queue.put(None)

        # Wait for worker to finish
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=timeout)
            except TimeoutError:
                logger.warning("Async worker did not finish within timeout")
                self._task.cancel()

        # Shutdown underlying exporter
        if hasattr(self._exporter, "shutdown"):
            self._exporter.shutdown()
        elif hasattr(self._exporter, "close"):
            self._exporter.close()

    def close(self) -> None:
        """Synchronous close - for compatibility."""
        try:
            asyncio.get_running_loop()  # Raises RuntimeError if no loop running
            # We're inside an async context, schedule shutdown
            asyncio.create_task(self.shutdown_async())
        except RuntimeError:
            # No running event loop, run shutdown synchronously
            asyncio.run(self.shutdown_async())
