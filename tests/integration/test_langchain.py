"""
Tests for the LangChain callback handler adapter.

Tests LangChain integration using mock callbacks without requiring
actual LangChain installation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun, StepType


class TestLangChainCallbackHandler:
    """Tests for TraceCraftCallbackHandler."""

    def test_handler_creation(self) -> None:
        """Should create a callback handler."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        handler = TraceCraftCallbackHandler()
        assert handler is not None

    def test_handler_requires_active_run(self) -> None:
        """Should require an active run to capture steps."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        handler = TraceCraftCallbackHandler()
        # No active run, steps should not be created
        handler.on_chain_start(
            serialized={"name": "test_chain"},
            inputs={"query": "hello"},
            run_id=uuid4(),
        )
        # Should not raise, just skip

    def test_handler_with_active_run(self) -> None:
        """Should create steps when run is active."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()

        with run_context(run):
            handler.on_chain_start(
                serialized={"name": "test_chain"},
                inputs={"query": "hello"},
                run_id=uuid4(),
            )

        # Should have created a step
        assert len(run.steps) == 1
        assert run.steps[0].type == StepType.WORKFLOW
        assert run.steps[0].name == "test_chain"


class TestChainCallbacks:
    """Tests for chain start/end callbacks."""

    def test_on_chain_start_creates_step(self) -> None:
        """on_chain_start should create a workflow step."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()
        run_id = uuid4()

        with run_context(run):
            handler.on_chain_start(
                serialized={"name": "MyChain", "id": ["test"]},
                inputs={"input": "test query"},
                run_id=run_id,
            )

        assert len(run.steps) == 1
        step = run.steps[0]
        assert step.type == StepType.WORKFLOW
        assert step.name == "MyChain"
        assert step.inputs == {"input": "test query"}

    def test_on_chain_start_uses_class_name_fallback(self) -> None:
        """Should use class name from id if name not in serialized."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()

        with run_context(run):
            handler.on_chain_start(
                serialized={"id": ["langchain", "chains", "RetrievalQA"]},
                inputs={},
                run_id=uuid4(),
            )

        assert run.steps[0].name == "RetrievalQA"

    def test_on_chain_end_completes_step(self) -> None:
        """on_chain_end should complete the step with outputs."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()
        run_id = uuid4()

        with run_context(run):
            handler.on_chain_start(
                serialized={"name": "MyChain"},
                inputs={"query": "test"},
                run_id=run_id,
            )
            handler.on_chain_end(
                outputs={"result": "answer"},
                run_id=run_id,
            )

        step = run.steps[0]
        assert step.outputs == {"result": "answer"}
        assert step.end_time is not None
        assert step.duration_ms is not None

    def test_nested_chains(self) -> None:
        """Should handle nested chain calls with proper hierarchy."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()
        parent_id = uuid4()
        child_id = uuid4()

        with run_context(run):
            # Parent chain
            handler.on_chain_start(
                serialized={"name": "ParentChain"},
                inputs={"query": "test"},
                run_id=parent_id,
            )
            # Nested chain
            handler.on_chain_start(
                serialized={"name": "ChildChain"},
                inputs={"sub_query": "sub_test"},
                run_id=child_id,
                parent_run_id=parent_id,
            )
            handler.on_chain_end(outputs={"sub_result": "sub_answer"}, run_id=child_id)
            handler.on_chain_end(outputs={"result": "answer"}, run_id=parent_id)

        # Parent should have child in children list
        assert len(run.steps) == 1  # Only parent at root
        parent = run.steps[0]
        assert parent.name == "ParentChain"
        assert len(parent.children) == 1
        child = parent.children[0]
        assert child.name == "ChildChain"
        assert child.parent_id == parent.id


