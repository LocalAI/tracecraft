"""
DeepEval adapter for TraceCraft evaluation.

Provides access to DeepEval's comprehensive LLM evaluation metrics:
- answer_relevancy: How relevant the answer is to the question
- faithfulness: How grounded the answer is in the context
- hallucination: Detection of hallucinated content
- bias: Detection of biased content
- toxicity: Detection of toxic content
- contextual_precision: Precision of retrieved context
- contextual_recall: Recall of retrieved context

Requires: pip install deepeval
"""

from __future__ import annotations

import asyncio
import json
from functools import partial
from typing import TYPE_CHECKING, Any

from tracecraft.evaluation.adapters.base import BaseMetricAdapter, MetricResult

if TYPE_CHECKING:
    from tracecraft.evaluation.models import EvaluationCase, EvaluationMetricConfig


class DeepEvalAdapter(BaseMetricAdapter):
    """Adapter for DeepEval evaluation metrics."""

    @property
    def framework_name(self) -> str:
        return "deepeval"

    @property
    def supported_metrics(self) -> list[str]:
        return [
            "answer_relevancy",
            "faithfulness",
            "hallucination",
            "bias",
            "toxicity",
            "contextual_precision",
            "contextual_recall",
            "summarization",
            "g_eval",
        ]

    async def evaluate(
        self,
        case: EvaluationCase,
        actual_output: str | dict[str, Any],
        metric_config: EvaluationMetricConfig,
    ) -> MetricResult:
        """Evaluate using DeepEval metrics."""
        try:
            from deepeval.metrics import (
                AnswerRelevancyMetric,
                BiasMetric,
                ContextualPrecisionMetric,
                ContextualRecallMetric,
                FaithfulnessMetric,
                GEval,
                HallucinationMetric,
                SummarizationMetric,
                ToxicityMetric,
            )
            from deepeval.test_case import LLMTestCase
        except ImportError:
            return MetricResult(
                metric_name=metric_config.metric_type,
                score=0.0,
                passed=False,
                reason="DeepEval not installed. Run: pip install deepeval",
            )

        metric_type = metric_config.metric_type
        threshold = metric_config.threshold

        # Normalize output
        if isinstance(actual_output, dict):
            actual = json.dumps(actual_output)
        else:
            actual = str(actual_output)

        # Get input
        input_text = case.input.get("input", case.input.get("query", json.dumps(case.input)))
        if isinstance(input_text, dict):
            input_text = json.dumps(input_text)

        # Get expected output if available
        expected = None
        if case.expected_output:
            expected = case.expected_output.get(
                "output", case.expected_output.get("answer", json.dumps(case.expected_output))
            )
            if isinstance(expected, dict):
                expected = json.dumps(expected)

        # Get retrieval context
        retrieval_context = case.retrieval_context or []

        # Create test case
        test_case = LLMTestCase(
            input=input_text,
            actual_output=actual,
            expected_output=expected,
            retrieval_context=retrieval_context,
        )

        try:
            # Create the appropriate metric
            model = metric_config.parameters.get("model", "gpt-4o-mini")

            if metric_type == "answer_relevancy":
                metric = AnswerRelevancyMetric(threshold=threshold, model=model)
            elif metric_type == "faithfulness":
                metric = FaithfulnessMetric(threshold=threshold, model=model)
            elif metric_type == "hallucination":
                metric = HallucinationMetric(threshold=threshold, model=model)
            elif metric_type == "bias":
                metric = BiasMetric(threshold=threshold, model=model)
            elif metric_type == "toxicity":
                metric = ToxicityMetric(threshold=threshold, model=model)
            elif metric_type == "contextual_precision":
                metric = ContextualPrecisionMetric(threshold=threshold, model=model)
            elif metric_type == "contextual_recall":
                metric = ContextualRecallMetric(threshold=threshold, model=model)
            elif metric_type == "summarization":
                metric = SummarizationMetric(threshold=threshold, model=model)
            elif metric_type == "g_eval":
                criteria = metric_config.parameters.get(
                    "criteria",
                    "Evaluate the quality of the response based on accuracy and helpfulness.",
                )
                name = metric_config.parameters.get("name", "quality")
                metric = GEval(
                    name=name,
                    criteria=criteria,
                    threshold=threshold,
                    model=model,
                )
            else:
                return MetricResult(
                    metric_name=metric_type,
                    score=0.0,
                    passed=False,
                    reason=f"Unsupported DeepEval metric: {metric_type}",
                )

            # Run the blocking measure() call in a thread pool to avoid blocking the event loop
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, partial(metric.measure, test_case))

            score = metric.score if metric.score is not None else 0.0
            passed = metric.is_successful()
            reason = metric.reason if hasattr(metric, "reason") else None

            return MetricResult(
                metric_name=metric_type,
                score=score,
                passed=passed,
                reason=reason,
                details={
                    "framework": "deepeval",
                    "threshold": threshold,
                },
            )

        except Exception as e:
            return MetricResult(
                metric_name=metric_type,
                score=0.0,
                passed=False,
                reason=f"DeepEval evaluation failed: {e}",
                details={"error": str(e)},
            )
