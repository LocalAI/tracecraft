"""Full pipeline end-to-end live tests.

Run with: uv run pytest tests/live/test_live_full_pipeline.py -v --live
Requires: OPENAI_API_KEY environment variable

These tests verify the complete TraceCraft pipeline from instrumentation
through processing to export.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from tests.live.conftest import requires_openai_key


@pytest.mark.live
class TestLiveFullPipelineBasic:
    """Basic end-to-end pipeline tests."""

    @requires_openai_key
    def test_complete_pipeline_console_jsonl(
        self, live_test_model: str, max_tokens: int, temp_jsonl_path: str
    ) -> None:
        """Test complete pipeline: instrumentation → processing → console + JSONL export."""
        import openai

        import tracecraft
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun
        from tracecraft.instrumentation.decorators import trace_agent, trace_llm, trace_tool

        # Initialize with all local exporters
        runtime = tracecraft.init(
            console=True,
            jsonl=True,
            jsonl_path=temp_jsonl_path,
        )

        @trace_tool(name="calculator")
        def calculator(expression: str) -> str:
            """Calculate a math expression."""
            try:
                return str(eval(expression))  # noqa: S307
            except Exception as e:
                return f"Error: {e}"

        @trace_llm(name="reasoning_llm", model=live_test_model, provider="openai")
        def reasoning_llm(prompt: str) -> str:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=live_test_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""

        @trace_agent(name="math_tutor")
        def math_tutor(question: str) -> str:
            # Get explanation from LLM
            explanation = reasoning_llm(f"Briefly explain how to solve: {question}")
            # Calculate the answer
            result = calculator("7 * 6")
            return f"{explanation}\n\nAnswer: {result}"

        run = AgentRun(name="math_tutor_session", start_time=datetime.now(UTC))

        with run_context(run):
            result = math_tutor("What is 7 times 6?")

        runtime.end_run(run)

        # Verify result
        assert "42" in result
        assert len(run.steps) == 1

        # Verify hierarchy
        agent_step = run.steps[0]
        assert agent_step.name == "math_tutor"
        assert len(agent_step.children) == 2

        llm_step = agent_step.children[0]
        assert llm_step.name == "reasoning_llm"
        assert llm_step.model_name == live_test_model

        tool_step = agent_step.children[1]
        assert tool_step.name == "calculator"

        # Verify JSONL export
        with open(temp_jsonl_path) as f:
            lines = f.readlines()
        assert len(lines) == 1

        exported_run = json.loads(lines[0])
        assert exported_run["name"] == "math_tutor_session"
        assert len(exported_run["steps"]) == 1

    @requires_openai_key
    def test_pipeline_with_redaction(
        self, live_test_model: str, max_tokens: int, temp_jsonl_path: str
    ) -> None:
        """Test pipeline with PII redaction enabled."""
        import openai

        import tracecraft
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun
        from tracecraft.instrumentation.decorators import trace_llm

        # Initialize with redaction
        runtime = tracecraft.init(
            console=True,
            jsonl=True,
            jsonl_path=temp_jsonl_path,
            redact_pii=True,
        )

        @trace_llm(name="support_llm", model=live_test_model, provider="openai")
        def support_llm(prompt: str) -> str:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=live_test_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""

        run = AgentRun(name="support_session", start_time=datetime.now(UTC))

        # Include PII in the prompt (email)
        with run_context(run):
            result = support_llm("My email is test@example.com. Say 'received' exactly.")

        runtime.end_run(run)

        # Verify response
        assert result is not None

        # Note: Redaction is applied at export time
        # The actual redaction verification would require checking the exported JSONL

    @requires_openai_key
    def test_pipeline_error_handling(self, max_tokens: int, temp_jsonl_path: str) -> None:
        """Test pipeline correctly captures and exports errors."""
        import openai

        import tracecraft
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun
        from tracecraft.instrumentation.decorators import trace_llm

        runtime = tracecraft.init(
            console=True,
            jsonl=True,
            jsonl_path=temp_jsonl_path,
        )

        @trace_llm(name="error_llm", model="invalid-model-xyz", provider="openai")
        def error_llm() -> str:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model="invalid-model-xyz",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""

        run = AgentRun(name="error_session", start_time=datetime.now(UTC))

        with run_context(run), pytest.raises(openai.NotFoundError):
            error_llm()

        runtime.end_run(run)

        # Verify error was captured
        assert len(run.steps) == 1
        error_step = run.steps[0]
        assert error_step.error is not None
        assert error_step.error_type is not None

        # Verify JSONL contains error
        with open(temp_jsonl_path) as f:
            exported = json.loads(f.readline())
        assert exported["steps"][0]["error"] is not None


@pytest.mark.live
class TestLiveFullPipelineAsync:
    """Async pipeline tests."""

    @requires_openai_key
    @pytest.mark.asyncio
    async def test_async_pipeline(
        self, live_test_model: str, max_tokens: int, temp_jsonl_path: str
    ) -> None:
        """Test complete async pipeline."""
        import openai

        import tracecraft
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun
        from tracecraft.instrumentation.decorators import trace_agent, trace_llm

        runtime = tracecraft.init(
            console=True,
            jsonl=True,
            jsonl_path=temp_jsonl_path,
        )

        @trace_llm(name="async_llm", model=live_test_model, provider="openai")
        async def async_llm(prompt: str) -> str:
            client = openai.AsyncOpenAI()
            response = await client.chat.completions.create(
                model=live_test_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""

        @trace_agent(name="async_agent")
        async def async_agent(query: str) -> str:
            result = await async_llm(query)
            return f"Response: {result}"

        run = AgentRun(name="async_session", start_time=datetime.now(UTC))

        with run_context(run):
            result = await async_agent("Say 'async pipeline works' exactly.")

        runtime.end_run(run)

        # Verify async execution
        assert result is not None
        assert len(run.steps) == 1
        assert run.steps[0].name == "async_agent"
        assert len(run.steps[0].children) == 1
        assert run.steps[0].children[0].name == "async_llm"


@pytest.mark.live
class TestLiveFullPipelineMultiFramework:
    """Tests combining multiple framework adapters."""

    @requires_openai_key
    def test_langchain_with_manual_instrumentation(
        self, live_test_model: str, max_tokens: int, temp_jsonl_path: str
    ) -> None:
        """Test combining LangChain adapter with manual decorators."""
        pytest.importorskip("langchain_openai")
        from langchain_openai import ChatOpenAI

        import tracecraft
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun
        from tracecraft.instrumentation.decorators import trace_agent, trace_tool

        runtime = tracecraft.init(
            console=True,
            jsonl=True,
            jsonl_path=temp_jsonl_path,
        )

        @trace_tool(name="manual_tool")
        def manual_tool(x: int) -> int:
            return x * 2

        @trace_agent(name="hybrid_agent")
        def hybrid_agent(_query: str) -> str:
            # Manual tool call
            tool_result = manual_tool(21)

            # LangChain LLM call
            llm = ChatOpenAI(model=live_test_model, max_tokens=max_tokens)
            handler = TraceCraftCallbackHandler()
            response = llm.invoke(
                f"The tool returned {tool_result}. Acknowledge it briefly.",
                config={"callbacks": [handler]},
            )
            handler.clear()

            return str(response.content)

        run = AgentRun(name="hybrid_session", start_time=datetime.now(UTC))

        with run_context(run):
            result = hybrid_agent("Test hybrid approach")

        runtime.end_run(run)

        # Verify both manual and LangChain traces captured
        assert result is not None
        assert len(run.steps) == 1
        agent_step = run.steps[0]
        assert agent_step.name == "hybrid_agent"
        # Should have manual tool + LangChain LLM
        assert len(agent_step.children) >= 2


@pytest.mark.live
class TestLiveFullPipelineHTML:
    """HTML export pipeline tests."""

    @requires_openai_key
    def test_html_export_pipeline(
        self, live_test_model: str, max_tokens: int, temp_html_path: str
    ) -> None:
        """Test complete pipeline with HTML export."""
        import openai

        import tracecraft
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun
        from tracecraft.exporters.html import HTMLExporter
        from tracecraft.instrumentation.decorators import trace_agent, trace_llm

        runtime = tracecraft.init(console=True, jsonl=False)

        @trace_llm(name="chat_llm", model=live_test_model, provider="openai")
        def chat_llm(prompt: str) -> str:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=live_test_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""

        @trace_agent(name="chat_agent")
        def chat_agent(message: str) -> str:
            return chat_llm(message)

        run = AgentRun(name="chat_session", start_time=datetime.now(UTC))

        with run_context(run):
            result = chat_agent("Say 'HTML export works' exactly.")

        runtime.end_run(run)

        # Verify result
        assert result is not None

        # Export to HTML
        html_exporter = HTMLExporter(output_path=temp_html_path)
        html_exporter.export(run)

        # Verify HTML file created
        with open(temp_html_path) as f:
            html_content = f.read()

        assert "<html" in html_content
        assert "chat_session" in html_content
        assert "chat_agent" in html_content


@pytest.mark.live
@pytest.mark.expensive
class TestLiveFullPipelineComplex:
    """Complex end-to-end pipeline tests (more API calls)."""

    @requires_openai_key
    def test_multi_agent_workflow(
        self, live_test_model: str, max_tokens: int, temp_jsonl_path: str
    ) -> None:
        """Test complex multi-agent workflow."""
        import openai

        import tracecraft
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun
        from tracecraft.instrumentation.decorators import trace_agent, trace_llm, trace_tool

        runtime = tracecraft.init(
            console=True,
            jsonl=True,
            jsonl_path=temp_jsonl_path,
        )

        @trace_tool(name="web_search")
        def web_search(query: str) -> str:
            # Mock web search
            return f"Search results for: {query}"

        @trace_tool(name="database_query")
        def database_query(sql: str) -> str:
            # Mock database query
            return f"Result of {sql}: {{'users': 100, 'orders': 500}}"

        @trace_llm(name="analyst_llm", model=live_test_model, provider="openai")
        def analyst_llm(prompt: str) -> str:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=live_test_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""

        @trace_agent(name="research_agent")
        def research_agent(topic: str) -> str:
            search_results = web_search(topic)
            return analyst_llm(f"Summarize: {search_results}")

        @trace_agent(name="data_agent")
        def data_agent(question: str) -> str:
            data = database_query(f"SELECT * FROM stats WHERE topic='{question}'")
            return analyst_llm(f"Analyze: {data}")

        @trace_agent(name="coordinator_agent")
        def coordinator_agent(task: str) -> str:
            research = research_agent(task)
            data = data_agent(task)
            return analyst_llm(f"Combine insights: {research} and {data}")

        run = AgentRun(name="multi_agent_session", start_time=datetime.now(UTC))

        with run_context(run):
            result = coordinator_agent("Analyze user behavior")

        runtime.end_run(run)

        # Verify complex hierarchy
        assert result is not None
        assert len(run.steps) == 1

        coordinator = run.steps[0]
        assert coordinator.name == "coordinator_agent"
        # Should have: research_agent, data_agent, final LLM
        assert len(coordinator.children) == 3

        # Verify nested agents have their own children
        research = coordinator.children[0]
        assert research.name == "research_agent"
        assert len(research.children) == 2  # search + llm

        data = coordinator.children[1]
        assert data.name == "data_agent"
        assert len(data.children) == 2  # db query + llm

        # Verify JSONL captures full hierarchy
        with open(temp_jsonl_path) as f:
            exported = json.loads(f.readline())

        assert exported["name"] == "multi_agent_session"
        assert len(exported["steps"]) == 1

    @requires_openai_key
    def test_pipeline_with_all_features(
        self, live_test_model: str, max_tokens: int, temp_jsonl_path: str
    ) -> None:
        """Test pipeline with all features enabled."""
        import openai

        import tracecraft
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun
        from tracecraft.instrumentation.decorators import trace_agent, trace_llm, trace_tool

        runtime = tracecraft.init(
            console=True,
            jsonl=True,
            jsonl_path=temp_jsonl_path,
            redact_pii=True,
            sampling_rate=1.0,  # 100% sampling for test
        )

        @trace_tool(name="full_test_tool")
        def test_tool(data: str) -> str:
            return f"Processed: {data}"

        @trace_llm(name="full_test_llm", model=live_test_model, provider="openai")
        def test_llm(prompt: str) -> str:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=live_test_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""

        @trace_agent(name="full_test_agent")
        def test_agent(query: str) -> str:
            tool_result = test_tool(query)
            llm_result = test_llm(tool_result)
            return llm_result

        run = AgentRun(name="full_feature_session", start_time=datetime.now(UTC))

        with run_context(run):
            result = test_agent("Test all features")

        runtime.end_run(run)

        # Verify all features worked together
        assert result is not None
        assert len(run.steps) == 1
        assert run.steps[0].name == "full_test_agent"
        assert len(run.steps[0].children) == 2

        # Verify JSONL export
        with open(temp_jsonl_path) as f:
            exported = json.loads(f.readline())
        assert exported["name"] == "full_feature_session"
