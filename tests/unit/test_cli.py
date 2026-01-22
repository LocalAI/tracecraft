"""
Tests for the AgentTrace CLI.

Tests CLI commands using typer's testing utilities.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agenttrace.core.models import AgentRun, Step, StepType


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def sample_run() -> AgentRun:
    """Create a sample run for testing."""
    run = AgentRun(name="test_run", start_time=datetime.now(UTC))
    step = Step(
        trace_id=run.id,
        type=StepType.AGENT,
        name="agent_step",
        start_time=run.start_time,
        end_time=datetime.now(UTC),
        duration_ms=100.0,
    )
    run.steps.append(step)
    run.end_time = datetime.now(UTC)
    run.duration_ms = 150.0
    return run


@pytest.fixture
def sample_jsonl(sample_run: AgentRun, tmp_path: Path) -> Path:
    """Create a sample JSONL trace file."""
    trace_file = tmp_path / "traces.jsonl"
    with trace_file.open("w") as f:
        f.write(sample_run.model_dump_json() + "\n")
    return trace_file


class TestCliApp:
    """Tests for CLI app creation."""

    def test_app_exists(self) -> None:
        """Should have a typer app."""
        from agenttrace.cli.main import app

        assert app is not None

    def test_app_has_version(self, runner: CliRunner) -> None:
        """Should show version with --version."""
        from agenttrace.cli.main import app

        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "agenttrace" in result.stdout.lower() or "0.1.0" in result.stdout

    def test_app_help(self, runner: CliRunner) -> None:
        """Should show help with --help."""
        from agenttrace.cli.main import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "agenttrace" in result.stdout.lower() or "usage" in result.stdout.lower()


class TestViewCommand:
    """Tests for the view command."""

    def test_view_command_exists(self, runner: CliRunner) -> None:
        """Should have a view command."""
        from agenttrace.cli.main import app

        result = runner.invoke(app, ["view", "--help"])
        assert result.exit_code == 0

    def test_view_requires_file_path(self, runner: CliRunner) -> None:
        """Should require a file path argument."""
        from agenttrace.cli.main import app

        result = runner.invoke(app, ["view"])
        # Should fail without file path
        assert result.exit_code != 0

    def test_view_nonexistent_file(self, runner: CliRunner) -> None:
        """Should error on nonexistent file."""
        from agenttrace.cli.main import app

        result = runner.invoke(app, ["view", "/nonexistent/path.jsonl"])
        assert result.exit_code != 0
        assert "not found" in result.stdout.lower() or "error" in result.stdout.lower()

    def test_view_displays_trace(self, runner: CliRunner, sample_jsonl: Path) -> None:
        """Should display trace from JSONL file."""
        from agenttrace.cli.main import app

        result = runner.invoke(app, ["view", str(sample_jsonl)])
        assert result.exit_code == 0
        # Should show run name
        assert "test_run" in result.stdout

    def test_view_displays_steps(self, runner: CliRunner, sample_jsonl: Path) -> None:
        """Should display steps in trace."""
        from agenttrace.cli.main import app

        result = runner.invoke(app, ["view", str(sample_jsonl)])
        assert result.exit_code == 0
        # Should show step info
        assert "agent" in result.stdout.lower()

    def test_view_json_output(self, runner: CliRunner, sample_jsonl: Path) -> None:
        """Should support --json output format."""
        from agenttrace.cli.main import app

        result = runner.invoke(app, ["view", str(sample_jsonl), "--json"])
        assert result.exit_code == 0
        # Should be valid JSON
        data = json.loads(result.stdout)
        assert "name" in data
        assert data["name"] == "test_run"

    def test_view_multiple_runs(self, runner: CliRunner, tmp_path: Path) -> None:
        """Should handle file with multiple runs."""
        from agenttrace.cli.main import app

        trace_file = tmp_path / "multi.jsonl"
        with trace_file.open("w") as f:
            for i in range(3):
                run = AgentRun(name=f"run_{i}", start_time=datetime.now(UTC))
                f.write(run.model_dump_json() + "\n")

        result = runner.invoke(app, ["view", str(trace_file)])
        assert result.exit_code == 0
        # Should show all runs
        for i in range(3):
            assert f"run_{i}" in result.stdout

    def test_view_run_index(self, runner: CliRunner, tmp_path: Path) -> None:
        """Should support --run option to select specific run."""
        from agenttrace.cli.main import app

        trace_file = tmp_path / "multi.jsonl"
        with trace_file.open("w") as f:
            for i in range(3):
                run = AgentRun(name=f"run_{i}", start_time=datetime.now(UTC))
                f.write(run.model_dump_json() + "\n")

        result = runner.invoke(app, ["view", str(trace_file), "--run", "1"])
        assert result.exit_code == 0
        assert "run_1" in result.stdout


class TestInfoCommand:
    """Tests for the info command."""

    def test_info_command_exists(self, runner: CliRunner) -> None:
        """Should have an info command."""
        from agenttrace.cli.main import app

        result = runner.invoke(app, ["info"])
        assert result.exit_code == 0

    def test_info_shows_version(self, runner: CliRunner) -> None:
        """Should show package version."""
        from agenttrace.cli.main import app

        result = runner.invoke(app, ["info"])
        assert result.exit_code == 0
        assert "0.1.0" in result.stdout or "version" in result.stdout.lower()

    def test_info_shows_exporters(self, runner: CliRunner) -> None:
        """Should list available exporters."""
        from agenttrace.cli.main import app

        result = runner.invoke(app, ["info"])
        assert result.exit_code == 0
        assert "console" in result.stdout.lower() or "exporter" in result.stdout.lower()


class TestStatsCommand:
    """Tests for the stats command."""

    def test_stats_command_exists(self, runner: CliRunner) -> None:
        """Should have a stats command."""
        from agenttrace.cli.main import app

        result = runner.invoke(app, ["stats", "--help"])
        assert result.exit_code == 0

    def test_stats_requires_file(self, runner: CliRunner) -> None:
        """Should require a file path."""
        from agenttrace.cli.main import app

        result = runner.invoke(app, ["stats"])
        assert result.exit_code != 0

    def test_stats_shows_summary(self, runner: CliRunner, tmp_path: Path) -> None:
        """Should show trace statistics."""
        from agenttrace.cli.main import app

        trace_file = tmp_path / "stats.jsonl"
        with trace_file.open("w") as f:
            for i in range(5):
                run = AgentRun(name=f"run_{i}", start_time=datetime.now(UTC))
                run.total_tokens = 100 * (i + 1)
                run.duration_ms = 1000.0 * (i + 1)
                f.write(run.model_dump_json() + "\n")

        result = runner.invoke(app, ["stats", str(trace_file)])
        assert result.exit_code == 0
        # Should show count
        assert "5" in result.stdout or "runs" in result.stdout.lower()


class TestExportCommand:
    """Tests for the export command."""

    def test_export_command_exists(self, runner: CliRunner) -> None:
        """Should have an export command."""
        from agenttrace.cli.main import app

        result = runner.invoke(app, ["export", "--help"])
        assert result.exit_code == 0

    def test_export_to_html(self, runner: CliRunner, sample_jsonl: Path, tmp_path: Path) -> None:
        """Should export trace to HTML."""
        from agenttrace.cli.main import app

        output_file = tmp_path / "output.html"
        result = runner.invoke(
            app, ["export", str(sample_jsonl), "--format", "html", "-o", str(output_file)]
        )
        assert result.exit_code == 0
        assert output_file.exists()
        content = output_file.read_text()
        assert "<html" in content.lower()

    def test_export_requires_file(self, runner: CliRunner) -> None:
        """Should require input file."""
        from agenttrace.cli.main import app

        result = runner.invoke(app, ["export"])
        assert result.exit_code != 0


class TestValidateCommand:
    """Tests for the validate command."""

    def test_validate_command_exists(self, runner: CliRunner) -> None:
        """Should have a validate command."""
        from agenttrace.cli.main import app

        result = runner.invoke(app, ["validate", "--help"])
        assert result.exit_code == 0

    def test_validate_valid_file(self, runner: CliRunner, sample_jsonl: Path) -> None:
        """Should validate a valid trace file."""
        from agenttrace.cli.main import app

        result = runner.invoke(app, ["validate", str(sample_jsonl)])
        assert result.exit_code == 0
        assert "valid" in result.stdout.lower()

    def test_validate_invalid_json(self, runner: CliRunner, tmp_path: Path) -> None:
        """Should report invalid JSON."""
        from agenttrace.cli.main import app

        invalid_file = tmp_path / "invalid.jsonl"
        invalid_file.write_text("not valid json\n")

        result = runner.invoke(app, ["validate", str(invalid_file)])
        assert result.exit_code != 0
        assert "invalid" in result.stdout.lower() or "error" in result.stdout.lower()

    def test_validate_missing_fields(self, runner: CliRunner, tmp_path: Path) -> None:
        """Should report missing required fields."""
        from agenttrace.cli.main import app

        invalid_file = tmp_path / "missing.jsonl"
        invalid_file.write_text('{"foo": "bar"}\n')

        result = runner.invoke(app, ["validate", str(invalid_file)])
        assert result.exit_code != 0


class TestErrorHandling:
    """Tests for error handling."""

    def test_handles_permission_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Should handle permission errors gracefully."""
        # This test is platform-dependent, skip if not possible
        import stat

        try:
            from agenttrace.cli.main import app

            # Create a directory without read permission
            protected_dir = tmp_path / "protected"
            protected_dir.mkdir()
            protected_file = protected_dir / "trace.jsonl"
            protected_file.write_text('{"name": "test"}\n')

            # Remove read permissions
            protected_file.chmod(0)

            result = runner.invoke(app, ["view", str(protected_file)])
            # Should fail gracefully
            assert result.exit_code != 0
        finally:
            # Restore permissions for cleanup
            if protected_file.exists():
                protected_file.chmod(stat.S_IRUSR | stat.S_IWUSR)


class TestOutputFormatting:
    """Tests for output formatting."""

    def test_view_tree_format(self, runner: CliRunner, tmp_path: Path) -> None:
        """Should display hierarchical steps in tree format."""
        from agenttrace.cli.main import app

        run = AgentRun(name="hierarchical_run", start_time=datetime.now(UTC))

        # Create nested steps
        parent_step = Step(
            trace_id=run.id,
            type=StepType.AGENT,
            name="parent_agent",
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            duration_ms=200.0,
        )

        child_step = Step(
            trace_id=run.id,
            type=StepType.LLM,
            name="child_llm",
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            duration_ms=100.0,
            parent_id=parent_step.id,
        )
        parent_step.children.append(child_step)

        run.steps.append(parent_step)
        run.end_time = datetime.now(UTC)
        run.duration_ms = 250.0

        trace_file = tmp_path / "hierarchical.jsonl"
        with trace_file.open("w") as f:
            f.write(run.model_dump_json() + "\n")

        result = runner.invoke(app, ["view", str(trace_file)])
        assert result.exit_code == 0
        assert "parent_agent" in result.stdout
        assert "child_llm" in result.stdout
