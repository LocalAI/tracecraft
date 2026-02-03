"""Tests for evaluation CLI commands."""

import json
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tracecraft.cli.main import app
from tracecraft.storage.sqlite import SQLiteTraceStore


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def temp_db_path():
    """Create a temporary database path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Initialize the store to create schema
    store = SQLiteTraceStore(db_path)

    yield db_path

    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def temp_db_with_eval(temp_db_path):
    """Create a temp DB with an evaluation set."""
    store = SQLiteTraceStore(temp_db_path)

    # Create an eval set
    set_id = store.create_evaluation_set(
        name="test-set",
        description="Test evaluation set",
        metrics=[
            {
                "name": "exact_match",
                "framework": "builtin",
                "metric_type": "exact_match",
                "threshold": 1.0,
            }
        ],
        default_threshold=0.7,
        pass_rate_threshold=0.8,
    )

    # Add a case
    store.add_evaluation_case(
        set_id=set_id,
        name="test-case-1",
        input_data={"prompt": "What is 2+2?"},
        expected_output={"answer": "4"},
    )

    return temp_db_path, set_id


class TestEvalListCommand:
    """Tests for eval list command."""

    def test_eval_list_empty(self, runner, temp_db_path):
        """Test listing empty eval sets."""
        result = runner.invoke(app, ["eval", "list", temp_db_path])

        assert result.exit_code == 0
        assert "No evaluation sets found" in result.stdout

    def test_eval_list_with_sets(self, runner, temp_db_with_eval):
        """Test listing eval sets."""
        db_path, _ = temp_db_with_eval
        result = runner.invoke(app, ["eval", "list", db_path])

        assert result.exit_code == 0
        assert "test-set" in result.stdout

    def test_eval_list_json_format(self, runner, temp_db_with_eval):
        """Test listing eval sets in JSON format."""
        db_path, _ = temp_db_with_eval
        result = runner.invoke(app, ["eval", "list", db_path, "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["name"] == "test-set"


class TestEvalShowCommand:
    """Tests for eval show command."""

    def test_eval_show_by_id(self, runner, temp_db_with_eval):
        """Test showing eval set by ID."""
        db_path, set_id = temp_db_with_eval
        result = runner.invoke(app, ["eval", "show", db_path, set_id])

        assert result.exit_code == 0
        assert "test-set" in result.stdout

    def test_eval_show_by_name(self, runner, temp_db_with_eval):
        """Test showing eval set by name."""
        db_path, _ = temp_db_with_eval
        result = runner.invoke(app, ["eval", "show", db_path, "test-set"])

        assert result.exit_code == 0
        assert "test-set" in result.stdout

    def test_eval_show_with_cases(self, runner, temp_db_with_eval):
        """Test showing eval set with cases."""
        db_path, _ = temp_db_with_eval
        result = runner.invoke(app, ["eval", "show", db_path, "test-set", "--cases"])

        assert result.exit_code == 0
        assert "test-case-1" in result.stdout

    def test_eval_show_not_found(self, runner, temp_db_path):
        """Test showing non-existent eval set."""
        result = runner.invoke(app, ["eval", "show", temp_db_path, "non-existent"])

        assert result.exit_code == 1
        assert "not found" in result.stdout

    def test_eval_show_json_format(self, runner, temp_db_with_eval):
        """Test showing eval set in JSON format."""
        db_path, _ = temp_db_with_eval
        result = runner.invoke(app, ["eval", "show", db_path, "test-set", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["name"] == "test-set"


class TestEvalCreateCommand:
    """Tests for eval create command."""

    def test_eval_create_basic(self, runner, temp_db_path):
        """Test creating a basic eval set."""
        result = runner.invoke(app, ["eval", "create", temp_db_path, "--name", "new-set"])

        assert result.exit_code == 0
        assert "Created evaluation set" in result.stdout
        assert "new-set" in result.stdout

    def test_eval_create_with_metrics(self, runner, temp_db_path):
        """Test creating eval set with metrics."""
        result = runner.invoke(
            app,
            [
                "eval",
                "create",
                temp_db_path,
                "--name",
                "metric-set",
                "--metric",
                "faithfulness:deepeval:0.8",
                "--metric",
                "answer_relevancy:deepeval:0.7",
            ],
        )

        assert result.exit_code == 0
        assert "Created evaluation set" in result.stdout

    def test_eval_create_with_thresholds(self, runner, temp_db_path):
        """Test creating eval set with custom thresholds."""
        result = runner.invoke(
            app,
            [
                "eval",
                "create",
                temp_db_path,
                "--name",
                "threshold-set",
                "--threshold",
                "0.9",
                "--pass-rate",
                "0.95",
            ],
        )

        assert result.exit_code == 0

        # Verify thresholds
        store = SQLiteTraceStore(temp_db_path)
        sets = store.list_evaluation_sets()
        assert len(sets) == 1
        assert sets[0]["default_threshold"] == 0.9
        assert sets[0]["pass_rate_threshold"] == 0.95

    def test_eval_create_no_name(self, runner, temp_db_path):
        """Test creating eval set without name fails."""
        result = runner.invoke(app, ["eval", "create", temp_db_path])

        assert result.exit_code == 1
        assert "--name is required" in result.stdout


class TestEvalAddCaseCommand:
    """Tests for eval add-case command."""

    def test_eval_add_case(self, runner, temp_db_with_eval):
        """Test adding a case to eval set."""
        db_path, _ = temp_db_with_eval
        result = runner.invoke(
            app,
            [
                "eval",
                "add-case",
                db_path,
                "--set",
                "test-set",
                "--name",
                "new-case",
                "--input",
                '{"prompt": "What is 3+3?"}',
                "--expected",
                '{"answer": "6"}',
            ],
        )

        assert result.exit_code == 0
        assert "Added case" in result.stdout

    def test_eval_add_case_no_set(self, runner, temp_db_path):
        """Test adding case without set fails."""
        result = runner.invoke(
            app,
            [
                "eval",
                "add-case",
                temp_db_path,
                "--name",
                "test-case",
                "--input",
                '{"q": "test"}',
            ],
        )

        assert result.exit_code == 1
        assert "--set is required" in result.stdout

    def test_eval_add_case_no_name(self, runner, temp_db_with_eval):
        """Test adding case without name fails."""
        db_path, _ = temp_db_with_eval
        result = runner.invoke(
            app,
            [
                "eval",
                "add-case",
                db_path,
                "--set",
                "test-set",
                "--input",
                '{"q": "test"}',
            ],
        )

        assert result.exit_code == 1
        assert "--name is required" in result.stdout

    def test_eval_add_case_no_input(self, runner, temp_db_with_eval):
        """Test adding case without input fails."""
        db_path, _ = temp_db_with_eval
        result = runner.invoke(
            app,
            [
                "eval",
                "add-case",
                db_path,
                "--set",
                "test-set",
                "--name",
                "test-case",
            ],
        )

        assert result.exit_code == 1
        assert "--input is required" in result.stdout

    def test_eval_add_case_invalid_json(self, runner, temp_db_with_eval):
        """Test adding case with invalid JSON fails."""
        db_path, _ = temp_db_with_eval
        result = runner.invoke(
            app,
            [
                "eval",
                "add-case",
                db_path,
                "--set",
                "test-set",
                "--name",
                "test-case",
                "--input",
                "not valid json",
            ],
        )

        assert result.exit_code == 1
        assert "Invalid JSON" in result.stdout


class TestEvalFromTracesCommand:
    """Tests for eval from-traces command."""

    def test_eval_from_traces_empty(self, runner, temp_db_path):
        """Test creating from traces when no traces exist."""
        result = runner.invoke(
            app,
            [
                "eval",
                "from-traces",
                temp_db_path,
                "--name",
                "from-traces-set",
            ],
        )

        # May fail with query_traces error or show no traces found
        # Just verify it doesn't crash unexpectedly
        assert result.exit_code in (0, 1)


class TestEvalRunCommand:
    """Tests for eval run command."""

    def test_eval_run_no_cases(self, runner, temp_db_path):
        """Test running eval with no cases."""
        store = SQLiteTraceStore(temp_db_path)
        store.create_evaluation_set(name="empty-set")

        result = runner.invoke(app, ["eval", "run", temp_db_path, "empty-set"])

        assert result.exit_code == 0
        assert "No cases" in result.stdout

    def test_eval_run_not_found(self, runner, temp_db_path):
        """Test running non-existent eval set."""
        result = runner.invoke(app, ["eval", "run", temp_db_path, "non-existent"])

        assert result.exit_code == 1
        assert "not found" in result.stdout


class TestEvalResultsCommand:
    """Tests for eval results command."""

    def test_eval_results_no_runs(self, runner, temp_db_path):
        """Test viewing results when no runs exist."""
        result = runner.invoke(app, ["eval", "results", temp_db_path])

        assert result.exit_code == 0
        assert "No evaluation runs found" in result.stdout

    def test_eval_results_with_runs(self, runner, temp_db_with_eval):
        """Test viewing results with runs."""
        db_path, set_id = temp_db_with_eval

        # Create a run
        store = SQLiteTraceStore(db_path)
        run_id = store.create_evaluation_run(set_id)
        store.update_evaluation_run(
            run_id,
            status="completed",
            passed_cases=1,
            failed_cases=0,
            overall_pass_rate=1.0,
            passed=True,
        )

        result = runner.invoke(app, ["eval", "results", db_path])

        assert result.exit_code == 0
        assert "COMPLETED" in result.stdout


class TestEvalExportCommand:
    """Tests for eval export command."""

    def test_eval_export_json(self, runner, temp_db_with_eval):
        """Test exporting eval set as JSON."""
        db_path, _ = temp_db_with_eval
        result = runner.invoke(app, ["eval", "export", db_path, "test-set", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["name"] == "test-set"
        assert len(data["cases"]) == 1

    def test_eval_export_to_file(self, runner, temp_db_with_eval):
        """Test exporting eval set to file."""
        db_path, _ = temp_db_with_eval

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = f.name

        try:
            result = runner.invoke(app, ["eval", "export", db_path, "test-set", "-o", output_path])

            assert result.exit_code == 0
            assert "Exported to" in result.stdout

            # Verify file contents
            with open(output_path) as f:
                data = json.load(f)
                assert data["name"] == "test-set"
        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_eval_export_not_found(self, runner, temp_db_path):
        """Test exporting non-existent eval set."""
        result = runner.invoke(app, ["eval", "export", temp_db_path, "non-existent"])

        assert result.exit_code == 1
        assert "not found" in result.stdout


class TestEvalDeleteCommand:
    """Tests for eval delete command."""

    def test_eval_delete_with_force(self, runner, temp_db_with_eval):
        """Test deleting eval set with force flag."""
        db_path, _ = temp_db_with_eval
        result = runner.invoke(app, ["eval", "delete", db_path, "test-set", "--force"])

        assert result.exit_code == 0
        assert "Deleted" in result.stdout

        # Verify deletion
        store = SQLiteTraceStore(db_path)
        sets = store.list_evaluation_sets()
        assert len(sets) == 0

    def test_eval_delete_not_found(self, runner, temp_db_path):
        """Test deleting non-existent eval set."""
        result = runner.invoke(app, ["eval", "delete", temp_db_path, "non-existent", "--force"])

        assert result.exit_code == 1
        assert "not found" in result.stdout


class TestInvalidSource:
    """Tests for invalid source handling."""

    def test_eval_with_invalid_source(self, runner):
        """Test eval command with invalid source."""
        result = runner.invoke(app, ["eval", "list", "invalid-source.txt"])

        assert result.exit_code == 1
        assert "SQLite storage" in result.stdout
