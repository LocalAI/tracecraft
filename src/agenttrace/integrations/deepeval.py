"""
DeepEval integration for AgentTrace.

Converts AgentTrace traces to DeepEval test cases for evaluation.
Supports all DeepEval metrics including faithfulness, answer relevancy,
hallucination, and more.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def traces_to_test_cases(
    traces: str | Path | list[Any],
    filter_fn: Callable[[Any], bool] | None = None,
    extract_input: Callable[[Any], str] | None = None,
    extract_output: Callable[[Any], str] | None = None,
    extract_context: Callable[[Any], list[str] | None] | None = None,
    extract_expected: Callable[[Any], str | None] | None = None,
) -> list[Any]:
    """
    Convert AgentTrace traces to DeepEval LLMTestCase objects.

    Args:
        traces: Path to JSONL file or list of AgentRun objects.
        filter_fn: Optional function to filter traces/steps.
        extract_input: Function to extract input from step (default: step.inputs).
        extract_output: Function to extract output from step (default: step.outputs).
        extract_context: Function to extract retrieval context (for RAG metrics).
        extract_expected: Function to extract expected output (for correctness metrics).

    Returns:
        List of DeepEval LLMTestCase objects.

    Example:
        from agenttrace.integrations.deepeval import traces_to_test_cases
        from deepeval import evaluate
        from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric

        # Convert traces to test cases
        test_cases = traces_to_test_cases(
            "traces/agenttrace.jsonl",
            filter_fn=lambda step: step.type.value == "llm"
        )

        # Evaluate with DeepEval
        results = evaluate(
            test_cases,
            metrics=[FaithfulnessMetric(), AnswerRelevancyMetric()]
        )
    """
    try:
        from deepeval.test_case import LLMTestCase
    except ImportError:
        raise ImportError("deepeval required. Install with: pip install deepeval")

    # Load traces if path provided
    if isinstance(traces, (str, Path)):
        traces = _load_traces_from_jsonl(traces)

    test_cases = []

    for run in traces:
        for step in _flatten_steps(run.steps):
            # Apply filter
            if filter_fn and not filter_fn(step):
                continue

            # Only process LLM steps by default
            if step.type.value != "llm" and filter_fn is None:
                continue

            # Extract fields
            input_text = extract_input(step) if extract_input else _default_extract_input(step)
            output_text = extract_output(step) if extract_output else _default_extract_output(step)
            context = extract_context(step) if extract_context else _default_extract_context(step)
            expected = extract_expected(step) if extract_expected else None

            # Build test case kwargs
            test_case_kwargs: dict[str, Any] = {
                "input": input_text,
                "actual_output": output_text,
            }

            if context:
                test_case_kwargs["retrieval_context"] = context

            if expected:
                test_case_kwargs["expected_output"] = expected

            # Add trace metadata
            test_case_kwargs["additional_metadata"] = {
                "trace_id": str(run.id),
                "step_id": str(step.id),
                "step_name": step.name,
                "model": step.model_name,
                "duration_ms": step.duration_ms,
                "input_tokens": step.input_tokens,
                "output_tokens": step.output_tokens,
            }

            test_case = LLMTestCase(**test_case_kwargs)
            test_cases.append(test_case)

    return test_cases


def evaluate_traces(
    traces: str | Path | list[Any],
    metrics: list[str] | None = None,
    model: str | None = None,
    **kwargs: Any,
) -> Any:
    """
    Evaluate traces using DeepEval metrics.

    Args:
        traces: Path to JSONL or list of AgentRun.
        metrics: List of metric names. Defaults to ["answer_relevancy"].
            Available: "answer_relevancy", "faithfulness", "hallucination",
            "contextual_precision", "contextual_recall", "contextual_relevancy",
            "bias", "toxicity"
        model: Model to use for evaluation (default: gpt-4o).
        **kwargs: Additional arguments to traces_to_test_cases.

    Returns:
        DeepEval evaluation results.

    Example:
        from agenttrace.integrations.deepeval import evaluate_traces

        results = evaluate_traces(
            "traces/agenttrace.jsonl",
            metrics=["faithfulness", "answer_relevancy"]
        )
        print(f"Pass rate: {results.pass_rate}")
    """
    from deepeval import evaluate

    metric_names = metrics or ["answer_relevancy"]
    metric_objects = _create_metrics(metric_names, model)

    test_cases = traces_to_test_cases(traces, **kwargs)

    if not test_cases:
        raise ValueError("No test cases generated from traces. Check filter criteria.")

    return evaluate(test_cases, metric_objects)


def _create_metrics(metric_names: list[str], model: str | None = None) -> list[Any]:
    """Create DeepEval metric objects from names."""
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        BiasMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        ContextualRelevancyMetric,
        FaithfulnessMetric,
        HallucinationMetric,
        ToxicityMetric,
    )

    METRIC_MAP = {
        "answer_relevancy": AnswerRelevancyMetric,
        "faithfulness": FaithfulnessMetric,
        "hallucination": HallucinationMetric,
        "contextual_precision": ContextualPrecisionMetric,
        "contextual_recall": ContextualRecallMetric,
        "contextual_relevancy": ContextualRelevancyMetric,
        "bias": BiasMetric,
        "toxicity": ToxicityMetric,
    }

    metrics = []
    for name in metric_names:
        if name not in METRIC_MAP:
            available = ", ".join(METRIC_MAP.keys())
            raise ValueError(f"Unknown metric: {name}. Available: {available}")

        metric_class = METRIC_MAP[name]
        kwargs = {}
        if model:
            kwargs["model"] = model

        metrics.append(metric_class(**kwargs))

    return metrics


def run_test_cases(
    test_cases: list[Any],
    metrics: list[str] | None = None,
    model: str | None = None,
) -> Any:
    """
    Run evaluation on pre-built test cases.

    Args:
        test_cases: List of LLMTestCase objects.
        metrics: List of metric names.
        model: Model to use for evaluation.

    Returns:
        DeepEval evaluation results.
    """
    from deepeval import evaluate

    metric_names = metrics or ["answer_relevancy"]
    metric_objects = _create_metrics(metric_names, model)

    return evaluate(test_cases, metric_objects)


def _load_traces_from_jsonl(path: str | Path) -> list[Any]:
    """Load traces from JSONL file."""
    from agenttrace.core.models import AgentRun

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Trace file not found: {path}")

    traces = []
    with path.open() as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                traces.append(AgentRun.model_validate(data))
    return traces


def _flatten_steps(steps: list[Any]) -> list[Any]:
    """Flatten nested steps into a list."""
    result = []
    for step in steps:
        result.append(step)
        if step.children:
            result.extend(_flatten_steps(step.children))
    return result


def _default_extract_input(step: Any) -> str:
    """Default input extraction."""
    inputs = step.inputs or {}

    # Try common input formats
    if "prompt" in inputs:
        return str(inputs["prompt"])
    if "query" in inputs:
        return str(inputs["query"])
    if "question" in inputs:
        return str(inputs["question"])
    if "input" in inputs:
        return str(inputs["input"])
    if "messages" in inputs:
        # Extract user message
        messages = inputs["messages"]
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return str(msg.get("content", ""))
        return str(messages)

    return str(inputs)


def _default_extract_output(step: Any) -> str:
    """Default output extraction."""
    outputs = step.outputs or {}

    if "result" in outputs:
        return str(outputs["result"])
    if "response" in outputs:
        return str(outputs["response"])
    if "content" in outputs:
        return str(outputs["content"])
    if "answer" in outputs:
        return str(outputs["answer"])
    if "text" in outputs:
        return str(outputs["text"])
    if "message" in outputs:
        msg = outputs["message"]
        if isinstance(msg, dict) and "content" in msg:
            return str(msg["content"])
        return str(msg)

    return str(outputs)


def _default_extract_context(step: Any) -> list[str] | None:
    """Default context extraction for RAG steps."""
    inputs = step.inputs or {}

    # Check various context field names
    for key in ["retrieval_context", "context", "contexts", "documents", "sources"]:
        if key in inputs:
            ctx = inputs[key]
            if isinstance(ctx, list):
                return [str(c) for c in ctx]
            return [str(ctx)]

    return None
