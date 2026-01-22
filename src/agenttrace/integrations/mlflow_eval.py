"""
MLflow evaluation bridge for AgentTrace.

Enables using MLflow's genai.evaluate() capabilities on AgentTrace traces.
Supports MLflow's built-in LLM judges and custom scorers.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def traces_to_mlflow_dataset(
    traces: str | Path | list[Any],
    filter_fn: Callable[[Any], bool] | None = None,
    extract_inputs: Callable[[Any], str] | None = None,
    extract_outputs: Callable[[Any], str] | None = None,
    extract_context: Callable[[Any], str | None] | None = None,
    extract_ground_truth: Callable[[Any], str | None] | None = None,
) -> Any:
    """
    Convert AgentTrace traces to MLflow evaluation dataset.

    Returns a pandas DataFrame compatible with mlflow.genai.evaluate().

    Args:
        traces: Path to JSONL file or list of AgentRun objects.
        filter_fn: Optional function to filter traces/steps.
        extract_inputs: Function to extract input text from step.
        extract_outputs: Function to extract output text from step.
        extract_context: Function to extract context (optional).
        extract_ground_truth: Function to extract ground truth (optional).

    Returns:
        pandas DataFrame ready for mlflow.genai.evaluate().

    Example:
        from agenttrace.integrations.mlflow_eval import traces_to_mlflow_dataset
        import mlflow

        df = traces_to_mlflow_dataset("traces/agenttrace.jsonl")

        results = mlflow.genai.evaluate(
            data=df,
            model_type="question-answering",
            evaluators=["default"]
        )
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("pandas required. Install with: pip install pandas")

    # Load traces if path provided
    if isinstance(traces, (str, Path)):
        traces = _load_traces_from_jsonl(traces)

    records = []

    for run in traces:
        for step in _flatten_steps(run.steps):
            # Apply filter
            if filter_fn and not filter_fn(step):
                continue

            # Only process LLM steps by default
            if step.type.value != "llm" and filter_fn is None:
                continue

            # Extract fields
            inputs = extract_inputs(step) if extract_inputs else _default_extract_inputs(step)
            outputs = extract_outputs(step) if extract_outputs else _default_extract_outputs(step)
            context = extract_context(step) if extract_context else _default_extract_context(step)
            ground_truth = (
                extract_ground_truth(step)
                if extract_ground_truth
                else _default_extract_ground_truth(step)
            )

            # Build record
            record: dict[str, Any] = {
                "inputs": inputs,
                "outputs": outputs,
                # Metadata
                "trace_id": str(run.id),
                "step_id": str(step.id),
                "step_name": step.name,
                "model": step.model_name,
            }

            # Add optional fields
            if context:
                record["context"] = context
            if ground_truth:
                record["ground_truth"] = ground_truth

            records.append(record)

    if not records:
        raise ValueError("No records generated from traces. Check filter criteria.")

    return pd.DataFrame(records)


def evaluate_with_mlflow_judges(
    traces: str | Path | list[Any],
    scorers: list[str] | None = None,
    model: str | None = None,
    **kwargs: Any,
) -> Any:
    """
    Evaluate traces using MLflow's built-in LLM judges.

    Args:
        traces: Path to JSONL or list of AgentRun.
        scorers: List of scorer names. Uses MLflow genai scorers.
            Available: "correctness", "relevance", "groundedness",
            "retrieval_precision", "guidelines"
        model: Model to use for evaluation (optional).
        **kwargs: Additional arguments to traces_to_mlflow_dataset.

    Returns:
        MLflow evaluation results.

    Example:
        from agenttrace.integrations.mlflow_eval import evaluate_with_mlflow_judges

        results = evaluate_with_mlflow_judges(
            "traces/agenttrace.jsonl",
            scorers=["correctness", "relevance"]
        )
    """
    import mlflow.genai

    scorer_names = scorers or ["correctness"]
    scorer_objects = _create_scorers(scorer_names, model)

    df = traces_to_mlflow_dataset(traces, **kwargs)

    return mlflow.genai.evaluate(
        data=df,
        scorers=scorer_objects,
    )


def evaluate_with_custom_scorer(
    traces: str | Path | list[Any],
    scorer_fn: Callable[[str, str], float],
    scorer_name: str = "custom",
    **kwargs: Any,
) -> Any:
    """
    Evaluate traces using a custom scoring function.

    Args:
        traces: Path to JSONL or list of AgentRun.
        scorer_fn: Function that takes (input, output) and returns a score.
        scorer_name: Name for the custom scorer.
        **kwargs: Additional arguments to traces_to_mlflow_dataset.

    Returns:
        MLflow evaluation results.

    Example:
        from agenttrace.integrations.mlflow_eval import evaluate_with_custom_scorer

        def length_scorer(input_text: str, output_text: str) -> float:
            # Score based on output length relative to input
            return min(1.0, len(output_text) / max(len(input_text), 1) / 10)

        results = evaluate_with_custom_scorer(
            "traces/agenttrace.jsonl",
            scorer_fn=length_scorer,
            scorer_name="output_length"
        )
    """
    import mlflow.genai
    from mlflow.genai.scorers import make_scorer

    custom_scorer = make_scorer(
        name=scorer_name,
        fn=scorer_fn,
    )

    df = traces_to_mlflow_dataset(traces, **kwargs)

    return mlflow.genai.evaluate(
        data=df,
        scorers=[custom_scorer],
    )


