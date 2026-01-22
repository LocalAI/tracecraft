"""Live tests for OTLP export integration.

Run with: uv run pytest tests/live/test_live_otlp.py -v --live
Requires: OTEL_EXPORTER_OTLP_ENDPOINT environment variable
          A running OTLP collector (Jaeger, Grafana Tempo, etc.)
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest

from tests.live.conftest import requires_openai_key, requires_otlp_endpoint


@pytest.mark.live
class TestLiveOTLPBasic:
    """Basic OTLP export tests."""

    @requires_otlp_endpoint
    def test_otlp_export_simple_run(self, otlp_endpoint: str) -> None:
        """Test that a simple run exports to OTLP collector."""
        import agenttrace
        from agenttrace.core.context import run_context
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_agent, trace_tool

        runtime = agenttrace.init(
            console=True,
            jsonl=False,
            otlp=True,
            otlp_endpoint=otlp_endpoint,
        )

        @trace_tool(name="simple_tool")
        def simple_tool(x: int) -> int:
            return x * 2

        @trace_agent(name="simple_agent")
        def simple_agent(value: int) -> int:
            return simple_tool(value)

        run = AgentRun(name="test_otlp_export", start_time=datetime.now(UTC))

        with run_context(run):
            result = simple_agent(21)

        runtime.end_run(run)

        # Give OTLP exporter time to flush
        time.sleep(1)

        # Verify run completed
        assert result == 42
        assert len(run.steps) == 1
        assert run.steps[0].name == "simple_agent"
        assert len(run.steps[0].children) == 1
        assert run.steps[0].children[0].name == "simple_tool"

    @requires_otlp_endpoint
    @requires_openai_key
    def test_otlp_export_with_llm_call(
        self, live_test_model: str, max_tokens: int, otlp_endpoint: str
    ) -> None:
        """Test OTLP export with real LLM call."""
        import openai

        import agenttrace
        from agenttrace.core.context import run_context
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_llm

        runtime = agenttrace.init(
            console=True,
            jsonl=False,
            otlp=True,
            otlp_endpoint=otlp_endpoint,
        )

        @trace_llm(name="openai_call", model=live_test_model, provider="openai")
        def call_openai(prompt: str) -> str:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=live_test_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""

        run = AgentRun(name="test_otlp_llm", start_time=datetime.now(UTC))

        with run_context(run):
            result = call_openai("Say 'OTLP works' exactly.")

        runtime.end_run(run)

        # Give OTLP exporter time to flush
        time.sleep(1)

        # Verify LLM call completed
        assert result is not None
        assert len(run.steps) == 1
        assert run.steps[0].model_name == live_test_model


@pytest.mark.live
class TestLiveOTLPSchemaDialects:
    """Test OTLP export with different schema dialects."""

    @requires_otlp_endpoint
    def test_otel_genai_dialect(self, otlp_endpoint: str) -> None:
        """Test export with OTel GenAI semantic conventions."""
        import agenttrace
        from agenttrace.core.context import run_context
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_llm

        runtime = agenttrace.init(
            console=True,
            jsonl=False,
            otlp=True,
            otlp_endpoint=otlp_endpoint,
            schema_dialect="otel_genai",
        )

        @trace_llm(name="test_llm", model="test-model", provider="test")
        def mock_llm_call() -> str:
            return "response"

        run = AgentRun(name="test_otel_genai_dialect", start_time=datetime.now(UTC))

        with run_context(run):
            result = mock_llm_call()

        runtime.end_run(run)
        time.sleep(1)

        assert result == "response"
        assert len(run.steps) == 1

    @requires_otlp_endpoint
    def test_openinference_dialect(self, otlp_endpoint: str) -> None:
        """Test export with OpenInference semantic conventions."""
        import agenttrace
        from agenttrace.core.context import run_context
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_llm

        runtime = agenttrace.init(
            console=True,
            jsonl=False,
            otlp=True,
            otlp_endpoint=otlp_endpoint,
            schema_dialect="openinference",
        )

        @trace_llm(name="test_llm", model="test-model", provider="test")
        def mock_llm_call() -> str:
            return "response"

        run = AgentRun(name="test_openinference_dialect", start_time=datetime.now(UTC))

        with run_context(run):
            result = mock_llm_call()

        runtime.end_run(run)
        time.sleep(1)

        assert result == "response"
        assert len(run.steps) == 1

    @requires_otlp_endpoint
    def test_both_dialects(self, otlp_endpoint: str) -> None:
        """Test export with both schema dialects."""
        import agenttrace
        from agenttrace.core.context import run_context
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_llm

        runtime = agenttrace.init(
            console=True,
            jsonl=False,
            otlp=True,
            otlp_endpoint=otlp_endpoint,
            schema_dialect="both",
        )

        @trace_llm(name="test_llm", model="test-model", provider="test")
        def mock_llm_call() -> str:
            return "response"

        run = AgentRun(name="test_both_dialects", start_time=datetime.now(UTC))

        with run_context(run):
            result = mock_llm_call()

        runtime.end_run(run)
        time.sleep(1)

        assert result == "response"


@pytest.mark.live
class TestLiveOTLPHierarchy:
    """Test OTLP export maintains correct span hierarchy."""

    @requires_otlp_endpoint
    def test_nested_spans_hierarchy(self, otlp_endpoint: str) -> None:
        """Test that nested spans maintain correct parent-child relationships."""
        import agenttrace
        from agenttrace.core.context import run_context
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_agent, trace_tool

        runtime = agenttrace.init(
            console=True,
            jsonl=False,
            otlp=True,
            otlp_endpoint=otlp_endpoint,
        )

        @trace_tool(name="inner_tool")
        def inner_tool() -> str:
            return "inner"

        @trace_agent(name="middle_agent")
        def middle_agent() -> str:
            return inner_tool() + "_middle"

        @trace_agent(name="outer_agent")
        def outer_agent() -> str:
            return middle_agent() + "_outer"

        run = AgentRun(name="test_hierarchy", start_time=datetime.now(UTC))

        with run_context(run):
            result = outer_agent()

        runtime.end_run(run)
        time.sleep(1)

        # Verify hierarchy
        assert result == "inner_middle_outer"
        assert len(run.steps) == 1
        outer = run.steps[0]
        assert outer.name == "outer_agent"
        assert len(outer.children) == 1
        middle = outer.children[0]
        assert middle.name == "middle_agent"
        assert len(middle.children) == 1
        inner = middle.children[0]
        assert inner.name == "inner_tool"


@pytest.mark.live
@pytest.mark.expensive
class TestLiveOTLPComplex:
    """Complex OTLP export tests with real LLM calls."""

    @requires_otlp_endpoint
    @requires_openai_key
    def test_full_agent_workflow_export(
        self, live_test_model: str, max_tokens: int, otlp_endpoint: str
    ) -> None:
        """Test exporting a complete agent workflow with tools."""
        import openai

        import agenttrace
        from agenttrace.core.context import run_context
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_agent, trace_llm, trace_tool

        runtime = agenttrace.init(
            console=True,
            jsonl=False,
            otlp=True,
            otlp_endpoint=otlp_endpoint,
        )

        @trace_tool(name="calculator")
        def calculator(expression: str) -> str:
            try:
                return str(eval(expression))  # noqa: S307
            except Exception as e:
                return f"Error: {e}"

        @trace_llm(name="planner_llm", model=live_test_model, provider="openai")
        def planner_llm(prompt: str) -> str:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=live_test_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""

        @trace_agent(name="math_agent")
        def math_agent(question: str) -> str:
            # Plan
            plan = planner_llm(f"Extract the math expression from: {question}")
            # Execute
            result = calculator("5 + 3")  # Simplified
            return f"Plan: {plan[:20]}... Result: {result}"

        run = AgentRun(name="test_full_workflow", start_time=datetime.now(UTC))

        with run_context(run):
            result = math_agent("What is 5 + 3?")

        runtime.end_run(run)
        time.sleep(2)  # Extra time for complex workflow

        # Verify workflow completed
        assert "8" in result
        assert len(run.steps) == 1
        agent_step = run.steps[0]
        assert agent_step.name == "math_agent"
        assert len(agent_step.children) == 2  # LLM + Tool

    @requires_otlp_endpoint
    @requires_openai_key
    def test_concurrent_traces_export(
        self, live_test_model: str, max_tokens: int, otlp_endpoint: str
    ) -> None:
        """Test exporting traces from concurrent operations."""
        import asyncio

        import openai

        import agenttrace
        from agenttrace.core.context import run_context
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_llm

        runtime = agenttrace.init(
            console=True,
            jsonl=False,
            otlp=True,
            otlp_endpoint=otlp_endpoint,
        )

        @trace_llm(name="async_llm", model=live_test_model, provider="openai")
        async def async_llm_call(prompt: str) -> str:
            client = openai.AsyncOpenAI()
            response = await client.chat.completions.create(
                model=live_test_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""

        async def run_concurrent() -> list[str]:
            run = AgentRun(name="test_concurrent", start_time=datetime.now(UTC))
            with run_context(run):
                tasks = [
                    async_llm_call("Say 'A'"),
                    async_llm_call("Say 'B'"),
                    async_llm_call("Say 'C'"),
                ]
                results = await asyncio.gather(*tasks)
            runtime.end_run(run)
            return results

        results = asyncio.run(run_concurrent())
        time.sleep(2)

        # Verify all calls completed
        assert len(results) == 3
        for r in results:
            assert r is not None
