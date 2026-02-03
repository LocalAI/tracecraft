"""
Evaluation metric adapters for TraceCraft.

Provides a unified interface for different evaluation frameworks:
- builtin: Built-in metrics (exact_match, regex_match, contains, llm_judge)
- deepeval: DeepEval framework metrics
- ragas: RAGAS RAG evaluation metrics
- mlflow: MLflow LLM evaluation metrics
"""

from tracecraft.evaluation.adapters.base import (
    BaseMetricAdapter,
    MetricResult,
    get_adapter,
    register_adapter,
)

__all__ = [
    "BaseMetricAdapter",
    "MetricResult",
    "get_adapter",
    "register_adapter",
]
