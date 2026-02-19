"""Live tests for auto-instrumentation functionality.

Run with: uv run pytest tests/live/test_live_auto_instrumentation.py -v --live
Requires: OPENAI_API_KEY environment variable

These tests validate that auto-instrumentation works correctly with real API calls,
without using explicit decorators or callback handlers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.live.conftest import requires_openai_key


@pytest.mark.live
class TestOpenAIAutoInstrumentation:
    """Tests for OpenAI auto-instrumentation via init(auto_instrument=["openai"])."""

    @requires_openai_key
    def test_openai_auto_instrumented_sync(
        self, live_test_model: str, max_tokens: int, temp_jsonl_path: str
    ) -> None:
        """Test that OpenAI chat completion is auto-traced without decorators."""
        import openai

        import tracecraft
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        # Initialize with auto-instrumentation for OpenAI
        runtime = tracecraft.init(
            console=True,
            jsonl=True,
            jsonl_path=temp_jsonl_path,
            auto_instrument=["openai"],
        )

        run = AgentRun(name="test_openai_auto", start_time=datetime.now(UTC))

        with run_context(run):
            # No decorators - should be auto-traced
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=live_test_model,
                messages=[{"role": "user", "content": "Say 'auto-instrumentation works' exactly."}],
                max_tokens=max_tokens,
            )
            result = response.choices[0].message.content

        runtime.end_run(run)

        # Verify trace was captured
        assert len(run.steps) >= 1, "No steps captured - auto-instrumentation may not be working"

        # Find LLM step
        llm_steps = [s for s in run.steps if s.type.value == "llm"]
        assert len(llm_steps) >= 1, "No LLM steps found"

        # Verify step has expected attributes
        llm_step = llm_steps[0]
        assert llm_step.model_name is not None or live_test_model in str(llm_step.attributes)
        assert llm_step.duration_ms is not None
        assert llm_step.duration_ms > 0

        # Verify result
        assert result is not None
        assert len(result) > 0

        # Verify JSONL was written
        assert Path(temp_jsonl_path).exists()
        with open(temp_jsonl_path) as f:
            lines = f.readlines()
        assert len(lines) == 1

        runtime.shutdown()

    @pytest.mark.asyncio
    @requires_openai_key
    async def test_openai_auto_instrumented_async(
        self, live_test_model: str, max_tokens: int
    ) -> None:
        """Test async OpenAI is auto-traced."""
        import openai

        import tracecraft
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        runtime = tracecraft.init(
            console=True,
            jsonl=False,
            auto_instrument=["openai"],
        )

        run = AgentRun(name="test_openai_auto_async", start_time=datetime.now(UTC))

        with run_context(run):
            client = openai.AsyncOpenAI()
            response = await client.chat.completions.create(
                model=live_test_model,
                messages=[{"role": "user", "content": "Say 'async auto works' exactly."}],
                max_tokens=max_tokens,
            )
            result = response.choices[0].message.content

        runtime.end_run(run)

        # Verify async tracing worked
        assert result is not None
        assert len(run.steps) >= 1, "No steps captured for async call"

        runtime.shutdown()

    @requires_openai_key
    def test_openai_auto_instrumented_streaming(
        self, live_test_model: str, max_tokens: int
    ) -> None:
        """Test streaming OpenAI is auto-traced."""
        import openai

        import tracecraft
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        runtime = tracecraft.init(
            console=True,
            jsonl=False,
            auto_instrument=["openai"],
        )

        run = AgentRun(name="test_openai_auto_stream", start_time=datetime.now(UTC))

        chunks = []
        with run_context(run):
            client = openai.OpenAI()
            stream = client.chat.completions.create(
                model=live_test_model,
                messages=[{"role": "user", "content": "Count from 1 to 3."}],
                max_tokens=max_tokens,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    chunks.append(chunk.choices[0].delta.content)

        runtime.end_run(run)

        # Verify streaming worked
        assert len(chunks) > 0
        assert len(run.steps) >= 1, "No steps captured for streaming call"

        runtime.shutdown()


@pytest.mark.live
class TestLangChainAutoInstrumentation:
    """Tests for LangChain auto-instrumentation via init(auto_instrument=["langchain"])."""

    @requires_openai_key
    def test_langchain_auto_instrumented_simple(
        self, live_test_model: str, max_tokens: int, temp_jsonl_path: str
    ) -> None:
        """Test that LangChain LLM call is auto-traced without explicit callback handler."""
        pytest.importorskip("langchain_openai")
        from langchain_openai import ChatOpenAI

        import tracecraft
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        # Initialize with auto-instrumentation for LangChain
        runtime = tracecraft.init(
            console=True,
            jsonl=True,
            jsonl_path=temp_jsonl_path,
            auto_instrument=["langchain"],
        )

        run = AgentRun(name="test_langchain_auto", start_time=datetime.now(UTC))

        with run_context(run):
            # No callback handler - should be auto-traced
            llm = ChatOpenAI(model=live_test_model, max_tokens=max_tokens)
            result = llm.invoke("Say 'LangChain auto works' exactly.")

        runtime.end_run(run)

        # Verify trace captured
        assert len(run.steps) >= 1, (
            "No steps captured - LangChain auto-instrumentation may not work"
        )

        # Find LLM step
        llm_steps = [s for s in run.steps if s.type.value == "llm"]
        assert len(llm_steps) >= 1, "No LLM steps found"

        # Verify result
        assert result.content is not None

        # Verify JSONL written
        assert Path(temp_jsonl_path).exists()

        runtime.shutdown()

    @requires_openai_key
    def test_langchain_auto_instrumented_chain(self, live_test_model: str, max_tokens: int) -> None:
        """Test LangChain chain (prompt | llm) is auto-traced."""
        pytest.importorskip("langchain_openai")
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI

        import tracecraft
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        runtime = tracecraft.init(
            console=True,
            jsonl=False,
            auto_instrument=["langchain"],
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "You are a helpful assistant. Be very concise."),
                ("human", "{input}"),
            ]
        )
        llm = ChatOpenAI(model=live_test_model, max_tokens=max_tokens)
        chain = prompt | llm

        run = AgentRun(name="test_langchain_chain_auto", start_time=datetime.now(UTC))

        with run_context(run):
            # No callback - should auto-trace the chain
            result = chain.invoke({"input": "What is 2+2? Answer with just the number."})

        runtime.end_run(run)

        # Verify chain was traced
        assert len(run.steps) >= 1, "No steps captured for chain"
        assert result.content is not None

        runtime.shutdown()

    @requires_openai_key
    def test_langchain_auto_instrumented_with_tools(
        self, live_test_model: str, max_tokens: int
    ) -> None:
        """Test LangChain with tools is auto-traced."""
        pytest.importorskip("langchain_openai")
        from langchain_core.tools import tool
        from langchain_openai import ChatOpenAI

        import tracecraft
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        runtime = tracecraft.init(
            console=True,
            jsonl=False,
            auto_instrument=["langchain"],
        )

        @tool
        def multiply(a: int, b: int) -> int:
            """Multiply two numbers together."""
            return a * b

        llm = ChatOpenAI(model=live_test_model, max_tokens=max_tokens)
        llm_with_tools = llm.bind_tools([multiply])

        run = AgentRun(name="test_langchain_tools_auto", start_time=datetime.now(UTC))

        with run_context(run):
            result = llm_with_tools.invoke("What is 15 times 7?")

        runtime.end_run(run)

        # Verify LLM was called and traced
        assert len(run.steps) >= 1
        assert result is not None

        runtime.shutdown()


@pytest.mark.live
class TestLangGraphAutoInstrumentation:
    """Tests for LangGraph auto-instrumentation."""

    @requires_openai_key
    def test_langgraph_auto_instrumented(self, live_test_model: str, max_tokens: int) -> None:
        """Test that LangGraph StateGraph is auto-traced."""
        pytest.importorskip("langgraph")
        pytest.importorskip("langchain_openai")
        from langchain_openai import ChatOpenAI
        from langgraph.graph import END, StateGraph
        from typing_extensions import TypedDict

        import tracecraft
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        # Initialize with auto-instrumentation for LangChain (covers LangGraph)
        runtime = tracecraft.init(
            console=True,
            jsonl=False,
            auto_instrument=["langchain"],
        )

        # Define state
        class State(TypedDict):
            messages: list[str]
            response: str

        # Create LLM
        llm = ChatOpenAI(model=live_test_model, max_tokens=max_tokens)

        # Define nodes
        def process_node(state: State) -> State:
            messages = state["messages"]
            response = llm.invoke(messages[-1])
            return {"messages": messages, "response": response.content or ""}

        # Build graph
        graph = StateGraph(State)
        graph.add_node("process", process_node)
        graph.set_entry_point("process")
        graph.add_edge("process", END)
        compiled = graph.compile()

        run = AgentRun(name="test_langgraph_auto", start_time=datetime.now(UTC))

        with run_context(run):
            result = compiled.invoke(
                {"messages": ["Say 'LangGraph works' exactly."], "response": ""}
            )

        runtime.end_run(run)

        # Verify graph execution was traced
        assert len(run.steps) >= 1, "No steps captured for LangGraph"
        assert result["response"] is not None

        runtime.shutdown()


@pytest.mark.live
class TestLlamaIndexAutoInstrumentation:
    """Tests for LlamaIndex auto-instrumentation."""

    @requires_openai_key
    def test_llamaindex_auto_instrumented_simple(
        self, live_test_model: str, max_tokens: int, temp_jsonl_path: str
    ) -> None:
        """Test that LlamaIndex LLM call is auto-traced."""
        pytest.importorskip("llama_index.core")
        pytest.importorskip("llama_index.llms.openai")
        from llama_index.core.llms import ChatMessage
        from llama_index.llms.openai import OpenAI

        import tracecraft
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        # Initialize with auto-instrumentation for LlamaIndex
        runtime = tracecraft.init(
            console=True,
            jsonl=True,
            jsonl_path=temp_jsonl_path,
            auto_instrument=["llamaindex"],
        )

        run = AgentRun(name="test_llamaindex_auto", start_time=datetime.now(UTC))

        with run_context(run):
            # No span handler - should be auto-traced
            llm = OpenAI(model=live_test_model, max_tokens=max_tokens)
            response = llm.chat([ChatMessage(role="user", content="Say 'LlamaIndex auto works'.")])
            result = response.message.content

        runtime.end_run(run)

        # Verify trace captured
        assert len(run.steps) >= 1, (
            "No steps captured - LlamaIndex auto-instrumentation may not work"
        )
        assert result is not None

        # Verify JSONL written
        assert Path(temp_jsonl_path).exists()

        runtime.shutdown()


@pytest.mark.live
class TestMultiProviderAutoInstrumentation:
    """Tests for auto-instrumenting multiple providers at once."""

    @requires_openai_key
    def test_all_providers_auto_instrumented(
        self, live_test_model: str, max_tokens: int, temp_jsonl_path: str
    ) -> None:
        """Test that all providers can be auto-instrumented together."""
        import openai

        import tracecraft
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        # Initialize with all auto-instrumentation
        runtime = tracecraft.init(
            console=True,
            jsonl=True,
            jsonl_path=temp_jsonl_path,
            auto_instrument=True,  # Enable all
        )

        run = AgentRun(name="test_all_auto", start_time=datetime.now(UTC))

        with run_context(run):
            # Make an OpenAI call
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=live_test_model,
                messages=[{"role": "user", "content": "Say 'all providers work' exactly."}],
                max_tokens=max_tokens,
            )
            result = response.choices[0].message.content

        runtime.end_run(run)

        # Verify trace captured
        assert len(run.steps) >= 1, "No steps captured with auto_instrument=True"
        assert result is not None

        runtime.shutdown()

    @requires_openai_key
    def test_env_var_auto_instrumentation(
        self, live_test_model: str, max_tokens: int, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test TRACECRAFT_AUTO_INSTRUMENT env var works."""
        import openai

        import tracecraft
        from tracecraft.core import runtime as rt
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        # Reset runtime
        rt._runtime = None

        # Set env var
        monkeypatch.setenv("TRACECRAFT_AUTO_INSTRUMENT", "openai")

        # Initialize without explicit auto_instrument (should use env var)
        runtime = tracecraft.init(console=True, jsonl=False)

        run = AgentRun(name="test_env_auto", start_time=datetime.now(UTC))

        with run_context(run):
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=live_test_model,
                messages=[{"role": "user", "content": "Say 'env var works' exactly."}],
                max_tokens=max_tokens,
            )
            result = response.choices[0].message.content

        runtime.end_run(run)

        # Verify trace captured via env var config
        assert len(run.steps) >= 1, "No steps captured with TRACECRAFT_AUTO_INSTRUMENT env var"
        assert result is not None

        runtime.shutdown()


