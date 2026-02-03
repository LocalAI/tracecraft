"""Tests for RAGAS integration."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from tracecraft.core.models import AgentRun, Step, StepType


@pytest.fixture
def sample_rag_traces():
    """Create sample RAG traces for testing."""
    trace_id_1 = uuid4()
    trace_id_2 = uuid4()
    return [
        AgentRun(
            id=trace_id_1,
            name="rag-run-1",
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            steps=[
                Step(
                    id=uuid4(),
                    trace_id=trace_id_1,
                    name="retrieval-step",
                    type=StepType.RETRIEVAL,
                    start_time=datetime.now(UTC),
                    end_time=datetime.now(UTC),
                    inputs={"query": "What is Python?"},
                    outputs={
                        "documents": [
                            "Python is a programming language.",
                            "Python was created by Guido van Rossum.",
                        ]
                    },
                ),
                Step(
                    id=uuid4(),
                    trace_id=trace_id_1,
                    name="llm-step-with-context",
                    type=StepType.LLM,
                    start_time=datetime.now(UTC),
                    end_time=datetime.now(UTC),
                    inputs={
                        "question": "What is Python?",
                        "contexts": [
                            "Python is a programming language.",
                            "Python was created by Guido van Rossum.",
                        ],
                    },
                    outputs={
                        "answer": "Python is a high-level programming language created by Guido van Rossum."
                    },
                    model_name="gpt-4",
                ),
            ],
        ),
        AgentRun(
            id=trace_id_2,
            name="rag-run-2",
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            steps=[
                Step(
                    id=uuid4(),
                    trace_id=trace_id_2,
                    name="llm-step-no-context",
                    type=StepType.LLM,
                    start_time=datetime.now(UTC),
                    end_time=datetime.now(UTC),
                    inputs={
                        "query": "What is 2+2?",
                    },
                    outputs={"response": "4"},
                    model_name="gpt-4",
                ),
            ],
        ),
    ]


@pytest.fixture
def rag_traces_jsonl(tmp_path, sample_rag_traces):
    """Create a JSONL file with sample RAG traces."""
    jsonl_path = tmp_path / "rag_traces.jsonl"
    with jsonl_path.open("w") as f:
        for trace in sample_rag_traces:
            f.write(trace.model_dump_json() + "\n")
    return jsonl_path


class TestRagasHelperFunctions:
    """Tests for helper functions that don't require ragas."""

    def test_flatten_steps(self):
        """Test flattening nested step hierarchy."""
        from tracecraft.integrations.ragas import _flatten_steps

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

    def test_load_traces_from_jsonl(self, rag_traces_jsonl):
        """Test loading traces from JSONL file."""
        from tracecraft.integrations.ragas import _load_traces_from_jsonl

        traces = _load_traces_from_jsonl(rag_traces_jsonl)

        assert len(traces) == 2
        assert traces[0].name == "rag-run-1"

    def test_load_traces_file_not_found(self, tmp_path):
        """Test FileNotFoundError for non-existent file."""
        from tracecraft.integrations.ragas import _load_traces_from_jsonl

        with pytest.raises(FileNotFoundError):
            _load_traces_from_jsonl(tmp_path / "nonexistent.jsonl")


class TestFilterRagSteps:
    """Tests for filter_rag_steps helper."""

    def test_includes_retrieval_steps(self, sample_rag_traces):
        """Test that retrieval steps are included."""
        from tracecraft.integrations.ragas import filter_rag_steps

        retrieval_step = sample_rag_traces[0].steps[0]
        assert filter_rag_steps(retrieval_step) is True

    def test_includes_llm_steps_with_context(self, sample_rag_traces):
        """Test that LLM steps with context are included."""
        from tracecraft.integrations.ragas import filter_rag_steps

        llm_step_with_context = sample_rag_traces[0].steps[1]
        assert filter_rag_steps(llm_step_with_context) is True

    def test_excludes_llm_steps_without_context(self, sample_rag_traces):
        """Test that LLM steps without context are excluded."""
        from tracecraft.integrations.ragas import filter_rag_steps

        llm_step_no_context = sample_rag_traces[1].steps[0]
        assert filter_rag_steps(llm_step_no_context) is False

    def test_excludes_other_step_types(self):
        """Test that non-RAG step types are excluded."""
        from tracecraft.integrations.ragas import filter_rag_steps

        trace_id = uuid4()
        tool_step = Step(
            id=uuid4(),
            trace_id=trace_id,
            name="tool",
            type=StepType.TOOL,
            start_time=datetime.now(UTC),
        )
        assert filter_rag_steps(tool_step) is False


