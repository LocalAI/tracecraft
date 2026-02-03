"""Live tests for LlamaIndex integration.

Run with: uv run pytest tests/live/test_live_llamaindex.py -v --live
Requires: OPENAI_API_KEY environment variable
          uv add llama-index-core llama-index-llms-openai
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.live.conftest import requires_openai_key


@pytest.mark.live
class TestLiveLlamaIndexBasic:
    """Basic LlamaIndex integration tests."""

    @requires_openai_key
    def test_simple_llm_call(
        self, live_test_model: str, max_tokens: int, temp_jsonl_path: str
    ) -> None:
        """Test simple LlamaIndex LLM call is traced."""
        pytest.importorskip("llama_index.core")
        pytest.importorskip("llama_index.llms.openai")

        from llama_index.core import Settings
        from llama_index.core.callbacks import CallbackManager
        from llama_index.llms.openai import OpenAI

        import tracecraft
        from tracecraft.adapters.llamaindex import TraceCraftSpanHandler
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        runtime = tracecraft.init(console=True, jsonl=True, jsonl_path=temp_jsonl_path)

        # Configure LlamaIndex
        handler = TraceCraftSpanHandler()
        Settings.callback_manager = CallbackManager(handlers=[handler])
        llm = OpenAI(model=live_test_model, max_tokens=max_tokens)

        run = AgentRun(name="test_llamaindex_simple", start_time=datetime.now(UTC))

        with run_context(run):
            response = llm.complete("Say 'LlamaIndex works' exactly.")

        runtime.end_run(run)
        handler.clear()

        # Verify trace captured
        assert len(run.steps) >= 1
        assert response.text is not None

        # Verify JSONL written
        with open(temp_jsonl_path) as f:
            lines = f.readlines()
        assert len(lines) == 1

    @requires_openai_key
    def test_chat_completion(self, live_test_model: str, max_tokens: int) -> None:
        """Test LlamaIndex chat completion is traced."""
        pytest.importorskip("llama_index.core")
        pytest.importorskip("llama_index.llms.openai")

        from llama_index.core import Settings
        from llama_index.core.callbacks import CallbackManager
        from llama_index.core.llms import ChatMessage
        from llama_index.llms.openai import OpenAI

        import tracecraft
        from tracecraft.adapters.llamaindex import TraceCraftSpanHandler
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        tracecraft.init(console=True, jsonl=False)

        handler = TraceCraftSpanHandler()
        Settings.callback_manager = CallbackManager(handlers=[handler])
        llm = OpenAI(model=live_test_model, max_tokens=max_tokens)

        messages = [
            ChatMessage(role="system", content="You are a helpful assistant."),
            ChatMessage(role="user", content="What is 2+2?"),
        ]

        run = AgentRun(name="test_chat", start_time=datetime.now(UTC))

        with run_context(run):
            response = llm.chat(messages)

        handler.clear()

        # Verify chat worked
        assert response.message.content is not None
        assert len(run.steps) >= 1


@pytest.mark.live
class TestLiveLlamaIndexIndex:
    """LlamaIndex indexing and query tests."""

    @requires_openai_key
    def test_simple_index_query(self, live_test_model: str, max_tokens: int) -> None:
        """Test LlamaIndex index and query is traced."""
        pytest.importorskip("llama_index.core")
        pytest.importorskip("llama_index.llms.openai")

        from llama_index.core import Document, Settings, VectorStoreIndex
        from llama_index.core.callbacks import CallbackManager
        from llama_index.llms.openai import OpenAI

        import tracecraft
        from tracecraft.adapters.llamaindex import TraceCraftSpanHandler
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        runtime = tracecraft.init(console=True, jsonl=False)

        handler = TraceCraftSpanHandler()
        Settings.callback_manager = CallbackManager(handlers=[handler])
        Settings.llm = OpenAI(model=live_test_model, max_tokens=max_tokens)
        Settings.chunk_size = 256

        # Create a simple index
        documents = [
            Document(text="The capital of France is Paris."),
            Document(text="The capital of Germany is Berlin."),
            Document(text="The capital of Italy is Rome."),
        ]

        run = AgentRun(name="test_index_query", start_time=datetime.now(UTC))

        with run_context(run):
            index = VectorStoreIndex.from_documents(documents)
            query_engine = index.as_query_engine()
            response = query_engine.query("What is the capital of France?")

        runtime.end_run(run)
        handler.clear()

        # Verify query returned result
        assert response.response is not None
        assert "Paris" in str(response.response)

        # Verify trace captured multiple steps (embedding, retrieval, LLM)
        assert len(run.steps) >= 1


@pytest.mark.live
class TestLiveLlamaIndexStreaming:
    """LlamaIndex streaming tests."""

    @requires_openai_key
    def test_streaming_completion(self, live_test_model: str, max_tokens: int) -> None:
        """Test streaming LlamaIndex completion is traced."""
        pytest.importorskip("llama_index.core")
        pytest.importorskip("llama_index.llms.openai")

        from llama_index.core import Settings
        from llama_index.core.callbacks import CallbackManager
        from llama_index.llms.openai import OpenAI

        import tracecraft
        from tracecraft.adapters.llamaindex import TraceCraftSpanHandler
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        tracecraft.init(console=True, jsonl=False)

        handler = TraceCraftSpanHandler()
        Settings.callback_manager = CallbackManager(handlers=[handler])
        llm = OpenAI(model=live_test_model, max_tokens=max_tokens)

        run = AgentRun(name="test_streaming", start_time=datetime.now(UTC))

        chunks = []
        with run_context(run):
            stream = llm.stream_complete("Count from 1 to 3.")
            for chunk in stream:
                chunks.append(chunk.text)

        handler.clear()

        # Verify streaming worked
        assert len(chunks) > 0
        full_response = "".join(chunks)
        assert len(full_response) > 0


@pytest.mark.live
@pytest.mark.expensive
class TestLiveLlamaIndexComplex:
    """More complex LlamaIndex tests."""

    @requires_openai_key
    def test_query_with_retrieval_tracing(self, live_test_model: str, max_tokens: int) -> None:
        """Test that retrieval steps are captured in trace."""
        pytest.importorskip("llama_index.core")
        pytest.importorskip("llama_index.llms.openai")

        from llama_index.core import Document, Settings, VectorStoreIndex
        from llama_index.core.callbacks import CallbackManager
        from llama_index.llms.openai import OpenAI

        import tracecraft
        from tracecraft.adapters.llamaindex import TraceCraftSpanHandler
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun, StepType

        runtime = tracecraft.init(console=True, jsonl=False)

        handler = TraceCraftSpanHandler()
        Settings.callback_manager = CallbackManager(handlers=[handler])
        Settings.llm = OpenAI(model=live_test_model, max_tokens=max_tokens)

        documents = [
            Document(text="TraceCraft is a vendor-neutral observability SDK."),
            Document(text="TraceCraft supports LangChain, LlamaIndex, and PydanticAI."),
        ]

        run = AgentRun(name="test_retrieval_trace", start_time=datetime.now(UTC))

        with run_context(run):
            index = VectorStoreIndex.from_documents(documents)
            query_engine = index.as_query_engine()
            response = query_engine.query("What frameworks does TraceCraft support?")

        runtime.end_run(run)
        handler.clear()

        # Verify response
        assert response.response is not None

        # Helper to find step types
        def find_step_types(steps: list) -> set:
            types = set()
            for step in steps:
                types.add(step.type)
                types.update(find_step_types(step.children))
            return types

        step_types = find_step_types(run.steps)

        # Verify we have LLM steps at minimum
        assert StepType.LLM in step_types or StepType.WORKFLOW in step_types
        assert run.total_tokens > 0