def _create_scorers(scorer_names: list[str], model: str | None = None) -> list[Any]:
    """Create MLflow scorer objects from names."""
    from mlflow.genai.scorers import (
        Correctness,
        Groundedness,
        Guidelines,
        RelevanceToQuery,
        RetrievalPrecision,
    )

    SCORER_MAP = {
        "correctness": Correctness,
        "relevance": RelevanceToQuery,
        "groundedness": Groundedness,
        "retrieval_precision": RetrievalPrecision,
        "guidelines": Guidelines,
    }

    scorers = []
    for name in scorer_names:
        if name not in SCORER_MAP:
            available = ", ".join(SCORER_MAP.keys())
            raise ValueError(f"Unknown scorer: {name}. Available: {available}")

        scorer_class = SCORER_MAP[name]
        kwargs = {}
        if model:
            kwargs["model"] = model

        scorers.append(scorer_class(**kwargs))

    return scorers


def log_traces_to_mlflow(
    traces: str | Path | list[Any],
    experiment_name: str | None = None,
    run_name: str | None = None,
    tags: dict[str, str] | None = None,
) -> str:
    """
    Log AgentTrace traces to MLflow as an artifact.

    Args:
        traces: Path to JSONL file or list of AgentRun objects.
        experiment_name: MLflow experiment name (optional).
        run_name: MLflow run name (optional).
        tags: Additional tags to add to the run.

    Returns:
        MLflow run ID.

    Example:
        from agenttrace.integrations.mlflow_eval import log_traces_to_mlflow

        run_id = log_traces_to_mlflow(
            "traces/agenttrace.jsonl",
            experiment_name="rag-evaluation",
            run_name="baseline-v1"
        )
    """
    import tempfile

    import mlflow

    # Set experiment if provided
    if experiment_name:
        mlflow.set_experiment(experiment_name)

    # Load traces if path provided
    if isinstance(traces, (str, Path)):
        trace_path = Path(traces)
        trace_data = _load_traces_from_jsonl(traces)
    else:
        trace_data = traces
        trace_path = None

    with mlflow.start_run(run_name=run_name, tags=tags) as run:
        # Log metadata
        mlflow.log_param("trace_count", len(trace_data))

        total_tokens = sum(t.total_tokens for t in trace_data)
        total_cost = sum(t.total_cost_usd or 0 for t in trace_data)
        error_count = sum(1 for t in trace_data if t.error)

        mlflow.log_metrics(
            {
                "total_tokens": total_tokens,
                "total_cost_usd": total_cost,
                "error_count": error_count,
            }
        )

        # Log trace file as artifact
        if trace_path and trace_path.exists():
            mlflow.log_artifact(str(trace_path), "traces")
        else:
            # Create temporary file with traces
            with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
                for trace in trace_data:
                    f.write(trace.model_dump_json() + "\n")
                temp_path = f.name

            mlflow.log_artifact(temp_path, "traces")

        return run.info.run_id


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


def _default_extract_inputs(step: Any) -> str:
    """Default input extraction."""
    inputs = step.inputs or {}

    for key in ["input", "query", "question", "prompt"]:
        if key in inputs:
            return str(inputs[key])

    if "messages" in inputs:
        messages = inputs["messages"]
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return str(msg.get("content", ""))

    return str(inputs)


def _default_extract_outputs(step: Any) -> str:
    """Default output extraction."""
    outputs = step.outputs or {}

    for key in ["output", "result", "response", "answer", "content"]:
        if key in outputs:
            return str(outputs[key])

    if "message" in outputs:
        msg = outputs["message"]
        if isinstance(msg, dict) and "content" in msg:
            return str(msg["content"])
        return str(msg)

    return str(outputs)


def _default_extract_context(step: Any) -> str | None:
    """Default context extraction."""
    inputs = step.inputs or {}

    for key in ["context", "contexts", "retrieval_context", "documents"]:
        if key in inputs:
            ctx = inputs[key]
            if isinstance(ctx, list):
                return "\n\n".join(str(c) for c in ctx)
            return str(ctx)

    return None


def _default_extract_ground_truth(step: Any) -> str | None:
    """Default ground truth extraction."""
    inputs = step.inputs or {}
    outputs = step.outputs or {}

    for container in [inputs, outputs]:
        for key in ["ground_truth", "expected", "expected_output", "reference"]:
            if key in container:
                return str(container[key])

    return None
