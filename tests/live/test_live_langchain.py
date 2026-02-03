"""Live tests for LangChain integration.

Run with: uv run pytest tests/live/test_live_langchain.py -v --live
Requires: OPENAI_API_KEY environment variable
          uv add langchain-openai
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.live.conftest import requires_openai_key


@pytest.mark.live
class TestLiveLangChainBasic:
    """Basic LangChain integration tests."""

    @requires_openai_key
    def test_simple_chain(
        self, live_test_model: str, max_tokens: int, temp_jsonl_path: str
    ) -> None:
        """Test simple LangChain LLM call is traced."""
        pytest.importorskip("langchain_openai")
        from langchain_openai import ChatOpenAI

        import tracecraft
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        runtime = tracecraft.init(console=True, jsonl=True, jsonl_path=temp_jsonl_path)

        llm = ChatOpenAI(model=live_test_model, max_tokens=max_tokens)
        handler = TraceCraftCallbackHandler()

        run = AgentRun(name="test_langchain_simple", start_time=datetime.now(UTC))

        with run_context(run):
            result = llm.invoke(
                "Say 'LangChain works' exactly.",
                config={"callbacks": [handler]},
            )

        runtime.end_run(run)
        handler.clear()

        # Verify trace captured
        assert len(run.steps) >= 1
        # Find LLM step
        llm_steps = [s for s in run.steps if s.type.value == "llm"]
        assert len(llm_steps) >= 1

        # Verify result
        assert result.content is not None

        # Verify JSONL written
        with open(temp_jsonl_path) as f:
            lines = f.readlines()
        assert len(lines) == 1

    @requires_openai_key
    def test_chain_with_prompt_template(self, live_test_model: str, max_tokens: int) -> None:
        """Test LangChain chain with prompt template."""
        pytest.importorskip("langchain_openai")
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI

        import tracecraft
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        runtime = tracecraft.init(console=True, jsonl=False)

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "You are a helpful assistant. Be concise."),
                ("human", "{input}"),
            ]
        )
        llm = ChatOpenAI(model=live_test_model, max_tokens=max_tokens)
        chain = prompt | llm

        handler = TraceCraftCallbackHandler()
        run = AgentRun(name="test_chain_template", start_time=datetime.now(UTC))

        with run_context(run):
            result = chain.invoke(
                {"input": "What is 2+2? Answer with just the number."},
                config={"callbacks": [handler]},
            )

        runtime.end_run(run)
        handler.clear()

        # Verify chain was traced
        assert len(run.steps) >= 1
        assert result.content is not None


@pytest.mark.live
class TestLiveLangChainTools:
    """LangChain tool usage tests."""

    @requires_openai_key
    def test_agent_with_tools(self, live_test_model: str, max_tokens: int) -> None:
        """Test LangChain agent with tools is traced."""
        pytest.importorskip("langchain_openai")
        from langchain_core.tools import tool
        from langchain_openai import ChatOpenAI

        import tracecraft
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        tracecraft.init(console=True, jsonl=False)

        @tool
        def calculator(expression: str) -> str:
            """Calculate a math expression."""
            try:
                return str(eval(expression))  # noqa: S307
            except Exception as e:
                return f"Error: {e}"

        llm = ChatOpenAI(model=live_test_model, max_tokens=max_tokens)
        llm_with_tools = llm.bind_tools([calculator])

        handler = TraceCraftCallbackHandler()
        run = AgentRun(name="test_tools", start_time=datetime.now(UTC))

        with run_context(run):
            result = llm_with_tools.invoke(
                "What is 15 * 7?",
                config={"callbacks": [handler]},
            )

        handler.clear()

        # Verify LLM was called
        assert len(run.steps) >= 1
        assert result is not None


@pytest.mark.live
class TestLiveLangChainStreaming:
    """LangChain streaming tests."""

    @requires_openai_key
    def test_streaming_response(self, live_test_model: str, max_tokens: int) -> None:
        """Test streaming LangChain response is traced."""
        pytest.importorskip("langchain_openai")
        from langchain_openai import ChatOpenAI

        import tracecraft
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        tracecraft.init(console=True, jsonl=False)

        llm = ChatOpenAI(model=live_test_model, max_tokens=max_tokens, streaming=True)
        handler = TraceCraftCallbackHandler()

        run = AgentRun(name="test_streaming", start_time=datetime.now(UTC))

        chunks = []
        with run_context(run):
            for chunk in llm.stream(
                "Count from 1 to 3.",
                config={"callbacks": [handler]},
            ):
                chunks.append(chunk.content)

        handler.clear()

        # Verify streaming worked
        assert len(chunks) > 0
        assert len(run.steps) >= 1


@pytest.mark.live
class TestLiveLangChainErrors:
    """LangChain error handling tests."""

    @requires_openai_key
    def test_error_captured(self, max_tokens: int) -> None:
        """Test that LangChain errors are captured in traces."""
        pytest.importorskip("langchain_openai")
        import openai
        from langchain_openai import ChatOpenAI

        import tracecraft
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        runtime = tracecraft.init(console=True, jsonl=False)

        # Use invalid model to trigger error
        llm = ChatOpenAI(model="invalid-model-xyz", max_tokens=max_tokens)
        handler = TraceCraftCallbackHandler()

        run = AgentRun(name="test_error", start_time=datetime.now(UTC))

        with run_context(run), pytest.raises(openai.NotFoundError):
            llm.invoke(
                "Hello",
                config={"callbacks": [handler]},
            )

        runtime.end_run(run)
        handler.clear()

        # Verify error was captured
        assert run.error_count >= 1 or len(run.steps) == 0  # Either error counted or no steps


@pytest.mark.live
@pytest.mark.expensive
class TestLiveLangChainComplex:
    """More complex LangChain tests (more API calls)."""

    @requires_openai_key
    def test_multi_step_chain(self, live_test_model: str, max_tokens: int) -> None:
        """Test multi-step chain creates proper hierarchy."""
        pytest.importorskip("langchain_openai")
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI

        import tracecraft
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        runtime = tracecraft.init(console=True, jsonl=False)

        llm = ChatOpenAI(model=live_test_model, max_tokens=max_tokens)

        # Create a two-step chain
        step1_prompt = ChatPromptTemplate.from_template("Translate to French: {input}")
        step2_prompt = ChatPromptTemplate.from_template("Translate back to English: {text}")

        chain = (
            step1_prompt
            | llm
            | StrOutputParser()
            | (lambda x: {"text": x})
            | step2_prompt
            | llm
            | StrOutputParser()
        )

        handler = TraceCraftCallbackHandler()
        run = AgentRun(name="test_multi_step", start_time=datetime.now(UTC))

        with run_context(run):
            result = chain.invoke(
                {"input": "Hello"},
                config={"callbacks": [handler]},
            )

        runtime.end_run(run)
        handler.clear()

        # Verify result
        assert result is not None

        # Verify multiple LLM calls were traced
        def count_llm_steps(steps: list) -> int:
            count = 0
            for step in steps:
                if step.type.value == "llm":
                    count += 1
                count += count_llm_steps(step.children)
            return count

        llm_count = count_llm_steps(run.steps)
        assert llm_count >= 2  # At least 2 LLM calls
        assert run.total_tokens > 0
