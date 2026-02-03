"""
AWS X-Ray Trace Context propagation.

Implements AWS X-Ray trace header format for distributed tracing,
particularly for AWS Bedrock AgentCore integration.

Format: X-Amzn-Trace-Id: Root=1-{hex-epoch}-{24-hex};Parent={16-hex};Sampled=1

See:
- https://docs.aws.amazon.com/xray/latest/devguide/xray-concepts.html#xray-concepts-tracingheader
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html
"""

from __future__ import annotations

import re
import secrets
from typing import TYPE_CHECKING

from tracecraft.propagation.w3c import generate_span_id

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun


# AWS X-Ray header names
XRAY_HEADER = "X-Amzn-Trace-Id"
AGENTCORE_SESSION_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"

# X-Ray trace ID format
# Root format: 1-{8-char hex epoch}-{24-char hex random}
# Parent format: 16-char hex
XRAY_ROOT_PATTERN = re.compile(
    r"Root=1-([0-9a-f]{8})-([0-9a-f]{24})",
    re.IGNORECASE,
)
XRAY_PARENT_PATTERN = re.compile(
    r"Parent=([0-9a-f]{16})",
    re.IGNORECASE,
)
XRAY_SAMPLED_PATTERN = re.compile(
    r"Sampled=([01])",
    re.IGNORECASE,
)


def generate_xray_root(epoch_hex: str, random_hex: str) -> str:
    """
    Generate an X-Ray Root ID.

    Args:
        epoch_hex: 8-character hex of Unix epoch time.
        random_hex: 24-character hex random value.

    Returns:
        X-Ray Root ID in format: 1-{epoch}-{random}
    """
    return f"1-{epoch_hex}-{random_hex}"


def epoch_to_hex(timestamp: float) -> str:
    """
    Convert Unix timestamp to 8-character hex string.

    Args:
        timestamp: Unix timestamp (seconds since epoch).

    Returns:
        8-character hex string representing the epoch.
    """
    epoch_int = int(timestamp)
    return format(epoch_int, "08x")