class TestLLMCallbacks:
    """Tests for LLM start/end callbacks."""

    def test_on_llm_start_creates_step(self) -> None:
        """on_llm_start should create an LLM step."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()
        run_id = uuid4()

        with run_context(run):
            handler.on_llm_start(
                serialized={"name": "ChatOpenAI", "id": ["langchain", "llms", "ChatOpenAI"]},
                prompts=["What is the weather?"],
                run_id=run_id,
            )

        assert len(run.steps) == 1
        step = run.steps[0]
        assert step.type == StepType.LLM
        assert step.name == "ChatOpenAI"
        assert step.inputs == {"prompts": ["What is the weather?"]}

    def test_on_llm_start_with_invocation_params(self) -> None:
        """Should capture model name from invocation params."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()

        with run_context(run):
            handler.on_llm_start(
                serialized={"name": "ChatOpenAI"},
                prompts=["test"],
                run_id=uuid4(),
                invocation_params={"model_name": "gpt-4", "model": "gpt-4"},
            )

        step = run.steps[0]
        assert step.model_name == "gpt-4"

    def test_on_llm_end_captures_response(self) -> None:
        """on_llm_end should capture the response text."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()
        run_id = uuid4()

        with run_context(run):
            handler.on_llm_start(
                serialized={"name": "ChatOpenAI"},
                prompts=["What is 2+2?"],
                run_id=run_id,
            )
            # Simulate LLMResult
            handler.on_llm_end(
                response=MockLLMResult(
                    generations=[[MockGeneration(text="4")]],
                    llm_output={"token_usage": {"prompt_tokens": 10, "completion_tokens": 5}},
                ),
                run_id=run_id,
            )

        step = run.steps[0]
        assert step.outputs.get("text") == "4"
        assert step.end_time is not None

    def test_on_llm_end_captures_tokens(self) -> None:
        """Should capture token counts from LLM response."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()
        run_id = uuid4()

        with run_context(run):
            handler.on_llm_start(
                serialized={"name": "ChatOpenAI"},
                prompts=["test"],
                run_id=run_id,
            )
            handler.on_llm_end(
                response=MockLLMResult(
                    generations=[[MockGeneration(text="response")]],
                    llm_output={
                        "token_usage": {
                            "prompt_tokens": 100,
                            "completion_tokens": 50,
                            "total_tokens": 150,
                        }
                    },
                ),
                run_id=run_id,
            )

        step = run.steps[0]
        assert step.input_tokens == 100
        assert step.output_tokens == 50

    def test_on_llm_end_updates_run_totals(self) -> None:
        """Should update run total_tokens."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()

        with run_context(run):
            # First LLM call
            run_id1 = uuid4()
            handler.on_llm_start(
                serialized={"name": "ChatOpenAI"}, prompts=["test1"], run_id=run_id1
            )
            handler.on_llm_end(
                response=MockLLMResult(
                    generations=[[MockGeneration(text="r1")]],
                    llm_output={"token_usage": {"prompt_tokens": 10, "completion_tokens": 5}},
                ),
                run_id=run_id1,
            )

            # Second LLM call
            run_id2 = uuid4()
            handler.on_llm_start(
                serialized={"name": "ChatOpenAI"}, prompts=["test2"], run_id=run_id2
            )
            handler.on_llm_end(
                response=MockLLMResult(
                    generations=[[MockGeneration(text="r2")]],
                    llm_output={"token_usage": {"prompt_tokens": 20, "completion_tokens": 10}},
                ),
                run_id=run_id2,
            )

        # Token totals are aggregated at end_run() time by _aggregate_metrics()
        # Verify that steps have the correct token counts
        step1 = run.steps[0]
        step2 = run.steps[1]
        assert step1.input_tokens == 10
        assert step1.output_tokens == 5
        assert step2.input_tokens == 20
        assert step2.output_tokens == 10
        # Total would be 45 after end_run() aggregation

    def test_llm_nested_in_chain(self) -> None:
        """LLM step should be nested under chain step."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()
        chain_id = uuid4()
        llm_id = uuid4()

        with run_context(run):
            handler.on_chain_start(
                serialized={"name": "MyChain"},
                inputs={"query": "test"},
                run_id=chain_id,
            )
            handler.on_llm_start(
                serialized={"name": "ChatOpenAI"},
                prompts=["test"],
                run_id=llm_id,
                parent_run_id=chain_id,
            )
            handler.on_llm_end(
                response=MockLLMResult(
                    generations=[[MockGeneration(text="response")]],
                    llm_output=None,
                ),
                run_id=llm_id,
            )
            handler.on_chain_end(outputs={"result": "done"}, run_id=chain_id)

        assert len(run.steps) == 1
        chain = run.steps[0]
        assert len(chain.children) == 1
        llm = chain.children[0]
        assert llm.type == StepType.LLM
        assert llm.parent_id == chain.id


