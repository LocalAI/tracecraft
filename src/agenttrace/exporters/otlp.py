"""
OTLP exporter for OpenTelemetry backends.

Exports AgentTrace runs to any OTLP-compatible backend (Jaeger, Grafana Tempo,
Datadog, Honeycomb, etc.) using OpenTelemetry Protocol.
"""

from __future__ import annotations

import logging
from datetime import UTC
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from agenttrace.exporters.base import BaseExporter
from agenttrace.schema.openinference import OpenInferenceMapper
from agenttrace.schema.otel_genai import OTelGenAIMapper

if TYPE_CHECKING:
    from agenttrace.core.models import AgentRun, Step

logger = logging.getLogger(__name__)


# Type alias for schema dialect
SchemaDialect = Literal["otel_genai", "openinference", "both"]


class OTLPExporter(BaseExporter):
    """
    OTLP exporter for sending traces to OpenTelemetry-compatible backends.

    Converts AgentTrace runs and steps to OpenTelemetry spans and exports
    them using the OTLP protocol (gRPC or HTTP).

    Example:
        >>> exporter = OTLPExporter(
        ...     endpoint="http://localhost:4317",
        ...     service_name="my-agent",
        ... )
        >>> exporter.export(run)
    """

    def __init__(
        self,
        endpoint: str,
        headers: dict[str, str] | None = None,
        protocol: Literal["grpc", "http"] = "grpc",
        timeout_ms: int = 10000,
        service_name: str = "agenttrace",
        schema_dialect: SchemaDialect = "both",
    ) -> None:
        """
        Initialize the OTLP exporter.

        Args:
            endpoint: OTLP collector endpoint (e.g., "http://localhost:4317").
            headers: Optional headers for authentication.
            protocol: Transport protocol ("grpc" or "http").
            timeout_ms: Export timeout in milliseconds.
            service_name: Service name for traces.
            schema_dialect: Schema convention to use ("otel_genai", "openinference", or "both").
        """
        self.endpoint = endpoint
        self.headers = headers or {}
        self.protocol = protocol
        self.timeout_ms = timeout_ms
        self.service_name = service_name
        self.schema_dialect = schema_dialect

        # Initialize schema mappers
        self._otel_mapper = OTelGenAIMapper()
        self._oi_mapper = OpenInferenceMapper()

        # Initialize the OTLP span exporter
        self._span_exporter = self._create_span_exporter()

    def _create_span_exporter(self) -> Any:
        """Create the appropriate OTLP span exporter based on protocol."""
        try:
            if self.protocol == "grpc":
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter,
                )

                return OTLPSpanExporter(
                    endpoint=self.endpoint,
                    headers=tuple(self.headers.items()) if self.headers else None,
                    timeout=self.timeout_ms // 1000,
                )
            else:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )

                return OTLPSpanExporter(
                    endpoint=self.endpoint,
                    headers=self.headers,
                    timeout=self.timeout_ms // 1000,
                )
        except ImportError:
            logger.warning(
                "OTLP exporter dependencies not installed. "
                "Install with: pip install agenttrace[otlp]"
            )
            return None

    def export(self, run: AgentRun) -> None:
        """
        Export an agent run as OpenTelemetry spans.

        Converts the run and all its steps to OTel spans, maintaining
        the parent-child hierarchy, and exports them to the configured
        OTLP endpoint.

        Args:
            run: The AgentRun to export.
        """
        if not run.steps:
            logger.debug("Skipping export for run with no steps: %s", run.name)
            return

        # Collect all spans from the run
        spans = self._collect_spans(run)

        if not spans:
            return

        # Send the spans
        try:
            self._send_spans(spans)
        except Exception as e:
            logger.exception("Failed to export spans to OTLP endpoint: %s", e)

    def _collect_spans(self, run: AgentRun) -> list[dict[str, Any]]:
        """
        Collect all spans from a run, flattening the hierarchy.

        Args:
            run: The AgentRun to collect spans from.

        Returns:
            List of span data dictionaries.
        """
        spans: list[dict[str, Any]] = []

        def collect_step(step: Step) -> None:
            span_data = self._step_to_span_data(step, run.id)
            spans.append(span_data)

            # Recursively collect children
            for child in step.children:
                collect_step(child)

        for step in run.steps:
            collect_step(step)

        return spans

    def _step_to_span_data(self, step: Step, trace_id: UUID) -> dict[str, Any]:
        """
        Convert a Step to span data dictionary.

        Args:
            step: The Step to convert.
            trace_id: The trace ID for this span.

        Returns:
            Dictionary containing span data.
        """
        # Build attributes based on schema dialect
        attributes = self._build_attributes(step)

        # Add common attributes
        attributes["agenttrace.step.type"] = step.type.value
        if step.error:
            attributes["error"] = True
            attributes["error.message"] = step.error
            if step.error_type:
                attributes["error.type"] = step.error_type

        # Calculate timestamps
        start_time_ns = self._datetime_to_ns(step.start_time)
        end_time_ns = self._datetime_to_ns(step.end_time) if step.end_time else start_time_ns

        span_data: dict[str, Any] = {
            "name": step.name,
            "trace_id": self._uuid_to_hex(trace_id),
            "span_id": self._uuid_to_hex(step.id)[:16],  # OTel span IDs are 8 bytes
            "start_time_ns": start_time_ns,
            "end_time_ns": end_time_ns,
            "attributes": attributes,
        }

        # Add parent span ID if this step has a parent
        if step.parent_id:
            span_data["parent_span_id"] = self._uuid_to_hex(step.parent_id)[:16]

        return span_data

    def _build_attributes(self, step: Step) -> dict[str, Any]:
        """
        Build span attributes based on the configured schema dialect.

        Args:
            step: The Step to build attributes for.

        Returns:
            Dictionary of span attributes.
        """
        attributes: dict[str, Any] = {}

        if self.schema_dialect in ("otel_genai", "both"):
            otel_attrs = self._otel_mapper.map_step(step)
            attributes.update(otel_attrs)

        if self.schema_dialect in ("openinference", "both"):
            oi_attrs = self._oi_mapper.map_step(step)
            attributes.update(oi_attrs)

        return attributes

    def _send_spans(self, spans: list[dict[str, Any]]) -> None:
        """
        Send spans to the OTLP endpoint.

        Args:
            spans: List of span data dictionaries to send.
        """
        if self._span_exporter is None:
            logger.warning("OTLP exporter not available - spans will not be exported")
            return

        # Convert span data to OTel ReadableSpans and export
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import ReadableSpan
        from opentelemetry.sdk.trace.export import SpanExportResult

        resource = Resource.create({"service.name": self.service_name})

        readable_spans: list[ReadableSpan] = []
        for span_data in spans:
            readable_span = self._create_readable_span(span_data, resource)
            if readable_span:
                readable_spans.append(readable_span)

        if readable_spans:
            result = self._span_exporter.export(readable_spans)
            if result != SpanExportResult.SUCCESS:
                logger.warning("Failed to export some spans: %s", result)

    def _create_readable_span(self, span_data: dict[str, Any], resource: Any) -> Any | None:
        """
        Create an OpenTelemetry ReadableSpan from span data.

        Args:
            span_data: The span data dictionary.
            resource: The OTel Resource to attach.

        Returns:
            A ReadableSpan or None if creation failed.
        """
        try:
            from opentelemetry.trace import SpanContext, SpanKind, TraceFlags
            from opentelemetry.trace.status import Status, StatusCode

            # Parse trace and span IDs
            trace_id = int(span_data["trace_id"], 16)
            span_id = int(span_data["span_id"], 16)

            parent_span_id = None
            if span_data.get("parent_span_id"):
                parent_span_id = int(span_data["parent_span_id"], 16)

            # Create span context
            span_context = SpanContext(
                trace_id=trace_id,
                span_id=span_id,
                is_remote=False,
                trace_flags=TraceFlags.SAMPLED,
            )

            # Determine status
            status = Status(StatusCode.OK)
            if span_data["attributes"].get("error"):
                status = Status(StatusCode.ERROR, span_data["attributes"].get("error.message", ""))

            # Convert attributes to OTel format
            attributes = {
                k: v
                for k, v in span_data["attributes"].items()
                if v is not None and not isinstance(v, (dict, list))
            }

            # Create a minimal ReadableSpan-like object
            # Note: We're using the internal _Span class for creation
            from opentelemetry.sdk.trace import _Span

            span = _Span(
                name=span_data["name"],
                context=span_context,
                parent=SpanContext(
                    trace_id=trace_id,
                    span_id=parent_span_id or 0,
                    is_remote=False,
                    trace_flags=TraceFlags.SAMPLED,
                )
                if parent_span_id
                else None,
                resource=resource,
                attributes=attributes,
                kind=SpanKind.INTERNAL,
            )

            # Set timing
            span._start_time = span_data["start_time_ns"]
            span._end_time = span_data["end_time_ns"]
            span._status = status

            return span

        except Exception as e:
            logger.warning("Failed to create ReadableSpan: %s", e)
            return None

    def _uuid_to_hex(self, uuid_val: UUID) -> str:
        """Convert a UUID to a hex string without dashes."""
        return uuid_val.hex

    def _datetime_to_ns(self, dt: Any) -> int:
        """Convert a datetime to nanoseconds since epoch."""
        if dt is None:
            return 0

        # Ensure timezone awareness
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)

        # Convert to nanoseconds
        return int(dt.timestamp() * 1_000_000_000)

    def close(self) -> None:
        """
        Close the exporter and release resources.

        Flushes any pending spans and shuts down the underlying exporter.
        """
        if self._span_exporter is not None:
            try:
                self._span_exporter.shutdown()
            except Exception as e:
                logger.warning("Error shutting down OTLP exporter: %s", e)
