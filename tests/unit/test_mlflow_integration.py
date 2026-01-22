"""Tests for MLflow evaluation integration."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from agenttrace.core.models import AgentRun, Step, StepType


@pytest.fixture
def sample_traces():
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
                    inputs={
                        "input": "What is Python?",
                        "context": "Python is a programming language.",
                    },
                    outputs={"output": "Python is a high-level programming language."},
                    model_name="gpt-4",
                    input_tokens=10,
                    output_tokens=20,
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
                        "messages": [{"role": "user", "content": "Explain AI"}],
                        "ground_truth": "AI is artificial intelligence.",
                    },
                    outputs={"response": "AI refers to artificial intelligence systems."},
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


class TestMlflowHelperFunctions:
    """Tests for helper functions that don't require mlflow."""

    def test_flatten_steps(self):
        """Test flattening nested step hierarchy."""
        from agenttrace.integrations.mlflow_eval import _flatten_steps

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

    def test_load_traces_from_jsonl(self, traces_jsonl):
        """Test loading traces from JSONL file."""
        from agenttrace.integrations.mlflow_eval import _load_traces_from_jsonl

        traces = _load_traces_from_jsonl(traces_jsonl)

        assert len(traces) == 2
        assert traces[0].name == "test-run-1"

    def test_load_traces_file_not_found(self, tmp_path):
        """Test FileNotFoundError for non-existent file."""
        from agenttrace.integrations.mlflow_eval import _load_traces_from_jsonl

        with pytest.raises(FileNotFoundError):
            _load_traces_from_jsonl(tmp_path / "nonexistent.jsonl")


class TestDefaultExtractors:
    """Tests for default extraction functions."""

    def test_extract_inputs_from_input_field(self, sample_traces):
        """Test extracting from 'input' field."""
        from agenttrace.integrations.mlflow_eval import _default_extract_inputs

        step = sample_traces[0].steps[0]
        result = _default_extract_inputs(step)

        assert result == "What is Python?"

    def test_extract_inputs_from_messages(self, sample_traces):
        """Test extracting from messages format."""
        from agenttrace.integrations.mlflow_eval import _default_extract_inputs

        step = sample_traces[1].steps[0]
        result = _default_extract_inputs(step)

        assert result == "Explain AI"

    def test_extract_outputs_from_output_field(self, sample_traces):
        """Test extracting from 'output' field."""
        from agenttrace.integrations.mlflow_eval import _default_extract_outputs

        step = sample_traces[0].steps[0]
        result = _default_extract_outputs(step)

        assert "Python" in result

    def test_extract_outputs_from_response_field(self, sample_traces):
        """Test extracting from 'response' field."""
        from agenttrace.integrations.mlflow_eval import _default_extract_outputs

        step = sample_traces[1].steps[0]
        result = _default_extract_outputs(step)

        assert "AI" in result

    def test_extract_context(self, sample_traces):
        """Test context extraction."""
        from agenttrace.integrations.mlflow_eval import _default_extract_context

        step = sample_traces[0].steps[0]
        result = _default_extract_context(step)

        assert result == "Python is a programming language."

    def test_extract_context_none_when_missing(self, sample_traces):
        """Test None returned when no context."""
        from agenttrace.integrations.mlflow_eval import _default_extract_context

        step = sample_traces[1].steps[0]
        result = _default_extract_context(step)

        assert result is None

    def test_extract_ground_truth(self, sample_traces):
        """Test ground truth extraction."""
        from agenttrace.integrations.mlflow_eval import _default_extract_ground_truth

        step = sample_traces[1].steps[0]
        result = _default_extract_ground_truth(step)

        assert result == "AI is artificial intelligence."

    def test_extract_ground_truth_none_when_missing(self, sample_traces):
        """Test None returned when no ground truth."""
        from agenttrace.integrations.mlflow_eval import _default_extract_ground_truth

        step = sample_traces[0].steps[0]
        result = _default_extract_ground_truth(step)

        assert result is None


# Tests that require mlflow to be installed
@pytest.mark.skipif(
    True,  # Skip - optional dependency not in test environment
    reason="mlflow not installed",
)
class TestTracesToMlflowDataset:
    """Tests for traces_to_mlflow_dataset function - requires mlflow."""

    def test_converts_traces_to_dataframe(self, sample_traces):
        """Test basic conversion of traces to pandas DataFrame."""
        pass  # Would require mlflow


@pytest.mark.skipif(
    True,  # Skip - optional dependency not in test environment
    reason="mlflow not installed",
)
class TestEvaluateWithMlflowJudges:
    """Tests for evaluate_with_mlflow_judges function - requires mlflow."""

    def test_evaluates_with_default_scorers(self, sample_traces):
        """Test evaluation with default scorers."""
        pass  # Would require mlflow


@pytest.mark.skipif(
    True,  # Skip - optional dependency not in test environment
    reason="mlflow not installed",
)
class TestLogTracesToMlflow:
    """Tests for log_traces_to_mlflow function - requires mlflow."""

    def test_logs_traces_to_mlflow(self, sample_traces):
        """Test logging traces to MLflow."""
        pass  # Would require mlflow
