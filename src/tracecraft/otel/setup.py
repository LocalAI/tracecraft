"""Simple OpenTelemetry setup for TraceCraft.

This module provides a streamlined way to configure OpenTelemetry
for exporting traces to TraceCraft and other OTLP-compatible backends.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

from .backends import get_service_name, parse_endpoint
from .instrumentors import instrument_sdks

if TYPE_CHECKING:
    from opentelemetry.trace import Tracer


def setup_exporter(
    endpoint: str | None = None,
    service_name: str | None = None,
    service_version: str = "1.0.0",
    instrument: list[str] | None = None,
    batch_export: bool = True,
    resource_attributes: dict[str, str] | None = None,
    tracer_name: str = "tracecraft",
) -> Tracer:
    """Configure OpenTelemetry to export traces to TraceCraft and other backends.

    This function replaces 20+ lines of OpenTelemetry boilerplate with a single call.
    It sets up a TracerProvider, configures OTLP export, and optionally instruments
    popular LLM SDKs for automatic tracing.

    Args:
        endpoint: OTLP HTTP endpoint URL. Defaults to http://localhost:4318.
            Supports custom schemes for backend hints:
            - tracecraft://host:port - TraceCraft receiver (alias for http://)
            - datadog://intake.datadoghq.com - DataDog OTLP intake
            - azure://appinsights.azure.com - Azure Application Insights
            - http(s)://host:port - Generic OTLP endpoint

            Falls back to environment variables:
            - TRACECRAFT_ENDPOINT
            - OTEL_EXPORTER_OTLP_ENDPOINT

        service_name: Name to identify this service in traces.
            Falls back to TRACECRAFT_SERVICE_NAME or OTEL_SERVICE_NAME env vars.
            Defaults to "tracecraft-agent".

        service_version: Version string for the service.

        instrument: List of SDK names to auto-instrument. Options:
            - "openai" - OpenAI SDK
            - "anthropic" - Anthropic SDK
            - "langchain" - LangChain
            - "llamaindex" - LlamaIndex
            - "cohere" - Cohere SDK
            - "bedrock" - AWS Bedrock
            - "vertexai" - Google Vertex AI
            - "mistral" - Mistral AI
            - "groq" - Groq

        batch_export: Use BatchSpanProcessor (True, default) or SimpleSpanProcessor
            (False). Batch export is more efficient for production use.

        resource_attributes: Additional OpenTelemetry resource attributes to include.
            Common attributes: "deployment.environment", "service.instance.id"

        tracer_name: Name for the returned tracer. Default: "tracecraft"

    Returns:
        Configured OpenTelemetry Tracer instance ready for creating spans.

    Example:
        Basic setup with OpenAI instrumentation:

        >>> from tracecraft.otel import setup_exporter
        >>> tracer = setup_exporter(
        ...     endpoint="http://localhost:4318",
        ...     service_name="my-agent",
        ...     instrument=["openai"],
        ... )
        >>> with tracer.start_as_current_span("my-task") as span:
        ...     span.set_attribute("tracecraft.step.type", "AGENT")
        ...     # OpenAI calls are automatically traced
        ...     pass

        Using environment variables:

        >>> # Set TRACECRAFT_ENDPOINT=http://localhost:4318
        >>> # Set TRACECRAFT_SERVICE_NAME=my-service
        >>> tracer = setup_exporter(instrument=["openai", "anthropic"])

        With custom resource attributes:

        >>> tracer = setup_exporter(
        ...     service_name="prod-agent",
        ...     resource_attributes={
        ...         "deployment.environment": "production",
        ...         "service.instance.id": "agent-1",
        ...     },
        ... )

    Note:
        This function sets the global TracerProvider. Calling it multiple times
        will overwrite the previous configuration. For multi-backend scenarios,
        configure additional exporters manually or use the underlying OTel APIs.
    """
    # Parse endpoint configuration
    backend_config = parse_endpoint(endpoint)

    # Resolve service name
    resolved_service_name = get_service_name(service_name)

    # Build resource attributes
    attrs: dict[str, str] = {
        "service.name": resolved_service_name,
        "service.version": service_version,
    }
    if resource_attributes:
        attrs.update(resource_attributes)

    # Add backend-specific attributes
    if backend_config.backend_type != "generic":
        attrs["tracecraft.backend"] = backend_config.backend_type

    # Create resource
    resource = Resource.create(attrs)

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Configure OTLP exporter
    exporter = OTLPSpanExporter(endpoint=backend_config.endpoint_url)

    # Add span processor
    processor: BatchSpanProcessor | SimpleSpanProcessor
    if batch_export:
        processor = BatchSpanProcessor(exporter)
    else:
        processor = SimpleSpanProcessor(exporter)

    provider.add_span_processor(processor)

    # Set as global tracer provider
    trace.set_tracer_provider(provider)

    # Auto-instrument requested SDKs
    if instrument:
        instrument_sdks(instrument)

    # Return a tracer
    return trace.get_tracer(tracer_name)


def get_tracer(name: str = "tracecraft") -> Tracer:
    """Get a tracer from the current global TracerProvider.

    This is a convenience function for getting a tracer after setup_exporter()
    has been called.

    Args:
        name: Name for the tracer. Default: "tracecraft"

    Returns:
        OpenTelemetry Tracer instance.

    Example:
        >>> setup_exporter(service_name="my-agent")
        >>> tracer = get_tracer("my-module")
        >>> with tracer.start_as_current_span("operation"):
        ...     pass
    """
    return trace.get_tracer(name)


def flush_traces(timeout_millis: int = 30000) -> bool:
    """Force flush all pending traces.

    Useful before application shutdown to ensure all traces are exported.

    Args:
        timeout_millis: Maximum time to wait for flush in milliseconds.

    Returns:
        True if flush succeeded, False if it timed out.
    """
    provider = trace.get_tracer_provider()
    if hasattr(provider, "force_flush"):
        return provider.force_flush(timeout_millis)  # type: ignore[no-any-return]
    return True


def shutdown() -> None:
    """Shutdown the TracerProvider and release resources.

    Call this when your application is shutting down to ensure
    all traces are flushed and resources are cleaned up.
    """
    provider = trace.get_tracer_provider()
    if hasattr(provider, "shutdown"):
        provider.shutdown()
