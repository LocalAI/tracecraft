"""
MLflow evaluation helpers for AgentTrace.

Provides utilities for evaluating LLM agent outputs using MLflow's
evaluation framework, with integration into AgentTrace traces.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from agenttrace.core.context import get_current_run
from agenttrace.core.models import Step, StepType

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@contextmanager
def evaluation_step(
    name: str,
    evaluator_name: str | None = None,
    inputs: dict[str, Any] | None = None,
) -> Generator[Step, None, None]:
    """
    Context manager for tracking evaluation operations.

    Creates a Step that captures an evaluation run, including the
    evaluator used, inputs evaluated, and results.

    Args:
        name: Name of the evaluation step.
        evaluator_name: Name of the evaluator (e.g., "relevance", "toxicity").
        inputs: Optional initial inputs dict.

    Yields:
        The Step object being tracked.

    Example:
        ```python
        from agenttrace.contrib.evaluation import evaluation_step

        with evaluation_step("evaluate_response", evaluator_name="relevance") as step:
            score = evaluate_relevance(question, answer)
            step.outputs = {"relevance_score": score}
        ```
    """
    from uuid import uuid4 as make_uuid

    run = get_current_run()

    step_inputs = inputs.copy() if inputs else {}
    if evaluator_name:
        step_inputs["evaluator_name"] = evaluator_name

    # Create step with trace_id from run or generate new one
    trace_id = run.id if run is not None else make_uuid()

    step = Step(
        trace_id=trace_id,
        type=StepType.EVALUATION,
        name=name,
        start_time=datetime.now(UTC),
        inputs=step_inputs,
    )

    # Only attach to run if we have one
    if run is not None:
        run.steps.append(step)

    try:
        yield step
    except BaseException as e:
        step.error = str(e)
        step.error_type = type(e).__name__
        raise
    finally:
        step.end_time = datetime.now(UTC)
        step.duration_ms = (step.end_time - step.start_time).total_seconds() * 1000


def record_evaluation_result(
    step: Step,
    scores: dict[str, float],
    passed: bool | None = None,
    threshold: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    Record evaluation results on a Step.

    Args:
        step: The Step to update.
        scores: Dictionary of score names to values.
        passed: Whether the evaluation passed (optional).
        threshold: The threshold used for pass/fail (optional).
        metadata: Additional metadata about the evaluation.

    Example:
        ```python
        with evaluation_step("quality_check") as step:
            scores = run_evaluation(output)
            record_evaluation_result(
                step,
                scores={"relevance": 0.85, "coherence": 0.92},
                passed=True,
                threshold=0.8
            )
        ```
    """
    step.outputs = step.outputs or {}
    step.outputs["scores"] = scores

    if passed is not None:
        step.outputs["passed"] = passed
    if threshold is not None:
        step.outputs["threshold"] = threshold

    step.attributes = step.attributes or {}
    if metadata:
        step.attributes.update(metadata)


def create_traced_evaluator(
    evaluator_fn: Callable[..., dict[str, float]],
    name: str | None = None,
) -> Callable[..., dict[str, float]]:
    """
    Wrap an evaluator function to automatically trace its execution.

    Args:
        evaluator_fn: The evaluator function to wrap.
        name: Optional name for the evaluation step.

    Returns:
        Wrapped evaluator function that creates traced steps.

    Example:
        ```python
        def my_evaluator(output: str, reference: str) -> dict[str, float]:
            # Custom evaluation logic
            return {"similarity": 0.9}

        traced_evaluator = create_traced_evaluator(my_evaluator, name="similarity_check")

        # Usage in traced context
        scores = traced_evaluator(output, reference)
        ```
    """
    eval_name = name or evaluator_fn.__name__

    def wrapper(*args: Any, **kwargs: Any) -> dict[str, float]:
        with evaluation_step(eval_name) as step:
            result = evaluator_fn(*args, **kwargs)
            step.outputs = {"scores": result}
            return result

    return wrapper


