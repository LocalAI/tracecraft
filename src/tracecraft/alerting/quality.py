"""
Quality score monitoring for TraceCraft.

Track quality metrics and trigger actions based on score thresholds.
Integrates with evaluation frameworks (DeepEval, RAGAS, MLflow) results.
"""

from __future__ import annotations

import logging
import statistics
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from tracecraft.processors.base import BaseProcessor

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun

logger = logging.getLogger(__name__)


class QualityMetric(Enum):
    """Standard quality metrics."""

    FAITHFULNESS = "faithfulness"
    ANSWER_RELEVANCY = "answer_relevancy"
    CONTEXT_PRECISION = "context_precision"
    CONTEXT_RECALL = "context_recall"
    HALLUCINATION = "hallucination"
    TOXICITY = "toxicity"
    LATENCY = "latency"
    COST = "cost"
    ERROR_RATE = "error_rate"
    CUSTOM = "custom"


@dataclass
class QualityThreshold:
    """
    Threshold configuration for a quality metric.

    Attributes:
        metric: The metric to monitor.
        min_value: Minimum acceptable value (alert if below).
        max_value: Maximum acceptable value (alert if above).
        window_size: Number of recent values to consider for aggregation.
        aggregation: How to aggregate values in window ("mean", "min", "max", "latest").
    """

    metric: QualityMetric | str
    min_value: float | None = None
    max_value: float | None = None
    window_size: int = 10
    aggregation: str = "mean"

    def __post_init__(self) -> None:
        if self.min_value is None and self.max_value is None:
            raise ValueError("At least one of min_value or max_value must be set")


@dataclass
class QualityAlert:
    """
    Represents a triggered quality alert.

    Attributes:
        threshold: The threshold that was violated.
        current_value: The value that triggered the alert.
        timestamp: When the alert was triggered.
        trace_id: ID of the trace that triggered the alert.
        trace_name: Name of the trace.
        message: Human-readable alert message.
    """

    threshold: QualityThreshold
    current_value: float
    timestamp: datetime
    trace_id: str
    trace_name: str
    message: str


