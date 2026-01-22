"""Tests for MLflow exporter."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from agenttrace.core.models import AgentRun, Step, StepType


@pytest.fixture
def sample_run() -> AgentRun:
    """Create a sample AgentRun for testing."""
    run = AgentRun(
        name="test_run",
        start_time=datetime.now(UTC),
        description="Test run description",
        session_id="session-123",
        user_id="user-456",
        tags=["test", "unit"],
    )

    step = Step(
        trace_id=run.id,
        type=StepType.LLM,
        name="test_llm",
        start_time=datetime.now(UTC),
        model_name="gpt-4o",
        model_provider="openai",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.01,
        duration_ms=500.0,
    )
    step.end_time = datetime.now(UTC)
    run.steps.append(step)

    run.end_time = datetime.now(UTC)
    run.duration_ms = 1000.0
    run.total_tokens = 150
    run.total_cost_usd = 0.01

    return run


class TestMLflowExporterInit:
    """Tests for MLflowExporter initialization."""

    def test_init_without_mlflow_installed(self):
        """Test graceful handling when MLflow not installed."""
        with patch.dict("sys.modules", {"mlflow": None}):
            # Re-import to test with mlflow unavailable
            from importlib import reload

            from agenttrace.exporters import mlflow as mlflow_module

            reload(mlflow_module)

    def test_init_with_mlflow_mock(self):
        """Test initialization with mocked MLflow."""
        mock_mlflow = MagicMock()

        with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
            from agenttrace.exporters.mlflow import MLflowExporter

            exporter = MLflowExporter(
                tracking_uri="http://localhost:5000",
                experiment_name="test-experiment",
            )

            assert exporter.tracking_uri == "http://localhost:5000"
            assert exporter.experiment_name == "test-experiment"
            assert exporter.log_artifacts is True
            assert exporter.log_input_output is True


class TestMLflowExport:
    """Tests for MLflow export functionality."""

    def test_export_with_mock_mlflow(self, sample_run: AgentRun):
        """Test exporting a run with mocked MLflow."""
        mock_mlflow = MagicMock()
        mock_run_context = MagicMock()
        mock_run_context.__enter__ = MagicMock(
            return_value=MagicMock(info=MagicMock(run_id="test-run-id"))
        )
        mock_run_context.__exit__ = MagicMock(return_value=False)
        mock_mlflow.start_run.return_value = mock_run_context

        with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
            from agenttrace.exporters.mlflow import MLflowExporter

            exporter = MLflowExporter(experiment_name="test")
            exporter._mlflow = mock_mlflow
            exporter._has_tracing = False  # Use fallback path

            exporter.export(sample_run)

            # Verify MLflow was called
            mock_mlflow.start_run.assert_called_once()
            mock_mlflow.log_param.assert_called()
            mock_mlflow.log_metric.assert_called()

    def test_export_logs_parameters(self, sample_run: AgentRun):
        """Test that run parameters are logged."""
        mock_mlflow = MagicMock()
        mock_run_context = MagicMock()
        mock_run_context.__enter__ = MagicMock(
            return_value=MagicMock(info=MagicMock(run_id="test-run-id"))
        )
        mock_run_context.__exit__ = MagicMock(return_value=False)
        mock_mlflow.start_run.return_value = mock_run_context

        with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
            from agenttrace.exporters.mlflow import MLflowExporter

            exporter = MLflowExporter()
            exporter._mlflow = mock_mlflow
            exporter._has_tracing = False

            exporter.export(sample_run)

            # Check parameters were logged
            param_calls = {call[0][0]: call[0][1] for call in mock_mlflow.log_param.call_args_list}
            assert "agenttrace.run_id" in param_calls
            assert "agenttrace.name" in param_calls
            assert param_calls["agenttrace.name"] == "test_run"

    def test_export_logs_metrics(self, sample_run: AgentRun):
        """Test that run metrics are logged."""
        mock_mlflow = MagicMock()
        mock_run_context = MagicMock()
        mock_run_context.__enter__ = MagicMock(
            return_value=MagicMock(info=MagicMock(run_id="test-run-id"))
        )
        mock_run_context.__exit__ = MagicMock(return_value=False)
        mock_mlflow.start_run.return_value = mock_run_context

        with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
            from agenttrace.exporters.mlflow import MLflowExporter

            exporter = MLflowExporter()
            exporter._mlflow = mock_mlflow
            exporter._has_tracing = False

            exporter.export(sample_run)

            # Check metrics were logged
            metric_calls = {
                call[0][0]: call[0][1] for call in mock_mlflow.log_metric.call_args_list
            }
            assert "duration_ms" in metric_calls
            assert "total_tokens" in metric_calls
            assert "total_cost_usd" in metric_calls

    def test_export_when_mlflow_not_available(self, sample_run: AgentRun):
        """Test export does nothing when MLflow not available."""
        from agenttrace.exporters.mlflow import MLflowExporter

        exporter = MLflowExporter()
        exporter._mlflow = None

        # Should not raise
        exporter.export(sample_run)


class TestMLflowExporterHelpers:
    """Tests for MLflowExporter helper methods."""

    def test_count_steps(self):
        """Test step counting including children."""
        from agenttrace.exporters.mlflow import MLflowExporter

        exporter = MLflowExporter()
        exporter._mlflow = MagicMock()

        # Create steps with children
        child_step = Step(
            trace_id=uuid4(),
            type=StepType.TOOL,
            name="child",
            start_time=datetime.now(UTC),
        )

        parent_step = Step(
            trace_id=uuid4(),
            type=StepType.AGENT,
            name="parent",
            start_time=datetime.now(UTC),
            children=[child_step],
        )

        count = exporter._count_steps([parent_step])
        assert count == 2  # parent + child

    def test_close_does_nothing(self):
        """Test close method doesn't raise."""
        from agenttrace.exporters.mlflow import MLflowExporter

        exporter = MLflowExporter()
        exporter._mlflow = MagicMock()

        # Should not raise
        exporter.close()


class TestCreateMLflowExporter:
    """Tests for the convenience factory function."""

    def test_create_mlflow_exporter_returns_exporter(self):
        """Test factory function returns MLflowExporter."""
        from agenttrace.exporters.mlflow import create_mlflow_exporter

        exporter = create_mlflow_exporter(
            tracking_uri="http://localhost:5000",
            experiment_name="test",
        )

        assert exporter.tracking_uri == "http://localhost:5000"
        assert exporter.experiment_name == "test"

    def test_create_mlflow_exporter_with_kwargs(self):
        """Test factory function passes kwargs."""
        from agenttrace.exporters.mlflow import create_mlflow_exporter

        exporter = create_mlflow_exporter(
            experiment_name="test",
            log_artifacts=False,
            log_input_output=False,
        )

        assert exporter.log_artifacts is False
        assert exporter.log_input_output is False
