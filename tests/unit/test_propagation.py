"""
Tests for distributed tracing propagation.

TDD approach: Tests for W3C Trace Context propagation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from agenttrace.core.models import AgentRun


class TestW3CTraceContextPropagator:
    """Tests for W3C Trace Context propagation."""

    def test_inject_creates_traceparent_header(self, sample_run) -> None:
        """inject should create traceparent header."""
        from agenttrace.propagation.w3c import W3CTraceContextPropagator

        propagator = W3CTraceContextPropagator()
        carrier: dict[str, str] = {}

        propagator.inject(carrier, sample_run)

        assert "traceparent" in carrier
        # Format: version-trace_id-parent_id-flags
        parts = carrier["traceparent"].split("-")
        assert len(parts) == 4
        assert parts[0] == "00"  # version

    def test_inject_uses_run_id_as_trace_id(self, sample_run) -> None:
        """inject should use run.id as trace_id."""
        from agenttrace.propagation.w3c import W3CTraceContextPropagator

        propagator = W3CTraceContextPropagator()
        carrier: dict[str, str] = {}

        propagator.inject(carrier, sample_run)

        parts = carrier["traceparent"].split("-")
        trace_id = parts[1]
        # trace_id should be 32 hex chars (128 bits)
        assert len(trace_id) == 32
        # Should be derived from run.id
        assert trace_id == sample_run.id.hex

    def test_inject_creates_span_id(self, sample_run) -> None:
        """inject should create a valid span_id."""
        from agenttrace.propagation.w3c import W3CTraceContextPropagator

        propagator = W3CTraceContextPropagator()
        carrier: dict[str, str] = {}

        propagator.inject(carrier, sample_run)

        parts = carrier["traceparent"].split("-")
        span_id = parts[2]
        # span_id should be 16 hex chars (64 bits)
        assert len(span_id) == 16

    def test_inject_sets_sampled_flag(self, sample_run) -> None:
        """inject should set sampled flag."""
        from agenttrace.propagation.w3c import W3CTraceContextPropagator

        propagator = W3CTraceContextPropagator()
        carrier: dict[str, str] = {}

        propagator.inject(carrier, sample_run)

        parts = carrier["traceparent"].split("-")
        flags = parts[3]
        assert flags == "01"  # sampled

    def test_inject_with_tracestate(self, sample_run) -> None:
        """inject should optionally include tracestate."""
        from agenttrace.propagation.w3c import W3CTraceContextPropagator

        propagator = W3CTraceContextPropagator(vendor="agenttrace")
        carrier: dict[str, str] = {}

        propagator.inject(carrier, sample_run)

        assert "tracestate" in carrier
        assert "agenttrace=" in carrier["tracestate"]

    def test_extract_parses_traceparent(self) -> None:
        """extract should parse traceparent header."""
        from agenttrace.propagation.w3c import W3CTraceContextPropagator

        propagator = W3CTraceContextPropagator()
        carrier = {"traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"}

        result = propagator.extract(carrier)

        assert result is not None
        trace_id, span_id, sampled = result
        assert trace_id == "0af7651916cd43dd8448eb211c80319c"
        assert span_id == "b7ad6b7169203331"
        assert sampled is True

    def test_extract_handles_unsampled(self) -> None:
        """extract should handle unsampled flag."""
        from agenttrace.propagation.w3c import W3CTraceContextPropagator

        propagator = W3CTraceContextPropagator()
        carrier = {"traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-00"}

        result = propagator.extract(carrier)

        assert result is not None
        _, _, sampled = result
        assert sampled is False

    def test_extract_returns_none_for_missing_header(self) -> None:
        """extract should return None when traceparent missing."""
        from agenttrace.propagation.w3c import W3CTraceContextPropagator

        propagator = W3CTraceContextPropagator()
        carrier: dict[str, str] = {}

        result = propagator.extract(carrier)

        assert result is None

    def test_extract_returns_none_for_invalid_format(self) -> None:
        """extract should return None for invalid traceparent."""
        from agenttrace.propagation.w3c import W3CTraceContextPropagator

        propagator = W3CTraceContextPropagator()

        # Test various invalid formats
        invalid_carriers = [
            {"traceparent": "invalid"},
            {"traceparent": "00-too-short"},
            {"traceparent": "00-notahexstring-b7ad6b7169203331-01"},
            {"traceparent": "ff-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"},
        ]

        for carrier in invalid_carriers:
            result = propagator.extract(carrier)
            assert result is None, f"Should reject: {carrier}"

    def test_extract_case_insensitive_header_names(self) -> None:
        """extract should handle case-insensitive header names."""
        from agenttrace.propagation.w3c import W3CTraceContextPropagator

        propagator = W3CTraceContextPropagator()
        carrier = {"Traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"}

        result = propagator.extract(carrier)

        assert result is not None


class TestTraceContextHelpers:
    """Tests for trace context helper functions."""

    def test_generate_span_id(self) -> None:
        """generate_span_id should create valid span IDs."""
        from agenttrace.propagation.w3c import generate_span_id

        span_id = generate_span_id()

        assert len(span_id) == 16
        # Should be valid hex
        int(span_id, 16)

    def test_generate_span_id_unique(self) -> None:
        """generate_span_id should create unique IDs."""
        from agenttrace.propagation.w3c import generate_span_id

        ids = {generate_span_id() for _ in range(100)}

        assert len(ids) == 100

    def test_format_trace_id_from_uuid(self) -> None:
        """format_trace_id should format UUID to 32-char hex."""
        from agenttrace.propagation.w3c import format_trace_id

        test_uuid = uuid4()
        result = format_trace_id(test_uuid)

        assert len(result) == 32
        assert result == test_uuid.hex


class TestContextPropagationIntegration:
    """Integration tests for context propagation."""

    def test_inject_extract_roundtrip(self, sample_run) -> None:
        """inject and extract should round-trip correctly."""
        from agenttrace.propagation.w3c import W3CTraceContextPropagator

        propagator = W3CTraceContextPropagator()
        carrier: dict[str, str] = {}

        # Inject
        propagator.inject(carrier, sample_run)

        # Extract
        result = propagator.extract(carrier)

        assert result is not None
        trace_id, span_id, sampled = result
        assert trace_id == sample_run.id.hex
        assert len(span_id) == 16
        assert sampled is True


# Fixtures
@pytest.fixture
def sample_run() -> AgentRun:
    """Create a sample run for testing."""
    return AgentRun(
        id=uuid4(),
        name="test_run",
        start_time=datetime.now(UTC),
    )
