"""Live tests for direct OpenAI integration.

Run with: uv run pytest tests/live/test_live_openai.py -v --live
Requires: OPENAI_API_KEY environment variable
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.live.conftest import requires_openai_key


@pytest.mark.live
class TestLiveOpenAIBasic:
    """Basic OpenAI API tests."""

    @requires_openai_key
    def test_chat_completion_traced(
        self, live_test_model: str, max_tokens: int, temp_jsonl_path: str
    ) -> None:
        """Test that OpenAI chat completion is traced correctly."""
        import openai

        import tracecraft
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun
        from tracecraft.instrumentation.decorators import trace_llm

        # Initialize with JSONL export
        runtime = tracecraft.init(console=True, jsonl=True, jsonl_path=temp_jsonl_path)

        @trace_llm(name="openai_chat", model=live_test_model, provider="openai")
        def call_openai(prompt: str) -> str:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=live_test_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""

        run = AgentRun(name="test_openai_chat", start_time=datetime.now(UTC))

        with run_context(run):
            result = call_openai("Say hello in exactly 3 words.")

        runtime.end_run(run)

        # Verify trace was captured
        assert len(run.steps) == 1
        step = run.steps[0]
        assert step.name == "openai_chat"
        assert step.model_name == live_test_model
        assert step.model_provider == "openai"
        assert step.duration_ms is not None
        assert step.duration_ms > 0

        # Verify result was captured
        assert result is not None
        assert len(result) > 0

        # Verify JSONL was written
        with open(temp_jsonl_path) as f:
            lines = f.readlines()
        assert len(lines) == 1

    @requires_openai_key
    def test_chat_completion_with_error(self, max_tokens: int, temp_jsonl_path: str) -> None:
        """Test that API errors are captured in traces."""
        import openai

        import tracecraft
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun
        from tracecraft.instrumentation.decorators import trace_llm

        runtime = tracecraft.init(console=True, jsonl=True, jsonl_path=temp_jsonl_path)

        @trace_llm(name="openai_chat_error", model="invalid-model-xyz", provider="openai")
        def call_with_invalid_model() -> str:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model="invalid-model-xyz",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""

        run = AgentRun(name="test_openai_error", start_time=datetime.now(UTC))

        with run_context(run), pytest.raises(openai.NotFoundError):
            call_with_invalid_model()

        runtime.end_run(run)

        # Verify error was captured
        assert len(run.steps) == 1
        step = run.steps[0]
        assert step.error is not None
        assert "NotFoundError" in step.error_type or "invalid" in step.error.lower()


@pytest.mark.live
class TestLiveOpenAIStreaming:
    """OpenAI streaming tests."""

    @requires_openai_key
    def test_streaming_chat_completion(self, live_test_model: str, max_tokens: int) -> None:
        """Test streaming chat completion tracing."""
        import openai

        import tracecraft
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun
        from tracecraft.instrumentation.decorators import trace_llm

        tracecraft.init(console=True, jsonl=False)

        @trace_llm(name="openai_stream", model=live_test_model, provider="openai")
        def stream_openai(prompt: str) -> str:
            client = openai.OpenAI()
            stream = client.chat.completions.create(
                model=live_test_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                stream=True,
            )
            chunks = []
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    chunks.append(chunk.choices[0].delta.content)
            return "".join(chunks)

        run = AgentRun(name="test_streaming", start_time=datetime.now(UTC))

        with run_context(run):
            result = stream_openai("Count from 1 to 5.")

        # Verify streaming worked
        assert result is not None
        assert len(run.steps) == 1
        assert run.steps[0].name == "openai_stream"


@pytest.mark.live
class TestLiveOpenAIAsync:
    """Async OpenAI tests."""

    @requires_openai_key
    @pytest.mark.asyncio
    async def test_async_chat_completion(self, live_test_model: str, max_tokens: int) -> None:
        """Test async chat completion tracing."""
        import openai

        import tracecraft
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun
        from tracecraft.instrumentation.decorators import trace_llm

        tracecraft.init(console=True, jsonl=False)

        @trace_llm(name="openai_async", model=live_test_model, provider="openai")
        async def call_openai_async(prompt: str) -> str:
            client = openai.AsyncOpenAI()
            response = await client.chat.completions.create(
                model=live_test_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""

        run = AgentRun(name="test_async", start_time=datetime.now(UTC))

        with run_context(run):
            result = await call_openai_async("Say 'async works' exactly.")

        # Verify async tracing worked
        assert result is not None
        assert len(run.steps) == 1
        assert run.steps[0].name == "openai_async"


@pytest.mark.live
@pytest.mark.expensive
class TestLiveOpenAIMultipleCalls:
    """Tests with multiple API calls (more expensive)."""

    @requires_openai_key
    def test_nested_llm_calls(self, live_test_model: str, max_tokens: int) -> None:
        """Test nested LLM call tracing."""
        import openai

        import tracecraft
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun
        from tracecraft.instrumentation.decorators import trace_agent, trace_llm

        runtime = tracecraft.init(console=True, jsonl=False)

        @trace_llm(name="inner_llm", model=live_test_model, provider="openai")
        def inner_call(prompt: str) -> str:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=live_test_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""

        @trace_agent(name="outer_agent")
        def outer_agent(query: str) -> str:
            step1 = inner_call(f"Analyze: {query}")
            step2 = inner_call(f"Summarize: {step1}")
            return step2

        run = AgentRun(name="test_nested", start_time=datetime.now(UTC))

        with run_context(run):
            result = outer_agent("What is 2+2?")

        runtime.end_run(run)

        # Verify result
        assert result is not None

        # Verify nested structure
        assert len(run.steps) == 1
        agent_step = run.steps[0]
        assert agent_step.name == "outer_agent"
        assert len(agent_step.children) == 2
        assert agent_step.children[0].name == "inner_llm"
        assert agent_step.children[1].name == "inner_llm"

        # Verify aggregated metrics
        assert run.total_tokens > 0
