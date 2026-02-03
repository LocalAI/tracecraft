"""
RAGAS adapter for TraceCraft evaluation.

Provides access to RAGAS (Retrieval Augmented Generation Assessment) metrics:
- faithfulness: How grounded the answer is in the given context
- answer_relevancy: How relevant the answer is to the question
- context_precision: How relevant the retrieved context is
- context_recall: How much of the ground truth is covered by context
- answer_correctness: Semantic similarity between answer and ground truth
- answer_similarity: Simple similarity between answer and ground truth

Requires: pip install ragas
"""

from __future__ import annotations

import asyncio
import json
from functools import partial
from typing import TYPE_CHECKING, Any

from tracecraft.evaluation.adapters.base import BaseMetricAdapter, MetricResult

if TYPE_CHECKING:
    from tracecraft.evaluation.models import EvaluationCase, EvaluationMetricConfig


class RagasAdapter(BaseMetricAdapter):
    """Adapter for RAGAS RAG evaluation metrics."""

    @property
    def framework_name(self) -> str:
        return "ragas"

    @property
    def supported_metrics(self) -> list[str]:
        return [
            "faithfulness",
            "answer_relevancy",
            "context_precision",
            "context_recall",
            "answer_correctness",
            "answer_similarity",
        ]

    async def evaluate(
        self,
        case: EvaluationCase,
        actual_output: str | dict[str, Any],
        metric_config: EvaluationMetricConfig,
    ) -> MetricResult:
        """Evaluate using RAGAS metrics."""
        try:
            from datasets import Dataset
            from ragas import evaluate
            from ragas.metrics import (
                answer_correctness,
                answer_relevancy,
                answer_similarity,
                context_precision,
                context_recall,
                faithfulness,
            )
        except ImportError:
            return MetricResult(
                metric_name=metric_config.metric_type,
                score=0.0,
                passed=False,
                reason="RAGAS not installed. Run: pip install ragas datasets",
            )

        metric_type = metric_config.metric_type
        threshold = metric_config.threshold

        # Normalize output
        if isinstance(actual_output, dict):
            actual = json.dumps(actual_output)
        else:
            actual = str(actual_output)

        # Get question/input
        question = case.input.get("input", case.input.get("query", case.input.get("question", "")))
        if isinstance(question, dict):
            question = json.dumps(question)

        # Get expected answer (ground truth)
        ground_truth = None
        if case.expected_output:
            ground_truth = case.expected_output.get(
                "output",
                case.expected_output.get("answer", case.expected_output.get("ground_truth", "")),
            )
            if isinstance(ground_truth, dict):
                ground_truth = json.dumps(ground_truth)

        # Get contexts
        contexts = case.retrieval_context or []

        # Map metric type to RAGAS metric
        metric_map = {
            "faithfulness": faithfulness,
            "answer_relevancy": answer_relevancy,
            "context_precision": context_precision,
            "context_recall": context_recall,
            "answer_correctness": answer_correctness,
            "answer_similarity": answer_similarity,
        }

        if metric_type not in metric_map:
            return MetricResult(
                metric_name=metric_type,
                score=0.0,
                passed=False,
                reason=f"Unsupported RAGAS metric: {metric_type}",
            )

        try:
            # Create dataset for evaluation
            data = {
                "question": [question],
                "answer": [actual],
                "contexts": [contexts],
            }

            # Add ground truth if available (required for some metrics)
            if ground_truth:
                data["ground_truth"] = [ground_truth]

            dataset = Dataset.from_dict(data)

            # Get the metric
            metric = metric_map[metric_type]

            # Run the blocking evaluate() call in a thread pool to avoid blocking the event loop
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, partial(evaluate, dataset, metrics=[metric]))

            # Extract score
            score = result.get(metric_type, 0.0)
            passed = score >= threshold

            return MetricResult(
                metric_name=metric_type,
                score=float(score),
                passed=passed,
                reason=f"RAGAS {metric_type} score: {score:.3f}",
                details={
                    "framework": "ragas",
                    "threshold": threshold,
                    "has_ground_truth": ground_truth is not None,
                    "context_count": len(contexts),
                },
            )

        except Exception as e:
            return MetricResult(
                metric_name=metric_type,
                score=0.0,
                passed=False,
                reason=f"RAGAS evaluation failed: {e}",
                details={"error": str(e)},
            )