class TestDefaultExtractors:
    """Tests for default extraction functions."""

    def test_extract_question_from_question_field(self, sample_rag_traces):
        """Test extracting question from 'question' field."""
        from tracecraft.integrations.ragas import _default_extract_question

        step = sample_rag_traces[0].steps[1]
        result = _default_extract_question(step)

        assert result == "What is Python?"

    def test_extract_question_from_query_field(self, sample_rag_traces):
        """Test extracting question from 'query' field."""
        from tracecraft.integrations.ragas import _default_extract_question

        step = sample_rag_traces[1].steps[0]
        result = _default_extract_question(step)

        assert result == "What is 2+2?"

    def test_extract_answer_from_answer_field(self, sample_rag_traces):
        """Test extracting answer from 'answer' field."""
        from tracecraft.integrations.ragas import _default_extract_answer

        step = sample_rag_traces[0].steps[1]
        result = _default_extract_answer(step)

        assert "Python" in result

    def test_extract_answer_from_response_field(self, sample_rag_traces):
        """Test extracting answer from 'response' field."""
        from tracecraft.integrations.ragas import _default_extract_answer

        step = sample_rag_traces[1].steps[0]
        result = _default_extract_answer(step)

        assert result == "4"

    def test_extract_contexts_list(self, sample_rag_traces):
        """Test extracting contexts list."""
        from tracecraft.integrations.ragas import _default_extract_contexts

        step = sample_rag_traces[0].steps[1]
        result = _default_extract_contexts(step)

        assert len(result) == 2
        assert "Python is a programming language." in result

    def test_extract_contexts_empty_when_missing(self, sample_rag_traces):
        """Test that empty list is returned when no contexts."""
        from tracecraft.integrations.ragas import _default_extract_contexts

        step = sample_rag_traces[1].steps[0]
        result = _default_extract_contexts(step)

        assert result == []

    def test_extract_ground_truth(self):
        """Test ground truth extraction."""
        from tracecraft.integrations.ragas import _default_extract_ground_truth

        trace_id = uuid4()
        step = Step(
            id=uuid4(),
            trace_id=trace_id,
            name="test",
            type=StepType.LLM,
            start_time=datetime.now(UTC),
            inputs={"ground_truth": "Expected answer"},
        )
        result = _default_extract_ground_truth(step)

        assert result == "Expected answer"

    def test_extract_ground_truth_none_when_missing(self, sample_rag_traces):
        """Test that None is returned when no ground truth."""
        from tracecraft.integrations.ragas import _default_extract_ground_truth

        step = sample_rag_traces[0].steps[0]
        result = _default_extract_ground_truth(step)

        assert result is None


# Tests that require ragas to be installed
@pytest.mark.skipif(
    True,  # Skip - optional dependency not in test environment
    reason="ragas not installed",
)
class TestTracesToRagasDataset:
    """Tests for traces_to_ragas_dataset function - requires ragas."""

    def test_converts_traces_to_dataset(self, sample_rag_traces):
        """Test basic conversion of traces to RAGAS dataset."""
        pass  # Would require ragas


@pytest.mark.skipif(
    True,  # Skip - optional dependency not in test environment
    reason="ragas not installed",
)
class TestEvaluateRagTraces:
    """Tests for evaluate_rag_traces function - requires ragas."""

    def test_evaluates_with_default_metrics(self, sample_rag_traces):
        """Test evaluation with default metrics."""
        pass  # Would require ragas


@pytest.mark.skipif(
    True,  # Skip - optional dependency not in test environment
    reason="ragas not installed",
)
class TestCreateMetrics:
    """Tests for _create_metrics helper function - requires ragas."""

    def test_creates_faithfulness_metric(self):
        """Test creating faithfulness metric."""
        pass  # Would require ragas