class QualityScoreProcessor(BaseProcessor):
    """
    Processor that monitors quality scores and triggers alerts.

    Tracks quality metrics over time using sliding windows and triggers
    alerts when thresholds are violated. Can integrate with evaluation
    results stored in trace attributes.

    Example:
        from tracecraft.alerting import QualityScoreProcessor, QualityThreshold, QualityMetric

        quality_monitor = QualityScoreProcessor(
            thresholds=[
                QualityThreshold(
                    metric=QualityMetric.FAITHFULNESS,
                    min_value=0.8,
                    window_size=20,
                ),
                QualityThreshold(
                    metric=QualityMetric.LATENCY,
                    max_value=5000,  # 5 seconds
                    window_size=10,
                ),
                QualityThreshold(
                    metric=QualityMetric.ERROR_RATE,
                    max_value=0.05,  # 5% error rate
                    window_size=100,
                ),
            ],
            on_alert=lambda alert: send_to_slack(alert),
        )

        # Add to runtime
        init(processors=[quality_monitor])
    """

    def __init__(
        self,
        thresholds: list[QualityThreshold],
        on_alert: Callable[[QualityAlert], None] | None = None,
        extract_scores: Callable[[AgentRun], dict[str, float]] | None = None,
    ) -> None:
        """
        Initialize the quality score processor.

        Args:
            thresholds: List of quality thresholds to monitor.
            on_alert: Callback function when a threshold is violated.
            extract_scores: Custom function to extract scores from a run.
                Default extracts from run.attributes with keys like
                'quality_faithfulness', 'quality_relevancy', etc.
        """
        self.thresholds = thresholds
        self.on_alert = on_alert
        self.extract_scores = extract_scores or self._default_extract_scores

        # Thread safety lock for window and alert updates
        self._lock = threading.Lock()

        # Initialize sliding windows for each metric
        self._windows: dict[str, deque[float]] = {}
        error_window_size = 100  # Default error window size
        for threshold in thresholds:
            metric_name = self._get_metric_name(threshold.metric)
            self._windows[metric_name] = deque(maxlen=threshold.window_size)
            # Use error_rate threshold's window_size if configured
            if metric_name == "error_rate":
                error_window_size = threshold.window_size

        # Track error rate separately (uses configured or default window size)
        self._error_window: deque[bool] = deque(maxlen=error_window_size)

        # Alert history for deduplication
        self._recent_alerts: dict[str, datetime] = {}
        self._alert_cooldown_seconds = 300  # 5 minutes between same alerts

    @property
    def name(self) -> str:
        """Processor name."""
        return "quality_score"

    def process(self, run: AgentRun) -> AgentRun | None:
        """
        Process a run and check quality thresholds.

        Args:
            run: The AgentRun to process.

        Returns:
            The run (always passes through).
        """
        # Extract scores from the run
        scores = self.extract_scores(run)

        # Add built-in metrics
        if run.duration_ms is not None:
            scores["latency"] = run.duration_ms
        if run.total_cost_usd is not None:
            scores["cost"] = run.total_cost_usd

        # Thread-safe updates to windows and alert checks
        with self._lock:
            # Track error rate
            self._error_window.append(run.error is not None)
            if len(self._error_window) > 0:
                scores["error_rate"] = sum(self._error_window) / len(self._error_window)

            # Update windows and check thresholds
            for threshold in self.thresholds:
                metric_name = self._get_metric_name(threshold.metric)

                if metric_name in scores:
                    # Update sliding window
                    self._windows[metric_name].append(scores[metric_name])

                    # Check threshold
                    alert = self._check_threshold(threshold, run)
                    if alert:
                        self._handle_alert(alert)

        return run

    def _get_metric_name(self, metric: QualityMetric | str) -> str:
        """Get string name for a metric."""
        if isinstance(metric, QualityMetric):
            return metric.value
        return metric

    def _default_extract_scores(self, run: AgentRun) -> dict[str, float]:
        """
        Default score extraction from run attributes.

        Looks for attributes with 'quality_' or 'score_' prefixes,
        as well as standard evaluation metric names.
        """
        scores: dict[str, float] = {}
        attributes = run.attributes or {}

        # Extract quality scores from attributes
        for key, value in attributes.items():
            if isinstance(value, (int, float)):
                # Remove common prefixes
                metric_name = key
                for prefix in ["quality_", "score_", "eval_", "metric_"]:
                    if key.startswith(prefix):
                        metric_name = key[len(prefix) :]
                        break
                scores[metric_name] = float(value)

        # Also check step attributes for aggregated scores
        for step in run.steps:
            step_attrs = step.attributes or {}
            for key, value in step_attrs.items():
                if isinstance(value, (int, float)) and key.startswith(("quality_", "score_")):
                    metric_name = key.replace("quality_", "").replace("score_", "")
                    if metric_name not in scores:
                        scores[metric_name] = float(value)

        return scores

    def _check_threshold(
        self,
        threshold: QualityThreshold,
        run: AgentRun,
    ) -> QualityAlert | None:
        """Check if a threshold is violated."""
        metric_name = self._get_metric_name(threshold.metric)
        window = self._windows.get(metric_name)

        if not window:
            return None

        # Calculate aggregated value
        values = list(window)
        if not values:
            return None

        if threshold.aggregation == "mean":
            current_value = statistics.mean(values)
        elif threshold.aggregation == "min":
            current_value = min(values)
        elif threshold.aggregation == "max":
            current_value = max(values)
        elif threshold.aggregation == "latest":
            current_value = values[-1]
        else:
            current_value = statistics.mean(values)

        # Check thresholds
        violated = False
        message_parts = []

        if threshold.min_value is not None and current_value < threshold.min_value:
            violated = True
            message_parts.append(
                f"{metric_name} ({current_value:.3f}) below minimum ({threshold.min_value})"
            )

        if threshold.max_value is not None and current_value > threshold.max_value:
            violated = True
            message_parts.append(
                f"{metric_name} ({current_value:.3f}) above maximum ({threshold.max_value})"
            )

        if violated:
            return QualityAlert(
                threshold=threshold,
                current_value=current_value,
                timestamp=datetime.now(UTC),
                trace_id=str(run.id),
                trace_name=run.name,
                message="; ".join(message_parts),
            )

        return None

    def _handle_alert(self, alert: QualityAlert) -> None:
        """Handle a triggered alert."""
        metric_name = self._get_metric_name(alert.threshold.metric)

        # Check cooldown
        last_alert = self._recent_alerts.get(metric_name)
        if last_alert is not None:
            elapsed = (alert.timestamp - last_alert).total_seconds()
            if elapsed < self._alert_cooldown_seconds:
                logger.debug(
                    "Quality alert '%s' in cooldown (%.1fs remaining)",
                    metric_name,
                    self._alert_cooldown_seconds - elapsed,
                )
                return

        # Update last alert time
        self._recent_alerts[metric_name] = alert.timestamp

        # Log the alert
        logger.warning(
            "Quality threshold violated: %s (trace: %s)",
            alert.message,
            alert.trace_name,
        )

        # Call the alert handler if provided
        if self.on_alert:
            try:
                self.on_alert(alert)
            except Exception:
                logger.exception("Error in quality alert handler")

    def get_current_scores(self) -> dict[str, float]:
        """
        Get current aggregated scores for all metrics.

        Returns:
            Dictionary of metric name to current value.
        """
        scores: dict[str, float] = {}

        with self._lock:
            for threshold in self.thresholds:
                metric_name = self._get_metric_name(threshold.metric)
                window = self._windows.get(metric_name)

                if window:
                    values = list(window)
                    if values:
                        if threshold.aggregation == "mean":
                            scores[metric_name] = statistics.mean(values)
                        elif threshold.aggregation == "min":
                            scores[metric_name] = min(values)
                        elif threshold.aggregation == "max":
                            scores[metric_name] = max(values)
                        else:
                            scores[metric_name] = values[-1]

        return scores

    def get_window_data(self, metric: QualityMetric | str) -> list[float]:
        """
        Get all values in the sliding window for a metric.

        Args:
            metric: The metric to get data for.

        Returns:
            List of values in the window.
        """
        metric_name = self._get_metric_name(metric)
        with self._lock:
            window = self._windows.get(metric_name)
            return list(window) if window else []

    def reset(self) -> None:
        """Reset all sliding windows and alert history."""
        with self._lock:
            for window in self._windows.values():
                window.clear()
            self._error_window.clear()
            self._recent_alerts.clear()


