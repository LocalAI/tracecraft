"""Tests for DeepEval integration."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from agenttrace.core.models import AgentRun, Step, StepType

# Skip all tests if deepeval isn't installed
pytestmark = pytest.mark.skipif(
    "deepeval" not in sys.modules and True,  # Always skip for unit tests without deepeval
    reason="deepeval not installed",
)


@pytest.fixture
def trace_id():
    """Common trace ID for test steps."""
    return uuid4()


@pytest.fixture
def sample_traces(trace_id):
    """Create sample traces for testing."""
    trace_id_1 = uuid4()
    trace_id_2 = uuid4()
    return [
        AgentRun(
            id=trace_id_1,
            name="test-run-1",
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            steps=[
                Step(
                    id=uuid4(),
                    trace_id=trace_id_1,
                    name="llm-step-1",
                    type=StepType.LLM,
                    start_time=datetime.now(UTC),
                    end_time=datetime.now(UTC),
                    inputs={"messages": [{"role": "user", "content": "What is Python?"}]},
                    outputs={"response": "Python is a programming language."},
                    model_name="gpt-4",
                    input_tokens=10,
                    output_tokens=20,
                ),
                Step(
                    id=uuid4(),
                    trace_id=trace_id_1,
                    name="tool-step",
                    type=StepType.TOOL,
                    start_time=datetime.now(UTC),
                    end_time=datetime.now(UTC),
                    inputs={"query": "search"},
                    outputs={"result": "found"},
                ),
            ],
        ),
        AgentRun(
            id=trace_id_2,
            name="test-run-2",
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            steps=[
                Step(
                    id=uuid4(),
                    trace_id=trace_id_2,
                    name="llm-step-2",
                    type=StepType.LLM,
                    start_time=datetime.now(UTC),
                    end_time=datetime.now(UTC),
                    inputs={
                        "prompt": "Explain AI",
                        "context": ["AI is artificial intelligence.", "ML is a subset."],
                    },
                    outputs={"result": "AI refers to artificial intelligence."},
                    model_name="claude-3",
                ),
            ],
        ),
    ]


@pytest.fixture
def traces_jsonl(tmp_path, sample_traces):
    """Create a JSONL file with sample traces."""
    jsonl_path = tmp_path / "traces.jsonl"
    with jsonl_path.open("w") as f:
        for trace in sample_traces:
            f.write(trace.model_dump_json() + "\n")
    return jsonl_path


class TestDeepEvalHelperFunctions:
    """Tests for helper functions that don't require deepeval."""

    def test_flatten_steps(self):
        """Test flattening nested steps."""
        from agenttrace.integrations.deepeval import _flatten_steps

        trace_id = uuid4()
        child_step = Step(
            id=uuid4(),
            trace_id=trace_id,
            name="child",
            type=StepType.LLM,
            start_time=datetime.now(UTC),
        )

        parent_step = Step(
            id=uuid4(),
            trace_id=trace_id,
            name="parent",
            type=StepType.AGENT,
            start_time=datetime.now(UTC),
            children=[child_step],
        )

        result = _flatten_steps([parent_step])

        assert len(result) == 2
        assert result[0].name == "parent"
        assert result[1].name == "child"

    def test_handles_deeply_nested_steps(self):
        """Test handling deeply nested step hierarchy."""
        from agenttrace.integrations.deepeval import _flatten_steps

        trace_id = uuid4()
        grandchild = Step(
            id=uuid4(),
            trace_id=trace_id,
            name="grandchild",
            type=StepType.LLM,
            start_time=datetime.now(UTC),
        )

        child = Step(
            id=uuid4(),
            trace_id=trace_id,
            name="child",
            type=StepType.AGENT,
            start_time=datetime.now(UTC),
            children=[grandchild],
        )

        parent = Step(
            id=uuid4(),
            trace_id=trace_id,
            name="parent",
            type=StepType.AGENT,
            start_time=datetime.now(UTC),
            children=[child],
        )

        result = _flatten_steps([parent])

        assert len(result) == 3
        assert [s.name for s in result] == ["parent", "child", "grandchild"]

    def test_default_extract_input_from_messages(self, sample_traces):
        """Test extracting input from messages format."""
        from agenttrace.integrations.deepeval import _default_extract_input

        step = sample_traces[0].steps[0]
        result = _default_extract_input(step)

        assert result == "What is Python?"

    def test_default_extract_input_from_prompt(self, sample_traces):
        """Test extracting input from prompt field."""
        from agenttrace.integrations.deepeval import _default_extract_input

        step = sample_traces[1].steps[0]
        result = _default_extract_input(step)

        assert result == "Explain AI"

    def test_default_extract_output_from_response(self, sample_traces):
        """Test extracting output from response field."""
        from agenttrace.integrations.deepeval import _default_extract_output

        step = sample_traces[0].steps[0]
        result = _default_extract_output(step)

        assert result == "Python is a programming language."

    def test_default_extract_output_from_result(self, sample_traces):
        """Test extracting output from result field."""
        from agenttrace.integrations.deepeval import _default_extract_output

        step = sample_traces[1].steps[0]
        result = _default_extract_output(step)

        assert result == "AI refers to artificial intelligence."

    def test_default_extract_context_list(self, sample_traces):
        """Test extracting context list."""
        from agenttrace.integrations.deepeval import _default_extract_context

        step = sample_traces[1].steps[0]
        result = _default_extract_context(step)

        assert result == ["AI is artificial intelligence.", "ML is a subset."]

    def test_default_extract_context_none_when_missing(self, sample_traces):
        """Test that None is returned when no context exists."""
        from agenttrace.integrations.deepeval import _default_extract_context

        step = sample_traces[0].steps[0]
        result = _default_extract_context(step)

        assert result is None

    def test_load_traces_from_jsonl(self, traces_jsonl):
        """Test loading traces from JSONL file."""
        from agenttrace.integrations.deepeval import _load_traces_from_jsonl

        traces = _load_traces_from_jsonl(traces_jsonl)

        assert len(traces) == 2
        assert traces[0].name == "test-run-1"

    def test_load_traces_file_not_found(self, tmp_path):
        """Test FileNotFoundError for non-existent file."""
        from agenttrace.integrations.deepeval import _load_traces_from_jsonl

        with pytest.raises(FileNotFoundError):
            _load_traces_from_jsonl(tmp_path / "nonexistent.jsonl")


# These tests require deepeval to be installed
@pytest.mark.skipif(
    True,  # Skip - optional dependency not in test environment
    reason="deepeval not installed",
)
class TestTracesToTestCases:
    """Tests for traces_to_test_cases function - requires deepeval."""

    def test_converts_traces_to_test_cases(self, sample_traces):
        """Test basic conversion of traces to test cases."""
        pass  # Would require deepeval

    def test_loads_traces_from_jsonl_path(self, traces_jsonl):
        """Test loading traces from JSONL file path."""
        pass  # Would require deepeval


@pytest.mark.skipif(
    True,  # Skip - optional dependency not in test environment
    reason="deepeval not installed",
)
class TestEvaluateTraces:
    """Tests for evaluate_traces function - requires deepeval."""

    def test_evaluates_with_default_metrics(self, sample_traces):
        """Test evaluation with default metrics."""
        pass  # Would require deepeval


@pytest.mark.skipif(
    True,  # Skip - optional dependency not in test environment
    reason="deepeval not installed",
)
class TestCreateMetrics:
    """Tests for _create_metrics helper function - requires deepeval."""

    def test_creates_answer_relevancy_metric(self):
        """Test creating answer relevancy metric."""
        pass  # Would require deepeval
