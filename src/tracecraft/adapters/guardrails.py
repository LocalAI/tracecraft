"""
Guardrails AI adapter for TraceCraft.

Provides utilities for tracking Guardrails validation operations
within TraceCraft traces.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from tracecraft.core.context import get_current_run
from tracecraft.core.models import Step, StepType

if TYPE_CHECKING:
    pass


@contextmanager
def guardrail_step(
    name: str,
    guard_name: str | None = None,
    inputs: dict[str, Any] | None = None,
) -> Generator[Step, None, None]:
    """
    Context manager for tracking Guardrails validation operations.

    Creates a Step that captures the validation process, including
    inputs, outputs, pass/fail status, and any validation errors.

    Usage:
        ```python
        from tracecraft.adapters.guardrails import guardrail_step
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        run = AgentRun(name="my_run", start_time=datetime.now(UTC))

        with run_context(run):
            with guardrail_step("validate_output", guard_name="OutputGuard") as step:
                result = guard.validate(llm_output)
                step.outputs = {
                    "validated_output": result.validated_output,
                    "validation_passed": result.validation_passed,
                }
                if not result.validation_passed:
                    step.attributes["failed_validations"] = result.failed_validations
        ```

    Args:
        name: Name of the validation step.
        guard_name: Optional name of the Guard being used.
        inputs: Optional initial inputs dict.

    Yields:
        The Step object being tracked.
    """
    from uuid import uuid4 as make_uuid

    run = get_current_run()

    step_inputs = inputs.copy() if inputs else {}
    if guard_name:
        step_inputs["guard_name"] = guard_name

    if run is None:
        # Create a dummy step that won't be tracked
        step = Step(
            trace_id=make_uuid(),
            type=StepType.GUARDRAIL,
            name=name,
            start_time=datetime.now(UTC),
            inputs=step_inputs,
        )
        yield step
        return

    step = Step(
        trace_id=run.id,
        type=StepType.GUARDRAIL,
        name=name,
        start_time=datetime.now(UTC),
        inputs=step_inputs,
    )
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


@contextmanager
def track_validation(
    guard_name: str,
    input_text: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Generator[Step, None, None]:
    """
    Track a Guardrails validation operation.

    Convenience wrapper around guardrail_step with common parameters.

    Args:
        guard_name: Name of the Guard being used.
        input_text: The text being validated (will be stored in inputs).
        metadata: Additional metadata to store in attributes.

    Yields:
        The Step object being tracked.
    """
    inputs: dict[str, Any] = {}
    if input_text is not None:
        inputs["input_text"] = input_text

    with guardrail_step(
        name=f"guardrail:{guard_name}",
        guard_name=guard_name,
        inputs=inputs,
    ) as step:
        if metadata:
            step.attributes = metadata
        yield step


def record_validation_result(
    step: Step,
    passed: bool,
    validated_output: Any | None = None,
    raw_output: Any | None = None,
    failed_validations: list[dict[str, Any]] | None = None,
    reasks: int = 0,
) -> None:
    """
    Record the result of a Guardrails validation on a Step.

    Use this helper to consistently record validation results.

    Args:
        step: The Step to update.
        passed: Whether validation passed.
        validated_output: The validated/corrected output.
        raw_output: The original raw LLM output.
        failed_validations: List of failed validation details.
        reasks: Number of reask attempts made.
    """
    step.outputs = {
        "validation_passed": passed,
    }

    if validated_output is not None:
        step.outputs["validated_output"] = validated_output
    if raw_output is not None:
        step.outputs["raw_output"] = raw_output

    step.attributes = step.attributes or {}
    step.attributes["reasks"] = reasks

    if failed_validations:
        step.attributes["failed_validations"] = failed_validations
        step.attributes["failure_count"] = len(failed_validations)


# Try to import Guardrails for advanced integration
try:
    from guardrails import Guard
    from guardrails.classes.history import Call

    _HAS_GUARDRAILS = True

    def wrap_guard(guard: Guard, name: str | None = None) -> Guard:
        """
        Wrap a Guardrails Guard to automatically trace validations.

        This creates a wrapper that tracks each validation call as a Step.

        Args:
            guard: The Guard instance to wrap.
            name: Optional custom name for tracing (defaults to guard name).

        Returns:
            The wrapped Guard (same instance, with tracing attached).
        """
        original_call = guard.__call__

        def traced_call(*args: Any, **kwargs: Any) -> Call:
            guard_name = name or getattr(guard, "name", "unnamed_guard")
            with guardrail_step(
                name=f"guardrail:{guard_name}",
                guard_name=guard_name,
                inputs={"args": str(args)[:500], "kwargs_keys": list(kwargs.keys())},
            ) as step:
                result = original_call(*args, **kwargs)

                # Record result
                record_validation_result(
                    step=step,
                    passed=result.validation_passed,
                    validated_output=str(result.validated_output)[:1000]
                    if result.validated_output
                    else None,
                    raw_output=str(result.raw_llm_output)[:1000] if result.raw_llm_output else None,
                    reasks=result.reask_count if hasattr(result, "reask_count") else 0,
                )

                return result

        guard.__call__ = traced_call
        return guard

except ImportError:
    _HAS_GUARDRAILS = False

    def wrap_guard(guard: Any, name: str | None = None) -> Any:  # noqa: ARG001
        """Guardrails not installed - returns guard unchanged."""
        return guard
