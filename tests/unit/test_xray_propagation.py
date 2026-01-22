"""
Tests for AWS X-Ray trace context propagation.

TDD approach: Tests for X-Ray header format inject/extract.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from agenttrace.core.models import AgentRun


class TestXRayTraceContextPropagator:
    """Tests for AWS X-Ray Trace Context propagation."""

    def test_inject_creates_xray_header(self, sample_run: AgentRun) -> None:
        """inject should create X-Amzn-Trace-Id header."""
        from agenttrace.propagation.xray import XRayTraceContextPropagator

        propagator = XRayTraceContextPropagator()
        carrier: dict[str, str] = {}

        propagator.inject(carrier, sample_run)

        assert "X-Amzn-Trace-Id" in carrier
        # Format: Root=1-{epoch}-{random};Parent={span};Sampled={0|1}
        header = carrier["X-Amzn-Trace-Id"]
        assert "Root=" in header
        assert "Parent=" in header
        assert "Sampled=" in header

    def test_inject_root_format(self, sample_run: AgentRun) -> None:
        """inject should create Root in format 1-{8hex}-{24hex}."""
        from agenttrace.propagation.xray import XRayTraceContextPropagator

        propagator = XRayTraceContextPropagator()
        carrier: dict[str, str] = {}

        propagator.inject(carrier, sample_run)

        header = carrier["X-Amzn-Trace-Id"]
        # Extract Root
        root_start = header.find("Root=") + 5
        root_end = header.find(";", root_start)
        root = header[root_start:root_end]

        # Root format: 1-{8hex}-{24hex}
        parts = root.split("-")
        assert len(parts) == 3
        assert parts[0] == "1"
        assert len(parts[1]) == 8  # epoch hex
        assert len(parts[2]) == 24  # random hex

    def test_inject_parent_format(self, sample_run: AgentRun) -> None:
        """inject should create Parent as 16-char hex."""
        from agenttrace.propagation.xray import XRayTraceContextPropagator

        propagator = XRayTraceContextPropagator()
        carrier: dict[str, str] = {}

        propagator.inject(carrier, sample_run)

        header = carrier["X-Amzn-Trace-Id"]
        # Extract Parent
        parent_start = header.find("Parent=") + 7
        parent_end = header.find(";", parent_start)
        if parent_end == -1:
            parent_end = len(header)
        parent = header[parent_start:parent_end]

        assert len(parent) == 16
        # Should be valid hex
        int(parent, 16)

    def test_inject_sampled_flag(self, sample_run: AgentRun) -> None:
        """inject should set Sampled flag."""
        from agenttrace.propagation.xray import XRayTraceContextPropagator

        propagator = XRayTraceContextPropagator()

        # Test sampled=True
        carrier: dict[str, str] = {}
        propagator.inject(carrier, sample_run, sampled=True)
        assert "Sampled=1" in carrier["X-Amzn-Trace-Id"]

        # Test sampled=False
        carrier = {}
        propagator.inject(carrier, sample_run, sampled=False)
        assert "Sampled=0" in carrier["X-Amzn-Trace-Id"]

    def test_inject_session_id_header(self, sample_run_with_session: AgentRun) -> None:
        """inject should add session ID header when available."""
        from agenttrace.propagation.xray import (
            AGENTCORE_SESSION_HEADER,
            XRayTraceContextPropagator,
        )

        propagator = XRayTraceContextPropagator()
        carrier: dict[str, str] = {}

        propagator.inject(carrier, sample_run_with_session)

        assert AGENTCORE_SESSION_HEADER in carrier
        assert carrier[AGENTCORE_SESSION_HEADER] == "session-12345"

    def test_inject_no_session_id_when_none(self, sample_run: AgentRun) -> None:
        """inject should not add session ID header when not set."""
        from agenttrace.propagation.xray import (
            AGENTCORE_SESSION_HEADER,
            XRayTraceContextPropagator,
        )

        propagator = XRayTraceContextPropagator()
        carrier: dict[str, str] = {}

        propagator.inject(carrier, sample_run)

        assert AGENTCORE_SESSION_HEADER not in carrier

    def test_extract_parses_xray_header(self) -> None:
        """extract should parse valid X-Ray headers."""
        from agenttrace.propagation.xray import XRayTraceContextPropagator

        propagator = XRayTraceContextPropagator()
        carrier = {
            "X-Amzn-Trace-Id": "Root=1-5759e988-bd862e3fe1be46a994272793;Parent=53995c3f42cd8ad8;Sampled=1"
        }

        result = propagator.extract(carrier)

        assert result is not None
        trace_id, span_id, sampled, session_id = result
        assert trace_id == "1-5759e988-bd862e3fe1be46a994272793"
        assert span_id == "53995c3f42cd8ad8"
        assert sampled is True
        assert session_id is None

    def test_extract_handles_unsampled(self) -> None:
        """extract should handle unsampled flag."""
        from agenttrace.propagation.xray import XRayTraceContextPropagator

        propagator = XRayTraceContextPropagator()
        carrier = {
            "X-Amzn-Trace-Id": "Root=1-5759e988-bd862e3fe1be46a994272793;Parent=53995c3f42cd8ad8;Sampled=0"
        }

        result = propagator.extract(carrier)

        assert result is not None
        _, _, sampled, _ = result
        assert sampled is False

    def test_extract_with_session_id(self) -> None:
        """extract should return session ID when present."""
        from agenttrace.propagation.xray import XRayTraceContextPropagator

        propagator = XRayTraceContextPropagator()
        carrier = {
            "X-Amzn-Trace-Id": "Root=1-5759e988-bd862e3fe1be46a994272793;Parent=53995c3f42cd8ad8;Sampled=1",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": "my-session-id",
        }

        result = propagator.extract(carrier)

        assert result is not None
        _, _, _, session_id = result
        assert session_id == "my-session-id"

    def test_extract_returns_none_for_missing_header(self) -> None:
        """extract should return None when X-Ray header missing."""
        from agenttrace.propagation.xray import XRayTraceContextPropagator

        propagator = XRayTraceContextPropagator()
        carrier: dict[str, str] = {}

        result = propagator.extract(carrier)

        assert result is None

    def test_extract_returns_none_for_invalid_format(self) -> None:
        """extract should return None for invalid X-Ray header."""
        from agenttrace.propagation.xray import XRayTraceContextPropagator

        propagator = XRayTraceContextPropagator()

        invalid_carriers = [
            {"X-Amzn-Trace-Id": "invalid"},
            {"X-Amzn-Trace-Id": "Root=invalid;Parent=abc;Sampled=1"},
            {"X-Amzn-Trace-Id": "Root=1-5759e988-bd862e3fe1be46a994272793"},  # Missing Parent
        ]

        for carrier in invalid_carriers:
            result = propagator.extract(carrier)
            assert result is None, f"Should reject: {carrier}"

    def test_extract_case_insensitive_header_names(self) -> None:
        """extract should handle case-insensitive header names."""
        from agenttrace.propagation.xray import XRayTraceContextPropagator

        propagator = XRayTraceContextPropagator()
        carrier = {
            "x-amzn-trace-id": "Root=1-5759e988-bd862e3fe1be46a994272793;Parent=53995c3f42cd8ad8;Sampled=1"
        }

        result = propagator.extract(carrier)

        assert result is not None


class TestXRayW3CConversion:
    """Tests for X-Ray to W3C format conversion."""

    def test_to_w3c_format(self) -> None:
        """to_w3c_format should convert X-Ray to traceparent."""
        from agenttrace.propagation.xray import XRayTraceContextPropagator

        propagator = XRayTraceContextPropagator()
        xray_header = "Root=1-5759e988-bd862e3fe1be46a994272793;Parent=53995c3f42cd8ad8;Sampled=1"

        result = propagator.to_w3c_format(xray_header)

        assert result is not None
        # W3C format: version-trace_id-span_id-flags
        parts = result.split("-")
        assert len(parts) == 4
        assert parts[0] == "00"  # version
        assert len(parts[1]) == 32  # trace_id
        assert parts[2] == "53995c3f42cd8ad8"  # span_id
        assert parts[3] == "01"  # sampled

    def test_to_w3c_format_unsampled(self) -> None:
        """to_w3c_format should handle unsampled traces."""
        from agenttrace.propagation.xray import XRayTraceContextPropagator

        propagator = XRayTraceContextPropagator()
        xray_header = "Root=1-5759e988-bd862e3fe1be46a994272793;Parent=53995c3f42cd8ad8;Sampled=0"

        result = propagator.to_w3c_format(xray_header)

        assert result is not None
        assert result.endswith("-00")

    def test_to_w3c_format_invalid_returns_none(self) -> None:
        """to_w3c_format should return None for invalid input."""
        from agenttrace.propagation.xray import XRayTraceContextPropagator

        propagator = XRayTraceContextPropagator()

        result = propagator.to_w3c_format("invalid")

        assert result is None

    def test_from_w3c_format(self) -> None:
        """from_w3c_format should convert traceparent to X-Ray."""
        from agenttrace.propagation.xray import XRayTraceContextPropagator

        propagator = XRayTraceContextPropagator()
        traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"

        result = propagator.from_w3c_format(traceparent)

        assert result is not None
        assert "Root=1-" in result
        assert "Parent=b7ad6b7169203331" in result
        assert "Sampled=1" in result

    def test_from_w3c_format_unsampled(self) -> None:
        """from_w3c_format should handle unsampled traces."""
        from agenttrace.propagation.xray import XRayTraceContextPropagator

        propagator = XRayTraceContextPropagator()
        traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-00"

        result = propagator.from_w3c_format(traceparent)

        assert result is not None
        assert "Sampled=0" in result

    def test_from_w3c_format_with_epoch(self) -> None:
        """from_w3c_format should use provided epoch time."""
        from agenttrace.propagation.xray import XRayTraceContextPropagator

        propagator = XRayTraceContextPropagator()
        traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
        epoch = 1609459200.0  # 2021-01-01 00:00:00 UTC

        result = propagator.from_w3c_format(traceparent, epoch_time=epoch)

        assert result is not None
        # Epoch 1609459200 in hex is 5fee6600
        assert "Root=1-5fee6600-" in result

    def test_from_w3c_format_invalid_returns_none(self) -> None:
        """from_w3c_format should return None for invalid input."""
        from agenttrace.propagation.xray import XRayTraceContextPropagator

        propagator = XRayTraceContextPropagator()

        result = propagator.from_w3c_format("invalid")

        assert result is None


class TestXRayHelpers:
    """Tests for X-Ray helper functions."""

    def test_generate_xray_root(self) -> None:
        """generate_xray_root should create valid Root format."""
        from agenttrace.propagation.xray import generate_xray_root

        root = generate_xray_root("5759e988", "bd862e3fe1be46a994272793")

        assert root == "1-5759e988-bd862e3fe1be46a994272793"

    def test_epoch_to_hex(self) -> None:
        """epoch_to_hex should convert timestamp to 8-char hex."""
        from agenttrace.propagation.xray import epoch_to_hex

        # Known epoch: 2021-01-01 00:00:00 UTC = 1609459200
        result = epoch_to_hex(1609459200.0)

        assert result == "5fee6600"
        assert len(result) == 8


class TestXRayContextIntegration:
    """Integration tests for X-Ray context propagation."""

    def test_inject_extract_roundtrip(self, sample_run: AgentRun) -> None:
        """inject and extract should round-trip correctly."""
        from agenttrace.propagation.xray import XRayTraceContextPropagator

        propagator = XRayTraceContextPropagator()
        carrier: dict[str, str] = {}

        # Inject
        propagator.inject(carrier, sample_run)

        # Extract
        result = propagator.extract(carrier)

        assert result is not None
        trace_id, span_id, sampled, _ = result
        # Trace ID should include epoch from run.start_time
        assert trace_id.startswith("1-")
        assert len(span_id) == 16
        assert sampled is True

    def test_inject_extract_with_session(self, sample_run_with_session: AgentRun) -> None:
        """inject and extract should preserve session ID."""
        from agenttrace.propagation.xray import XRayTraceContextPropagator

        propagator = XRayTraceContextPropagator()
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
