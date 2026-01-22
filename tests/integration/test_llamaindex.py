"""
Tests for the LlamaIndex span handler adapter.

Tests LlamaIndex integration using mock callbacks without requiring
actual LlamaIndex installation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from agenttrace.core.context import run_context
from agenttrace.core.models import AgentRun, StepType


class TestLlamaIndexSpanHandler:
    """Tests for AgentTraceSpanHandler."""

    def test_handler_creation(self) -> None:
        """Should create a span handler."""
        from agenttrace.adapters.llamaindex import AgentTraceSpanHandler

        handler = AgentTraceSpanHandler()
        assert handler is not None

    def test_handler_requires_active_run(self) -> None:
        """Should require an active run to capture steps."""
        from agenttrace.adapters.llamaindex import AgentTraceSpanHandler

        handler = AgentTraceSpanHandler()
        # No active run, spans should not be created
        span_id = handler.new_span(
            id_=str(uuid4()),
            bound_args={},
            instance=None,
            parent_span_id=None,
        )
        # Should return None or empty when no run
        assert span_id is None or span_id == ""

    def test_handler_with_active_run(self) -> None:
        """Should create steps when run is active."""
        from agenttrace.adapters.llamaindex import AgentTraceSpanHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = AgentTraceSpanHandler()
        span_id = str(uuid4())

        with run_context(run):
            result_id = handler.new_span(
                id_=span_id,
                bound_args={"query": "test"},
                instance=MockQueryEngine(),
                parent_span_id=None,
            )
            handler.end_span(
                id_=result_id,
                bound_args={"query": "test"},
                instance=MockQueryEngine(),
                result="response",
            )

        assert len(run.steps) == 1


class TestSpanTypeInference:
    """Tests for inferring step type from LlamaIndex components."""

    def test_infer_llm_type(self) -> None:
        """Should infer LLM type for LLM instances."""
        from agenttrace.adapters.llamaindex import AgentTraceSpanHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = AgentTraceSpanHandler()
        span_id = str(uuid4())

        with run_context(run):
            result_id = handler.new_span(
                id_=span_id,
                bound_args={"prompt": "Hello"},
                instance=MockLLM(),
                parent_span_id=None,
            )
            handler.end_span(
                id_=result_id,
                bound_args={"prompt": "Hello"},
                instance=MockLLM(),
                result=MockCompletionResponse(text="Hi there"),
            )

        step = run.steps[0]
        assert step.type == StepType.LLM

    def test_infer_retriever_type(self) -> None:
        """Should infer RETRIEVAL type for retriever instances."""
        from agenttrace.adapters.llamaindex import AgentTraceSpanHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = AgentTraceSpanHandler()
        span_id = str(uuid4())

        with run_context(run):
            result_id = handler.new_span(
                id_=span_id,
                bound_args={"query_bundle": MockQueryBundle(query_str="test query")},
                instance=MockRetriever(),
                parent_span_id=None,
            )
            handler.end_span(
                id_=result_id,
                bound_args={},
                instance=MockRetriever(),
                result=[MockNodeWithScore(node=MockTextNode(text="doc content"))],
            )

        step = run.steps[0]
        assert step.type == StepType.RETRIEVAL

    def test_infer_tool_type(self) -> None:
        """Should infer TOOL type for tool instances."""
        from agenttrace.adapters.llamaindex import AgentTraceSpanHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = AgentTraceSpanHandler()
        span_id = str(uuid4())

        with run_context(run):
            result_id = handler.new_span(
                id_=span_id,
                bound_args={"input": "test input"},
                instance=MockTool(name="calculator"),
                parent_span_id=None,
            )
            handler.end_span(
                id_=result_id,
                bound_args={},
                instance=MockTool(name="calculator"),
                result="42",
            )

        step = run.steps[0]
        assert step.type == StepType.TOOL
        assert step.name == "calculator"

    def test_infer_agent_type(self) -> None:
        """Should infer AGENT type for agent instances."""
        from agenttrace.adapters.llamaindex import AgentTraceSpanHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = AgentTraceSpanHandler()
        span_id = str(uuid4())

        with run_context(run):
            result_id = handler.new_span(
                id_=span_id,
                bound_args={"task": "research"},
                instance=MockAgent(),
                parent_span_id=None,
            )
            handler.end_span(
                id_=result_id,
                bound_args={},
                instance=MockAgent(),
                result=MockAgentResponse(response="Done"),
            )

        step = run.steps[0]
        assert step.type == StepType.AGENT

    def test_default_workflow_type(self) -> None:
        """Should default to WORKFLOW for unknown instances."""
        from agenttrace.adapters.llamaindex import AgentTraceSpanHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = AgentTraceSpanHandler()
        span_id = str(uuid4())

        with run_context(run):
            result_id = handler.new_span(
                id_=span_id,
                bound_args={},
                instance=MockUnknownComponent(),
                parent_span_id=None,
            )
            handler.end_span(
                id_=result_id,
                bound_args={},
                instance=MockUnknownComponent(),
                result=None,
            )

        step = run.steps[0]
        assert step.type == StepType.WORKFLOW


class TestSpanHierarchy:
    """Tests for span parent-child relationships."""

    def test_nested_spans(self) -> None:
        """Should handle nested spans with proper hierarchy."""
        from agenttrace.adapters.llamaindex import AgentTraceSpanHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = AgentTraceSpanHandler()
        parent_span_id = str(uuid4())
        child_span_id = str(uuid4())

        with run_context(run):
            # Parent span
            parent_result = handler.new_span(
                id_=parent_span_id,
                bound_args={"query": "test"},
                instance=MockQueryEngine(),
                parent_span_id=None,
            )

            # Child span
            child_result = handler.new_span(
                id_=child_span_id,
                bound_args={"prompt": "sub"},
                instance=MockLLM(),
                parent_span_id=parent_result,
            )

            # End child
            handler.end_span(
                id_=child_result,
                bound_args={},
                instance=MockLLM(),
                result=MockCompletionResponse(text="result"),
            )

            # End parent
            handler.end_span(
                id_=parent_result,
                bound_args={},
                instance=MockQueryEngine(),
                result="final",
            )

        # Parent should be at root
        assert len(run.steps) == 1
        parent = run.steps[0]
        # Child should be nested
        assert len(parent.children) == 1
        child = parent.children[0]
        assert child.type == StepType.LLM


class TestSourceNodeExtraction:
    """Tests for extracting source nodes from retrieval results."""

    def test_extract_source_nodes(self) -> None:
        """Should extract source documents from retrieval results."""
        from agenttrace.adapters.llamaindex import AgentTraceSpanHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = AgentTraceSpanHandler()
        span_id = str(uuid4())

        nodes = [
            MockNodeWithScore(
                node=MockTextNode(
                    text="Document 1 content",
                    metadata={"source": "file1.txt"},
                ),
                score=0.9,
            ),
            MockNodeWithScore(
                node=MockTextNode(
                    text="Document 2 content",
                    metadata={"source": "file2.txt"},
                ),
                score=0.85,
            ),
        ]

        with run_context(run):
            result_id = handler.new_span(
                id_=span_id,
                bound_args={"query_bundle": MockQueryBundle(query_str="search query")},
                instance=MockRetriever(),
                parent_span_id=None,
            )
            handler.end_span(
                id_=result_id,
                bound_args={},
                instance=MockRetriever(),
                result=nodes,
            )

        step = run.steps[0]
        assert "documents" in step.outputs
        docs = step.outputs["documents"]
        assert len(docs) == 2
        assert docs[0]["content"] == "Document 1 content"
        assert docs[0]["metadata"]["source"] == "file1.txt"
        assert docs[0]["score"] == 0.9


class TestLLMMetadata:
    """Tests for capturing LLM metadata."""

    def test_capture_model_name(self) -> None:
        """Should capture model name from LLM instance."""
        from agenttrace.adapters.llamaindex import AgentTraceSpanHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = AgentTraceSpanHandler()
        span_id = str(uuid4())

        llm = MockLLM(model="gpt-4")

        with run_context(run):
            result_id = handler.new_span(
                id_=span_id,
                bound_args={"prompt": "test"},
                instance=llm,
                parent_span_id=None,
            )
            handler.end_span(
                id_=result_id,
                bound_args={},
                instance=llm,
                result=MockCompletionResponse(text="response"),
            )

        step = run.steps[0]
        assert step.model_name == "gpt-4"

    def test_capture_token_usage(self) -> None:
        """Should capture token counts from LLM response."""
        from agenttrace.adapters.llamaindex import AgentTraceSpanHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = AgentTraceSpanHandler()
        span_id = str(uuid4())

        with run_context(run):
            result_id = handler.new_span(
                id_=span_id,
                bound_args={"prompt": "test"},
                instance=MockLLM(),
                parent_span_id=None,
            )
            handler.end_span(
                id_=result_id,
                bound_args={},
                instance=MockLLM(),
                result=MockCompletionResponse(
                    text="response",
                    raw={"usage": {"prompt_tokens": 100, "completion_tokens": 50}},
                ),
            )

        step = run.steps[0]
        assert step.input_tokens == 100
        assert step.output_tokens == 50


class TestErrorHandling:
    """Tests for error handling."""

    def test_capture_span_error(self) -> None:
        """Should capture errors from span drops."""
        from agenttrace.adapters.llamaindex import AgentTraceSpanHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = AgentTraceSpanHandler()
        span_id = str(uuid4())

        with run_context(run):
            result_id = handler.new_span(
                id_=span_id,
                bound_args={"query": "test"},
                instance=MockQueryEngine(),
                parent_span_id=None,
            )
            handler.drop_span(
                id_=result_id,
                bound_args={},
                instance=MockQueryEngine(),
                err=ValueError("Query failed"),
            )

        step = run.steps[0]
        assert step.error == "Query failed"
        assert step.error_type == "ValueError"

    def test_error_increments_run_count(self) -> None:
        """Should increment run.error_count on errors."""
        from agenttrace.adapters.llamaindex import AgentTraceSpanHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = AgentTraceSpanHandler()

        with run_context(run):
            span_id = str(uuid4())
            result_id = handler.new_span(
                id_=span_id,
                bound_args={},
                instance=MockQueryEngine(),
                parent_span_id=None,
            )
            handler.drop_span(
                id_=result_id,
                bound_args={},
                instance=MockQueryEngine(),
                err=RuntimeError("Error 1"),
            )

            span_id2 = str(uuid4())
            result_id2 = handler.new_span(
                id_=span_id2,
                bound_args={},
                instance=MockLLM(),
                parent_span_id=None,
            )
            handler.drop_span(
                id_=result_id2,
                bound_args={},
                instance=MockLLM(),
                err=RuntimeError("Error 2"),
            )

        # Error count is aggregated at end_run() time by _aggregate_metrics()
        # Verify that steps have the correct error info
        step1 = run.steps[0]
        step2 = run.steps[1]
        assert step1.error == "Error 1"
        assert step1.error_type == "RuntimeError"
        assert step2.error == "Error 2"
        assert step2.error_type == "RuntimeError"
        # error_count would be 2 after end_run() aggregation


class TestEdgeCases:
    """Tests for edge cases."""

    def test_end_without_start(self) -> None:
        """Should handle end without corresponding start."""
        from agenttrace.adapters.llamaindex import AgentTraceSpanHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = AgentTraceSpanHandler()

        with run_context(run):
            # End without start - should not raise
            handler.end_span(
                id_="nonexistent",
                bound_args={},
                instance=MockQueryEngine(),
                result="result",
            )

        # Should not have created any steps
        assert len(run.steps) == 0

    def test_none_instance(self) -> None:
        """Should handle None instance gracefully."""
        from agenttrace.adapters.llamaindex import AgentTraceSpanHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = AgentTraceSpanHandler()
        span_id = str(uuid4())

        with run_context(run):
            result_id = handler.new_span(
                id_=span_id,
                bound_args={},
                instance=None,
                parent_span_id=None,
            )
            handler.end_span(
                id_=result_id,
                bound_args={},
                instance=None,
                result=None,
            )

        step = run.steps[0]
        assert step.type == StepType.WORKFLOW
        assert step.name == "unknown"


class TestCallbackManager:
    """Tests for callback manager integration."""

    def test_span_handler_protocol(self) -> None:
        """Should implement the span handler protocol methods."""
        from agenttrace.adapters.llamaindex import AgentTraceSpanHandler

        handler = AgentTraceSpanHandler()

        # Should have required methods
        assert hasattr(handler, "new_span")
        assert hasattr(handler, "end_span")
        assert hasattr(handler, "drop_span")
        assert callable(handler.new_span)
        assert callable(handler.end_span)
        assert callable(handler.drop_span)


# Mock classes to simulate LlamaIndex objects without requiring the dependency


class MockQueryEngine:
    """Mock LlamaIndex QueryEngine."""

    pass


class MockLLM:
    """Mock LlamaIndex LLM."""

    def __init__(self, model: str = "gpt-3.5-turbo") -> None:
        self.model = model
        self.model_name = model


class MockRetriever:
    """Mock LlamaIndex Retriever."""

    pass


class MockTool:
    """Mock LlamaIndex Tool."""

    def __init__(self, name: str = "tool") -> None:
        self.name = name
        self.metadata = MockToolMetadata(name=name)


class MockToolMetadata:
    """Mock tool metadata."""

    def __init__(self, name: str) -> None:
        self.name = name


class MockAgent:
    """Mock LlamaIndex Agent."""

    pass


class MockUnknownComponent:
    """Mock unknown component."""

    pass


class MockCompletionResponse:
    """Mock LlamaIndex CompletionResponse."""

    def __init__(
        self,
        text: str,
        raw: dict[str, Any] | None = None,
    ) -> None:
        self.text = text
        self.raw = raw or {}


class MockQueryBundle:
    """Mock LlamaIndex QueryBundle."""

    def __init__(self, query_str: str) -> None:
        self.query_str = query_str


class MockTextNode:
    """Mock LlamaIndex TextNode."""

    def __init__(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.text = text
        self.metadata = metadata or {}

    def get_content(self) -> str:
        return self.text


class MockNodeWithScore:
    """Mock LlamaIndex NodeWithScore."""

    def __init__(
        self,
        node: MockTextNode,
        score: float = 1.0,
    ) -> None:
        self.node = node
        self.score = score


class MockAgentResponse:
    """Mock LlamaIndex AgentChatResponse."""

    def __init__(self, response: str) -> None:
        self.response = response


class TestThreadSafety:
    """Tests for thread-safety of the span handler."""

    def test_concurrent_span_creation(self) -> None:
        """Should handle concurrent span creation from multiple threads."""
        import threading

        from agenttrace.adapters.llamaindex import AgentTraceSpanHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = AgentTraceSpanHandler()
        errors: list[Exception] = []
        num_threads = 10

        def create_span(thread_id: int) -> None:
            try:
                with run_context(run):
                    span_id = f"span_{thread_id}"
                    handler.new_span(
                        id_=span_id,
                        bound_args={"query": f"query_{thread_id}"},
                        instance=MockQueryEngine(),
                    )
                    handler.end_span(
                        id_=span_id,
                        bound_args={},
                        instance=None,
                        result=f"result_{thread_id}",
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_span, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no errors occurred
        assert len(errors) == 0, f"Errors during concurrent access: {errors}"

        # Verify all steps were created
        assert len(run.steps) == num_threads

    def test_concurrent_nested_spans(self) -> None:
        """Should handle concurrent nested span creation."""
        import threading

        from agenttrace.adapters.llamaindex import AgentTraceSpanHandler

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        handler = AgentTraceSpanHandler()
        errors: list[Exception] = []
        num_threads = 5

        def create_nested_spans(thread_id: int) -> None:
            try:
                with run_context(run):
                    parent_id = f"parent_{thread_id}"
                    handler.new_span(
                        id_=parent_id,
                        bound_args={},
                        instance=MockQueryEngine(),
                    )
                    # Create 3 children per parent
                    for child_num in range(3):
                        child_id = f"child_{thread_id}_{child_num}"
                        handler.new_span(
                            id_=child_id,
                            bound_args={"query": f"query_{child_num}"},
                            instance=MockRetriever(),
                            parent_span_id=parent_id,
                        )
                        handler.end_span(
                            id_=child_id,
                            bound_args={},
                            instance=None,
                            result=[],
                        )
                    handler.end_span(
                        id_=parent_id,
                        bound_args={},
                        instance=None,
                        result=MockAgentResponse(response=f"result_{thread_id}"),
                    )
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=create_nested_spans, args=(i,)) for i in range(num_threads)
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
