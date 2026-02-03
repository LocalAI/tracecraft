"""Tests for async export pipeline functionality."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from tracecraft.core.models import AgentRun, Step, StepType
from tracecraft.exporters.async_pipeline import (
    AsyncBatchExporter,
    AsyncExporter,
    AsyncioExporter,
)
from tracecraft.exporters.base import BaseExporter


class MockExporter(BaseExporter):
    """Mock exporter for testing."""

    def __init__(self, delay: float = 0, fail_after: int | None = None):
        self.exported: list[AgentRun] = []
        self.delay = delay
        self.fail_after = fail_after
        self.export_count = 0

    def export(self, run: AgentRun) -> None:
        self.export_count += 1
        if self.fail_after and self.export_count > self.fail_after:
            raise RuntimeError("Simulated export failure")
        if self.delay:
            time.sleep(self.delay)
        self.exported.append(run)

    def close(self) -> None:
        pass


@pytest.fixture
def sample_run() -> AgentRun:
    """Create a sample run for testing."""
    trace_id = uuid4()
    return AgentRun(
        id=trace_id,
        name="test-run",
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC),
        steps=[
            Step(
                id=uuid4(),
                trace_id=trace_id,
                name="step",
                type=StepType.LLM,
                start_time=datetime.now(UTC),
            )
        ],
    )


def create_run(name: str = "test") -> AgentRun:
    """Helper to create runs."""
    trace_id = uuid4()
    return AgentRun(
        id=trace_id,
        name=name,
        start_time=datetime.now(UTC),
        steps=[],
    )


class TestAsyncExporter:
    """Tests for AsyncExporter."""

    def test_creates_exporter(self):
        """Test creating async exporter."""
        mock = MockExporter()
        async_exp = AsyncExporter(mock, queue_size=100, num_workers=2)

        assert async_exp._num_workers == 2
        assert len(async_exp._workers) == 2

        async_exp.shutdown(timeout=1)

    def test_export_returns_immediately(self, sample_run):
        """Test export doesn't block."""
        mock = MockExporter(delay=0.5)
        async_exp = AsyncExporter(mock, queue_size=100)

        start = time.time()
        async_exp.export(sample_run)
        elapsed = time.time() - start

        # Should return much faster than the delay
        assert elapsed < 0.1

        async_exp.shutdown(timeout=2)
        assert len(mock.exported) == 1

    def test_exports_multiple_runs(self, sample_run):
        """Test exporting multiple runs."""
        mock = MockExporter()
        async_exp = AsyncExporter(mock, queue_size=100)

        for i in range(10):
            async_exp.export(create_run(f"run-{i}"))

        # Give time for processing before shutdown
        time.sleep(0.5)
        async_exp.shutdown(timeout=10)

        assert len(mock.exported) == 10

    def test_drops_when_queue_full(self, sample_run):
        """Test dropping runs when queue is full."""
        mock = MockExporter(delay=0.5)  # Slow exporter
        on_drop = MagicMock()
        async_exp = AsyncExporter(
            mock,
            queue_size=2,
            num_workers=1,
            on_drop=on_drop,
        )

        # Fill queue
        for i in range(5):
            async_exp.export(create_run(f"run-{i}"))

        # Some should be dropped
        time.sleep(0.1)
        stats = async_exp.get_stats()

        async_exp.shutdown(timeout=5)

        assert stats["dropped"] > 0 or on_drop.called

    def test_on_error_callback(self):
        """Test on_error callback on export failure."""
        mock = MockExporter(fail_after=1)
        on_error = MagicMock()
        async_exp = AsyncExporter(mock, on_error=on_error)

        async_exp.export(create_run("good"))
        async_exp.export(create_run("bad"))

        # Give time for processing
        time.sleep(0.5)
        async_exp.shutdown(timeout=5)

        # Error callback should have been called
        assert on_error.called or async_exp.get_stats()["errors"] > 0

    def test_get_stats(self, sample_run):
        """Test statistics tracking."""
        mock = MockExporter()
        async_exp = AsyncExporter(mock)

        for _ in range(5):
            async_exp.export(sample_run)

        # Give time for processing
        time.sleep(0.5)
        async_exp.shutdown(timeout=5)

        stats = async_exp.get_stats()
        assert stats["exported"] == 5
        assert stats["dropped"] == 0
        assert stats["errors"] == 0

    def test_queue_size(self, sample_run):
        """Test queue size reporting."""
        mock = MockExporter(delay=0.5)
        async_exp = AsyncExporter(mock, queue_size=100, num_workers=1)

        for _ in range(5):
            async_exp.export(sample_run)

        # Queue should have items
        assert async_exp.queue_size() > 0 or mock.export_count > 0

        async_exp.shutdown(timeout=5)

    def test_is_healthy(self):
        """Test health check."""
        mock = MockExporter()
        async_exp = AsyncExporter(mock)

        assert async_exp.is_healthy() is True

        async_exp.shutdown(timeout=1)

    def test_multiple_workers(self, sample_run):
        """Test multiple worker threads."""
        mock = MockExporter(delay=0.05)  # Shorter delay
        async_exp = AsyncExporter(mock, num_workers=4)

        for _ in range(20):
            async_exp.export(sample_run)

        # Give time for processing with multiple workers
        time.sleep(1)
        async_exp.shutdown(timeout=10)

        assert len(mock.exported) == 20