# MLflow-specific evaluation helpers
try:
    import mlflow

    _HAS_MLFLOW = True

    def evaluate_with_mlflow(
        data: Any,
        model: Any = None,
        evaluators: list[str] | None = None,
        experiment_name: str | None = None,
        track_in_agenttrace: bool = True,
        **kwargs: Any,
    ) -> Any:
        """
        Run MLflow evaluation with AgentTrace tracking.

        Wraps mlflow.evaluate() to automatically create AgentTrace
        evaluation steps for each evaluator run.

        Args:
            data: Evaluation dataset (pandas DataFrame or path).
            model: Model to evaluate (optional, can use predictions in data).
            evaluators: List of evaluator names (e.g., ["toxicity", "relevance"]).
            experiment_name: MLflow experiment name.
            track_in_agenttrace: Whether to create AgentTrace steps.
            **kwargs: Additional arguments passed to mlflow.evaluate().

        Returns:
            MLflow EvaluationResult object.

        Example:
            ```python
            import pandas as pd
            from agenttrace.contrib.evaluation import evaluate_with_mlflow

            eval_data = pd.DataFrame({
                "questions": ["What is AI?", "What is ML?"],
                "answers": ["AI is...", "ML is..."],
                "ground_truth": ["Artificial Intelligence", "Machine Learning"]
            })

            results = evaluate_with_mlflow(
                data=eval_data,
                evaluators=["toxicity"],
                experiment_name="my-eval"
            )
            ```
        """
        if experiment_name:
            mlflow.set_experiment(experiment_name)

        if not track_in_agenttrace:
            return mlflow.evaluate(data=data, model=model, evaluators=evaluators, **kwargs)

        # Track in AgentTrace
        evaluator_list = evaluators or ["default"]

        with evaluation_step(
            name="mlflow_evaluate",
            evaluator_name=",".join(evaluator_list),
            inputs={"evaluators": evaluator_list},
        ) as step:
            result = mlflow.evaluate(data=data, model=model, evaluators=evaluators, **kwargs)

            # Extract metrics from result
            if hasattr(result, "metrics"):
                step.outputs = {"metrics": result.metrics}
            else:
                step.outputs = {"result": str(result)}

            return result

    def log_evaluation_to_mlflow(
        step: Step,
        run_id: str | None = None,
    ) -> None:
        """
        Log an AgentTrace evaluation step to MLflow.

        Args:
            step: The evaluation Step to log.
            run_id: Optional MLflow run ID. If None, uses active run.

        Example:
            ```python
            from agenttrace.contrib.evaluation import evaluation_step, log_evaluation_to_mlflow

            with evaluation_step("my_eval") as step:
                step.outputs = {"score": 0.95}

            log_evaluation_to_mlflow(step)
            ```
        """
        if run_id:
            with mlflow.start_run(run_id=run_id):
                _log_step_to_mlflow(step)
        elif mlflow.active_run():
            _log_step_to_mlflow(step)
        else:
            with mlflow.start_run():
                _log_step_to_mlflow(step)

    def _log_step_to_mlflow(step: Step) -> None:
        """Internal helper to log step metrics to MLflow."""
        # Log scores as metrics
        if step.outputs and "scores" in step.outputs:
            for score_name, score_value in step.outputs["scores"].items():
                if isinstance(score_value, (int, float)):
                    mlflow.log_metric(f"eval.{step.name}.{score_name}", score_value)

        # Log pass/fail
        if step.outputs and "passed" in step.outputs:
            mlflow.log_metric(f"eval.{step.name}.passed", int(step.outputs["passed"]))

        # Log duration
        if step.duration_ms:
            mlflow.log_metric(f"eval.{step.name}.duration_ms", step.duration_ms)

        # Log evaluator as tag
        if step.inputs and "evaluator_name" in step.inputs:
            mlflow.set_tag(f"eval.{step.name}.evaluator", step.inputs["evaluator_name"])

except ImportError:
    _HAS_MLFLOW = False

    def evaluate_with_mlflow(*args: Any, **kwargs: Any) -> Any:  # noqa: ARG001
        """MLflow not installed - raises ImportError."""
        raise ImportError(
            "mlflow required for evaluate_with_mlflow. Install with: pip install agenttrace[mlflow]"
        )

    def log_evaluation_to_mlflow(*args: Any, **kwargs: Any) -> Any:  # noqa: ARG001
        """MLflow not installed - raises ImportError."""
        raise ImportError(
            "mlflow required for log_evaluation_to_mlflow. "
            "Install with: pip install agenttrace[mlflow]"
        )


def has_mlflow() -> bool:
    """Check if MLflow is available."""
    return _HAS_MLFLOW
