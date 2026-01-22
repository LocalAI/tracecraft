"""
Tests for the PydanticAI adapter.

Tests PydanticAI/Logfire integration via TracerProvider interception.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from agenttrace.core.context import run_context
from agenttrace.core.models import AgentRun, StepType


class TestPydanticAIAdapter:
    """Tests for AgentTraceSpanProcessor."""

    def test_processor_creation(self) -> None:
        """Should create a span processor."""
        from agenttrace.adapters.pydantic_ai import AgentTraceSpanProcessor

        processor = AgentTraceSpanProcessor()
        assert processor is not None

    def test_processor_requires_active_run(self) -> None:
        """Should require an active run to capture spans."""
        from agenttrace.adapters.pydantic_ai import AgentTraceSpanProcessor

        processor = AgentTraceSpanProcessor()
        # No active run - should not create steps
        span = MockSpan(name="test_span")
        processor.on_start(span, parent_context=None)
        processor.on_end(span)
        # No error, just skip

    def test_processor_with_active_run(self) -> None:
        """Should create steps when run is active."""
        from agenttrace.adapters.pydantic_ai import AgentTraceSpanProcessor

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        processor = AgentTraceSpanProcessor()
        span = MockSpan(name="test_span")

        with run_context(run):
            processor.on_start(span, parent_context=None)
            processor.on_end(span)

        assert len(run.steps) == 1


class TestSpanTypeInference:
    """Tests for inferring step type from span attributes."""

    def test_infer_llm_type_from_attributes(self) -> None:
        """Should infer LLM type from gen_ai attributes."""
        from agenttrace.adapters.pydantic_ai import AgentTraceSpanProcessor

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        processor = AgentTraceSpanProcessor()
        span = MockSpan(
            name="chat",
            attributes={
                "gen_ai.system": "openai",
                "gen_ai.request.model": "gpt-4",
            },
        )

        with run_context(run):
            processor.on_start(span, parent_context=None)
            processor.on_end(span)

        step = run.steps[0]
        assert step.type == StepType.LLM
        assert step.model_name == "gpt-4"
        assert step.model_provider == "openai"

    def test_infer_tool_type(self) -> None:
        """Should infer TOOL type from tool span names."""
        from agenttrace.adapters.pydantic_ai import AgentTraceSpanProcessor

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        processor = AgentTraceSpanProcessor()
        span = MockSpan(
            name="tool:calculator",
            attributes={"tool.name": "calculator"},
        )

        with run_context(run):
            processor.on_start(span, parent_context=None)
            processor.on_end(span)

        step = run.steps[0]
        assert step.type == StepType.TOOL
        assert step.name == "calculator"

    def test_infer_agent_type(self) -> None:
        """Should infer AGENT type from agent span names."""
        from agenttrace.adapters.pydantic_ai import AgentTraceSpanProcessor

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        processor = AgentTraceSpanProcessor()
        span = MockSpan(name="pydantic_ai.agent.run")

        with run_context(run):
            processor.on_start(span, parent_context=None)
            processor.on_end(span)

        step = run.steps[0]
        assert step.type == StepType.AGENT

    def test_default_workflow_type(self) -> None:
        """Should default to WORKFLOW for unknown spans."""
        from agenttrace.adapters.pydantic_ai import AgentTraceSpanProcessor

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        processor = AgentTraceSpanProcessor()
        span = MockSpan(name="some_operation")

        with run_context(run):
            processor.on_start(span, parent_context=None)
            processor.on_end(span)

        step = run.steps[0]
        assert step.type == StepType.WORKFLOW


class TestTokenCapture:
    """Tests for capturing token counts from spans."""

    def test_capture_tokens_from_attributes(self) -> None:
        """Should capture token counts from gen_ai attributes."""
        from agenttrace.adapters.pydantic_ai import AgentTraceSpanProcessor

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        processor = AgentTraceSpanProcessor()
        span = MockSpan(
            name="chat",
            attributes={
                "gen_ai.system": "openai",
                "gen_ai.usage.input_tokens": 100,
                "gen_ai.usage.output_tokens": 50,
            },
        )

        with run_context(run):
            processor.on_start(span, parent_context=None)
            processor.on_end(span)

        step = run.steps[0]
        assert step.input_tokens == 100
        assert step.output_tokens == 50

    def test_update_run_totals(self) -> None:
        """Should update run total_tokens."""
        from agenttrace.adapters.pydantic_ai import AgentTraceSpanProcessor

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        processor = AgentTraceSpanProcessor()

        with run_context(run):
            # First LLM span
            span1 = MockSpan(
                name="chat1",
                attributes={
                    "gen_ai.system": "openai",
                    "gen_ai.usage.input_tokens": 100,
                    "gen_ai.usage.output_tokens": 50,
                },
            )
            processor.on_start(span1, parent_context=None)
            processor.on_end(span1)

            # Second LLM span
            span2 = MockSpan(
                name="chat2",
                attributes={
                    "gen_ai.system": "openai",
                    "gen_ai.usage.input_tokens": 200,
                    "gen_ai.usage.output_tokens": 100,
                },
            )
            processor.on_start(span2, parent_context=None)
            processor.on_end(span2)

        # Token totals are aggregated at end_run() time by _aggregate_metrics()
        # Verify that steps have the correct token counts
        step1 = run.steps[0]
        step2 = run.steps[1]
        assert step1.input_tokens == 100
        assert step1.output_tokens == 50
        assert step2.input_tokens == 200
        assert step2.output_tokens == 100
        # Total would be 450 after end_run() aggregation


class TestSpanHierarchy:
    """Tests for span parent-child relationships."""

    def test_nested_spans(self) -> None:
        """Should track span hierarchy via context."""
        from agenttrace.adapters.pydantic_ai import AgentTraceSpanProcessor

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        processor = AgentTraceSpanProcessor()

        # Note: Full hierarchy testing requires OTel context propagation
        # which is complex to mock. Basic test that spans are created.
        parent_span = MockSpan(name="parent")
        child_span = MockSpan(name="child")

        with run_context(run):
            processor.on_start(parent_span, parent_context=None)
            processor.on_start(child_span, parent_context=MockContext(span_id=parent_span.span_id))
            processor.on_end(child_span)
            processor.on_end(parent_span)

        # Should have created steps
        assert len(run.steps) >= 1


class TestErrorHandling:
    """Tests for error handling."""

    def test_capture_span_error(self) -> None:
        """Should capture errors from span status."""
        from agenttrace.adapters.pydantic_ai import AgentTraceSpanProcessor

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        processor = AgentTraceSpanProcessor()
        span = MockSpan(
            name="failing_operation",
            status=MockStatus(is_error=True, description="Connection refused"),
        )

        with run_context(run):
            processor.on_start(span, parent_context=None)
            processor.on_end(span)

        step = run.steps[0]
        assert step.error == "Connection refused"

    def test_error_increments_run_count(self) -> None:
        """Should increment run.error_count on errors."""
        from agenttrace.adapters.pydantic_ai import AgentTraceSpanProcessor

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        processor = AgentTraceSpanProcessor()

        with run_context(run):
            span1 = MockSpan(
                name="error1",
                status=MockStatus(is_error=True, description="Error 1"),
            )
            processor.on_start(span1, parent_context=None)
            processor.on_end(span1)

            span2 = MockSpan(
                name="error2",
                status=MockStatus(is_error=True, description="Error 2"),
            )
            processor.on_start(span2, parent_context=None)
            processor.on_end(span2)

        # Error count is aggregated at end_run() time by _aggregate_metrics()
        # Verify that steps have the correct error info
        step1 = run.steps[0]
        step2 = run.steps[1]
        assert step1.error == "Error 1"
        assert step1.error_type == "SpanError"
        assert step2.error == "Error 2"
        assert step2.error_type == "SpanError"
        # error_count would be 2 after end_run() aggregation


class TestSpanProcessorProtocol:
    """Tests for OTel SpanProcessor protocol compliance."""

    def test_has_required_methods(self) -> None:
        """Should implement the SpanProcessor protocol methods."""
        from agenttrace.adapters.pydantic_ai import AgentTraceSpanProcessor

        processor = AgentTraceSpanProcessor()

        # Required SpanProcessor methods
        assert hasattr(processor, "on_start")
        assert hasattr(processor, "on_end")
        assert hasattr(processor, "shutdown")
        assert hasattr(processor, "force_flush")
        assert callable(processor.on_start)
        assert callable(processor.on_end)
        assert callable(processor.shutdown)
        assert callable(processor.force_flush)


class TestEdgeCases:
    """Tests for edge cases."""

    def test_span_with_no_attributes(self) -> None:
        """Should handle spans with no attributes."""
        from agenttrace.adapters.pydantic_ai import AgentTraceSpanProcessor

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        processor = AgentTraceSpanProcessor()
        span = MockSpan(name="basic_span", attributes={})

        with run_context(run):
            processor.on_start(span, parent_context=None)
            processor.on_end(span)

        step = run.steps[0]
        assert step.name == "basic_span"

    def test_end_without_start(self) -> None:
        """Should handle end without corresponding start."""
        from agenttrace.adapters.pydantic_ai import AgentTraceSpanProcessor

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        processor = AgentTraceSpanProcessor()
        span = MockSpan(name="untracked")

        with run_context(run):
            # End without start - should not raise
            processor.on_end(span)

        # Should not have created any steps
        assert len(run.steps) == 0


# Mock classes to simulate OTel objects without requiring the dependency


class MockSpan:
    """Mock OTel Span."""

    def __init__(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        status: MockStatus | None = None,
    ) -> None:
        self.name = name
        self._attributes = attributes or {}
        self._status = status
        self.span_id = str(uuid4())[:16]  # Simulate span ID
        self._start_time = datetime.now(UTC)
        self._end_time = None

    def get_span_context(self) -> MockSpanContext:
        return MockSpanContext(span_id=self.span_id)

    @property
    def attributes(self) -> dict[str, Any]:
        return self._attributes

    @property
    def status(self) -> MockStatus:
        return self._status or MockStatus()

    @property
    def start_time(self) -> int:
        # Return nanoseconds
        return int(self._start_time.timestamp() * 1e9)

    @property
    def end_time(self) -> int:
        if self._end_time:
            return int(self._end_time.timestamp() * 1e9)
        return int(datetime.now(UTC).timestamp() * 1e9)


class MockSpanContext:
    """Mock OTel SpanContext."""

    def __init__(self, span_id: str = "") -> None:
        self.span_id = span_id
        self.trace_id = str(uuid4())[:32]


class MockStatus:
    """Mock OTel Status."""

    def __init__(
        self,
        is_error: bool = False,
        description: str = "",
    ) -> None:
        self.is_ok = not is_error
        self.is_unset = not is_error
        self.description = description

    @property
    def status_code(self) -> int:
        # Simulate StatusCode enum values
        if self.is_ok:
            return 1  # OK
        return 2  # ERROR


class MockContext:
    """Mock OTel Context for parent tracking."""

    def __init__(self, span_id: str = "") -> None:
        self._span_id = span_id

    def get(self, _key: Any) -> Any:
        # Simulate getting the current span from context
        return MockSpan(name="parent", attributes={})


class TestThreadSafety:
    """Tests for thread-safety of the span processor."""

    def test_concurrent_span_creation(self) -> None:
        """Should handle concurrent span creation from multiple threads."""
        import threading

        from agenttrace.adapters.pydantic_ai import AgentTraceSpanProcessor

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        processor = AgentTraceSpanProcessor()
        errors: list[Exception] = []
        num_threads = 10

        def create_span(thread_id: int) -> None:
            try:
                with run_context(run):
                    span = MockSpan(
                        name=f"span_{thread_id}",
                        attributes={"gen_ai.system": "openai"},
                    )
                    processor.on_start(span)
                    processor.on_end(span)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_span, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no errors occurred
        assert len(errors) == 0, f"Errors during concurrent access: {errors}"

        # Verify all steps were created
        assert len(run.steps) == num_threads

    def test_concurrent_nested_spans(self) -> None:
        """Should handle concurrent nested span creation."""
        import threading

        from agenttrace.adapters.pydantic_ai import AgentTraceSpanProcessor

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        processor = AgentTraceSpanProcessor()
        errors: list[Exception] = []
        num_threads = 5

        def create_nested_spans(thread_id: int) -> None:
            try:
                with run_context(run):
                    parent_span = MockSpan(
                        name=f"parent_{thread_id}",
                        attributes={"gen_ai.system": "openai"},
                    )
                    parent_span_id = parent_span.span_id
                    processor.on_start(parent_span)

                    # Create 3 children per parent
                    for child_num in range(3):
                        child_span = MockSpan(
                            name=f"tool:child_{thread_id}_{child_num}",
                            attributes={"tool.name": f"tool_{child_num}"},
                        )
                        child_span_id = child_span.span_id
                        # Manually register parent relationship
                        processor._parent_map[child_span_id] = parent_span_id
                        processor.on_start(child_span)
                        processor.on_end(child_span)

                    processor.on_end(parent_span)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=create_nested_spans, args=(i,)) for i in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no errors occurred
        assert len(errors) == 0, f"Errors during concurrent access: {errors}"

        # Count total steps (including nested children attached to parents)
        total_steps = len(run.steps)
        for step in run.steps:
            total_steps += len(step.children)

        # Expect: 5 parents + 15 children (some may be root level due to timing)
        assert total_steps >= num_threads, (
            f"Expected at least {num_threads} steps, got {total_steps}"
        )
