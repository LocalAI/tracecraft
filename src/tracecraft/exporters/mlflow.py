"""
MLflow exporter for trace storage and analysis.

Exports TraceCraft runs to MLflow Tracking for visualization,
experiment comparison, and evaluation workflows.
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tracecraft.exporters.base import BaseExporter

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun, Step

logger = logging.getLogger(__name__)


class MLflowExporter(BaseExporter):
    """
    Exports traces to MLflow Tracking.

    Creates MLflow runs with nested spans representing the trace hierarchy
    using MLflow's native tracing API (MLflow 2.14+). Falls back to logging
    metrics/artifacts for older MLflow versions.

    Example:
        ```python
        from tracecraft.exporters.mlflow import MLflowExporter
        import tracecraft

        mlflow_exporter = MLflowExporter(
            tracking_uri="http://localhost:5000",
            experiment_name="my-agent-traces"
        )
        tracecraft.init(exporters=[mlflow_exporter])
        ```
    """

    def __init__(
        self,
        tracking_uri: str | None = None,
        experiment_name: str = "tracecraft",
        run_name_prefix: str = "",
        log_artifacts: bool = True,
        log_input_output: bool = True,
    ) -> None:
        """
        Initialize MLflow exporter.

        Args:
            tracking_uri: MLflow tracking server URI. If None, uses
                         MLFLOW_TRACKING_URI env var or local file store.
            experiment_name: MLflow experiment name.
            run_name_prefix: Prefix for MLflow run names.
            log_artifacts: Whether to log trace JSON as artifact.
            log_input_output: Whether to log input/output as artifacts.
        """
        self.tracking_uri = tracking_uri
        self.experiment_name = experiment_name
        self.run_name_prefix = run_name_prefix
        self.log_artifacts = log_artifacts
        self.log_input_output = log_input_output

        self._mlflow: Any = None
        self._has_tracing = False
        self._setup_mlflow()

    def _setup_mlflow(self) -> None:
        """Initialize MLflow client and check for tracing support."""
        try:
            import mlflow

            self._mlflow = mlflow

            if self.tracking_uri:
                mlflow.set_tracking_uri(self.tracking_uri)

            mlflow.set_experiment(self.experiment_name)

            # Check if MLflow Tracing is available (MLflow 2.14+)
            try:
                from mlflow import start_span  # noqa: F401

                self._has_tracing = True
                logger.debug("MLflow Tracing API available")
            except ImportError:
                self._has_tracing = False
                logger.debug("MLflow Tracing API not available, using fallback")

        except ImportError:
            logger.warning("mlflow not installed. Install with: pip install tracecraft[mlflow]")

    def export(self, run: AgentRun) -> None:
        """
        Export an AgentRun to MLflow.

        Creates an MLflow run with:
        - Run-level parameters (run_id, name, session_id, user_id)
        - Run-level metrics (duration, tokens, cost, error_count)
        - Tags from the AgentRun
        - Steps as spans (if MLflow Tracing available) or metrics
        - Full trace JSON as artifact (if enabled)

        Args:
            run: The AgentRun to export.
        """
        if self._mlflow is None:
            return

        run_name = f"{self.run_name_prefix}{run.name}"

        try:
            with self._mlflow.start_run(run_name=run_name) as mlflow_run:
                self._log_run_params(run)
                self._log_run_metrics(run)
                self._log_run_tags(run)

                # Export steps
                if self._has_tracing:
                    self._export_steps_with_tracing(run.steps)
                else:
                    self._export_steps_as_metrics(run.steps)

                # Log artifacts
                if self.log_artifacts:
                    self._log_trace_artifact(run)

                if self.log_input_output:
                    self._log_io_artifacts(run)

                logger.debug(
                    "Exported run '%s' to MLflow run '%s'",
                    run.name,
                    mlflow_run.info.run_id,
                )

        except Exception:
            logger.exception("Failed to export run '%s' to MLflow", run.name)

    def _log_run_params(self, run: AgentRun) -> None:
        """Log run-level parameters."""
        self._mlflow.log_param("tracecraft.run_id", str(run.id))
        self._mlflow.log_param("tracecraft.name", run.name)

        if run.description:
            self._mlflow.log_param("tracecraft.description", run.description[:250])
        if run.session_id:
            self._mlflow.log_param("session_id", run.session_id)
        if run.user_id:
            self._mlflow.log_param("user_id", run.user_id)

    def _log_run_metrics(self, run: AgentRun) -> None:
        """Log run-level metrics."""
        if run.duration_ms is not None:
            self._mlflow.log_metric("duration_ms", run.duration_ms)
        if run.total_tokens is not None:
            self._mlflow.log_metric("total_tokens", run.total_tokens)
        if run.total_cost_usd is not None:
            self._mlflow.log_metric("total_cost_usd", run.total_cost_usd)
        if run.error_count is not None:
            self._mlflow.log_metric("error_count", run.error_count)

        # Log step count
        step_count = self._count_steps(run.steps)
        self._mlflow.log_metric("step_count", step_count)

    def _count_steps(self, steps: list[Step]) -> int:
        """Count total steps including children."""
        count = len(steps)
        for step in steps:
            count += self._count_steps(step.children)
        return count

    def _log_run_tags(self, run: AgentRun) -> None:
        """Log run tags."""
        for tag in run.tags:
            # MLflow tag names have restrictions, sanitize
            safe_tag = tag.replace(" ", "_").replace(":", "_")[:250]
            self._mlflow.set_tag(f"tracecraft.tag.{safe_tag}", "true")

        # Log if there was an error
        if run.error:
            self._mlflow.set_tag("tracecraft.has_error", "true")
            self._mlflow.set_tag("tracecraft.error_type", run.error_type or "Unknown")

    def _export_steps_with_tracing(self, steps: list[Step]) -> None:
        """Export steps using MLflow Tracing API (MLflow 2.14+)."""
        try:
            for step in steps:
                with self._mlflow.start_span(name=step.name) as span:
                    # Set span attributes
                    span.set_attribute("tracecraft.step.id", str(step.id))
                    span.set_attribute("tracecraft.step.type", step.type.value)

                    if step.model_name:
                        span.set_attribute("model", step.model_name)
                    if step.model_provider:
                        span.set_attribute("provider", step.model_provider)
                    if step.input_tokens:
                        span.set_attribute("input_tokens", step.input_tokens)
                    if step.output_tokens:
                        span.set_attribute("output_tokens", step.output_tokens)
                    if step.cost_usd:
                        span.set_attribute("cost_usd", step.cost_usd)
                    if step.duration_ms:
                        span.set_attribute("duration_ms", step.duration_ms)
                    if step.error:
                        span.set_attribute("error", step.error)
                        span.set_attribute("error_type", step.error_type or "Unknown")

                    # Recursively handle children within this span context
                    if step.children:
                        self._export_steps_with_tracing(step.children)

        except Exception:
            logger.exception("Error using MLflow Tracing, falling back to metrics")
            self._export_steps_as_metrics(steps)

    def _export_steps_as_metrics(self, steps: list[Step], prefix: str = "", depth: int = 0) -> None:
        """
        Fall back: log steps as metrics.

        Used when MLflow Tracing is not available.
        """
        for i, step in enumerate(steps):
            step_prefix = f"{prefix}step_{depth}_{i}_"

            # Log step metrics
            if step.duration_ms:
                self._mlflow.log_metric(f"{step_prefix}duration_ms", step.duration_ms)
            if step.input_tokens:
                self._mlflow.log_metric(f"{step_prefix}input_tokens", step.input_tokens)
            if step.output_tokens:
                self._mlflow.log_metric(f"{step_prefix}output_tokens", step.output_tokens)
            if step.cost_usd:
                self._mlflow.log_metric(f"{step_prefix}cost_usd", step.cost_usd)

            # Log step type as tag
            self._mlflow.set_tag(f"{step_prefix}type", step.type.value)
            self._mlflow.set_tag(f"{step_prefix}name", step.name[:250])

            if step.model_name:
                self._mlflow.set_tag(f"{step_prefix}model", step.model_name)

            if step.error:
                self._mlflow.set_tag(f"{step_prefix}has_error", "true")

            # Recursively process children
            if step.children:
                self._export_steps_as_metrics(step.children, prefix=step_prefix, depth=depth + 1)

    def _log_trace_artifact(self, run: AgentRun) -> None:
        """Log full trace as JSON artifact."""
        try:
            trace_data = run.model_dump(mode="json")

            with tempfile.TemporaryDirectory() as tmpdir:
                filepath = Path(tmpdir) / "trace.json"
                with open(filepath, "w") as f:
                    json.dump(trace_data, f, indent=2, default=str)
                self._mlflow.log_artifact(str(filepath), artifact_path="tracecraft")

        except Exception:
            logger.exception("Failed to log trace artifact")

    def _log_io_artifacts(self, run: AgentRun) -> None:
        """Log input and output as separate artifacts."""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmppath = Path(tmpdir)

                # Log input
                if run.input is not None:
                    input_path = tmppath / "input.json"
                    with open(input_path, "w") as f:
                        json.dump(run.input, f, indent=2, default=str)
                    self._mlflow.log_artifact(str(input_path), artifact_path="tracecraft")

                # Log output
                if run.output is not None:
                    output_path = tmppath / "output.json"
                    with open(output_path, "w") as f:
                        json.dump(run.output, f, indent=2, default=str)
                    self._mlflow.log_artifact(str(output_path), artifact_path="tracecraft")

        except Exception:
            logger.exception("Failed to log I/O artifacts")

    def close(self) -> None:
        """Close MLflow exporter."""
        # MLflow handles cleanup automatically
        pass


def create_mlflow_exporter(
    tracking_uri: str | None = None,
    experiment_name: str = "tracecraft",
    **kwargs: Any,
) -> MLflowExporter:
    """
    Create an MLflow exporter with common defaults.

    Convenience function for creating an MLflow exporter.

    Args:
        tracking_uri: MLflow tracking URI.
        experiment_name: MLflow experiment name.
        **kwargs: Additional arguments passed to MLflowExporter.

    Returns:
        Configured MLflowExporter.

    Example:
        ```python
        from tracecraft.exporters.mlflow import create_mlflow_exporter
        import tracecraft

        exporter = create_mlflow_exporter(
            tracking_uri="http://localhost:5000",
            experiment_name="my-llm-agent"
        )
        tracecraft.init(exporters=[exporter])
        ```
    """
    return MLflowExporter(
        tracking_uri=tracking_uri,
        experiment_name=experiment_name,
        **kwargs,
    )
