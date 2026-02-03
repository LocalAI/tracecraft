"""
Tests for the retry exporter wrapper.

TDD approach: Tests for exponential backoff retry logic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from tracecraft.core.models import AgentRun


class TestRetryingExporter:
    """Tests for the RetryingExporter wrapper."""

    def test_retrying_exporter_wraps_exporter(self) -> None:
        """RetryingExporter should wrap another exporter."""
        from tracecraft.exporters.retry import RetryingExporter

        mock_exporter = MagicMock()
        retry_exporter = RetryingExporter(exporter=mock_exporter)

        assert retry_exporter._exporter is mock_exporter

    def test_successful_export_no_retry(self, sample_run) -> None:
        """Successful export should not trigger retry."""
        from tracecraft.exporters.retry import RetryingExporter

        mock_exporter = MagicMock()
        retry_exporter = RetryingExporter(exporter=mock_exporter, max_retries=3)

        retry_exporter.export(sample_run)

        mock_exporter.export.assert_called_once_with(sample_run)

    def test_retry_on_failure(self, sample_run) -> None:
        """Should retry on export failure."""
        from tracecraft.exporters.retry import RetryingExporter

        mock_exporter = MagicMock()
        # Fail twice, then succeed
        mock_exporter.export.side_effect = [
            ConnectionError("Network error"),
            ConnectionError("Network error"),
            None,  # Success
        ]

        retry_exporter = RetryingExporter(
            exporter=mock_exporter,
            max_retries=3,
            base_delay_ms=10,  # Fast for tests
        )

        retry_exporter.export(sample_run)

        assert mock_exporter.export.call_count == 3

    def test_max_retries_exceeded_raises(self, sample_run) -> None:
        """Should raise after max retries exceeded."""
        from tracecraft.exporters.retry import RetryingExporter

        mock_exporter = MagicMock()
        mock_exporter.export.side_effect = ConnectionError("Always fails")

        retry_exporter = RetryingExporter(
            exporter=mock_exporter,
            max_retries=3,
            base_delay_ms=1,
        )

        with pytest.raises(ConnectionError):
            retry_exporter.export(sample_run)

        assert mock_exporter.export.call_count == 4  # Initial + 3 retries

    def test_exponential_backoff(self, sample_run, monkeypatch) -> None:
        """Should use exponential backoff between retries."""
        from tracecraft.exporters import retry as retry_module
        from tracecraft.exporters.retry import RetryingExporter

        sleep_calls: list[float] = []

        def mock_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        monkeypatch.setattr(retry_module.time, "sleep", mock_sleep)

        mock_exporter = MagicMock()
        mock_exporter.export.side_effect = [
            ConnectionError("Fail 1"),
            ConnectionError("Fail 2"),
            ConnectionError("Fail 3"),
            None,  # Success
        ]

        retry_exporter = RetryingExporter(
            exporter=mock_exporter,
            max_retries=3,
            base_delay_ms=100,
            max_delay_ms=10000,
        )

        retry_exporter.export(sample_run)

        # Should have 3 sleep calls with exponential backoff
        assert len(sleep_calls) == 3
        # Each delay should be roughly double the previous (with jitter)
        assert sleep_calls[0] >= 0.05  # At least half of base
        assert sleep_calls[1] >= sleep_calls[0]  # Growing

    def test_retryable_exceptions_config(self, sample_run) -> None:
        """Should only retry on configured exception types."""
        from tracecraft.exporters.retry import RetryingExporter

        mock_exporter = MagicMock()
        mock_exporter.export.side_effect = ValueError("Not retryable")

        retry_exporter = RetryingExporter(
            exporter=mock_exporter,
            max_retries=3,
            retryable_exceptions=(ConnectionError, TimeoutError),
        )

        with pytest.raises(ValueError):
            retry_exporter.export(sample_run)

        # Should not retry non-retryable exceptions
        mock_exporter.export.assert_called_once()

    def test_default_retryable_exceptions(self, sample_run) -> None:
        """Should have sensible default retryable exceptions."""
        from tracecraft.exporters.retry import RetryingExporter

        mock_exporter = MagicMock()
        mock_exporter.export.side_effect = [
            TimeoutError("Timeout"),
            None,
        ]

        retry_exporter = RetryingExporter(
            exporter=mock_exporter,
            max_retries=3,
            base_delay_ms=1,
        )

        retry_exporter.export(sample_run)

        assert mock_exporter.export.call_count == 2


class TestBufferingExporter:
    """Tests for the BufferingExporter wrapper."""

    def test_buffering_exporter_buffers_runs(self, sample_run) -> None:
        """BufferingExporter should buffer runs before flushing."""
        from tracecraft.exporters.retry import BufferingExporter

        mock_exporter = MagicMock()
        buffer_exporter = BufferingExporter(
            exporter=mock_exporter,
            buffer_size=5,
        )

        # Add 3 runs - should not flush yet
        for _ in range(3):
            buffer_exporter.export(sample_run)

        mock_exporter.export.assert_not_called()

    def test_buffering_exporter_flushes_at_capacity(self, sample_run) -> None:
        """BufferingExporter should flush when buffer is full."""
        from tracecraft.exporters.retry import BufferingExporter

        mock_exporter = MagicMock()
        buffer_exporter = BufferingExporter(
            exporter=mock_exporter,
            buffer_size=3,
        )

        # Add 3 runs - should flush
        for _ in range(3):
            buffer_exporter.export(sample_run)

        assert mock_exporter.export.call_count == 3

    def test_buffering_exporter_manual_flush(self, sample_run) -> None:
        """BufferingExporter should support manual flush."""
        from tracecraft.exporters.retry import BufferingExporter

        mock_exporter = MagicMock()
        buffer_exporter = BufferingExporter(
            exporter=mock_exporter,
            buffer_size=10,
        )

        # Add 2 runs
        buffer_exporter.export(sample_run)
        buffer_exporter.export(sample_run)

        mock_exporter.export.assert_not_called()

        # Manual flush
        buffer_exporter.flush()

        assert mock_exporter.export.call_count == 2

    def test_buffering_exporter_flush_clears_buffer(self, sample_run) -> None:
        """Flush should clear the buffer."""
        from tracecraft.exporters.retry import BufferingExporter

        mock_exporter = MagicMock()
        buffer_exporter = BufferingExporter(
            exporter=mock_exporter,
            buffer_size=10,
        )

        buffer_exporter.export(sample_run)
        buffer_exporter.flush()
        buffer_exporter.flush()  # Second flush should do nothing

        assert mock_exporter.export.call_count == 1

    def test_buffering_exporter_shutdown_flushes(self, sample_run) -> None:
        """Shutdown should flush remaining runs."""
        from tracecraft.exporters.retry import BufferingExporter

        mock_exporter = MagicMock()
        buffer_exporter = BufferingExporter(
            exporter=mock_exporter,
            buffer_size=10,
        )

        buffer_exporter.export(sample_run)
        buffer_exporter.export(sample_run)

        buffer_exporter.shutdown()

        assert mock_exporter.export.call_count == 2

    def test_buffering_with_retry(self, sample_run) -> None:
        """Buffering and retry should work together."""
        from tracecraft.exporters.retry import BufferingExporter, RetryingExporter

        mock_exporter = MagicMock()
        retrying = RetryingExporter(exporter=mock_exporter, max_retries=2)
        buffering = BufferingExporter(exporter=retrying, buffer_size=2)

        buffering.export(sample_run)
        buffering.export(sample_run)

        assert mock_exporter.export.call_count == 2


# Fixtures
@pytest.fixture
def sample_run() -> AgentRun:
    """Create a sample run for testing."""
    return AgentRun(
        id=uuid4(),
        name="test_run",
        start_time=datetime.now(UTC),
    )
