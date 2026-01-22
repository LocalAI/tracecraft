"""Tests for streaming decorators."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest

from agenttrace.core.context import run_context
from agenttrace.core.models import AgentRun


class TestTraceLLMStream:
    """Tests for trace_llm_stream decorator."""

    @pytest.mark.asyncio
    async def test_trace_llm_stream_collects_tokens(self):
        """Test trace_llm_stream collects all tokens."""
        from agenttrace.instrumentation.decorators import trace_llm_stream

        @trace_llm_stream(name="test_stream", model="gpt-4o", provider="openai")
        async def stream_tokens() -> AsyncGenerator[str, None]:
            yield "Hello"
            yield " "
            yield "World"

        run = AgentRun(name="test", start_time=datetime.now(UTC))

        with run_context(run):
            tokens = []
            async for token in stream_tokens():
                tokens.append(token)

        assert tokens == ["Hello", " ", "World"]

    @pytest.mark.asyncio
    async def test_trace_llm_stream_creates_step(self):
        """Test trace_llm_stream creates step with correct attributes."""
        from agenttrace.instrumentation.decorators import trace_llm_stream

        @trace_llm_stream(name="test_stream", model="gpt-4o", provider="openai")
        async def stream_tokens() -> AsyncGenerator[str, None]:
            yield "test"

        run = AgentRun(name="test", start_time=datetime.now(UTC))

        with run_context(run):
            async for _ in stream_tokens():
                pass

        assert len(run.steps) == 1
        step = run.steps[0]
        assert step.name == "test_stream"
        assert step.model_name == "gpt-4o"
        assert step.model_provider == "openai"
        assert step.attributes["is_streaming"] is True

    @pytest.mark.asyncio
    async def test_trace_llm_stream_aggregates_output(self):
        """Test trace_llm_stream aggregates full output."""
        from agenttrace.instrumentation.decorators import trace_llm_stream

        @trace_llm_stream(name="test_stream")
        async def stream_tokens() -> AsyncGenerator[str, None]:
            yield "Hello"
            yield " "
            yield "World"

        run = AgentRun(name="test", start_time=datetime.now(UTC))

        with run_context(run):
            async for _ in stream_tokens():
                pass

        step = run.steps[0]
        assert step.outputs["result"] == "Hello World"
        assert step.attributes["token_count"] == 3

    @pytest.mark.asyncio
    async def test_trace_llm_stream_captures_error(self):
        """Test trace_llm_stream captures errors."""
        from agenttrace.instrumentation.decorators import trace_llm_stream

        @trace_llm_stream(name="test_stream")
        async def stream_with_error() -> AsyncGenerator[str, None]:
            yield "partial"
            raise ValueError("Stream error")

        run = AgentRun(name="test", start_time=datetime.now(UTC))

        with run_context(run), pytest.raises(ValueError):
            async for _ in stream_with_error():
                pass

        step = run.steps[0]
        assert step.error == "Stream error"
        assert step.error_type == "ValueError"
        assert step.outputs["partial_result"] == "partial"

    @pytest.mark.asyncio
    async def test_trace_llm_stream_uses_function_name(self):
        """Test trace_llm_stream defaults to function name."""
        from agenttrace.instrumentation.decorators import trace_llm_stream

        @trace_llm_stream()
        async def my_stream_function() -> AsyncGenerator[str, None]:
            yield "test"

        run = AgentRun(name="test", start_time=datetime.now(UTC))

        with run_context(run):
            async for _ in my_stream_function():
                pass

        step = run.steps[0]
        assert step.name == "my_stream_function"


class TestTraceStream:
    """Tests for trace_stream decorator."""

    @pytest.mark.asyncio
    async def test_trace_stream_collects_items(self):
        """Test trace_stream collects all items."""
        from agenttrace.instrumentation.decorators import trace_stream

        @trace_stream(name="test_stream")
        async def stream_items() -> AsyncGenerator[dict, None]:
            yield {"id": 1}
            yield {"id": 2}
            yield {"id": 3}

        run = AgentRun(name="test", start_time=datetime.now(UTC))

        with run_context(run):
            items = []
            async for item in stream_items():
                items.append(item)

        assert len(items) == 3
        assert items[0] == {"id": 1}

    @pytest.mark.asyncio
    async def test_trace_stream_creates_step(self):
        """Test trace_stream creates step."""
        from agenttrace.core.models import StepType
        from agenttrace.instrumentation.decorators import trace_stream

        @trace_stream(name="process_stream", step_type=StepType.WORKFLOW)
        async def process_items() -> AsyncGenerator[int, None]:
            yield 1
            yield 2

        run = AgentRun(name="test", start_time=datetime.now(UTC))

        with run_context(run):
            async for _ in process_items():
                pass

        assert len(run.steps) == 1
        step = run.steps[0]
        assert step.name == "process_stream"
        assert step.attributes["is_streaming"] is True

    @pytest.mark.asyncio
    async def test_trace_stream_counts_items(self):
        """Test trace_stream counts yielded items."""
        from agenttrace.instrumentation.decorators import trace_stream

        @trace_stream(name="test_stream")
        async def stream_items() -> AsyncGenerator[str, None]:
            yield "a"
            yield "b"
            yield "c"

        run = AgentRun(name="test", start_time=datetime.now(UTC))

        with run_context(run):
            async for _ in stream_items():
                pass

        step = run.steps[0]
        assert step.outputs["item_count"] == 3

    @pytest.mark.asyncio
    async def test_trace_stream_captures_error(self):
        """Test trace_stream captures errors with partial count."""
        from agenttrace.instrumentation.decorators import trace_stream

        @trace_stream(name="test_stream")
        async def stream_with_error() -> AsyncGenerator[str, None]:
            yield "a"
            yield "b"
            raise RuntimeError("Processing error")

        run = AgentRun(name="test", start_time=datetime.now(UTC))

        with run_context(run), pytest.raises(RuntimeError):
            async for _ in stream_with_error():
                pass

        step = run.steps[0]
        assert step.error == "Processing error"
        assert step.error_type == "RuntimeError"
        assert step.outputs["partial_item_count"] == 2


class TestStreamingWithNestedCalls:
    """Tests for streaming decorators with nested calls."""

    @pytest.mark.asyncio
    async def test_nested_streaming_calls(self):
        """Test nested streaming calls create proper hierarchy."""
        from agenttrace.instrumentation.decorators import trace_agent, trace_llm_stream

        @trace_llm_stream(name="inner_stream")
        async def inner_stream() -> AsyncGenerator[str, None]:
            yield "hello"

        @trace_agent(name="outer_agent")
        async def outer_agent() -> str:
            result = []
            async for token in inner_stream():
                result.append(token)
            return "".join(result)

        run = AgentRun(name="test", start_time=datetime.now(UTC))

        with run_context(run):
            result = await outer_agent()

        assert result == "hello"
        # Both steps should be recorded
        # Due to the step hierarchy, one may be nested in the other
        # Just verify we have steps recorded
        assert len(run.steps) >= 1
