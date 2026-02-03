"""
Tests for trace exporters (Console, JSONL).

TDD approach: These tests are written BEFORE the implementation.
"""

import json
import tempfile
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from uuid import uuid4

import pytest


class TestBaseExporter:
    """Tests for the base exporter interface."""

    def test_exporter_has_export_method(self):
        """Base exporter should define an export method."""
        from tracecraft.exporters.base import BaseExporter

        # Check that the abstract class defines the method
        assert hasattr(BaseExporter, "export")
        assert callable(BaseExporter.export)

    def test_exporter_has_close_method(self):
        """Base exporter should define a close method."""
        from tracecraft.exporters.base import BaseExporter

        assert hasattr(BaseExporter, "close")
        assert callable(BaseExporter.close)


class TestConsoleExporter:
    """Tests for the Rich console exporter."""

    def test_console_exporter_creates_tree(self, sample_run):
        """Console exporter should create a Rich tree structure."""
        from tracecraft.exporters.console import ConsoleExporter

        output = StringIO()
        exporter = ConsoleExporter(file=output)
        exporter.export(sample_run)

        output_str = output.getvalue()
        # Should contain the run name
        assert sample_run.name in output_str

    def test_console_exporter_shows_step_names(self, sample_run_with_steps):
        """Console exporter should display step names."""
        from tracecraft.exporters.console import ConsoleExporter

        output = StringIO()
        exporter = ConsoleExporter(file=output)
        exporter.export(sample_run_with_steps)

        output_str = output.getvalue()
        # Should contain step names
        assert "llm_call" in output_str
        assert "tool_call" in output_str

    def test_console_step_icons_agent(self, sample_run_with_agent_step):
        """Console exporter should show agent icon for AGENT steps."""
        from tracecraft.core.models import StepType
        from tracecraft.exporters.console import STEP_ICONS, ConsoleExporter

        output = StringIO()
        exporter = ConsoleExporter(file=output)
        exporter.export(sample_run_with_agent_step)

        output_str = output.getvalue()
        # Should contain the agent icon
        assert STEP_ICONS[StepType.AGENT] in output_str

    def test_console_step_icons_llm(self, sample_run_with_llm_step):
        """Console exporter should show LLM icon for LLM steps."""
        from tracecraft.core.models import StepType
        from tracecraft.exporters.console import STEP_ICONS, ConsoleExporter

        output = StringIO()
        exporter = ConsoleExporter(file=output)
        exporter.export(sample_run_with_llm_step)

        output_str = output.getvalue()
        assert STEP_ICONS[StepType.LLM] in output_str

    def test_console_step_icons_tool(self, sample_run_with_tool_step):
        """Console exporter should show tool icon for TOOL steps."""
        from tracecraft.core.models import StepType
        from tracecraft.exporters.console import STEP_ICONS, ConsoleExporter

        output = StringIO()
        exporter = ConsoleExporter(file=output)
        exporter.export(sample_run_with_tool_step)

        output_str = output.getvalue()
        assert STEP_ICONS[StepType.TOOL] in output_str

    def test_console_step_icons_retrieval(self, sample_run_with_retrieval_step):
        """Console exporter should show retrieval icon for RETRIEVAL steps."""
        from tracecraft.core.models import StepType
        from tracecraft.exporters.console import STEP_ICONS, ConsoleExporter

        output = StringIO()
        exporter = ConsoleExporter(file=output)
        exporter.export(sample_run_with_retrieval_step)

        output_str = output.getvalue()
        assert STEP_ICONS[StepType.RETRIEVAL] in output_str

    def test_console_step_icons_error(self, sample_run_with_error_step):
        """Console exporter should show error icon for ERROR steps."""
        from tracecraft.core.models import StepType
        from tracecraft.exporters.console import STEP_ICONS, ConsoleExporter

        output = StringIO()
        exporter = ConsoleExporter(file=output)
        exporter.export(sample_run_with_error_step)

        output_str = output.getvalue()
        assert STEP_ICONS[StepType.ERROR] in output_str

    def test_console_duration_display(self, sample_run_with_timed_step):
        """Console exporter should display duration in ms."""
        from tracecraft.exporters.console import ConsoleExporter

        output = StringIO()
        exporter = ConsoleExporter(file=output)
        exporter.export(sample_run_with_timed_step)

        output_str = output.getvalue()
        # Should contain duration (e.g., "150.5ms" or "150ms")
        assert "ms" in output_str

    def test_console_token_display(self, sample_run_with_token_step):
        """Console exporter should display token counts."""
        from tracecraft.exporters.console import ConsoleExporter

        output = StringIO()
        exporter = ConsoleExporter(file=output)
        exporter.export(sample_run_with_token_step)

        output_str = output.getvalue()
        # Should contain token info
        assert "100" in output_str  # input_tokens
        assert "250" in output_str  # output_tokens

    def test_console_nested_steps(self, sample_run_with_nested_steps):
        """Console exporter should properly display nested steps."""
        from tracecraft.exporters.console import ConsoleExporter

        output = StringIO()
        exporter = ConsoleExporter(file=output)
        exporter.export(sample_run_with_nested_steps)

        output_str = output.getvalue()
        # Both steps should appear
        assert "parent_agent" in output_str
        assert "child_tool" in output_str

    def test_console_exporter_color_option(self, sample_run):
        """Console exporter should support disabling color."""
        from tracecraft.exporters.console import ConsoleExporter

        output = StringIO()
        exporter = ConsoleExporter(file=output, no_color=True)
        exporter.export(sample_run)

        # Should still produce output without error
        assert len(output.getvalue()) > 0

    def test_console_exporter_verbose_mode(self, sample_run_with_steps):
        """Console exporter verbose mode should show inputs/outputs."""
        from tracecraft.exporters.console import ConsoleExporter

        output = StringIO()
        exporter = ConsoleExporter(file=output, verbose=True)
        exporter.export(sample_run_with_steps)

        output_str = output.getvalue()
        # In verbose mode, should show more detail
        assert len(output_str) > 0


