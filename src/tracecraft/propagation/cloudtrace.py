"""
GCP Cloud Trace Context propagation.

Implements both W3C Trace Context and legacy X-Cloud-Trace-Context header
format for GCP Cloud Trace integration.

The X-Cloud-Trace-Context header format:
    TRACE_ID/SPAN_ID;o=OPTIONS

Where:
- TRACE_ID: 32-character hex string
- SPAN_ID: decimal representation of the span ID
- OPTIONS: Trace options (1 = sampled, 0 = not sampled)

Example:
    X-Cloud-Trace-Context: 105445aa7843bc8bf206b12000100000/1;o=1

See:
- https://cloud.google.com/trace/docs/setup#force-trace
- https://cloud.google.com/trace/docs/trace-context
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from tracecraft.propagation.w3c import (
    W3CTraceContextPropagator,
    format_trace_id,
    generate_span_id,
)

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun


# GCP Cloud Trace header names
CLOUD_TRACE_HEADER = "X-Cloud-Trace-Context"
CLOUD_TRACE_SESSION_HEADER = "X-Cloud-Trace-Session-Id"  # Custom for agent sessions

# Cloud Trace header pattern
# Format: TRACE_ID/SPAN_ID;o=OPTIONS
CLOUD_TRACE_PATTERN = re.compile(
    r"^([0-9a-f]{32})/(\d+);o=([01])$",
    re.IGNORECASE,
)

# Alternative pattern without options
CLOUD_TRACE_PATTERN_NO_OPTIONS = re.compile(
    r"^([0-9a-f]{32})/(\d+)$",
    re.IGNORECASE,
)


def span_id_to_decimal(hex_span_id: str) -> str:
    """
    Convert a hex span ID to decimal for Cloud Trace.

    Args:
        hex_span_id: 16-character hex span ID.

    Returns:
        Decimal string representation.
    """
    return str(int(hex_span_id, 16))


def decimal_to_span_id(decimal_span_id: str) -> str:
    """
    Convert a decimal span ID to hex for W3C format.

    Args:
        decimal_span_id: Decimal string span ID.

    Returns:
        16-character hex span ID.
    """
    return format(int(decimal_span_id), "016x")


class CloudTraceContextPropagator:
    """
    Propagator for GCP Cloud Trace Context.

    Supports both W3C Trace Context (traceparent/tracestate) and legacy
    X-Cloud-Trace-Context header format. GCP Cloud Trace natively supports
    W3C format, but the legacy format is still used by some GCP services.

    The X-Cloud-Trace-Context header format:
        TRACE_ID/SPAN_ID;o=OPTIONS

    Example:
        X-Cloud-Trace-Context: 105445aa7843bc8bf206b12000100000/1;o=1

    Usage:
        ```python
        from tracecraft.propagation.cloudtrace import CloudTraceContextPropagator

        propagator = CloudTraceContextPropagator()

        # Inject into outgoing request headers
        headers = {}
        propagator.inject(headers, run)
        requests.post(url, headers=headers)

        # Extract from incoming request headers
        result = propagator.extract(request.headers)
        if result:
            trace_id, span_id, sampled, session_id = result
        ```
    """

    def __init__(self, use_legacy_format: bool = False) -> None:
        """
        Initialize the propagator.

        Args:
            use_legacy_format: If True, inject legacy X-Cloud-Trace-Context
                header instead of W3C traceparent. Default is False (W3C).
        """
        self._use_legacy_format = use_legacy_format
        self._w3c_propagator = W3CTraceContextPropagator(vendor="gcp")

    def inject(
        self,
        carrier: dict[str, str],
        run: AgentRun,
        span_id: str | None = None,
        sampled: bool = True,
    ) -> None:
        """
        Inject Cloud Trace context into carrier (headers dict).

        Args:
            carrier: Dictionary to inject headers into.
            run: The AgentRun providing the trace context.
            span_id: Optional span ID (generated if not provided).
            sampled: Whether the trace is sampled.
        """
        trace_id = format_trace_id(run.id)
        span = span_id or generate_span_id()

        if self._use_legacy_format:
            # Legacy X-Cloud-Trace-Context format
            decimal_span = span_id_to_decimal(span)
            options = "1" if sampled else "0"
            carrier[CLOUD_TRACE_HEADER] = f"{trace_id}/{decimal_span};o={options}"
        else:
            # W3C Trace Context format (preferred)
            self._w3c_propagator.inject(carrier, run, span_id=span, sampled=sampled)
            # Also add legacy header for compatibility
            decimal_span = span_id_to_decimal(span)
            options = "1" if sampled else "0"
            carrier[CLOUD_TRACE_HEADER] = f"{trace_id}/{decimal_span};o={options}"

        # Inject session ID if available (for Vertex AI Agent Builder)
        if run.session_id:
            carrier[CLOUD_TRACE_SESSION_HEADER] = run.session_id

    def extract(
        self,
        carrier: dict[str, str],
    ) -> tuple[str, str, bool, str | None] | None:
        """
        Extract Cloud Trace context from carrier (headers dict).

        Tries W3C format first, then falls back to legacy Cloud Trace format.

        Args:
            carrier: Dictionary containing headers.

        Returns:
            Tuple of (trace_id, span_id, sampled, session_id) if valid,
            None otherwise. trace_id and span_id are in hex format.
        """
        # Try W3C format first
        w3c_result = self._w3c_propagator.extract(carrier)
        if w3c_result:
            trace_id, span_id, sampled = w3c_result
            session_id = self._extract_session_id(carrier)
            return (trace_id, span_id, sampled, session_id)

        # Fall back to legacy Cloud Trace format
        cloud_trace_header = None
        for key, value in carrier.items():
            if key.lower() == CLOUD_TRACE_HEADER.lower():
                cloud_trace_header = value
                break

        if not cloud_trace_header:
            return None

        # Try pattern with options
        match = CLOUD_TRACE_PATTERN.match(cloud_trace_header)
        if match:
            trace_id, decimal_span, options = match.groups()
            span_id = decimal_to_span_id(decimal_span)
            sampled = options == "1"
            session_id = self._extract_session_id(carrier)
            return (trace_id.lower(), span_id, sampled, session_id)

        # Try pattern without options
        match = CLOUD_TRACE_PATTERN_NO_OPTIONS.match(cloud_trace_header)
        if match:
            trace_id, decimal_span = match.groups()
            span_id = decimal_to_span_id(decimal_span)
            session_id = self._extract_session_id(carrier)
            return (trace_id.lower(), span_id, True, session_id)  # Default sampled

        return None

    def _extract_session_id(self, carrier: dict[str, str]) -> str | None:
        """Extract session ID from carrier if present."""
        for key, value in carrier.items():
            if key.lower() == CLOUD_TRACE_SESSION_HEADER.lower():
                return value
        return None

    def to_w3c_format(self, cloud_trace_header: str) -> str | None:
        """
        Convert legacy Cloud Trace header to W3C traceparent format.

        Args:
            cloud_trace_header: X-Cloud-Trace-Context header value.

        Returns:
            W3C traceparent header value, or None if invalid.
        """
        # Try pattern with options
        match = CLOUD_TRACE_PATTERN.match(cloud_trace_header)
        if match:
            trace_id, decimal_span, options = match.groups()
            span_id = decimal_to_span_id(decimal_span)
            flags = "01" if options == "1" else "00"
            return f"00-{trace_id.lower()}-{span_id}-{flags}"

        # Try pattern without options
        match = CLOUD_TRACE_PATTERN_NO_OPTIONS.match(cloud_trace_header)
        if match:
            trace_id, decimal_span = match.groups()
            span_id = decimal_to_span_id(decimal_span)
            return f"00-{trace_id.lower()}-{span_id}-01"

        return None

    def from_w3c_format(self, traceparent: str) -> str | None:
        """
        Convert W3C traceparent to legacy Cloud Trace header format.

        Args:
            traceparent: W3C traceparent header value.

        Returns:
            X-Cloud-Trace-Context header value, or None if invalid.
        """
        from tracecraft.propagation.w3c import TRACEPARENT_PATTERN

        match = TRACEPARENT_PATTERN.match(traceparent)
        if not match:
            return None

        version, trace_id, span_id, flags = match.groups()

        # Only accept version 00
        if version != "00":
            return None

        # Convert span_id to decimal
        decimal_span = span_id_to_decimal(span_id)

        # Parse flags
        try:
            flags_int = int(flags, 16)
            options = "1" if (flags_int & 0x01) else "0"
        except ValueError:
            options = "1"

        return f"{trace_id}/{decimal_span};o={options}"
