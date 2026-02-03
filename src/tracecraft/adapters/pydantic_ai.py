"""
PydanticAI/Logfire adapter via OTel SpanProcessor.

Provides TraceCraftSpanProcessor that intercepts OpenTelemetry spans
from PydanticAI/Logfire and creates TraceCraft Steps.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from tracecraft.core.context import get_current_run
from tracecraft.core.models import Step, StepType

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun

# Try to import SpanProcessor for proper inheritance
try:
    from opentelemetry.sdk.trace import SpanProcessor

    _HAS_OTEL = True
except ImportError:
    # Fallback: create a stub base class when opentelemetry is not installed
    class SpanProcessor:  # type: ignore[no-redef]
        """Stub base class when opentelemetry is not installed."""

        pass

    _HAS_OTEL = False


class TraceCraftSpanProcessor(SpanProcessor):
    """
    OTel SpanProcessor that creates TraceCraft Steps from spans.

    This processor implements the OpenTelemetry SpanProcessor protocol
    to capture spans from PydanticAI/Logfire and convert them to
    TraceCraft Steps with OpenInference attributes.

    Usage:
        ```python
        from tracecraft.adapters.pydantic_ai import TraceCraftSpanProcessor
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider

        processor = TraceCraftSpanProcessor()
        provider = TracerProvider()
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        run = AgentRun(name="my_run", start_time=datetime.now(UTC))
        with run_context(run):
            # Your PydanticAI code here
            agent.run_sync("What is 2+2?")

        # run.steps now contains the trace
        # Call clear() when done to free memory
        processor.clear()
        ```
    """

    def __init__(self) -> None:
        """Initialize the span processor."""
        super().__init__()
        # Maps span_id -> Step for tracking in-progress spans
        self._steps: dict[str, Step] = {}
        # Maps span_id -> parent_span_id for hierarchy tracking
        self._parent_map: dict[str, str | None] = {}
        self._lock = threading.Lock()

    def clear(self) -> None:
        """Clear tracked steps to free memory. Call after run completes."""
        with self._lock:
            self._steps.clear()
            self._parent_map.clear()

    def _register_step(self, span_id: str, step: Step, parent_span_id: str | None = None) -> None:
        """Register a step in the tracking dict (thread-safe)."""
        with self._lock:
            self._steps[span_id] = step
            self._parent_map[span_id] = parent_span_id

    def _get_step(self, span_id: str) -> Step | None:
        """Get a step from the tracking dict (thread-safe)."""
        with self._lock:
            return self._steps.get(span_id)

    def _pop_step(self, span_id: str) -> Step | None:
        """Remove and return a step from the tracking dict (thread-safe)."""
        with self._lock:
            self._parent_map.pop(span_id, None)
            return self._steps.pop(span_id, None)

    def _get_run(self) -> AgentRun | None:
        """Get the current AgentRun from context."""
        return get_current_run()

    def _get_span_id(self, span: Any) -> str:
        """Extract span ID from span."""
        if hasattr(span, "get_span_context"):
            ctx = span.get_span_context()
            if hasattr(ctx, "span_id"):
                return str(ctx.span_id)
        if hasattr(span, "span_id"):
            return str(span.span_id)
        return ""

    def _get_parent_span_id(self, parent_context: Any) -> str | None:
        """Extract parent span ID from parent context."""
        if parent_context is None:
            return None
        # Try to get span from context
        if hasattr(parent_context, "get"):
            try:
                # OpenTelemetry context
                from opentelemetry import trace as otel_trace

                parent_span = otel_trace.get_current_span(parent_context)
                if parent_span and hasattr(parent_span, "get_span_context"):
                    ctx = parent_span.get_span_context()
                    if hasattr(ctx, "span_id") and ctx.span_id:
                        return str(ctx.span_id)
            except (ImportError, AttributeError):
                pass
        return None

    def _get_attributes(self, span: Any) -> dict[str, Any]:
        """Extract attributes from span."""
        if hasattr(span, "attributes"):
            attrs = span.attributes
            if isinstance(attrs, dict):
                return attrs
            # Handle immutable attribute mapping
            if hasattr(attrs, "items"):
                return dict(attrs.items())
        return {}

    def _infer_step_type(self, span_name: str, attributes: dict[str, Any]) -> StepType:
        """Infer StepType from span name and attributes."""
        # Check for gen_ai attributes (LLM)
        if "gen_ai.system" in attributes or "gen_ai.request.model" in attributes:
            return StepType.LLM

        # Check for tool spans
        if span_name.startswith("tool:") or "tool.name" in attributes:
            return StepType.TOOL

        # Check for agent spans
        if "agent" in span_name.lower():
            return StepType.AGENT

        # Check for retrieval
        if "retriev" in span_name.lower() or "vector" in span_name.lower():
            return StepType.RETRIEVAL

        return StepType.WORKFLOW

    def _get_step_name(self, span_name: str, attributes: dict[str, Any]) -> str:
        """Extract step name from span."""
        # Check for tool name
        if "tool.name" in attributes:
            return str(attributes["tool.name"])

        # Strip tool: prefix
        if span_name.startswith("tool:"):
            return span_name[5:]

        return span_name

    def _extract_model_info(self, attributes: dict[str, Any]) -> tuple[str | None, str | None]:
        """Extract model name and provider from attributes."""
        model_name = None
        model_provider = None

        if "gen_ai.request.model" in attributes:
            model_name = str(attributes["gen_ai.request.model"])
        if "gen_ai.system" in attributes:
            model_provider = str(attributes["gen_ai.system"])

        return model_name, model_provider

    def _extract_tokens(self, attributes: dict[str, Any]) -> tuple[int | None, int | None]:
        """Extract token counts from attributes."""
        input_tokens = None
        output_tokens = None

        if "gen_ai.usage.input_tokens" in attributes:
            input_tokens = int(attributes["gen_ai.usage.input_tokens"])
        if "gen_ai.usage.output_tokens" in attributes:
            output_tokens = int(attributes["gen_ai.usage.output_tokens"])

        return input_tokens, output_tokens

    def _check_error(self, span: Any) -> tuple[str | None, str | None]:
        """Check if span has error status."""
        if not hasattr(span, "status"):
            return None, None

        status = span.status
        # Check for error status code (value 2 in OTel)
        if hasattr(status, "status_code") and status.status_code == 2:  # ERROR
            description = getattr(status, "description", "Unknown error")
            return description, "SpanError"

        return None, None

    def _add_step_to_run(self, step: Step, parent_span_id: str | None = None) -> None:
        """Add a step to the current run, handling hierarchy (thread-safe)."""
        run = self._get_run()
        if run is None:
            return

        # Hold lock during entire operation to ensure thread-safety
        # for both parent lookup and list append operations
        with self._lock:
            parent = self._steps.get(parent_span_id) if parent_span_id else None
            if parent:
                step.parent_id = parent.id
                parent.children.append(step)
            else:
                run.steps.append(step)

    def on_start(
        self,
        span: Any,
        parent_context: Any = None,
    ) -> None:
        """
        Called when a span is started.

        Args:
            span: The span that was started.
            parent_context: Optional parent context for hierarchy tracking.
        """
        run = self._get_run()
        if run is None:
            return

        span_id = self._get_span_id(span)
        if not span_id:
            return

        attributes = self._get_attributes(span)
        span_name = getattr(span, "name", "unknown")
        parent_span_id = self._get_parent_span_id(parent_context)

        step_type = self._infer_step_type(span_name, attributes)
        step_name = self._get_step_name(span_name, attributes)
        model_name, model_provider = self._extract_model_info(attributes)

        step = Step(
            trace_id=run.id,
            type=step_type,
            name=step_name,
            start_time=datetime.now(UTC),
            model_name=model_name if step_type == StepType.LLM else None,
            model_provider=model_provider if step_type == StepType.LLM else None,
        )

        self._register_step(span_id, step, parent_span_id)
        self._add_step_to_run(step, parent_span_id)

    def on_end(self, span: Any) -> None:
        """
        Called when a span is ended.

        Args:
            span: The span that was ended.
        """
        span_id = self._get_span_id(span)
        if not span_id:
            return

        step = self._pop_step(span_id)
        if step is None:
            return

        # Set end time and duration
        end_time = datetime.now(UTC)
        step.end_time = end_time
        step.duration_ms = (end_time - step.start_time).total_seconds() * 1000

        # Extract final attributes (they may have been added during span)
        attributes = self._get_attributes(span)

        # Extract tokens for LLM steps
        if step.type == StepType.LLM:
            input_tokens, output_tokens = self._extract_tokens(attributes)
            if input_tokens is not None:
                step.input_tokens = input_tokens
            if output_tokens is not None:
                step.output_tokens = output_tokens

            # Note: Token aggregation is done in runtime._aggregate_metrics()
            # at end_run() time, so no need to update run.total_tokens here

        # Check for errors
        error_msg, error_type = self._check_error(span)
        if error_msg:
            step.error = error_msg
            step.error_type = error_type
            # Note: Error aggregation is done in runtime._aggregate_metrics()

    def shutdown(self) -> None:
        """Shutdown the processor."""
        self.clear()

    def force_flush(self, timeout_millis: int = 30000) -> bool:  # noqa: ARG002
        """
        Force flush any pending spans.

        Args:
            timeout_millis: Timeout in milliseconds.

        Returns:
            True if flush was successful.
        """
        return True

    def on_event(
        self, span: Any, event_name: str, attributes: dict[str, Any] | None = None
    ) -> None:
        """
        Handle span event for streaming tokens.

        This can be called when the span emits events during streaming.
        For gen_ai spans, streaming tokens are often emitted as events.

        Args:
            span: The span that emitted the event.
            event_name: Name of the event (e.g., "gen_ai.content.chunk").
            attributes: Event attributes containing the chunk content.
        """
        span_id = self._get_span_id(span)
        if not span_id:
            return

        # Check for streaming chunk events
        if event_name in ("gen_ai.content.chunk", "llm.content.chunk"):
            with self._lock:
                step = self._steps.get(span_id)
                if step is not None:
                    step.is_streaming = True
                    if attributes:
                        chunk = attributes.get("gen_ai.chunk.text") or attributes.get("text")
                        if chunk:
                            step.streaming_chunks.append(str(chunk))
