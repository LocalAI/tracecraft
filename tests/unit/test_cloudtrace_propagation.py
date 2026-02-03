"""
Tests for GCP Cloud Trace context propagation.

TDD approach: Tests for Cloud Trace header format inject/extract.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from tracecraft.core.models import AgentRun


class TestCloudTraceContextPropagator:
    """Tests for GCP Cloud Trace Context propagation."""

    def test_inject_creates_both_headers(self, sample_run: AgentRun) -> None:
        """inject should create both W3C and Cloud Trace headers by default."""
        from tracecraft.propagation.cloudtrace import CloudTraceContextPropagator

        propagator = CloudTraceContextPropagator()
        carrier: dict[str, str] = {}

        propagator.inject(carrier, sample_run)

        # Should have W3C traceparent
        assert "traceparent" in carrier
        # Should have legacy Cloud Trace header
        assert "X-Cloud-Trace-Context" in carrier

    def test_inject_legacy_format(self, sample_run: AgentRun) -> None:
        """inject with use_legacy_format should create Cloud Trace header."""
        from tracecraft.propagation.cloudtrace import CloudTraceContextPropagator

        propagator = CloudTraceContextPropagator(use_legacy_format=True)
        carrier: dict[str, str] = {}

        propagator.inject(carrier, sample_run)

        assert "X-Cloud-Trace-Context" in carrier
        header = carrier["X-Cloud-Trace-Context"]
        # Format: TRACE_ID/SPAN_ID;o=OPTIONS
        assert "/" in header
        assert ";o=" in header

    def test_inject_cloud_trace_format(self, sample_run: AgentRun) -> None:
        """inject should create Cloud Trace in format TRACE_ID/SPAN_ID;o=OPTIONS."""
        from tracecraft.propagation.cloudtrace import CloudTraceContextPropagator

        propagator = CloudTraceContextPropagator()
        carrier: dict[str, str] = {}

        propagator.inject(carrier, sample_run)

        header = carrier["X-Cloud-Trace-Context"]
        parts = header.split(";o=")
        assert len(parts) == 2

        trace_span = parts[0]
        options = parts[1]

        # trace_span should be TRACE_ID/SPAN_ID
        trace_id, span_id = trace_span.split("/")
        assert len(trace_id) == 32  # 32 hex chars
        assert span_id.isdigit()  # Decimal span ID
        assert options in ("0", "1")

    def test_inject_session_id_header(self, sample_run_with_session: AgentRun) -> None:
        """inject should add session ID header when available."""
        from tracecraft.propagation.cloudtrace import (
            CLOUD_TRACE_SESSION_HEADER,
            CloudTraceContextPropagator,
        )

        propagator = CloudTraceContextPropagator()
        carrier: dict[str, str] = {}

        propagator.inject(carrier, sample_run_with_session)

        assert CLOUD_TRACE_SESSION_HEADER in carrier
        assert carrier[CLOUD_TRACE_SESSION_HEADER] == "session-12345"

    def test_inject_no_session_id_when_none(self, sample_run: AgentRun) -> None:
        """inject should not add session ID header when not set."""
        from tracecraft.propagation.cloudtrace import (
            CLOUD_TRACE_SESSION_HEADER,
            CloudTraceContextPropagator,
        )

        propagator = CloudTraceContextPropagator()
        carrier: dict[str, str] = {}

        propagator.inject(carrier, sample_run)

        assert CLOUD_TRACE_SESSION_HEADER not in carrier

    def test_inject_sampled_flag(self, sample_run: AgentRun) -> None:
        """inject should respect sampled parameter."""
        from tracecraft.propagation.cloudtrace import CloudTraceContextPropagator

        propagator = CloudTraceContextPropagator()

        # Test sampled=True
        carrier: dict[str, str] = {}
        propagator.inject(carrier, sample_run, sampled=True)
        assert ";o=1" in carrier["X-Cloud-Trace-Context"]

        # Test sampled=False
        carrier = {}
        propagator.inject(carrier, sample_run, sampled=False)
        assert ";o=0" in carrier["X-Cloud-Trace-Context"]

    def test_extract_parses_w3c_header(self) -> None:
        """extract should parse W3C traceparent headers first."""
        from tracecraft.propagation.cloudtrace import CloudTraceContextPropagator

        propagator = CloudTraceContextPropagator()
        carrier = {"traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"}

        result = propagator.extract(carrier)

        assert result is not None
        trace_id, span_id, sampled, session_id = result
        assert trace_id == "0af7651916cd43dd8448eb211c80319c"
        assert span_id == "b7ad6b7169203331"
        assert sampled is True
        assert session_id is None

    def test_extract_parses_cloud_trace_header(self) -> None:
        """extract should parse legacy Cloud Trace header."""
        from tracecraft.propagation.cloudtrace import CloudTraceContextPropagator

        propagator = CloudTraceContextPropagator()
        # Span ID in decimal
        carrier = {
            "X-Cloud-Trace-Context": "105445aa7843bc8bf206b12000100000/12345678901234567;o=1"
        }

        result = propagator.extract(carrier)

        assert result is not None
        trace_id, span_id, sampled, session_id = result
        assert trace_id == "105445aa7843bc8bf206b12000100000"
        # Span ID should be converted to hex
        assert len(span_id) == 16
        assert sampled is True
        assert session_id is None

    def test_extract_handles_unsampled(self) -> None:
        """extract should handle unsampled flag."""
        from tracecraft.propagation.cloudtrace import CloudTraceContextPropagator

        propagator = CloudTraceContextPropagator()
        carrier = {"X-Cloud-Trace-Context": "105445aa7843bc8bf206b12000100000/123;o=0"}

        result = propagator.extract(carrier)

        assert result is not None
        _, _, sampled, _ = result
        assert sampled is False

    def test_extract_with_session_id(self) -> None:
        """extract should return session ID when present."""
        from tracecraft.propagation.cloudtrace import CloudTraceContextPropagator

        propagator = CloudTraceContextPropagator()
        carrier = {
            "X-Cloud-Trace-Context": "105445aa7843bc8bf206b12000100000/123;o=1",
            "X-Cloud-Trace-Session-Id": "my-session-id",
        }

        result = propagator.extract(carrier)

        assert result is not None
        _, _, _, session_id = result
        assert session_id == "my-session-id"

    def test_extract_returns_none_for_missing_header(self) -> None:
        """extract should return None when no trace header is present."""
        from tracecraft.propagation.cloudtrace import CloudTraceContextPropagator

        propagator = CloudTraceContextPropagator()
        carrier: dict[str, str] = {}

        result = propagator.extract(carrier)

        assert result is None

    def test_extract_returns_none_for_invalid_format(self) -> None:
        """extract should return None for invalid Cloud Trace header."""
        from tracecraft.propagation.cloudtrace import CloudTraceContextPropagator

        propagator = CloudTraceContextPropagator()

        invalid_carriers = [
            {"X-Cloud-Trace-Context": "invalid"},
            {"X-Cloud-Trace-Context": "abc/123"},  # Missing options
            {"X-Cloud-Trace-Context": "abc;o=1"},  # Missing span
        ]

        for carrier in invalid_carriers:
            result = propagator.extract(carrier)
            assert result is None, f"Should reject: {carrier}"

    def test_extract_without_options(self) -> None:
        """extract should handle Cloud Trace header without options."""
        from tracecraft.propagation.cloudtrace import CloudTraceContextPropagator

        propagator = CloudTraceContextPropagator()
        carrier = {"X-Cloud-Trace-Context": "105445aa7843bc8bf206b12000100000/123"}

        result = propagator.extract(carrier)

        assert result is not None
        _, _, sampled, _ = result
        assert sampled is True  # Default to sampled


class TestCloudTraceW3CConversion:
    """Tests for Cloud Trace to W3C format conversion."""

    def test_to_w3c_format(self) -> None:
        """to_w3c_format should convert Cloud Trace to traceparent."""
        from tracecraft.propagation.cloudtrace import CloudTraceContextPropagator

        propagator = CloudTraceContextPropagator()
        # Span ID 123 in hex is 000000000000007b
        cloud_trace = "105445aa7843bc8bf206b12000100000/123;o=1"

        result = propagator.to_w3c_format(cloud_trace)

        assert result is not None
        # W3C format: version-trace_id-span_id-flags
        parts = result.split("-")
        assert len(parts) == 4
        assert parts[0] == "00"  # version
        assert parts[1] == "105445aa7843bc8bf206b12000100000"  # trace_id
        assert len(parts[2]) == 16  # span_id (hex)
        assert parts[3] == "01"  # sampled

    def test_to_w3c_format_unsampled(self) -> None:
        """to_w3c_format should handle unsampled traces."""
        from tracecraft.propagation.cloudtrace import CloudTraceContextPropagator

        propagator = CloudTraceContextPropagator()
        cloud_trace = "105445aa7843bc8bf206b12000100000/123;o=0"

        result = propagator.to_w3c_format(cloud_trace)

        assert result is not None
        assert result.endswith("-00")

    def test_to_w3c_format_invalid_returns_none(self) -> None:
        """to_w3c_format should return None for invalid input."""
        from tracecraft.propagation.cloudtrace import CloudTraceContextPropagator

        propagator = CloudTraceContextPropagator()

        result = propagator.to_w3c_format("invalid")

        assert result is None

    def test_from_w3c_format(self) -> None:
        """from_w3c_format should convert traceparent to Cloud Trace."""
        from tracecraft.propagation.cloudtrace import CloudTraceContextPropagator

        propagator = CloudTraceContextPropagator()
        traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"

        result = propagator.from_w3c_format(traceparent)

        assert result is not None
        assert "0af7651916cd43dd8448eb211c80319c/" in result
        assert ";o=1" in result

    def test_from_w3c_format_unsampled(self) -> None:
        """from_w3c_format should handle unsampled traces."""
        from tracecraft.propagation.cloudtrace import CloudTraceContextPropagator

        propagator = CloudTraceContextPropagator()
        traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-00"

        result = propagator.from_w3c_format(traceparent)

        assert result is not None
        assert ";o=0" in result

    def test_from_w3c_format_invalid_returns_none(self) -> None:
        """from_w3c_format should return None for invalid input."""
        from tracecraft.propagation.cloudtrace import CloudTraceContextPropagator

        propagator = CloudTraceContextPropagator()

        result = propagator.from_w3c_format("invalid")

        assert result is None


class TestCloudTraceHelpers:
    """Tests for Cloud Trace helper functions."""

    def test_span_id_to_decimal(self) -> None:
        """span_id_to_decimal should convert hex to decimal string."""
        from tracecraft.propagation.cloudtrace import span_id_to_decimal

        # b7ad6b7169203331 in decimal is 13235353014750950193
        result = span_id_to_decimal("b7ad6b7169203331")

        assert result == "13235353014750950193"

    def test_decimal_to_span_id(self) -> None:
        """decimal_to_span_id should convert decimal to 16-char hex."""
        from tracecraft.propagation.cloudtrace import decimal_to_span_id

        result = decimal_to_span_id("13235353014750950193")

        assert result == "b7ad6b7169203331"
        assert len(result) == 16

    def test_decimal_to_span_id_small_number(self) -> None:
        """decimal_to_span_id should pad small numbers."""
        from tracecraft.propagation.cloudtrace import decimal_to_span_id

        result = decimal_to_span_id("123")

        assert result == "000000000000007b"
        assert len(result) == 16


class TestCloudTraceContextIntegration:
    """Integration tests for Cloud Trace context propagation."""

    def test_inject_extract_roundtrip(self, sample_run: AgentRun) -> None:
        """inject and extract should round-trip correctly."""
        from tracecraft.propagation.cloudtrace import CloudTraceContextPropagator

        propagator = CloudTraceContextPropagator()
        carrier: dict[str, str] = {}

        # Inject
        propagator.inject(carrier, sample_run)

        # Extract
        result = propagator.extract(carrier)

        assert result is not None
        trace_id, span_id, sampled, _ = result
        assert len(trace_id) == 32
        assert len(span_id) == 16
        assert sampled is True

    def test_inject_extract_with_session(self, sample_run_with_session: AgentRun) -> None:
        """inject and extract should preserve session ID."""
        from tracecraft.propagation.cloudtrace import CloudTraceContextPropagator

        propagator = CloudTraceContextPropagator()
        carrier: dict[str, str] = {}

        # Inject
        propagator.inject(carrier, sample_run_with_session)

        # Extract
        result = propagator.extract(carrier)

        assert result is not None
        _, _, _, session_id = result
        assert session_id == "session-12345"


# Fixtures
@pytest.fixture
def sample_run() -> AgentRun:
    """Create a sample run for testing."""
    return AgentRun(
        id=uuid4(),
        name="test_run",
        start_time=datetime.now(UTC),
    )


@pytest.fixture
def sample_run_with_session() -> AgentRun:
    """Create a sample run with session ID for testing."""
    return AgentRun(
        id=uuid4(),
        name="test_run",
        start_time=datetime.now(UTC),
        session_id="session-12345",
    )
