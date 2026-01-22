"""
MLflow storage backend for AgentTrace.

Supports bidirectional trace storage:
- Write: Export traces to MLflow (via MLflowExporter)
- Read: Query traces from MLflow (via search_traces)
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agenttrace.storage.base import BaseTraceStore, TraceQuery

if TYPE_CHECKING:
    from agenttrace.core.models import AgentRun

logger = logging.getLogger(__name__)


class MLflowTraceStore(BaseTraceStore):
    """
    MLflow-based trace storage.

    Reads and writes traces to MLflow Tracking Server.

    Features:
    - Query traces with filter DSL
    - Pagination support
    - Automatic experiment management
    - Bidirectional sync with TUI

    Example:
        from agenttrace.storage.mlflow import MLflowTraceStore

        store = MLflowTraceStore(
            tracking_uri="http://localhost:5000",
            experiment_name="my_agents"
        )

        # Query traces
        traces = store.query(TraceQuery(has_error=True))

        # Search with custom filter
        traces = store.search("status = 'ERROR' AND execution_time_ms > 1000")
    """

    def __init__(
        self,
        tracking_uri: str | None = None,
        experiment_name: str | None = None,
        experiment_ids: list[str] | None = None,
    ) -> None:
        """
        Initialize MLflow storage.

        Args:
            tracking_uri: MLflow tracking server URI.
            experiment_name: Experiment name to query.
            experiment_ids: Specific experiment IDs (overrides experiment_name).
        """
        try:
            import mlflow

            self._mlflow = mlflow
        except ImportError:
            raise ImportError("mlflow required. Install with: pip install agenttrace[mlflow]")

        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)

        self.experiment_name = experiment_name
        self.experiment_ids = experiment_ids

        # Get experiment IDs if name provided
        if experiment_name and not experiment_ids:
            experiment = mlflow.get_experiment_by_name(experiment_name)
            if experiment:
                self.experiment_ids = [experiment.experiment_id]

    def save(self, run: AgentRun) -> None:
        """
        Save trace to MLflow.

        Creates an MLflow run with metrics, tags, and the full trace as an artifact.
        """
        # Set experiment if specified
        if self.experiment_name:
            self._mlflow.set_experiment(self.experiment_name)

        with self._mlflow.start_run(run_name=run.name):
            # Log metrics
            if run.duration_ms is not None:
                self._mlflow.log_metric("duration_ms", run.duration_ms)
            self._mlflow.log_metric("total_tokens", run.total_tokens)
            self._mlflow.log_metric("total_cost_usd", run.total_cost_usd)
            self._mlflow.log_metric("error_count", run.error_count)

            # Log tags for searchability
            self._mlflow.set_tag("agenttrace.run_id", str(run.id))
            self._mlflow.set_tag("agenttrace.name", run.name)
            if run.environment:
                self._mlflow.set_tag("agenttrace.environment", run.environment)
            if run.session_id:
                self._mlflow.set_tag("agenttrace.session_id", run.session_id)
            if run.user_id:
                self._mlflow.set_tag("agenttrace.user_id", run.user_id)
            if run.error:
                self._mlflow.set_tag("agenttrace.has_error", "true")
            for tag in run.tags:
                self._mlflow.set_tag(f"agenttrace.tag.{tag}", "true")

            # Log full trace as artifact
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                f.write(run.model_dump_json(indent=2))
                temp_path = f.name

            self._mlflow.log_artifact(temp_path, artifact_path="")
            # Rename to trace.json
            Path(temp_path).unlink()

    def get(self, trace_id: str) -> AgentRun | None:
        """
        Get trace by ID.

        Searches for MLflow run with matching agenttrace.run_id tag.
        """
        filter_string = f"tags.`agenttrace.run_id` = '{trace_id}'"

        try:
            runs = self._mlflow.search_runs(
                experiment_ids=self.experiment_ids,
                filter_string=filter_string,
                max_results=1,
            )

            if runs.empty:
                return None

            # Load trace from artifact
            mlflow_run_id = runs.iloc[0]["run_id"]
            return self._load_trace_artifact(mlflow_run_id)

        except Exception as e:
            logger.warning(f"Failed to get trace {trace_id}: {e}")
            return None

    def query(self, query: TraceQuery) -> list[AgentRun]:
        """Query traces with filters."""
        filter_parts: list[str] = []

        if query.name:
            filter_parts.append(f"tags.`agenttrace.name` = '{query.name}'")

        if query.name_contains:
            filter_parts.append(f"tags.`agenttrace.name` LIKE '%{query.name_contains}%'")

        if query.has_error is not None:
            if query.has_error:
                filter_parts.append("metrics.error_count > 0")
            else:
                filter_parts.append("metrics.error_count = 0")

        if query.min_duration_ms is not None:
            filter_parts.append(f"metrics.duration_ms >= {query.min_duration_ms}")

        if query.max_duration_ms is not None:
            filter_parts.append(f"metrics.duration_ms <= {query.max_duration_ms}")

        if query.min_cost_usd is not None:
            filter_parts.append(f"metrics.total_cost_usd >= {query.min_cost_usd}")

        if query.max_cost_usd is not None:
            filter_parts.append(f"metrics.total_cost_usd <= {query.max_cost_usd}")

        if query.environment:
            filter_parts.append(f"tags.`agenttrace.environment` = '{query.environment}'")

        if query.session_id:
            filter_parts.append(f"tags.`agenttrace.session_id` = '{query.session_id}'")

        if query.user_id:
            filter_parts.append(f"tags.`agenttrace.user_id` = '{query.user_id}'")

        filter_string = " AND ".join(filter_parts) if filter_parts else ""

        # Order mapping
        order_col = {
            "start_time": "start_time",
            "duration_ms": "metrics.duration_ms",
            "total_cost_usd": "metrics.total_cost_usd",
        }.get(query.order_by, "start_time")

        order_by = [f"{order_col} {'DESC' if query.order_desc else 'ASC'}"]

        try:
            runs = self._mlflow.search_runs(
                experiment_ids=self.experiment_ids,
                filter_string=filter_string,
                order_by=order_by,
                max_results=query.limit + query.offset,
            )

            # Apply offset (MLflow doesn't support offset directly)
            runs = runs.iloc[query.offset : query.offset + query.limit]

            # Load trace artifacts
            traces = []
            for _, row in runs.iterrows():
                trace = self._load_trace_artifact(row["run_id"])
                if trace:
                    traces.append(trace)

            return traces

        except Exception as e:
            logger.warning(f"Failed to query traces: {e}")
            return []

    def list_all(self, limit: int = 100, offset: int = 0) -> list[AgentRun]:
        """List all traces."""
        return self.query(TraceQuery(limit=limit, offset=offset))

    def delete(self, trace_id: str) -> bool:
        """Delete trace by ID."""
        filter_string = f"tags.`agenttrace.run_id` = '{trace_id}'"

        try:
            runs = self._mlflow.search_runs(
                experiment_ids=self.experiment_ids,
                filter_string=filter_string,
                max_results=1,
            )

            if runs.empty:
                return False

            mlflow_run_id = runs.iloc[0]["run_id"]
            self._mlflow.delete_run(mlflow_run_id)
            return True

        except Exception as e:
            logger.warning(f"Failed to delete trace {trace_id}: {e}")
            return False

    def count(self, query: TraceQuery | None = None) -> int:
        """Count traces."""
        # MLflow doesn't have a count API, so we query with high limit
        if query is None:
            q = TraceQuery(limit=10000)
        else:
            q = TraceQuery(
                name=query.name,
                name_contains=query.name_contains,
                has_error=query.has_error,
                min_duration_ms=query.min_duration_ms,
                max_duration_ms=query.max_duration_ms,
                min_cost_usd=query.min_cost_usd,
                max_cost_usd=query.max_cost_usd,
                session_id=query.session_id,
                user_id=query.user_id,
                environment=query.environment,
                limit=10000,
            )

        return len(self.query(q))

    def _load_trace_artifact(self, mlflow_run_id: str) -> AgentRun | None:
        """Load AgentRun from MLflow artifact."""
        from agenttrace.core.models import AgentRun

        try:
            # Download artifact - try different possible names
            for artifact_name in ["trace.json", "agenttrace.json"]:
                try:
                    artifact_path = self._mlflow.artifacts.download_artifacts(
                        run_id=mlflow_run_id,
                        artifact_path=artifact_name,
                    )
                    with open(artifact_path) as f:
                        data = json.load(f)
                    return AgentRun.model_validate(data)
                except Exception:  # nosec B112 - intentional fallback
                    continue

            # Try listing artifacts to find the trace file
            client = self._mlflow.MlflowClient()
            artifacts = client.list_artifacts(mlflow_run_id)
            for artifact in artifacts:
                if artifact.path.endswith(".json"):
                    artifact_path = self._mlflow.artifacts.download_artifacts(
                        run_id=mlflow_run_id,
                        artifact_path=artifact.path,
                    )
                    with open(artifact_path) as f:
                        data = json.load(f)
                    return AgentRun.model_validate(data)

            logger.debug(f"No trace artifact found for run {mlflow_run_id}")
            return None

        except Exception as e:
            logger.debug(f"Failed to load trace artifact for {mlflow_run_id}: {e}")
            return None

    def search(self, filter_string: str) -> list[AgentRun]:
        """
        Search traces with raw MLflow filter DSL.

        For advanced queries not supported by TraceQuery.

        Example:
            traces = store.search(
                "metrics.duration_ms > 1000 AND tags.`agenttrace.name` LIKE '%research%'"
            )
        """
        try:
            runs = self._mlflow.search_runs(
                experiment_ids=self.experiment_ids,
                filter_string=filter_string,
            )

            traces = []
            for _, row in runs.iterrows():
                trace = self._load_trace_artifact(row["run_id"])
                if trace:
                    traces.append(trace)

            return traces

        except Exception as e:
            logger.warning(f"Failed to search traces: {e}")
            return []

    def get_experiments(self) -> list[dict[str, Any]]:
        """List available experiments."""
        experiments = self._mlflow.search_experiments()
        return [
            {
                "id": exp.experiment_id,
                "name": exp.name,
                "artifact_location": exp.artifact_location,
            }
            for exp in experiments
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        count = self.count()

        # Get aggregate metrics
        try:
            runs = self._mlflow.search_runs(
                experiment_ids=self.experiment_ids,
                max_results=10000,
            )

            if runs.empty:
                return {
                    "trace_count": 0,
                    "total_tokens": 0,
                    "total_cost_usd": 0.0,
                }

            total_tokens = (
                runs["metrics.total_tokens"].sum() if "metrics.total_tokens" in runs.columns else 0
            )
            total_cost = (
                runs["metrics.total_cost_usd"].sum()
                if "metrics.total_cost_usd" in runs.columns
                else 0.0
            )

            return {
                "trace_count": count,
                "total_tokens": int(total_tokens),
                "total_cost_usd": float(total_cost),
            }

        except Exception as e:
            logger.warning(f"Failed to get stats: {e}")
            return {"trace_count": count}
