"""Live tests for PydanticAI integration.

Run with: uv run pytest tests/live/test_live_pydantic_ai.py -v --live
Requires: OPENAI_API_KEY environment variable
          uv add pydantic-ai
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.live.conftest import requires_openai_key


@pytest.mark.live
class TestLivePydanticAIBasic:
    """Basic PydanticAI integration tests."""

    @requires_openai_key
    def test_simple_agent(
        self, live_test_model: str, _max_tokens: int, temp_jsonl_path: str
    ) -> None:
        """Test simple PydanticAI agent is traced."""
        pytest.importorskip("pydantic_ai")

        from pydantic_ai import Agent

        import tracecraft
        from tracecraft.adapters.pydantic_ai import TraceCraftSpanProcessor
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        # Note: PydanticAI uses Logfire/OpenTelemetry internally
        # We intercept via our SpanProcessor
        runtime = tracecraft.init(console=True, jsonl=True, jsonl_path=temp_jsonl_path)
        processor = TraceCraftSpanProcessor()

        # Create a simple agent
        agent = Agent(
            live_test_model,
            system_prompt="You are a helpful assistant. Be very concise.",
        )

        run = AgentRun(name="test_pydantic_ai_simple", start_time=datetime.now(UTC))

        with run_context(run):
            # Run synchronously
            result = agent.run_sync("Say 'Hello' and nothing else.")

        runtime.end_run(run)
        processor.clear()

        # Verify result
        assert result.data is not None
        assert len(str(result.data)) > 0

    @requires_openai_key
    def test_agent_with_structured_output(self, live_test_model: str, _max_tokens: int) -> None:
        """Test PydanticAI agent with structured output."""
        pytest.importorskip("pydantic_ai")

        from pydantic import BaseModel
        from pydantic_ai import Agent

        import tracecraft
        from tracecraft.adapters.pydantic_ai import TraceCraftSpanProcessor
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        tracecraft.init(console=True, jsonl=False)
        processor = TraceCraftSpanProcessor()

        class MathResult(BaseModel):
            expression: str
            result: int

        agent = Agent(
            live_test_model,
            result_type=MathResult,
            system_prompt="Extract the math expression and calculate the result.",
        )

        run = AgentRun(name="test_structured_output", start_time=datetime.now(UTC))

        with run_context(run):
            result = agent.run_sync("What is 5 + 3?")

        processor.clear()

        # Verify structured output
        assert isinstance(result.data, MathResult)
        assert result.data.result == 8


@pytest.mark.live
class TestLivePydanticAITools:
    """PydanticAI tool usage tests."""

    @requires_openai_key
    def test_agent_with_tools(self, live_test_model: str, _max_tokens: int) -> None:
        """Test PydanticAI agent with tool calls."""
        pytest.importorskip("pydantic_ai")

        from pydantic_ai import Agent

        import tracecraft
        from tracecraft.adapters.pydantic_ai import TraceCraftSpanProcessor
        from tracecraft.core.context import run_context as trace_context
        from tracecraft.core.models import AgentRun

        tracecraft.init(console=True, jsonl=False)
        processor = TraceCraftSpanProcessor()

        agent = Agent(
            live_test_model,
            system_prompt="You are a helpful calculator. Use the calculator tool.",
        )

        @agent.tool_plain
        def calculator(expression: str) -> str:
            """Calculate a math expression."""
            try:
                return str(eval(expression))  # noqa: S307
            except Exception as e:
                return f"Error: {e}"

        run = AgentRun(name="test_tools", start_time=datetime.now(UTC))

        with trace_context(run):
            result = agent.run_sync("What is 7 * 8?")

        processor.clear()

        # Verify agent completed
        assert result.data is not None
        # The result should contain 56
        assert "56" in str(result.data)


@pytest.mark.live
class TestLivePydanticAIAsync:
    """PydanticAI async tests."""

    @requires_openai_key
    @pytest.mark.asyncio
    async def test_async_agent(self, live_test_model: str, _max_tokens: int) -> None:
        """Test async PydanticAI agent execution."""
        pytest.importorskip("pydantic_ai")

        from pydantic_ai import Agent

        import tracecraft
        from tracecraft.adapters.pydantic_ai import TraceCraftSpanProcessor
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        tracecraft.init(console=True, jsonl=False)
        processor = TraceCraftSpanProcessor()

        agent = Agent(
            live_test_model,
            system_prompt="Be very concise.",
        )

        run = AgentRun(name="test_async", start_time=datetime.now(UTC))

        with run_context(run):
            result = await agent.run("Say 'async works' exactly.")

        processor.clear()

        assert result.data is not None


@pytest.mark.live
class TestLivePydanticAIStreaming:
    """PydanticAI streaming tests."""

    @requires_openai_key
    @pytest.mark.asyncio
    async def test_streaming_response(self, live_test_model: str, _max_tokens: int) -> None:
        """Test streaming PydanticAI response."""
        pytest.importorskip("pydantic_ai")

        from pydantic_ai import Agent

        import tracecraft
        from tracecraft.adapters.pydantic_ai import TraceCraftSpanProcessor
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        tracecraft.init(console=True, jsonl=False)
        processor = TraceCraftSpanProcessor()

        agent = Agent(
            live_test_model,
            system_prompt="Be concise.",
        )

        run = AgentRun(name="test_streaming", start_time=datetime.now(UTC))

        chunks = []
        with run_context(run):
            async with agent.run_stream("Count 1 to 3.") as stream:
                async for chunk in stream.stream_text():
                    chunks.append(chunk)

        processor.clear()

        # Verify streaming worked
        assert len(chunks) > 0


@pytest.mark.live
@pytest.mark.expensive
class TestLivePydanticAIComplex:
    """More complex PydanticAI tests."""

    @requires_openai_key
    def test_multi_turn_conversation(self, live_test_model: str, _max_tokens: int) -> None:
        """Test multi-turn conversation tracing."""
        pytest.importorskip("pydantic_ai")

        from pydantic_ai import Agent

        import tracecraft
        from tracecraft.adapters.pydantic_ai import TraceCraftSpanProcessor
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        runtime = tracecraft.init(console=True, jsonl=False)
        processor = TraceCraftSpanProcessor()

        agent = Agent(
            live_test_model,
            system_prompt="You are a helpful assistant. Be very concise.",
        )

        run = AgentRun(name="test_multi_turn", start_time=datetime.now(UTC))

        with run_context(run):
            # First turn
            result1 = agent.run_sync("My name is Alice.")

            # Second turn with history
            result2 = agent.run_sync(
                "What is my name?",
                message_history=result1.new_messages(),
            )

        runtime.end_run(run)
        processor.clear()

        # Verify second response knows the name
        assert "Alice" in str(result2.data)
        # Should have multiple steps from multiple calls
        assert run.total_tokens > 0
