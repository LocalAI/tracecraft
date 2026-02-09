"""
OTLP to TraceCraft importer.

Converts OpenTelemetry spans to TraceCraft AgentRun objects.
Supports both OTel GenAI and OpenInference semantic conventions.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from tracecraft.core.models import AgentRun, Step, StepType

if TYPE_CHECKING:
    from opentelemetry.proto.trace.v1.trace_pb2 import (
        ResourceSpans,
        ScopeSpans,
        Span,
    )

logger = logging.getLogger(__name__)


def _ns_to_datetime(ns: int) -> datetime:
    """Convert nanoseconds since epoch to datetime."""
    return datetime.fromtimestamp(ns / 1_000_000_000, tz=UTC)


def _hex_to_uuid(hex_str: str) -> UUID:
    """Convert hex string to UUID, padding if needed."""
    # Handle empty or None values
    if not hex_str:
        # Generate a deterministic UUID for empty/missing IDs
        hex_str = "0" * 32

    # OTel trace IDs are 32 hex chars (16 bytes), span IDs are 16 hex chars (8 bytes)
    # We need to pad span IDs to make valid UUIDs
    if len(hex_str) == 16:
        # Span ID: pad to 32 chars
        hex_str = hex_str + "0" * 16
    elif len(hex_str) < 32:
        hex_str = hex_str.ljust(32, "0")

    try:
        return UUID(hex_str[:32])
    except ValueError:
        # Invalid hex characters - hash the string to get a valid UUID
        import hashlib

        hash_hex = hashlib.md5(hex_str.encode(), usedforsecurity=False).hexdigest()  # nosec B324
        return UUID(hash_hex)


def _bytes_to_hex(b: bytes) -> str:
    """Convert bytes to hex string."""
    return b.hex()


class OTelImporter:
    """
    Imports OTLP spans and converts them to TraceCraft AgentRun objects.

    Supports auto-detection of schema dialect (OTel GenAI vs OpenInference)
    based on span attributes.

    Example:
        ```python
        importer = OTelImporter()

        # From OTLP protobuf
        agent_runs = importer.import_resource_spans(resource_spans_list)

        # From JSON dict (OTLP JSON format)
        agent_runs = importer.import_from_json(otlp_json)
        ```
    """

    # OTel GenAI attribute mappings
    OTEL_GENAI_MAPPINGS: dict[str, str] = {
        "gen_ai.request.model": "model_name",
        "gen_ai.system": "model_provider",
        "gen_ai.usage.input_tokens": "input_tokens",
        "gen_ai.usage.output_tokens": "output_tokens",
        "gen_ai.usage.cost": "cost_usd",
    }

    # OpenInference attribute mappings
    OPENINFERENCE_MAPPINGS: dict[str, str] = {
        "llm.model_name": "model_name",
        "llm.provider": "model_provider",
        "llm.token_count.prompt": "input_tokens",
        "llm.token_count.completion": "output_tokens",
    }

    # Attributes that indicate step type
    TYPE_INDICATORS: dict[str, StepType] = {
        "gen_ai.agent.name": StepType.AGENT,
        "gen_ai.agent.id": StepType.AGENT,
        "tool.name": StepType.TOOL,
        "tool.parameters": StepType.TOOL,
        "retrieval.query": StepType.RETRIEVAL,
        "retrieval.documents": StepType.RETRIEVAL,
    }

    def import_resource_spans(self, resource_spans_list: list[ResourceSpans]) -> list[AgentRun]:
        """
        Import OTLP ResourceSpans and convert to AgentRun objects.

        Args:
            resource_spans_list: List of OTLP ResourceSpans from ExportTraceServiceRequest.

        Returns:
            List of AgentRun objects, one per unique trace_id.
        """
        # Collect all spans grouped by trace_id
        spans_by_trace: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for resource_spans in resource_spans_list:
            resource_attrs = self._extract_resource_attributes(resource_spans)

            for scope_spans in resource_spans.scope_spans:
                for span in scope_spans.spans:
                    span_data = self._span_to_dict(span, resource_attrs)
                    trace_id = span_data["trace_id"]
                    spans_by_trace[trace_id].append(span_data)

        # Convert each trace's spans to an AgentRun
        return [
            self._spans_to_agent_run(trace_id, spans) for trace_id, spans in spans_by_trace.items()
        ]

    def import_from_json(self, otlp_json: dict[str, Any]) -> list[AgentRun]:
        """
        Import OTLP traces from JSON format.

        Args:
            otlp_json: OTLP ExportTraceServiceRequest in JSON format.

        Returns:
            List of AgentRun objects.
        """
        spans_by_trace: dict[str, list[dict[str, Any]]] = defaultdict(list)

        resource_spans_list = otlp_json.get("resourceSpans", [])
        for resource_spans in resource_spans_list:
            resource_attrs = self._extract_resource_attributes_json(resource_spans)

            scope_spans_list = resource_spans.get("scopeSpans", [])
            for scope_spans in scope_spans_list:
                spans = scope_spans.get("spans", [])
                for span in spans:
                    span_data = self._json_span_to_dict(span, resource_attrs)
                    trace_id = span_data["trace_id"]
                    spans_by_trace[trace_id].append(span_data)

        return [
            self._spans_to_agent_run(trace_id, spans) for trace_id, spans in spans_by_trace.items()
        ]

    def _extract_resource_attributes(self, resource_spans: ResourceSpans) -> dict[str, Any]:
        """Extract attributes from resource."""
        attrs: dict[str, Any] = {}
        if resource_spans.resource:
            for attr in resource_spans.resource.attributes:
                attrs[attr.key] = self._get_attr_value(attr.value)
        return attrs

    def _extract_resource_attributes_json(self, resource_spans: dict[str, Any]) -> dict[str, Any]:
        """Extract attributes from resource (JSON format)."""
        attrs: dict[str, Any] = {}
        resource = resource_spans.get("resource", {})
        for attr in resource.get("attributes", []):
            key = attr.get("key", "")
            value = attr.get("value", {})
            attrs[key] = self._get_json_attr_value(value)
        return attrs

    def _get_attr_value(self, value: Any) -> Any:
        """Extract value from OTLP AnyValue protobuf."""
        # Use WhichOneof to determine which value field is set
        # This is the correct way to check protobuf oneof fields
        if hasattr(value, "WhichOneof"):
            field = value.WhichOneof("value")
            if field == "string_value":
                return value.string_value
            if field == "int_value":
                return value.int_value
            if field == "double_value":
                return value.double_value
            if field == "bool_value":
                return value.bool_value
            if field == "array_value":
                return [self._get_attr_value(v) for v in value.array_value.values]
            if field == "kvlist_value":
                return {kv.key: self._get_attr_value(kv.value) for kv in value.kvlist_value.values}
            if field == "bytes_value":
                return value.bytes_value.hex()
        # Fallback for non-protobuf or older versions
        elif hasattr(value, "string_value") and value.string_value:
            return value.string_value
        elif hasattr(value, "int_value") and value.int_value != 0:
            return value.int_value
        elif hasattr(value, "double_value") and value.double_value != 0.0:
            return value.double_value
        elif hasattr(value, "bool_value"):
            return value.bool_value
        elif hasattr(value, "array_value") and value.array_value.values:
            return [self._get_attr_value(v) for v in value.array_value.values]
        return None

    def _get_json_attr_value(self, value: dict[str, Any]) -> Any:
        """Extract value from OTLP AnyValue JSON format."""
        if "stringValue" in value:
            return value["stringValue"]
        if "intValue" in value:
            return int(value["intValue"])
        if "doubleValue" in value:
            return float(value["doubleValue"])
        if "boolValue" in value:
            return value["boolValue"]
        if "arrayValue" in value:
            return [self._get_json_attr_value(v) for v in value["arrayValue"].get("values", [])]
        return None

    def _span_to_dict(self, span: Span, resource_attrs: dict[str, Any]) -> dict[str, Any]:
        """Convert OTLP Span protobuf to dict."""
        attrs: dict[str, Any] = {}
        for attr in span.attributes:
            attrs[attr.key] = self._get_attr_value(attr.value)

        return {
            "trace_id": _bytes_to_hex(span.trace_id),
            "span_id": _bytes_to_hex(span.span_id),
            "parent_span_id": _bytes_to_hex(span.parent_span_id) if span.parent_span_id else None,
            "name": span.name,
            "start_time_ns": span.start_time_unix_nano,
            "end_time_ns": span.end_time_unix_nano,
            "attributes": attrs,
            "resource_attrs": resource_attrs,
            "status_code": span.status.code if span.status else 0,
            "status_message": span.status.message if span.status else None,
        }

    def _json_span_to_dict(
        self, span: dict[str, Any], resource_attrs: dict[str, Any]
    ) -> dict[str, Any]:
        """Convert OTLP Span JSON to dict."""
        attrs: dict[str, Any] = {}
        for attr in span.get("attributes", []):
            key = attr.get("key", "")
            value = attr.get("value", {})
            attrs[key] = self._get_json_attr_value(value)

        status = span.get("status", {})

        return {
            "trace_id": span.get("traceId", ""),
            "span_id": span.get("spanId", ""),
            "parent_span_id": span.get("parentSpanId") or None,
            "name": span.get("name", ""),
            "start_time_ns": int(span.get("startTimeUnixNano", 0)),
            "end_time_ns": int(span.get("endTimeUnixNano", 0)),
            "attributes": attrs,
            "resource_attrs": resource_attrs,
            "status_code": status.get("code", 0),
            "status_message": status.get("message"),
        }

    def _spans_to_agent_run(self, trace_id: str, spans: list[dict[str, Any]]) -> AgentRun:
        """
        Convert a list of spans (same trace_id) to an AgentRun.

        Builds the step hierarchy from parent_span_id relationships.
        """
        if not spans:
            raise ValueError("No spans provided")

        # Build span lookup and find roots
        span_lookup: dict[str, dict[str, Any]] = {s["span_id"]: s for s in spans}
        root_spans: list[dict[str, Any]] = []
        child_map: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for span in spans:
            parent_id = span["parent_span_id"]
            if parent_id is None or parent_id not in span_lookup:
                root_spans.append(span)
            else:
                child_map[parent_id].append(span)

        # Sort root spans by start time
        root_spans.sort(key=lambda s: s["start_time_ns"])

        # Build step tree recursively
        def build_step(span_data: dict[str, Any]) -> Step:
            span_id = span_data["span_id"]
            children_data = child_map.get(span_id, [])
            children_data.sort(key=lambda s: s["start_time_ns"])

            step = self._span_to_step(span_data, trace_id)
            step.children = [build_step(c) for c in children_data]
            return step

        steps = [build_step(s) for s in root_spans]

        # Calculate aggregates
        total_tokens = 0
        total_cost = 0.0
        error_count = 0

        def aggregate_step(step: Step) -> None:
            nonlocal total_tokens, total_cost, error_count
            if step.input_tokens:
                total_tokens += step.input_tokens
            if step.output_tokens:
                total_tokens += step.output_tokens
            if step.cost_usd:
                total_cost += step.cost_usd
            if step.error:
                error_count += 1
            for child in step.children:
                aggregate_step(child)

        for step in steps:
            aggregate_step(step)

        # Determine run-level metadata from first/last spans
        first_span = min(spans, key=lambda s: s["start_time_ns"])
        last_span = max(spans, key=lambda s: s["end_time_ns"])

        start_time = _ns_to_datetime(first_span["start_time_ns"])
        end_time = _ns_to_datetime(last_span["end_time_ns"])
        # Ensure non-negative duration (handle malformed data)
        duration_ns = max(0, last_span["end_time_ns"] - first_span["start_time_ns"])
        duration_ms = duration_ns / 1_000_000

        # Extract run name from first root span or resource
        run_name = first_span.get("name", "imported_trace")
        resource_attrs = first_span.get("resource_attrs", {})

        # Extract agent identity from attributes
        agent_name = None
        agent_id = None
        for span in spans:
            attrs = span.get("attributes", {})
            if "gen_ai.agent.name" in attrs:
                agent_name = attrs["gen_ai.agent.name"]
            if "gen_ai.agent.id" in attrs:
                agent_id = attrs["gen_ai.agent.id"]
            if agent_name:
                break

        # Extract run-level input/output from root step (if available)
        run_input = None
        run_output = None
        run_error = None
        run_error_type = None
        if steps:
            root_step = steps[0]
            # Use root step's inputs/outputs for run-level data
            if root_step.inputs:
                run_input = root_step.inputs
            if root_step.outputs:
                run_output = root_step.outputs
            if root_step.error:
                run_error = root_step.error
                run_error_type = root_step.error_type

        return AgentRun(
            id=_hex_to_uuid(trace_id),
            name=run_name,
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            steps=steps,
            total_tokens=total_tokens,
            total_cost_usd=total_cost,
            error_count=error_count,
            agent_name=agent_name,
            agent_id=agent_id,
            environment=resource_attrs.get("deployment.environment", "development"),
            attributes={"imported_from": "otlp"},
            input=run_input,
            output=run_output,
            error=run_error,
            error_type=run_error_type,
        )

    def _span_to_step(self, span_data: dict[str, Any], trace_id: str) -> Step:
        """Convert a single span to a Step."""
        attrs = span_data.get("attributes", {})

        # Determine step type
        step_type = self._infer_step_type(attrs)

        # Extract timing
        start_time = _ns_to_datetime(span_data["start_time_ns"])
        end_time = _ns_to_datetime(span_data["end_time_ns"])
        # Ensure non-negative duration (handle malformed data)
        duration_ns = max(0, span_data["end_time_ns"] - span_data["start_time_ns"])
        duration_ms = duration_ns / 1_000_000

        # Extract model info (try OTel GenAI first, then OpenInference)
        model_name = attrs.get("gen_ai.request.model") or attrs.get("llm.model_name")
        model_provider = attrs.get("gen_ai.system") or attrs.get("llm.provider")

        # Extract token counts (try multiple naming conventions)
        input_tokens = (
            attrs.get("gen_ai.usage.input_tokens")
            or attrs.get("gen_ai.usage.prompt_tokens")
            or attrs.get("llm.token_count.prompt")
        )
        output_tokens = (
            attrs.get("gen_ai.usage.output_tokens")
            or attrs.get("gen_ai.usage.completion_tokens")
            or attrs.get("llm.token_count.completion")
        )
        if input_tokens is not None:
            input_tokens = int(input_tokens)
        if output_tokens is not None:
            output_tokens = int(output_tokens)

        # Extract cost
        cost_usd = attrs.get("gen_ai.usage.cost")
        if cost_usd is not None:
            cost_usd = float(cost_usd)

        # Extract inputs/outputs
        inputs = self._extract_io(attrs, "input")
        outputs = self._extract_io(attrs, "output")

        # Extract error info
        error = None
        error_type = None
        if span_data.get("status_code") == 2:  # ERROR status
            error = span_data.get("status_message") or attrs.get("error.message") or "Error"
            error_type = attrs.get("error.type")
        elif attrs.get("error.message"):
            error = attrs["error.message"]
            error_type = attrs.get("error.type")

        # Build parent_id
        parent_id = None
        if span_data.get("parent_span_id"):
            parent_id = _hex_to_uuid(span_data["parent_span_id"])

        # Filter out known attributes from custom attributes
        custom_attrs = {
            k: v
            for k, v in attrs.items()
            if not k.startswith(
                (
                    "gen_ai.",
                    "llm.",
                    "tool.",
                    "retrieval.",
                    "input.",
                    "output.",
                    "error.",
                    "tracecraft.",
                )
            )
        }

        return Step(
            id=_hex_to_uuid(span_data["span_id"]),
            parent_id=parent_id,
            trace_id=_hex_to_uuid(trace_id),
            type=step_type,
            name=span_data.get("name", "unknown"),
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            inputs=inputs,
            outputs=outputs,
            attributes=custom_attrs,
            model_name=model_name,
            model_provider=model_provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            error=error,
            error_type=error_type,
        )

    def _infer_step_type(self, attrs: dict[str, Any]) -> StepType:
        """Infer step type from attributes."""
        # Check for explicit tracecraft type
        if "tracecraft.step.type" in attrs:
            type_str = attrs["tracecraft.step.type"]
            try:
                return StepType(type_str)
            except ValueError:
                logger.warning("Unknown step type: %s", type_str)

        # Check for type indicators
        for attr_key, step_type in self.TYPE_INDICATORS.items():
            if attr_key in attrs:
                return step_type

        # Check for LLM indicators
        if any(k.startswith("gen_ai.") for k in attrs) or any(k.startswith("llm.") for k in attrs):
            # Distinguish between agent and LLM
            if "gen_ai.agent.name" in attrs or "gen_ai.agent.id" in attrs:
                return StepType.AGENT
            return StepType.LLM

        # Default to workflow
        return StepType.WORKFLOW

    def _extract_io(self, attrs: dict[str, Any], prefix: str) -> dict[str, Any]:
        """Extract input or output from attributes."""
        result: dict[str, Any] = {}

        # Check for OpenInference format (input.value / output.value)
        value_key = f"{prefix}.value"
        if value_key in attrs:
            value = attrs[value_key]
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    # Ensure result is always a dict
                    result = parsed if isinstance(parsed, dict) else {"value": parsed}
                except json.JSONDecodeError:
                    result = {"value": value}
            else:
                result = {"value": value}

        # Check for OTel GenAI messages format (single attribute)
        messages_key = f"gen_ai.{'request' if prefix == 'input' else 'response'}.messages"
        if messages_key in attrs:
            value = attrs[messages_key]
            if isinstance(value, str):
                try:
                    result["messages"] = json.loads(value)
                except json.JSONDecodeError:
                    result["messages"] = value
            else:
                result["messages"] = value

        # Check for indexed message format (gen_ai.prompt.0.content, gen_ai.completion.0.content)
        # Used by opentelemetry-instrumentation-openai
        indexed_prefix = "gen_ai.prompt" if prefix == "input" else "gen_ai.completion"
        indexed_messages = []
        idx = 0
        while True:
            content_key = f"{indexed_prefix}.{idx}.content"
            role_key = f"{indexed_prefix}.{idx}.role"
            if content_key not in attrs and role_key not in attrs:
                break
            msg: dict[str, Any] = {}
            if role_key in attrs:
                msg["role"] = attrs[role_key]
            if content_key in attrs:
                msg["content"] = attrs[content_key]
            if msg:
                indexed_messages.append(msg)
            idx += 1

        if indexed_messages:
            # If there's only one message, extract content directly for cleaner display
            if len(indexed_messages) == 1 and "content" in indexed_messages[0]:
                if prefix == "input":
                    result["prompt"] = indexed_messages[0]["content"]
                else:
                    result["response"] = indexed_messages[0]["content"]
            else:
                result["messages"] = indexed_messages

        # Check for tool parameters (merge with existing, don't overwrite)
        if prefix == "input" and "tool.parameters" in attrs:
            value = attrs["tool.parameters"]
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, dict):
                        result.update(parsed)
                    else:
                        result["parameters"] = parsed
                except json.JSONDecodeError:
                    result["parameters"] = value
            else:
                result["parameters"] = value

        # Check for retrieval query
        if prefix == "input" and "retrieval.query" in attrs:
            result["query"] = attrs["retrieval.query"]

        # Check for retrieval documents
        if prefix == "output" and "retrieval.documents" in attrs:
            value = attrs["retrieval.documents"]
            if isinstance(value, str):
                try:
                    result["documents"] = json.loads(value)
                except json.JSONDecodeError:
                    result["documents"] = value
            else:
                result["documents"] = value

        return result
