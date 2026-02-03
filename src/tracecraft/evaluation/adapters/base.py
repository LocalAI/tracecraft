"""
Base adapter for evaluation metrics.

Defines the interface that all metric adapters must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tracecraft.evaluation.models import EvaluationCase, EvaluationMetricConfig


@dataclass
class MetricResult:
    """Result from evaluating a single metric."""

    metric_name: str
    score: float  # 0.0 to 1.0
    passed: bool
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "metric_name": self.metric_name,
            "score": self.score,
            "passed": self.passed,
            "reason": self.reason,
            "details": self.details,
        }


class BaseMetricAdapter(ABC):
    """
    Abstract base class for evaluation metric adapters.

    Each adapter provides access to metrics from a specific framework
    (builtin, deepeval, ragas, mlflow).
    """

    @property
    @abstractmethod
    def framework_name(self) -> str:
        """Return the framework name (e.g., 'builtin', 'deepeval')."""
        ...

    @property
    @abstractmethod
    def supported_metrics(self) -> list[str]:
        """Return list of supported metric types."""
        ...

    @abstractmethod
    async def evaluate(
        self,
        case: EvaluationCase,
        actual_output: str | dict[str, Any],
        metric_config: EvaluationMetricConfig,
    ) -> MetricResult:
        """
        Evaluate a case against a metric.

        Args:
            case: The evaluation case with input and expected output.
            actual_output: The actual output to evaluate.
            metric_config: Configuration for the metric.

        Returns:
            MetricResult with score, passed status, and explanation.

        Raises:
            ValueError: If metric_type is not supported.
        """
        ...

    def supports(self, metric_type: str) -> bool:
        """Check if this adapter supports a given metric type."""
        return metric_type in self.supported_metrics


# Global adapter registry
_adapters: dict[str, type[BaseMetricAdapter]] = {}


def register_adapter(framework: str, adapter_class: type[BaseMetricAdapter]) -> None:
    """
    Register an adapter for a framework.

    Args:
        framework: Framework name (e.g., 'builtin', 'deepeval').
        adapter_class: The adapter class to register.
    """
    _adapters[framework] = adapter_class


def get_adapter(framework: str) -> BaseMetricAdapter:
    """
    Get an adapter instance for a framework.

    Args:
        framework: Framework name.

    Returns:
        Adapter instance.

    Raises:
        ValueError: If framework is not registered.
    """
    if framework not in _adapters:
        # Try to import and auto-register
        _auto_import_adapter(framework)

    if framework not in _adapters:
        raise ValueError(
            f"Unknown evaluation framework: {framework}. Available: {list(_adapters.keys())}"
        )

    return _adapters[framework]()


def _auto_import_adapter(framework: str) -> None:
    """Try to auto-import an adapter for a framework."""
    try:
        if framework == "builtin":
            from tracecraft.evaluation.adapters.builtin import BuiltinMetricAdapter

            register_adapter("builtin", BuiltinMetricAdapter)
        elif framework == "deepeval":
            from tracecraft.evaluation.adapters.deepeval_adapter import DeepEvalAdapter

            register_adapter("deepeval", DeepEvalAdapter)
        elif framework == "ragas":
            from tracecraft.evaluation.adapters.ragas_adapter import RagasAdapter

            register_adapter("ragas", RagasAdapter)
        elif framework == "mlflow":
            from tracecraft.evaluation.adapters.mlflow_adapter import MLflowAdapter

            register_adapter("mlflow", MLflowAdapter)
    except ImportError:
        pass  # Framework not installed
