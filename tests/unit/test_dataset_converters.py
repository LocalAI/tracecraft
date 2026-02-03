"""Tests for dataset conversion utilities."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from tracecraft.core.models import AgentRun, Step, StepType


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
                        "messages": [
                            {"role": "system", "content": "You are helpful"},
                            {"role": "user", "content": "What is Python?"},
                        ]
                    },
                    outputs={"response": "Python is a programming language."},
                    model_name="gpt-4",
                    input_tokens=15,
                    output_tokens=10,
                    cost_usd=0.001,
                    duration_ms=500,
                ),
                Step(
                    id=uuid4(),
                    trace_id=trace_id_1,
                    name="tool-step",
                    type=StepType.TOOL,
                    start_time=datetime.now(UTC),
                    end_time=datetime.now(UTC),
                    inputs={"query": "search term"},
                    outputs={"result": "search result"},
                    duration_ms=100,
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
                        "system": "Be concise",
                    },
                    outputs={"result": "AI is artificial intelligence."},
                    model_name="claude-3",
                    input_tokens=8,
                    output_tokens=5,
                    cost_usd=0.0005,
                    duration_ms=300,
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


class TestTracesToCsv:
    """Tests for traces_to_csv function."""

    def test_exports_traces_to_csv(self, sample_traces, tmp_path):
        """Test basic CSV export."""
        from tracecraft.datasets.converters import traces_to_csv

        output_path = tmp_path / "output.csv"
        count = traces_to_csv(sample_traces, output_path)

        # Should export all steps (3 total)
        assert count == 3
        assert output_path.exists()

        # Verify CSV content
        with output_path.open() as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 3

    def test_exports_from_jsonl_path(self, traces_jsonl, tmp_path):
        """Test export from JSONL file path."""
        from tracecraft.datasets.converters import traces_to_csv

        output_path = tmp_path / "output.csv"
        count = traces_to_csv(traces_jsonl, output_path)

        assert count == 3
        assert output_path.exists()

    def test_custom_columns(self, sample_traces, tmp_path):
        """Test export with custom columns."""
        from tracecraft.datasets.converters import traces_to_csv

        output_path = tmp_path / "output.csv"
        columns = ["trace_id", "step_name", "model", "duration_ms"]
        count = traces_to_csv(sample_traces, output_path, columns=columns)

        with output_path.open() as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert set(rows[0].keys()) == set(columns)

    def test_filter_function(self, sample_traces, tmp_path):
        """Test export with filter function."""
        from tracecraft.datasets.converters import traces_to_csv

        output_path = tmp_path / "output.csv"
        filter_fn = lambda step: step.type.value == "llm"
        count = traces_to_csv(sample_traces, output_path, filter_fn=filter_fn)

        # Should only export LLM steps (2)
        assert count == 2

    def test_creates_parent_directories(self, sample_traces, tmp_path):
        """Test that parent directories are created."""
        from tracecraft.datasets.converters import traces_to_csv

        output_path = tmp_path / "nested" / "dir" / "output.csv"
        traces_to_csv(sample_traces, output_path)

        assert output_path.exists()

    def test_csv_row_content(self, sample_traces, tmp_path):
        """Test CSV row content is correct."""
        from tracecraft.datasets.converters import traces_to_csv

        output_path = tmp_path / "output.csv"
        traces_to_csv(sample_traces, output_path)

        with output_path.open() as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            # Check first LLM row
            llm_row = next(r for r in rows if r["step_type"] == "llm")
            assert llm_row["model"] == "gpt-4"
            assert llm_row["step_name"] == "llm-step-1"


class TestTracesToJsonl:
    """Tests for traces_to_jsonl function."""

    def test_exports_raw_format(self, sample_traces, tmp_path):
        """Test export in raw format."""
        from tracecraft.datasets.converters import traces_to_jsonl

        output_path = tmp_path / "output.jsonl"
        count = traces_to_jsonl(sample_traces, output_path, format_type="raw")

        assert count == 3
        assert output_path.exists()

        # Verify JSONL content
        with output_path.open() as f:
            lines = f.readlines()
            assert len(lines) == 3
            record = json.loads(lines[0])
            assert "trace_id" in record
            assert "step_id" in record

    def test_exports_openai_format(self, sample_traces, tmp_path):
        """Test export in OpenAI format."""
        from tracecraft.datasets.converters import traces_to_jsonl

        output_path = tmp_path / "output.jsonl"
        count = traces_to_jsonl(sample_traces, output_path, format_type="openai")

        # Should only export LLM steps with valid messages
        assert count >= 1

        with output_path.open() as f:
            lines = f.readlines()
            record = json.loads(lines[0])
            assert "messages" in record

    def test_exports_anthropic_format(self, sample_traces, tmp_path):
        """Test export in Anthropic format."""
        from tracecraft.datasets.converters import traces_to_jsonl

        output_path = tmp_path / "output.jsonl"
        count = traces_to_jsonl(sample_traces, output_path, format_type="anthropic")

        assert count >= 1

        with output_path.open() as f:
            lines = f.readlines()
            record = json.loads(lines[0])
            assert "messages" in record

    def test_applies_filter(self, sample_traces, tmp_path):
        """Test filter function is applied."""
        from tracecraft.datasets.converters import traces_to_jsonl

        output_path = tmp_path / "output.jsonl"
        filter_fn = lambda step: step.model_name == "gpt-4"
        count = traces_to_jsonl(sample_traces, output_path, format_type="raw", filter_fn=filter_fn)

        assert count == 1

    def test_loads_from_jsonl_path(self, traces_jsonl, tmp_path):
        """Test loading from JSONL path."""
        from tracecraft.datasets.converters import traces_to_jsonl

        output_path = tmp_path / "output.jsonl"
        count = traces_to_jsonl(traces_jsonl, output_path, format_type="raw")

        assert count == 3


class TestCreateGoldenDataset:
    """Tests for create_golden_dataset function."""

    def test_creates_golden_dataset(self, sample_traces, tmp_path):
        """Test creating golden dataset."""
        from tracecraft.datasets.converters import create_golden_dataset

        output_path = tmp_path / "golden.jsonl"
        count = create_golden_dataset(sample_traces, output_path)

        # Should only include successful LLM steps by default
        assert count == 2
        assert output_path.exists()

    def test_includes_expected_output(self, sample_traces, tmp_path):
        """Test that expected output is included."""
        from tracecraft.datasets.converters import create_golden_dataset

        output_path = tmp_path / "golden.jsonl"
        create_golden_dataset(sample_traces, output_path, include_expected=True)

        with output_path.open() as f:
            record = json.loads(f.readline())
            assert "expected_output" in record

    def test_excludes_expected_output(self, sample_traces, tmp_path):
        """Test that expected output can be excluded."""
        from tracecraft.datasets.converters import create_golden_dataset

        output_path = tmp_path / "golden.jsonl"
        create_golden_dataset(sample_traces, output_path, include_expected=False)

        with output_path.open() as f:
            record = json.loads(f.readline())
            assert "expected_output" not in record

    def test_includes_metadata(self, sample_traces, tmp_path):
        """Test that metadata is included."""
        from tracecraft.datasets.converters import create_golden_dataset

        output_path = tmp_path / "golden.jsonl"
        create_golden_dataset(sample_traces, output_path)

        with output_path.open() as f:
            record = json.loads(f.readline())
            assert "metadata" in record
            assert "source_trace_id" in record["metadata"]
            assert "source_step_id" in record["metadata"]

    def test_applies_filter(self, sample_traces, tmp_path):
        """Test filter function is applied."""
        from tracecraft.datasets.converters import create_golden_dataset

        output_path = tmp_path / "golden.jsonl"
        filter_fn = lambda step: step.model_name == "gpt-4"
        count = create_golden_dataset(sample_traces, output_path, filter_fn=filter_fn)

        assert count == 1


class TestCreateFinetuningDataset:
    """Tests for create_finetuning_dataset function."""

    def test_creates_openai_finetuning_dataset(self, sample_traces, tmp_path):
        """Test creating OpenAI fine-tuning dataset."""
        from tracecraft.datasets.converters import create_finetuning_dataset

        output_path = tmp_path / "finetune.jsonl"
        count = create_finetuning_dataset(sample_traces, output_path, format_type="openai")

        assert count >= 1

        with output_path.open() as f:
            record = json.loads(f.readline())
            assert "messages" in record

    def test_creates_anthropic_finetuning_dataset(self, sample_traces, tmp_path):
        """Test creating Anthropic fine-tuning dataset."""
        from tracecraft.datasets.converters import create_finetuning_dataset

        output_path = tmp_path / "finetune.jsonl"
        count = create_finetuning_dataset(sample_traces, output_path, format_type="anthropic")

        assert count >= 1

        with output_path.open() as f:
            record = json.loads(f.readline())
            assert "messages" in record

    def test_adds_system_prompt(self, sample_traces, tmp_path):
        """Test adding system prompt."""
        from tracecraft.datasets.converters import create_finetuning_dataset

        output_path = tmp_path / "finetune.jsonl"
        create_finetuning_dataset(
            sample_traces,
            output_path,
            format_type="openai",
            system_prompt="You are a helpful assistant.",
        )

        with output_path.open() as f:
            for line in f:
                record = json.loads(line)
                messages = record.get("messages", [])
                # Should have system prompt
                system_msgs = [m for m in messages if m.get("role") == "system"]
                assert len(system_msgs) >= 1

    def test_applies_filter(self, sample_traces, tmp_path):
        """Test filter function is applied."""
        from tracecraft.datasets.converters import create_finetuning_dataset

        output_path = tmp_path / "finetune.jsonl"
        filter_fn = lambda step: step.model_name == "gpt-4"
        count = create_finetuning_dataset(sample_traces, output_path, filter_fn=filter_fn)

        assert count == 1

    def test_respects_quality_score(self, sample_traces, tmp_path):
        """Test quality score filtering."""
        from tracecraft.datasets.converters import create_finetuning_dataset

        # Add quality scores to steps
        sample_traces[0].steps[0].attributes = {"quality_score": 0.9}
        sample_traces[1].steps[0].attributes = {"quality_score": 0.3}

        output_path = tmp_path / "finetune.jsonl"
        count = create_finetuning_dataset(sample_traces, output_path, min_quality_score=0.5)

        # Only high quality step should be included
        assert count == 1

    def test_raises_for_unknown_format(self, sample_traces, tmp_path):
        """Test ValueError for unknown format type."""
        from tracecraft.datasets.converters import create_finetuning_dataset

        output_path = tmp_path / "finetune.jsonl"

        with pytest.raises(ValueError, match="Unknown format_type"):
            create_finetuning_dataset(sample_traces, output_path, format_type="invalid")


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_load_traces_from_jsonl(self, traces_jsonl):
        """Test loading traces from JSONL."""
        from tracecraft.datasets.converters import _load_traces_from_jsonl

        traces = _load_traces_from_jsonl(traces_jsonl)

        assert len(traces) == 2
        assert traces[0].name == "test-run-1"

    def test_load_traces_file_not_found(self, tmp_path):
        """Test FileNotFoundError for missing file."""
        from tracecraft.datasets.converters import _load_traces_from_jsonl

        with pytest.raises(FileNotFoundError):
            _load_traces_from_jsonl(tmp_path / "nonexistent.jsonl")

    def test_flatten_steps(self):
        """Test flattening nested steps."""
        from tracecraft.datasets.converters import _flatten_steps

        trace_id = uuid4()
        child = Step(
            id=uuid4(),
            trace_id=trace_id,
            name="child",
            type=StepType.LLM,
            start_time=datetime.now(UTC),
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

        assert len(result) == 2
        assert result[0].name == "parent"
        assert result[1].name == "child"

    def test_extract_messages(self, sample_traces):
        """Test message extraction from step."""
        from tracecraft.datasets.converters import _extract_messages

        step = sample_traces[0].steps[0]
        messages = _extract_messages(step)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_extract_messages_from_prompt(self, sample_traces):
        """Test message extraction from prompt field."""
        from tracecraft.datasets.converters import _extract_messages

        step = sample_traces[1].steps[0]
        messages = _extract_messages(step)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Explain AI"

    def test_extract_output_text(self, sample_traces):
        """Test output text extraction."""
        from tracecraft.datasets.converters import _extract_output_text

        step = sample_traces[0].steps[0]
        output = _extract_output_text(step)

        assert output == "Python is a programming language."

    def test_extract_output_text_from_result(self, sample_traces):
        """Test output extraction from 'result' field."""
        from tracecraft.datasets.converters import _extract_output_text

        step = sample_traces[1].steps[0]
        output = _extract_output_text(step)

        assert output == "AI is artificial intelligence."


class TestOpenAIFormat:
    """Tests for OpenAI format conversion."""

    def test_format_openai(self, sample_traces):
        """Test OpenAI format output."""
        from tracecraft.datasets.converters import _format_openai

        step = sample_traces[0].steps[0]
        result = _format_openai(step)

        assert result is not None
        assert "messages" in result
        # Should end with assistant message
        assert result["messages"][-1]["role"] == "assistant"

    def test_format_openai_returns_none_for_no_messages(self):
        """Test None returned when no messages can be extracted."""
        from tracecraft.datasets.converters import _format_openai

        trace_id = uuid4()
        step = Step(
            id=uuid4(),
            trace_id=trace_id,
            name="empty",
            type=StepType.LLM,
            start_time=datetime.now(UTC),
            inputs={},
            outputs={},
        )

        result = _format_openai(step)

        assert result is None


class TestAnthropicFormat:
    """Tests for Anthropic format conversion."""

    def test_format_anthropic(self, sample_traces):
        """Test Anthropic format output."""
        from tracecraft.datasets.converters import _format_anthropic

        step = sample_traces[0].steps[0]
        result = _format_anthropic(step)

        assert result is not None
        assert "messages" in result
        # System should be separate in Anthropic format
        assert "system" in result
        # Messages should not contain system role
        assert all(m["role"] != "system" for m in result["messages"])

    def test_format_anthropic_finetune_with_system(self, sample_traces):
        """Test Anthropic fine-tune format with system prompt."""
        from tracecraft.datasets.converters import _format_anthropic_finetune

        step = sample_traces[0].steps[0]
        result = _format_anthropic_finetune(step, "Custom system prompt")

        assert result is not None
        assert result["system"] == "Custom system prompt"


# Tests that require datasets (HuggingFace) to be installed
@pytest.mark.skipif(
    True,  # Skip - optional dependency not in test environment
    reason="datasets not installed",
)
class TestTracesToHuggingface:
    """Tests for traces_to_huggingface function - requires datasets."""

    def test_converts_traces_to_dataset(self, sample_traces):
        """Test conversion to HuggingFace Dataset."""
        pass  # Would require datasets package