class TestJSONLExporter:
    """Tests for the JSONL exporter."""

    def test_jsonl_writes_valid_json(self, sample_run):
        """JSONL exporter should write valid JSON."""
        from tracecraft.exporters.jsonl import JSONLExporter

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            filepath = f.name

        try:
            exporter = JSONLExporter(filepath)
            exporter.export(sample_run)
            exporter.close()

            with open(filepath) as f:
                line = f.readline()
                data = json.loads(line)
                assert data["name"] == sample_run.name
        finally:
            Path(filepath).unlink(missing_ok=True)

    def test_jsonl_appends_to_file(self, sample_run, sample_timestamp):
        """JSONL exporter should append multiple runs."""
        from tracecraft.core.models import AgentRun
        from tracecraft.exporters.jsonl import JSONLExporter

        run2 = AgentRun(name="second_run", start_time=sample_timestamp)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            filepath = f.name

        try:
            exporter = JSONLExporter(filepath)
            exporter.export(sample_run)
            exporter.export(run2)
            exporter.close()

            with open(filepath) as f:
                lines = f.readlines()
                assert len(lines) == 2
                assert json.loads(lines[0])["name"] == sample_run.name
                assert json.loads(lines[1])["name"] == "second_run"
        finally:
            Path(filepath).unlink(missing_ok=True)

    def test_jsonl_one_run_per_line(self, sample_run):
        """JSONL exporter should write one run per line."""
        from tracecraft.exporters.jsonl import JSONLExporter

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            filepath = f.name

        try:
            exporter = JSONLExporter(filepath)
            exporter.export(sample_run)
            exporter.close()

            with open(filepath) as f:
                content = f.read()
                # Should be a single line (possibly with trailing newline)
                lines = [line for line in content.strip().split("\n") if line]
                assert len(lines) == 1
        finally:
            Path(filepath).unlink(missing_ok=True)

    def test_jsonl_includes_steps(self, sample_run_with_steps):
        """JSONL exporter should include nested steps."""
        from tracecraft.exporters.jsonl import JSONLExporter

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            filepath = f.name

        try:
            exporter = JSONLExporter(filepath)
            exporter.export(sample_run_with_steps)
            exporter.close()

            with open(filepath) as f:
                data = json.loads(f.readline())
                assert "steps" in data
                assert len(data["steps"]) > 0
        finally:
            Path(filepath).unlink(missing_ok=True)

    def test_jsonl_creates_directory_if_needed(self, sample_run):
        """JSONL exporter should create parent directories."""
        from tracecraft.exporters.jsonl import JSONLExporter

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "nested" / "dir" / "traces.jsonl"

            exporter = JSONLExporter(str(filepath))
            exporter.export(sample_run)
            exporter.close()

            assert filepath.exists()
            with open(filepath) as f:
                data = json.loads(f.readline())
                assert data["name"] == sample_run.name

    def test_jsonl_handles_datetime_serialization(self, sample_run):
        """JSONL exporter should properly serialize datetime fields."""
        from tracecraft.exporters.jsonl import JSONLExporter

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            filepath = f.name

        try:
            exporter = JSONLExporter(filepath)
            exporter.export(sample_run)
            exporter.close()

            with open(filepath) as f:
                data = json.loads(f.readline())
                # Should be valid ISO format
                assert "start_time" in data
                datetime.fromisoformat(data["start_time"].replace("Z", "+00:00"))
        finally:
            Path(filepath).unlink(missing_ok=True)


