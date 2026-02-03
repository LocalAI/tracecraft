"""
RAGAS integration for TraceCraft.

Converts TraceCraft traces to RAGAS evaluation datasets for RAG evaluation.
Supports faithfulness, answer relevancy, context precision, and context recall.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def traces_to_ragas_dataset(
    traces: str | Path | list[Any],
    filter_fn: Callable[[Any], bool] | None = None,
    extract_question: Callable[[Any], str] | None = None,
    extract_answer: Callable[[Any], str] | None = None,
    extract_contexts: Callable[[Any], list[str]] | None = None,
    extract_ground_truth: Callable[[Any], str | None] | None = None,
) -> Any:
    """
    Convert TraceCraft traces to a RAGAS evaluation dataset.

    Args:
        traces: Path to JSONL file or list of AgentRun objects.
        filter_fn: Optional function to filter traces/steps.
        extract_question: Function to extract question/input from step.
        extract_answer: Function to extract answer/output from step.
        extract_contexts: Function to extract retrieval contexts.
        extract_ground_truth: Function to extract ground truth answer.

    Returns:
        RAGAS Dataset object ready for evaluation.

    Example:
        from tracecraft.integrations.ragas import traces_to_ragas_dataset
        from ragas import evaluate
        from ragas.metrics import faithfulness, context_precision

        dataset = traces_to_ragas_dataset("traces/tracecraft.jsonl")
        results = evaluate(dataset, metrics=[faithfulness, context_precision])
    """
    try:
        from datasets import Dataset
    except ImportError:
        raise ImportError("datasets required. Install with: pip install datasets")

    # Load traces if path provided
    if isinstance(traces, (str, Path)):
        traces = _load_traces_from_jsonl(traces)

    records = []

    for run in traces:
        for step in _flatten_steps(run.steps):
            # Apply filter
            if filter_fn and not filter_fn(step):
                continue

            # Extract RAG-relevant fields
            question = (
                extract_question(step) if extract_question else _default_extract_question(step)
            )
            answer = extract_answer(step) if extract_answer else _default_extract_answer(step)
            contexts = (
                extract_contexts(step) if extract_contexts else _default_extract_contexts(step)
            )
            ground_truth = (
                extract_ground_truth(step)
                if extract_ground_truth
                else _default_extract_ground_truth(step)
            )

            # Build record - RAGAS expects specific field names
            record: dict[str, Any] = {
                "question": question,
                "answer": answer,
                "contexts": contexts or [],
            }

            # Add ground truth if available (needed for some metrics)
            if ground_truth:
                record["ground_truth"] = ground_truth

            # Add metadata
            record["trace_id"] = str(run.id)
            record["step_id"] = str(step.id)
            record["step_name"] = step.name

            # Only include if we have the required fields
            if question and answer:
                records.append(record)

    if not records:
        raise ValueError("No valid records found. Check filter criteria and data extraction.")

    return Dataset.from_list(records)


def evaluate_rag_traces(
    traces: str | Path | list[Any],
    metrics: list[str] | None = None,
    llm: Any = None,
    embeddings: Any = None,
    **kwargs: Any,
) -> Any:
    """
    Evaluate RAG traces using RAGAS metrics.

    Args:
        traces: Path to JSONL or list of AgentRun.
        metrics: List of metric names. Defaults to common RAG metrics.
            Available: "faithfulness", "answer_relevancy", "context_precision",
            "context_recall", "context_utilization", "answer_similarity",
            "answer_correctness"
        llm: LangChain LLM to use for evaluation (optional).
        embeddings: LangChain embeddings to use (optional).
        **kwargs: Additional arguments to traces_to_ragas_dataset.

    Returns:
        RAGAS evaluation results.

    Example:
        from tracecraft.integrations.ragas import evaluate_rag_traces

        results = evaluate_rag_traces("traces/tracecraft.jsonl")
        print(f"Faithfulness: {results['faithfulness']}")
    """
    from ragas import evaluate

    metric_names = metrics or ["faithfulness", "answer_relevancy"]
    metric_objects = _create_metrics(metric_names)

    dataset = traces_to_ragas_dataset(traces, **kwargs)

    # Build evaluate kwargs
    eval_kwargs: dict[str, Any] = {
        "dataset": dataset,
        "metrics": metric_objects,
    }

    if llm:
        eval_kwargs["llm"] = llm
    if embeddings:
        eval_kwargs["embeddings"] = embeddings

    return evaluate(**eval_kwargs)


def _create_metrics(metric_names: list[str]) -> list[Any]:
    """Create RAGAS metric objects from names."""
    from ragas.metrics import (
        answer_correctness,
        answer_relevancy,
        answer_similarity,
        context_precision,
        context_recall,
        context_utilization,
        faithfulness,
    )

    METRIC_MAP = {
        "faithfulness": faithfulness,
        "answer_relevancy": answer_relevancy,
        "context_precision": context_precision,
        "context_recall": context_recall,
        "context_utilization": context_utilization,
        "answer_similarity": answer_similarity,
        "answer_correctness": answer_correctness,
    }

    metrics = []
    for name in metric_names:
        if name not in METRIC_MAP:
            available = ", ".join(METRIC_MAP.keys())
            raise ValueError(f"Unknown metric: {name}. Available: {available}")
        metrics.append(METRIC_MAP[name])

    return metrics


def filter_rag_steps(step: Any) -> bool:
    """
    Default filter to identify RAG-related steps.

    A step is considered RAG-related if it:
    - Is an LLM step with retrieval context, OR
    - Is a retrieval step

    Args:
        step: The step to check.

    Returns:
        True if the step is RAG-related.
    """
    # Check if it's a retrieval step
    if step.type.value == "retrieval":
        return True

    # Check if it's an LLM step with context
    if step.type.value == "llm":
        inputs = step.inputs or {}
        context_keys = ["context", "contexts", "retrieval_context", "documents", "sources"]
        return any(key in inputs for key in context_keys)

    return False


def _load_traces_from_jsonl(path: str | Path) -> list[Any]:
    """Load traces from JSONL file."""
    from tracecraft.core.models import AgentRun

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


def _default_extract_question(step: Any) -> str:
    """Default question/input extraction."""
    inputs = step.inputs or {}

    # Try common question/input formats
    for key in ["question", "query", "input", "prompt", "user_input"]:
        if key in inputs:
            return str(inputs[key])

    # Try to extract from messages
    if "messages" in inputs:
        messages = inputs["messages"]
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return str(msg.get("content", ""))

    return str(inputs)


def _default_extract_answer(step: Any) -> str:
    """Default answer/output extraction."""
    outputs = step.outputs or {}

    for key in ["answer", "response", "result", "output", "content", "text"]:
        if key in outputs:
            return str(outputs[key])

    if "message" in outputs:
        msg = outputs["message"]
        if isinstance(msg, dict) and "content" in msg:
            return str(msg["content"])
        return str(msg)

    return str(outputs)


def _default_extract_contexts(step: Any) -> list[str]:
    """Default contexts extraction."""
    inputs = step.inputs or {}

    # Check various context field names
    for key in [
        "contexts",
        "context",
        "retrieval_context",
        "documents",
        "sources",
        "retrieved_documents",
    ]:
        if key in inputs:
            ctx = inputs[key]
            if isinstance(ctx, list):
                return [str(c) for c in ctx]
            return [str(ctx)]

    return []


def _default_extract_ground_truth(step: Any) -> str | None:
    """Default ground truth extraction."""
    inputs = step.inputs or {}
    outputs = step.outputs or {}

    # Check for ground truth in various places
    for container in [inputs, outputs]:
        for key in ["ground_truth", "expected", "expected_answer", "reference", "gold"]:
            if key in container:
                return str(container[key])

    return None
