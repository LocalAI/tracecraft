"""
Tests for rate limiting exporter wrapper.

TDD approach: Tests for token bucket rate limiting.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from agenttrace.core.models import AgentRun


class TestRateLimitedExporter:
    """Tests for the RateLimitedExporter wrapper."""

    def test_rate_limited_exporter_wraps_exporter(self) -> None:
        """RateLimitedExporter should wrap another exporter."""
        from agenttrace.exporters.rate_limited import RateLimitedExporter

        mock_exporter = MagicMock()
        rate_limited = RateLimitedExporter(
            exporter=mock_exporter,
            rate=10.0,
        )

        assert rate_limited._exporter is mock_exporter

    def test_export_within_rate_limit(self, sample_run) -> None:
        """Exports within rate limit should succeed immediately."""
        from agenttrace.exporters.rate_limited import RateLimitedExporter

        mock_exporter = MagicMock()
        rate_limited = RateLimitedExporter(
            exporter=mock_exporter,
            rate=100.0,  # High rate
            burst=10,
        )

        # Should succeed immediately
        rate_limited.export(sample_run)

        mock_exporter.export.assert_called_once_with(sample_run)

    def test_export_respects_rate_limit(self, sample_run) -> None:
        """Exports should be rate limited."""
        from agenttrace.exporters.rate_limited import RateLimitedExporter

        mock_exporter = MagicMock()
        rate_limited = RateLimitedExporter(
            exporter=mock_exporter,
            rate=10.0,  # 10 per second
            burst=1,  # Only 1 token
        )

        # First export uses the burst token
        rate_limited.export(sample_run)
        assert mock_exporter.export.call_count == 1

        # Second export should wait for token
        start = time.monotonic()
        rate_limited.export(sample_run)
        elapsed = time.monotonic() - start

        # Should have waited ~0.1 seconds for token
        assert elapsed >= 0.05  # Allow some tolerance
        assert mock_exporter.export.call_count == 2

    def test_burst_allows_initial_burst(self, sample_run) -> None:
        """Burst tokens should allow immediate exports up to burst limit."""
        from agenttrace.exporters.rate_limited import RateLimitedExporter

        mock_exporter = MagicMock()
        rate_limited = RateLimitedExporter(
            exporter=mock_exporter,
            rate=1.0,  # Slow rate
            burst=5,  # But 5 burst tokens
        )

        # Should be able to export 5 times immediately
        start = time.monotonic()
        for _ in range(5):
            rate_limited.export(sample_run)
        elapsed = time.monotonic() - start

        # All 5 should be near-instant
        assert elapsed < 0.5
        assert mock_exporter.export.call_count == 5

    def test_rate_limiter_non_blocking_mode(self, sample_run) -> None:
        """Non-blocking mode should drop exports when rate exceeded."""
        from agenttrace.exporters.rate_limited import RateLimitedExporter

        mock_exporter = MagicMock()
        rate_limited = RateLimitedExporter(
            exporter=mock_exporter,
            rate=1.0,
            burst=1,
            blocking=False,
        )

        # First export succeeds
        rate_limited.export(sample_run)

        # Second export should be dropped (non-blocking)
        rate_limited.export(sample_run)

        assert mock_exporter.export.call_count == 1

    def test_rate_limiter_tracks_dropped_exports(self, sample_run) -> None:
        """Should track number of dropped exports."""
        from agenttrace.exporters.rate_limited import RateLimitedExporter

        mock_exporter = MagicMock()
        rate_limited = RateLimitedExporter(
            exporter=mock_exporter,
            rate=1.0,
            burst=1,
            blocking=False,
        )

        # Export multiple times quickly
        rate_limited.export(sample_run)
        rate_limited.export(sample_run)
        rate_limited.export(sample_run)

        assert rate_limited.dropped_count >= 2

    def test_rate_limiter_shutdown(self, sample_run) -> None:  # noqa: ARG002
        """Shutdown should propagate to underlying exporter."""
        from agenttrace.exporters.rate_limited import RateLimitedExporter

        mock_exporter = MagicMock()
        rate_limited = RateLimitedExporter(
            exporter=mock_exporter,
            rate=10.0,
        )

        rate_limited.shutdown()

        mock_exporter.shutdown.assert_called_once()


class TestTokenBucket:
    """Tests for the TokenBucket implementation."""

    def test_token_bucket_initial_tokens(self) -> None:
        """Token bucket should start with burst tokens."""
        from agenttrace.exporters.rate_limited import TokenBucket

        bucket = TokenBucket(rate=10.0, burst=5)

        # Should be able to acquire 5 tokens immediately
        for _ in range(5):
            assert bucket.acquire(blocking=False)

        # 6th should fail (no blocking)
        assert not bucket.acquire(blocking=False)

    def test_token_bucket_refills(self) -> None:
        """Token bucket should refill over time."""
        from agenttrace.exporters.rate_limited import TokenBucket

        bucket = TokenBucket(rate=100.0, burst=1)  # 100 tokens/sec

        # Use the token
        assert bucket.acquire(blocking=False)
        assert not bucket.acquire(blocking=False)

        # Wait for refill
        time.sleep(0.02)  # 20ms = 2 tokens at 100/sec

        # Should have tokens again
        assert bucket.acquire(blocking=False)

    def test_token_bucket_blocking_acquire(self) -> None:
        """Blocking acquire should wait for token."""
        from agenttrace.exporters.rate_limited import TokenBucket

        bucket = TokenBucket(rate=50.0, burst=1)  # 50 tokens/sec

        # Use the token
        assert bucket.acquire(blocking=False)

        # Blocking acquire should wait
        start = time.monotonic()
        bucket.acquire(blocking=True)
        elapsed = time.monotonic() - start

        # Should have waited ~0.02 seconds
        assert elapsed >= 0.01


# Fixtures
@pytest.fixture
def sample_run() -> AgentRun:
    """Create a sample run for testing."""
    return AgentRun(
        id=uuid4(),
        name="test_run",
        start_time=datetime.now(UTC),
    )
