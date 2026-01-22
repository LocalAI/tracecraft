"""
W3C Trace Context propagation.

Implements the W3C Trace Context specification for distributed tracing.
See: https://www.w3.org/TR/trace-context/
"""

from __future__ import annotations

import re
import secrets
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from agenttrace.core.models import AgentRun

# W3C Trace Context header names
TRACEPARENT_HEADER = "traceparent"
TRACESTATE_HEADER = "tracestate"

# Version for traceparent
TRACE_VERSION = "00"

# Regex for validating traceparent format
# Format: version-trace_id-parent_id-flags
# Example: 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01
TRACEPARENT_PATTERN = re.compile(
    r"^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$",
    re.IGNORECASE,
)


def generate_span_id() -> str:
    """
    Generate a random span ID.

    Returns:
        A 16-character hex string (64 bits).
    """
    return secrets.token_hex(8)


def format_trace_id(uuid: UUID) -> str:
    """
    Format a UUID as a trace ID.

    Args:
        uuid: The UUID to format.

    Returns:
        A 32-character hex string (128 bits).
    """
    return uuid.hex


class W3CTraceContextPropagator:
    """
    Propagator for W3C Trace Context.

    Injects and extracts trace context from HTTP headers following
    the W3C Trace Context specification.

    Usage:
        ```python
        from agenttrace.propagation.w3c import W3CTraceContextPropagator

        propagator = W3CTraceContextPropagator()

        # Inject into outgoing request headers
        headers = {}
        propagator.inject(headers, run)
        requests.get(url, headers=headers)

        # Extract from incoming request headers
        result = propagator.extract(request.headers)
        if result:
            trace_id, span_id, sampled = result
            # Use trace context...
        ```
    """

    def __init__(self, vendor: str | None = None) -> None:
        """
        Initialize the propagator.

        Args:
            vendor: Optional vendor name for tracestate header.
        """
        self._vendor = vendor

    def inject(
        self,
        carrier: dict[str, str],
        run: AgentRun,
        span_id: str | None = None,
        sampled: bool = True,
    ) -> None:
        """
        Inject trace context into carrier (headers dict).

        Args:
            carrier: Dictionary to inject headers into.
            run: The AgentRun providing the trace ID.
            span_id: Optional span ID (generated if not provided).
            sampled: Whether the trace is sampled.
        """
        trace_id = format_trace_id(run.id)
        span = span_id or generate_span_id()
        flags = "01" if sampled else "00"

        # Create traceparent header
        traceparent = f"{TRACE_VERSION}-{trace_id}-{span}-{flags}"
        carrier[TRACEPARENT_HEADER] = traceparent

        # Optionally add tracestate
        if self._vendor:
            carrier[TRACESTATE_HEADER] = f"{self._vendor}={run.name}"

    def extract(
        self,
        carrier: dict[str, str],
    ) -> tuple[str, str, bool] | None:
        """
        Extract trace context from carrier (headers dict).

        Args:
            carrier: Dictionary containing headers.

        Returns:
            Tuple of (trace_id, span_id, sampled) if valid, None otherwise.
        """
        # Find traceparent header (case-insensitive)
        traceparent = None
        for key, value in carrier.items():
            if key.lower() == TRACEPARENT_HEADER:
                traceparent = value
                break

        if not traceparent:
            return None

        # Parse traceparent
        match = TRACEPARENT_PATTERN.match(traceparent)
        if not match:
            return None

        version, trace_id, span_id, flags = match.groups()

        # Only accept version 00
        if version != TRACE_VERSION:
            return None

        # Parse flags
        try:
            flags_int = int(flags, 16)
            sampled = bool(flags_int & 0x01)
        except ValueError:
            return None

        return (trace_id.lower(), span_id.lower(), sampled)

    def extract_tracestate(
        self,
        carrier: dict[str, str],
    ) -> dict[str, str]:
        """
        Extract tracestate from carrier.

        Args:
            carrier: Dictionary containing headers.

        Returns:
            Dictionary of vendor to value mappings.
        """
        tracestate = None
        for key, value in carrier.items():
            if key.lower() == TRACESTATE_HEADER:
                tracestate = value
                break

        if not tracestate:
            return {}

        # Parse tracestate (comma-separated key=value pairs)
        result: dict[str, str] = {}
        for pair in tracestate.split(","):
            pair = pair.strip()
            if "=" in pair:
                key, value = pair.split("=", 1)
                result[key.strip()] = value.strip()

        return result
