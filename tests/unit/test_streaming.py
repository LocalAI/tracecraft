"""
Tests for streaming functionality in adapters.

Verifies that streaming tokens are captured correctly and thread-safely.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from uuid import uuid4

from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun, Step, StepType


class TestStepStreamingFields:
    """Tests for Step streaming fields."""

    def test_step_has_streaming_fields(self) -> None:
        """Step model should have is_streaming and streaming_chunks fields."""
        step = Step(
            trace_id=uuid4(),
            type=StepType.LLM,
            name="test_llm",
            start_time=datetime.now(UTC),
        )
        assert step.is_streaming is False
        assert step.streaming_chunks == []

    def test_step_streaming_chunks_default_empty_list(self) -> None:
        """streaming_chunks should default to empty list, not shared."""
        step1 = Step(
            trace_id=uuid4(),
            type=StepType.LLM,
            name="test_llm_1",
            start_time=datetime.now(UTC),
        )
        step2 = Step(
            trace_id=uuid4(),
            type=StepType.LLM,
            name="test_llm_2",
            start_time=datetime.now(UTC),
        )
        step1.streaming_chunks.append("token1")
        # step2 should not be affected
        assert step2.streaming_chunks == []

    def test_step_can_store_streaming_chunks(self) -> None:
        """Step should be able to store streaming chunks."""
        step = Step(
            trace_id=uuid4(),
            type=StepType.LLM,
            name="test_llm",
            start_time=datetime.now(UTC),
        )
        step.is_streaming = True
        step.streaming_chunks.extend(["Hello", " ", "world", "!"])

        assert step.is_streaming is True
        assert step.streaming_chunks == ["Hello", " ", "world", "!"]
        assert "".join(step.streaming_chunks) == "Hello world!"


class TestLangChainStreaming:
    """Tests for LangChain adapter streaming functionality."""

    def test_on_llm_new_token_captures_tokens(self) -> None:
        """on_llm_new_token should capture streaming tokens."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        handler = TraceCraftCallbackHandler()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            # Simulate LLM start
            run_id = uuid4()
            handler.on_llm_start(
                serialized={"name": "test_llm"},
                prompts=["Hello"],
                run_id=run_id,
            )

            # Simulate streaming tokens
            handler.on_llm_new_token("Hello", run_id=run_id)
            handler.on_llm_new_token(" ", run_id=run_id)
            handler.on_llm_new_token("world", run_id=run_id)

            # Get the step to check
            step = handler._get_step(run_id)
            assert step is not None
            assert step.is_streaming is True
            assert step.streaming_chunks == ["Hello", " ", "world"]

    def test_streaming_tokens_thread_safe(self) -> None:
        """Streaming token capture should be thread-safe."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        handler = TraceCraftCallbackHandler()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        run_id = uuid4()
        errors: list[Exception] = []

        with run_context(run):
            # Start LLM
            handler.on_llm_start(
                serialized={"name": "test_llm"},
                prompts=["Hello"],
                run_id=run_id,
            )

            # Spawn multiple threads to add tokens concurrently
            def add_tokens(prefix: str) -> None:
                try:
                    for i in range(10):
                        handler.on_llm_new_token(f"{prefix}_{i}", run_id=run_id)
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=add_tokens, args=(f"t{i}",)) for i in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # Check no errors occurred
            assert errors == []

            # All 50 tokens should be captured
            step = handler._get_step(run_id)
            assert step is not None
            assert len(step.streaming_chunks) == 50


class TestLlamaIndexStreaming:
    """Tests for LlamaIndex adapter streaming functionality."""

    def test_on_llm_stream_captures_chunks(self) -> None:
        """on_llm_stream should capture streaming chunks."""
        from tracecraft.adapters.llamaindex import TraceCraftSpanHandler

        handler = TraceCraftSpanHandler()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            # Simulate span creation
            span_id = "test_span_123"
            handler.new_span(
                id_=span_id,
                bound_args={},
                instance=None,  # Will be treated as workflow
            )

            # Get the step and manually set it as LLM type for this test
            step = handler._get_step(span_id)
            assert step is not None
            step.type = StepType.LLM

            # Simulate streaming
            handler.on_llm_stream(span_id, "Token1")
            handler.on_llm_stream(span_id, "Token2")
            handler.on_llm_stream(span_id, "Token3")

            assert step.is_streaming is True
            assert step.streaming_chunks == ["Token1", "Token2", "Token3"]


class TestPydanticAIStreaming:
    """Tests for PydanticAI adapter streaming functionality."""

    def test_on_event_captures_streaming_chunks(self) -> None:
        """on_event should capture gen_ai streaming chunks."""
        from tracecraft.adapters.pydantic_ai import TraceCraftSpanProcessor

        processor = TraceCraftSpanProcessor()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            # Create a mock span
            class MockSpanContext:
                span_id = 12345

            class MockSpan:
                name = "test_llm"
                attributes = {"gen_ai.system": "openai"}

                def get_span_context(self):
                    return MockSpanContext()

            mock_span = MockSpan()
            processor.on_start(mock_span)

            # Get the step
            step = processor._get_step("12345")
            assert step is not None

            # Simulate streaming events
            processor.on_event(
                mock_span,
                "gen_ai.content.chunk",
                {"gen_ai.chunk.text": "Hello"},
            )
            processor.on_event(
                mock_span,
                "gen_ai.content.chunk",
                {"gen_ai.chunk.text": " world"},
            )

            assert step.is_streaming is True
            assert step.streaming_chunks == ["Hello", " world"]

    def test_on_event_ignores_non_streaming_events(self) -> None:
        """on_event should ignore non-streaming event types."""
        from tracecraft.adapters.pydantic_ai import TraceCraftSpanProcessor

        processor = TraceCraftSpanProcessor()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):

            class MockSpanContext:
                span_id = 12345

            class MockSpan:
                name = "test_llm"
                attributes = {"gen_ai.system": "openai"}

                def get_span_context(self):
                    return MockSpanContext()

            mock_span = MockSpan()
            processor.on_start(mock_span)

            step = processor._get_step("12345")
            assert step is not None

            # This event type should be ignored
            processor.on_event(
                mock_span,
                "some.other.event",
                {"text": "ignored"},
            )

            assert step.is_streaming is False
            assert step.streaming_chunks == []
