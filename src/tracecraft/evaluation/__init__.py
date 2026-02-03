"""
TraceCraft Evaluation System.

Provides comprehensive evaluation capabilities for LLM/agent outputs:
- Create evaluation sets with configurable metrics
- Run evaluations with DeepEval, RAGAS, MLflow, or built-in scorers
- Track results with persistent storage
"""

from tracecraft.evaluation.models import (
    EvaluationCase,
    EvaluationMetricConfig,
    EvaluationResult,
    EvaluationRun,
    EvaluationRunSummary,
    EvaluationSet,
    EvaluationStatus,
    MetricFramework,
    MetricScore,
)
from tracecraft.evaluation.runner import (
    EvaluationRunner,
    EvaluationRunResult,
    ProgressInfo,
    run_evaluation_sync,
)

__all__ = [
    # Enums
    "MetricFramework",
    "EvaluationStatus",
    # Core models
    "EvaluationMetricConfig",
    "EvaluationCase",
    "EvaluationSet",
    "MetricScore",
    "EvaluationResult",
    "EvaluationRun",
    "EvaluationRunSummary",
    # Runner
    "EvaluationRunner",
    "EvaluationRunResult",
    "ProgressInfo",
    "run_evaluation_sync",
]