@pytest.mark.live
class TestSQLiteStorage:
    """Tests for auto-instrumentation with SQLite storage."""

    @requires_openai_key
    def test_auto_instrumented_to_sqlite(
        self, live_test_model: str, max_tokens: int, tmp_path: Path
    ) -> None:
        """Test that auto-instrumented traces are saved to SQLite correctly."""
        import openai

        import tracecraft
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun
        from tracecraft.storage.sqlite import SQLiteTraceStore

        sqlite_path = tmp_path / "test_traces.db"

        # Initialize with auto-instrumentation
        runtime = tracecraft.init(
            console=True,
            jsonl=False,
            auto_instrument=["openai"],
        )

        # Create SQLite store manually for this test
        store = SQLiteTraceStore(str(sqlite_path))

        run = AgentRun(name="test_sqlite_auto", start_time=datetime.now(UTC))

        with run_context(run):
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=live_test_model,
                messages=[{"role": "user", "content": "Say 'SQLite works' exactly."}],
                max_tokens=max_tokens,
            )
            result = response.choices[0].message.content

        runtime.end_run(run)

        # Save to SQLite
        store.save(run)

        # Verify trace can be retrieved
        traces = store.list_all(limit=10)
        assert len(traces) >= 1, "No traces saved to SQLite"

        # Verify trace has steps
        saved_run = store.get(str(run.id))
        assert saved_run is not None
        assert len(saved_run.steps) >= 1, "Steps not saved to SQLite"

        store.close()
        runtime.shutdown()