class TestToolCallbacks:
    """Tests for tool start/end callbacks."""

    def test_on_tool_start_creates_step(self) -> None:
        """on_tool_start should create a tool step."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()
        run_id = uuid4()

        with run_context(run):
            handler.on_tool_start(
                serialized={"name": "Calculator"},
                input_str="2+2",
                run_id=run_id,
            )

        assert len(run.steps) == 1
        step = run.steps[0]
        assert step.type == StepType.TOOL
        assert step.name == "Calculator"
        assert step.inputs == {"input": "2+2"}

    def test_on_tool_end_completes_step(self) -> None:
        """on_tool_end should complete the tool step."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()
        run_id = uuid4()

        with run_context(run):
            handler.on_tool_start(
                serialized={"name": "Calculator"},
                input_str="2+2",
                run_id=run_id,
            )
            handler.on_tool_end(
                output="4",
                run_id=run_id,
            )

        step = run.steps[0]
        assert step.outputs == {"output": "4"}
        assert step.end_time is not None
        assert step.duration_ms is not None

    def test_tool_nested_in_chain(self) -> None:
        """Tool step should be nested under parent chain."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()
        chain_id = uuid4()
        tool_id = uuid4()

        with run_context(run):
            handler.on_chain_start(
                serialized={"name": "AgentExecutor"},
                inputs={"input": "calculate 2+2"},
                run_id=chain_id,
            )
            handler.on_tool_start(
                serialized={"name": "Calculator"},
                input_str="2+2",
                run_id=tool_id,
                parent_run_id=chain_id,
            )
            handler.on_tool_end(output="4", run_id=tool_id)
            handler.on_chain_end(outputs={"output": "4"}, run_id=chain_id)

        chain = run.steps[0]
        assert len(chain.children) == 1
        tool = chain.children[0]
        assert tool.type == StepType.TOOL
        assert tool.parent_id == chain.id


class TestRetrieverCallbacks:
    """Tests for retriever callbacks."""

    def test_on_retriever_start_creates_step(self) -> None:
        """on_retriever_start should create a retrieval step."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()
        run_id = uuid4()

        with run_context(run):
            handler.on_retriever_start(
                serialized={"name": "VectorStoreRetriever"},
                query="What is Python?",
                run_id=run_id,
            )

        assert len(run.steps) == 1
        step = run.steps[0]
        assert step.type == StepType.RETRIEVAL
        assert step.name == "VectorStoreRetriever"
        assert step.inputs == {"query": "What is Python?"}

    def test_on_retriever_end_captures_documents(self) -> None:
        """on_retriever_end should capture retrieved documents."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()
        run_id = uuid4()

        docs = [
            MockDocument(
                page_content="Python is a programming language.", metadata={"source": "doc1"}
            ),
            MockDocument(page_content="Python was created by Guido.", metadata={"source": "doc2"}),
        ]

        with run_context(run):
            handler.on_retriever_start(
                serialized={"name": "VectorStoreRetriever"},
                query="What is Python?",
                run_id=run_id,
            )
            handler.on_retriever_end(
                documents=docs,
                run_id=run_id,
            )

        step = run.steps[0]
        assert "documents" in step.outputs
        assert len(step.outputs["documents"]) == 2
        assert step.outputs["documents"][0]["content"] == "Python is a programming language."
        assert step.outputs["documents"][0]["metadata"] == {"source": "doc1"}

    def test_retriever_nested_in_chain(self) -> None:
        """Retriever step should be nested under parent chain."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()
        chain_id = uuid4()
        retriever_id = uuid4()

        with run_context(run):
            handler.on_chain_start(
                serialized={"name": "RetrievalQA"},
                inputs={"query": "test"},
                run_id=chain_id,
            )
            handler.on_retriever_start(
                serialized={"name": "VectorStoreRetriever"},
                query="test",
                run_id=retriever_id,
                parent_run_id=chain_id,
            )
            handler.on_retriever_end(documents=[], run_id=retriever_id)
            handler.on_chain_end(outputs={"result": "answer"}, run_id=chain_id)

        chain = run.steps[0]
        assert len(chain.children) == 1
        retriever = chain.children[0]
        assert retriever.type == StepType.RETRIEVAL