# Additional fixtures for exporter tests
@pytest.fixture
def sample_run_with_steps(sample_timestamp):
    """Create a run with multiple steps."""
    from tracecraft.core.models import AgentRun, Step, StepType

    run_id = uuid4()
    step1 = Step(
        trace_id=run_id,
        type=StepType.LLM,
        name="llm_call",
        start_time=sample_timestamp,
        duration_ms=100.5,
        inputs={"prompt": "Hello"},
        outputs={"response": "Hi there"},
    )
    step2 = Step(
        trace_id=run_id,
        type=StepType.TOOL,
        name="tool_call",
        start_time=sample_timestamp,
        duration_ms=50.0,
    )

    return AgentRun(
        id=run_id,
        name="run_with_steps",
        start_time=sample_timestamp,
        steps=[step1, step2],
    )


@pytest.fixture
def sample_run_with_agent_step(sample_timestamp):
    """Create a run with an agent step."""
    from tracecraft.core.models import AgentRun, Step, StepType

    run_id = uuid4()
    step = Step(
        trace_id=run_id,
        type=StepType.AGENT,
        name="test_agent",
        start_time=sample_timestamp,
    )

    return AgentRun(
        id=run_id,
        name="agent_run",
        start_time=sample_timestamp,
        steps=[step],
    )


@pytest.fixture
def sample_run_with_llm_step(sample_timestamp):
    """Create a run with an LLM step."""
    from tracecraft.core.models import AgentRun, Step, StepType

    run_id = uuid4()
    step = Step(
        trace_id=run_id,
        type=StepType.LLM,
        name="llm_call",
        start_time=sample_timestamp,
    )

    return AgentRun(
        id=run_id,
        name="llm_run",
        start_time=sample_timestamp,
        steps=[step],
    )


@pytest.fixture
def sample_run_with_tool_step(sample_timestamp):
    """Create a run with a tool step."""
    from tracecraft.core.models import AgentRun, Step, StepType

    run_id = uuid4()
    step = Step(
        trace_id=run_id,
        type=StepType.TOOL,
        name="tool_call",
        start_time=sample_timestamp,
    )

    return AgentRun(
        id=run_id,
        name="tool_run",
        start_time=sample_timestamp,
        steps=[step],
    )


@pytest.fixture
def sample_run_with_retrieval_step(sample_timestamp):
    """Create a run with a retrieval step."""
    from tracecraft.core.models import AgentRun, Step, StepType

    run_id = uuid4()
    step = Step(
        trace_id=run_id,
        type=StepType.RETRIEVAL,
        name="retrieval_call",
        start_time=sample_timestamp,
    )

    return AgentRun(
        id=run_id,
        name="retrieval_run",
        start_time=sample_timestamp,
        steps=[step],
    )


@pytest.fixture
def sample_run_with_error_step(sample_timestamp):
    """Create a run with an error step."""
    from tracecraft.core.models import AgentRun, Step, StepType

    run_id = uuid4()
    step = Step(
        trace_id=run_id,
        type=StepType.ERROR,
        name="error_step",
        start_time=sample_timestamp,
        error="Something went wrong",
        error_type="ValueError",
    )

    return AgentRun(
        id=run_id,
        name="error_run",
        start_time=sample_timestamp,
        steps=[step],
    )


@pytest.fixture
def sample_run_with_timed_step(sample_timestamp):
    """Create a run with a timed step."""
    from tracecraft.core.models import AgentRun, Step, StepType

    run_id = uuid4()
    end_time = datetime.now(UTC)
    step = Step(
        trace_id=run_id,
        type=StepType.TOOL,
        name="timed_step",
        start_time=sample_timestamp,
        end_time=end_time,
        duration_ms=150.5,
    )

    return AgentRun(
        id=run_id,
        name="timed_run",
        start_time=sample_timestamp,
        steps=[step],
    )


@pytest.fixture
def sample_run_with_token_step(sample_timestamp):
    """Create a run with a step that has token counts."""
    from tracecraft.core.models import AgentRun, Step, StepType

    run_id = uuid4()
    step = Step(
        trace_id=run_id,
        type=StepType.LLM,
        name="token_step",
        start_time=sample_timestamp,
        model_name="gpt-4",
        input_tokens=100,
        output_tokens=250,
        cost_usd=0.015,
    )

    return AgentRun(
        id=run_id,
        name="token_run",
        start_time=sample_timestamp,
        steps=[step],
    )


@pytest.fixture
def sample_run_with_nested_steps(sample_timestamp):
    """Create a run with nested steps."""
    from tracecraft.core.models import AgentRun, Step, StepType

    run_id = uuid4()
    parent_id = uuid4()

    child_step = Step(
        id=uuid4(),
        trace_id=run_id,
        parent_id=parent_id,
        type=StepType.TOOL,
        name="child_tool",
        start_time=sample_timestamp,
    )

    parent_step = Step(
        id=parent_id,
        trace_id=run_id,
        type=StepType.AGENT,
        name="parent_agent",
        start_time=sample_timestamp,
        children=[child_step],
    )

    return AgentRun(
        id=run_id,
        name="nested_run",
        start_time=sample_timestamp,
        steps=[parent_step],
    )