class QualityScoreAggregator:
    """
    Utility class to aggregate quality scores across multiple traces.

    Useful for batch evaluation and reporting.
    """

    def __init__(self) -> None:
        self._scores: dict[str, list[float]] = {}

    def add_score(self, metric: str, value: float) -> None:
        """Add a score for a metric."""
        if metric not in self._scores:
            self._scores[metric] = []
        self._scores[metric].append(value)

    def add_scores(self, scores: dict[str, float]) -> None:
        """Add multiple scores at once."""
        for metric, value in scores.items():
            self.add_score(metric, value)

    def get_summary(self) -> dict[str, dict[str, float]]:
        """
        Get summary statistics for all metrics.

        Returns:
            Dictionary of metric name to stats (mean, min, max, std, count).
        """
        summary: dict[str, dict[str, float]] = {}

        for metric, values in self._scores.items():
            if values:
                summary[metric] = {
                    "mean": statistics.mean(values),
                    "min": min(values),
                    "max": max(values),
                    "std": statistics.stdev(values) if len(values) > 1 else 0.0,
                    "count": len(values),
                }

        return summary

    def passes_thresholds(self, thresholds: list[QualityThreshold]) -> bool:
        """
        Check if current aggregated scores pass all thresholds.

        Args:
            thresholds: List of thresholds to check.

        Returns:
            True if all thresholds pass.
        """
        for threshold in thresholds:
            metric_name = (
                threshold.metric.value
                if isinstance(threshold.metric, QualityMetric)
                else threshold.metric
            )

            values = self._scores.get(metric_name, [])
            if not values:
                continue

            value = statistics.mean(values)

            if threshold.min_value is not None and value < threshold.min_value:
                return False
            if threshold.max_value is not None and value > threshold.max_value:
                return False

        return True

    def reset(self) -> None:
        """Reset all scores."""
        self._scores.clear()