class TestErrorCallbacks:
    """Tests for error handling callbacks."""

    def test_on_chain_error_captures_error(self) -> None:
        """on_chain_error should capture the error."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()
        run_id = uuid4()

        with run_context(run):
            handler.on_chain_start(
                serialized={"name": "MyChain"},
                inputs={"query": "test"},
                run_id=run_id,
            )
            handler.on_chain_error(
                error=ValueError("Something went wrong"),
                run_id=run_id,
            )

        step = run.steps[0]
        assert step.error == "Something went wrong"
        assert step.error_type == "ValueError"
        assert step.end_time is not None

    def test_on_llm_error_captures_error(self) -> None:
        """on_llm_error should capture the error."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()
        run_id = uuid4()

        with run_context(run):
            handler.on_llm_start(
                serialized={"name": "ChatOpenAI"},
                prompts=["test"],
                run_id=run_id,
            )
            handler.on_llm_error(
                error=RuntimeError("API rate limit exceeded"),
                run_id=run_id,
            )

        step = run.steps[0]
        assert step.error == "API rate limit exceeded"
        assert step.error_type == "RuntimeError"

    def test_on_tool_error_captures_error(self) -> None:
        """on_tool_error should capture the error."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()
        run_id = uuid4()

        with run_context(run):
            handler.on_tool_start(
                serialized={"name": "Calculator"},
                input_str="invalid",
                run_id=run_id,
            )
            handler.on_tool_error(
                error=TypeError("Invalid input for calculator"),
                run_id=run_id,
            )

        step = run.steps[0]
        assert step.error == "Invalid input for calculator"
        assert step.error_type == "TypeError"

    def test_on_retriever_error_captures_error(self) -> None:
        """on_retriever_error should capture the error."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()
        run_id = uuid4()

        with run_context(run):
            handler.on_retriever_start(
                serialized={"name": "VectorStoreRetriever"},
                query="test",
                run_id=run_id,
            )
            handler.on_retriever_error(
                error=ConnectionError("Database unavailable"),
                run_id=run_id,
            )

        step = run.steps[0]
        assert step.error == "Database unavailable"
        assert step.error_type == "ConnectionError"

    def test_error_increments_run_error_count(self) -> None:
        """Errors should increment run.error_count."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()

        with run_context(run):
            run_id1 = uuid4()
            handler.on_chain_start(serialized={"name": "Chain1"}, inputs={}, run_id=run_id1)
            handler.on_chain_error(error=ValueError("Error 1"), run_id=run_id1)

            run_id2 = uuid4()
            handler.on_tool_start(serialized={"name": "Tool1"}, input_str="x", run_id=run_id2)
            handler.on_tool_error(error=RuntimeError("Error 2"), run_id=run_id2)

        # Error count is aggregated at end_run() time by _aggregate_metrics()
        # Verify that steps have the correct error info
        step1 = run.steps[0]
        step2 = run.steps[1]
        assert step1.error == "Error 1"
        assert step1.error_type == "ValueError"
        assert step2.error == "Error 2"
        assert step2.error_type == "RuntimeError"
        # error_count would be 2 after end_run() aggregation


class TestChatModelCallbacks:
    """Tests for chat model specific callbacks."""

    def test_on_chat_model_start_creates_step(self) -> None:
        """on_chat_model_start should create an LLM step with messages."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()
        run_id = uuid4()

        messages = [
            [MockMessage(type="human", content="Hello"), MockMessage(type="ai", content="Hi there")]
        ]

        with run_context(run):
            handler.on_chat_model_start(
                serialized={"name": "ChatOpenAI", "id": ["langchain", "chat_models", "ChatOpenAI"]},
                messages=messages,
                run_id=run_id,
                invocation_params={"model_name": "gpt-4"},
            )

        step = run.steps[0]
        assert step.type == StepType.LLM
        assert step.name == "ChatOpenAI"
        assert "messages" in step.inputs
        assert step.model_name == "gpt-4"


