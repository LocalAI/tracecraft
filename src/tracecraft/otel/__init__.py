"""Simple OpenTelemetry setup for TraceCraft.

This module provides a streamlined API for configuring OpenTelemetry
to export traces to TraceCraft and other OTLP-compatible backends.

Example:
    Basic usage with auto-instrumentation:

    >>> from tracecraft.otel import setup_exporter
    >>> tracer = setup_exporter(
    ...     endpoint="http://localhost:4318",
    ...     service_name="my-agent",
    ...     instrument=["openai"],
    ... )
    >>> with tracer.start_as_current_span("my-task") as span:
    ...     span.set_attribute("tracecraft.step.type", "AGENT")
    ...     # Your code here - OpenAI calls are automatically traced

    Using environment variables:

    >>> # Set TRACECRAFT_ENDPOINT=http://localhost:4318
    >>> # Set TRACECRAFT_SERVICE_NAME=my-service
    >>> tracer = setup_exporter(instrument=["openai", "anthropic"])
"""

from __future__ import annotations

from .backends import BackendConfig, get_service_name, parse_endpoint
from .instrumentors import (
    get_available_instrumentors,
    instrument_sdk,
    instrument_sdks,
    uninstrument_sdk,
)
from .setup import flush_traces, get_tracer, setup_exporter, shutdown

__all__ = [
    # Main setup function
    "setup_exporter",
    # Tracer utilities
    "get_tracer",
    "flush_traces",
    "shutdown",
    # Backend configuration
    "parse_endpoint",
    "get_service_name",
    "BackendConfig",
    # Instrumentation utilities
    "instrument_sdk",
    "instrument_sdks",
    "uninstrument_sdk",
    "get_available_instrumentors",
]