class TestAsyncBatchExporter:
    """Tests for AsyncBatchExporter."""

    def test_creates_exporter(self):
        """Test creating batch exporter."""
        mock = MockExporter()
        batch_exp = AsyncBatchExporter(
            mock,
            batch_size=10,
            flush_interval_seconds=1.0,
        )

        assert batch_exp._batch_size == 10

        batch_exp.shutdown(timeout=1)

    def test_batches_exports(self, sample_run):
        """Test runs are batched."""
        mock = MockExporter()
        batch_exp = AsyncBatchExporter(
            mock,
            batch_size=5,
            flush_interval_seconds=60,  # Long interval
        )

        # Add fewer than batch size
        for i in range(3):
            batch_exp.export(create_run(f"run-{i}"))

        # Nothing exported yet
        time.sleep(0.1)
        assert len(mock.exported) < 3

        # Add more to trigger batch
        for i in range(3, 6):
            batch_exp.export(create_run(f"run-{i}"))

        time.sleep(0.2)
        assert len(mock.exported) >= 5

        batch_exp.shutdown(timeout=2)

    def test_flushes_on_interval(self, sample_run):
        """Test flush on interval."""
        mock = MockExporter()
        batch_exp = AsyncBatchExporter(
            mock,
            batch_size=100,  # Large batch
            flush_interval_seconds=0.2,  # Short interval
        )

        batch_exp.export(sample_run)

        # Wait for interval
        time.sleep(0.5)

        assert len(mock.exported) == 1

        batch_exp.shutdown(timeout=1)

    def test_manual_flush(self, sample_run):
        """Test manual flush."""
        mock = MockExporter()
        batch_exp = AsyncBatchExporter(
            mock,
            batch_size=100,
            flush_interval_seconds=60,
        )

        batch_exp.export(sample_run)
        time.sleep(0.1)  # Wait for item to be queued
        batch_exp.flush()

        time.sleep(0.5)
        assert len(mock.exported) == 1

        batch_exp.shutdown(timeout=5)

    def test_get_stats(self, sample_run):
        """Test statistics tracking."""
        mock = MockExporter()
        batch_exp = AsyncBatchExporter(mock, batch_size=3)

        for _ in range(6):
            batch_exp.export(sample_run)

        # Give time for batches to be processed
        time.sleep(0.5)
        batch_exp.shutdown(timeout=5)

        stats = batch_exp.get_stats()
        assert stats["runs_exported"] == 6
        assert stats["batches_exported"] == 2

    def test_pending_count(self, sample_run):
        """Test pending count."""
        mock = MockExporter(delay=0.5)
        batch_exp = AsyncBatchExporter(mock, batch_size=100)

        for _ in range(5):
            batch_exp.export(sample_run)

        assert batch_exp.pending_count() > 0

        batch_exp.shutdown(timeout=5)

    def test_on_error_callback(self):
        """Test error callback for batch failures."""
        mock = MockExporter(fail_after=2)
        on_error = MagicMock()
        batch_exp = AsyncBatchExporter(
            mock,
            batch_size=3,
            on_error=on_error,
        )

        for i in range(6):
            batch_exp.export(create_run(f"run-{i}"))

        # Give time for batches to be processed
        time.sleep(0.5)
        batch_exp.shutdown(timeout=5)

        stats = batch_exp.get_stats()
        assert stats["errors"] > 0 or on_error.called