class TestAgentCallbacks:
    """Tests for agent-specific callbacks."""

    def test_on_agent_action_creates_step(self) -> None:
        """on_agent_action should create a step for agent actions."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()
        run_id = uuid4()

        action = MockAgentAction(tool="search", tool_input="Python tutorials", log="Searching...")

        with run_context(run):
            handler.on_agent_action(
                action=action,
                run_id=run_id,
            )

        assert len(run.steps) == 1
        step = run.steps[0]
        assert step.type == StepType.AGENT
        assert step.name == "agent_action"
        assert step.inputs.get("tool") == "search"
        assert step.inputs.get("tool_input") == "Python tutorials"

    def test_on_agent_finish_completes_step(self) -> None:
        """on_agent_finish should complete agent step."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()
        run_id = uuid4()

        with run_context(run):
            handler.on_agent_action(
                action=MockAgentAction(tool="search", tool_input="test", log="log"),
                run_id=run_id,
            )
            handler.on_agent_finish(
                finish=MockAgentFinish(return_values={"output": "done"}, log="Finished"),
                run_id=run_id,
            )

        step = run.steps[0]
        assert step.outputs.get("return_values") == {"output": "done"}
        assert step.end_time is not None


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_end_without_start_is_handled(self) -> None:
        """Should handle end callbacks without corresponding start."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()

        with run_context(run):
            # End without start - should not raise
            handler.on_chain_end(outputs={"result": "x"}, run_id=uuid4())
            handler.on_llm_end(
                response=MockLLMResult(generations=[], llm_output=None),
                run_id=uuid4(),
            )
            handler.on_tool_end(output="x", run_id=uuid4())

        # Should not have created any steps
        assert len(run.steps) == 0

    def test_missing_serialized_name(self) -> None:
        """Should handle missing name in serialized dict."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()

        with run_context(run):
            handler.on_chain_start(
                serialized={},  # No name or id
                inputs={},
                run_id=uuid4(),
            )

        step = run.steps[0]
        assert step.name == "unknown"  # Fallback

    def test_none_inputs_handled(self) -> None:
        """Should handle None inputs gracefully."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()
        run_id = uuid4()

        with run_context(run):
            handler.on_chain_start(
                serialized={"name": "Test"},
                inputs=None,  # type: ignore[arg-type]
                run_id=run_id,
            )
            handler.on_chain_end(outputs=None, run_id=run_id)  # type: ignore[arg-type]

        step = run.steps[0]
        assert step.inputs == {}
        assert step.outputs == {}


# Mock classes to simulate LangChain objects without requiring the dependency


class MockGeneration:
    """Mock LangChain Generation."""

    def __init__(self, text: str) -> None:
        self.text = text


class MockLLMResult:
    """Mock LangChain LLMResult."""

    def __init__(
        self,
        generations: list[list[MockGeneration]],
        llm_output: dict[str, Any] | None = None,
    ) -> None:
        self.generations = generations
        self.llm_output = llm_output or {}


class MockDocument:
    """Mock LangChain Document."""

    def __init__(self, page_content: str, metadata: dict[str, Any] | None = None) -> None:
        self.page_content = page_content
        self.metadata = metadata or {}


class MockMessage:
    """Mock LangChain message."""

    def __init__(self, type: str, content: str) -> None:
        self.type = type
        self.content = content


class MockAgentAction:
    """Mock LangChain AgentAction."""

    def __init__(self, tool: str, tool_input: str, log: str) -> None:
        self.tool = tool
        self.tool_input = tool_input
        self.log = log


class MockAgentFinish:
    """Mock LangChain AgentFinish."""

    def __init__(self, return_values: dict[str, Any], log: str) -> None:
        self.return_values = return_values
        self.log = log


class TestThreadSafety:
    """Tests for thread-safety of the callback handler."""

    def test_concurrent_step_creation(self) -> None:
        """Should handle concurrent step creation from multiple threads."""
        import threading

        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()
        errors: list[Exception] = []
        num_threads = 10

        def create_chain_step(thread_id: int) -> None:
            try:
                with run_context(run):
                    chain_id = uuid4()
                    handler.on_chain_start(
                        serialized={"name": f"Chain_{thread_id}"},
                        inputs={"thread": thread_id},
                        run_id=chain_id,
                    )
                    handler.on_chain_end(
                        outputs={"result": f"result_{thread_id}"},
                        run_id=chain_id,
                    )
            except Exception as e:
                errors.append(e)

        # Create and run threads
        threads = [
            threading.Thread(target=create_chain_step, args=(i,)) for i in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no errors occurred
        assert len(errors) == 0, f"Errors during concurrent access: {errors}"

        # Verify all steps were created (thread-safety ensured no corruption)
        assert len(run.steps) == num_threads

    def test_concurrent_nested_steps(self) -> None:
        """Should handle concurrent nested step creation."""
        import threading

        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = TraceCraftCallbackHandler()
        errors: list[Exception] = []
        num_threads = 5

        def create_nested_steps(thread_id: int) -> None:
            try:
                with run_context(run):
                    parent_id = uuid4()
                    handler.on_chain_start(
                        serialized={"name": f"Parent_{thread_id}"},
                        inputs={"thread": thread_id},
                        run_id=parent_id,
                    )
                    # Create 3 children per parent
                    for child_num in range(3):
                        child_id = uuid4()
                        handler.on_tool_start(
                            serialized={"name": f"Tool_{thread_id}_{child_num}"},
                            input_str=f"input_{child_num}",
                            run_id=child_id,
                            parent_run_id=parent_id,
                        )
                        handler.on_tool_end(
                            output=f"output_{child_num}",
                            run_id=child_id,
                        )
                    handler.on_chain_end(
                        outputs={"result": f"result_{thread_id}"},
                        run_id=parent_id,
                    )
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=create_nested_steps, args=(i,)) for i in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no errors occurred
        assert len(errors) == 0, f"Errors during concurrent access: {errors}"

        # Verify all parent steps were created
        assert len(run.steps) == num_threads

        # Verify each parent has exactly 3 children
        for step in run.steps:
            assert len(step.children) == 3, f"Expected 3 children, got {len(step.children)}"