def generate_random_hex(length: int = 24) -> str:
    """
    Generate a random hex string.

    Args:
        length: Length of hex string (default 24 for X-Ray).

    Returns:
        Random hex string of specified length.
    """
    return secrets.token_hex(length // 2)


class XRayTraceContextPropagator:
    """
    Propagator for AWS X-Ray Trace Context.

    Injects and extracts trace context from HTTP headers following
    the AWS X-Ray trace header format.

    The X-Ray trace header format:
        X-Amzn-Trace-Id: Root=1-{hex-epoch}-{24-hex};Parent={16-hex};Sampled={0|1}

    Example:
        X-Amzn-Trace-Id: Root=1-5759e988-bd862e3fe1be46a994272793;Parent=53995c3f42cd8ad8;Sampled=1

    Usage:
        ```python
        from tracecraft.propagation.xray import XRayTraceContextPropagator

        propagator = XRayTraceContextPropagator()

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

    def inject(
        self,
        carrier: dict[str, str],
        run: AgentRun,
        span_id: str | None = None,
        sampled: bool = True,
    ) -> None:
        """
        Inject X-Ray trace context into carrier (headers dict).

        Args:
            carrier: Dictionary to inject headers into.
            run: The AgentRun providing the trace context.
            span_id: Optional span ID (generated if not provided).
            sampled: Whether the trace is sampled.
        """
        # Generate Root ID from run
        # Use first 24 hex chars of run.id for random part
        epoch_hex = epoch_to_hex(run.start_time.timestamp())
        random_hex = run.id.hex[:24]
        root = generate_xray_root(epoch_hex, random_hex)

        # Generate or use provided span ID as Parent
        parent = span_id or generate_span_id()

        # Create X-Ray trace header
        sampled_str = "1" if sampled else "0"
        header_value = f"Root={root};Parent={parent};Sampled={sampled_str}"
        carrier[XRAY_HEADER] = header_value

        # Also inject session ID if available (for Bedrock AgentCore)
        if run.session_id:
            carrier[AGENTCORE_SESSION_HEADER] = run.session_id

    def extract(
        self,
        carrier: dict[str, str],
    ) -> tuple[str, str, bool, str | None] | None:
        """
        Extract X-Ray trace context from carrier (headers dict).

        Args:
            carrier: Dictionary containing headers.

        Returns:
            Tuple of (trace_id, span_id, sampled, session_id) if valid,
            None otherwise. trace_id is the full Root value.
        """
        # Find X-Ray trace header (case-insensitive)
        xray_header = None
        for key, value in carrier.items():
            if key.lower() == XRAY_HEADER.lower():
                xray_header = value
                break

        if not xray_header:
            return None

        # Parse Root
        root_match = XRAY_ROOT_PATTERN.search(xray_header)
        if not root_match:
            return None
        epoch_hex, random_hex = root_match.groups()
        trace_id = f"1-{epoch_hex.lower()}-{random_hex.lower()}"

        # Parse Parent
        parent_match = XRAY_PARENT_PATTERN.search(xray_header)
        if not parent_match:
            return None
        span_id = parent_match.group(1).lower()

        # Parse Sampled
        sampled = True  # Default to sampled
        sampled_match = XRAY_SAMPLED_PATTERN.search(xray_header)
        if sampled_match:
            sampled = sampled_match.group(1) == "1"

        # Extract session ID if present (for Bedrock AgentCore)
        session_id = None
        for key, value in carrier.items():
            if key.lower() == AGENTCORE_SESSION_HEADER.lower():
                session_id = value
                break

        return (trace_id, span_id, sampled, session_id)

    def to_w3c_format(self, xray_header: str) -> str | None:
        """
        Convert X-Ray header to W3C traceparent format.

        Args:
            xray_header: X-Ray trace header value.

        Returns:
            W3C traceparent header value, or None if invalid.
        """
        # Parse X-Ray header
        root_match = XRAY_ROOT_PATTERN.search(xray_header)
        parent_match = XRAY_PARENT_PATTERN.search(xray_header)
        sampled_match = XRAY_SAMPLED_PATTERN.search(xray_header)

        if not root_match or not parent_match:
            return None

        epoch_hex, random_hex = root_match.groups()
        span_id = parent_match.group(1)

        # Convert Root to W3C trace_id (32 hex chars)
        # Combine epoch and random parts
        # X-Ray: 1-{8hex}-{24hex} -> W3C: {8hex}{24hex} = 32hex
        trace_id = f"{epoch_hex}{random_hex}"

        # Determine sampled flag
        sampled = "01" if (not sampled_match or sampled_match.group(1) == "1") else "00"

        # W3C format: version-trace_id-span_id-flags
        return f"00-{trace_id.lower()}-{span_id.lower()}-{sampled}"

    def from_w3c_format(
        self,
        traceparent: str,
        epoch_time: float | None = None,
    ) -> str | None:
        """
        Convert W3C traceparent to X-Ray header format.

        Args:
            traceparent: W3C traceparent header value.
            epoch_time: Optional Unix timestamp for the epoch part.
                If not provided, uses first 8 chars of trace_id.

        Returns:
            X-Ray trace header value, or None if invalid.
        """
        from tracecraft.propagation.w3c import TRACEPARENT_PATTERN

        match = TRACEPARENT_PATTERN.match(traceparent)
        if not match:
            return None

        version, trace_id, span_id, flags = match.groups()

        # Only accept version 00
        if version != "00":
            return None

        # Convert trace_id to X-Ray Root
        # W3C: 32 hex chars -> X-Ray: 1-{8hex}-{24hex}
        if epoch_time is not None:
            epoch_hex = epoch_to_hex(epoch_time)
        else:
            # Use first 8 chars as epoch
            epoch_hex = trace_id[:8]

        random_hex = trace_id[8:32]
        root = f"1-{epoch_hex}-{random_hex}"

        # Convert flags to sampled
        try:
            flags_int = int(flags, 16)
            sampled = "1" if (flags_int & 0x01) else "0"
        except ValueError:
            sampled = "1"

        return f"Root={root};Parent={span_id};Sampled={sampled}"