class TestAsyncioExporter:
    """Tests for AsyncioExporter."""

    @pytest.mark.asyncio
    async def test_creates_exporter(self):
        """Test creating asyncio exporter."""
        mock = MockExporter()
        async_exp = AsyncioExporter(mock)

        await async_exp.start()
        assert async_exp._running is True

        await async_exp.shutdown_async(timeout=1)

    @pytest.mark.asyncio
    async def test_export_async(self, sample_run):
        """Test async export."""
        mock = MockExporter()
        async_exp = AsyncioExporter(mock)

        await async_exp.start()
        await async_exp.export_async(sample_run)

        # Give time for background export
        await asyncio.sleep(0.2)

        assert len(mock.exported) == 1

        await async_exp.shutdown_async(timeout=1)

    @pytest.mark.asyncio
    async def test_exports_multiple_runs(self, sample_run):
        """Test exporting multiple runs."""
        mock = MockExporter()
        async_exp = AsyncioExporter(mock)

        await async_exp.start()

        for i in range(10):
            await async_exp.export_async(create_run(f"run-{i}"))

        # Give time for processing
        await asyncio.sleep(0.5)
        await async_exp.shutdown_async(timeout=5)

        assert len(mock.exported) == 10

    @pytest.mark.asyncio
    async def test_raises_if_not_started(self, sample_run):
        """Test raises error if not started."""
        mock = MockExporter()
        async_exp = AsyncioExporter(mock)

        with pytest.raises(RuntimeError, match="not started"):
            await async_exp.export_async(sample_run)

    @pytest.mark.asyncio
    async def test_shutdown_drains_queue(self, sample_run):
        """Test shutdown processes remaining items."""
        mock = MockExporter(delay=0.02)  # Faster delay
        async_exp = AsyncioExporter(mock, queue_size=100)

        await async_exp.start()

        for i in range(5):
            await async_exp.export_async(create_run(f"run-{i}"))

        # Give time for processing
        await asyncio.sleep(0.5)
        await async_exp.shutdown_async(timeout=10)

        assert len(mock.exported) == 5


class TestExporterIntegration:
    """Integration tests for async exporters."""

    def test_chain_with_retrying(self, sample_run):
        """Test async exporter with retrying exporter."""
        from tracecraft.exporters.retry import RetryingExporter

        mock = MockExporter()
        retrying = RetryingExporter(mock, max_retries=2)
        async_exp = AsyncExporter(retrying)

        async_exp.export(sample_run)
        async_exp.shutdown(timeout=2)

        assert len(mock.exported) == 1

    def test_chain_with_buffering(self, sample_run):
        """Test async batch exporter similar to buffering."""
        mock = MockExporter()
        batch_exp = AsyncBatchExporter(
            mock,
            batch_size=5,
            flush_interval_seconds=0.1,
        )

        for i in range(10):
            batch_exp.export(create_run(f"run-{i}"))

        # Give time for batches to be processed
        time.sleep(0.5)
        batch_exp.shutdown(timeout=5)

        assert len(mock.exported) == 10
