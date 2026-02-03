"""
Tests for Guardrails adapter.

TDD approach: Tests for the Guardrails validation tracking integration.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun, StepType


class TestGuardrailStep:
    """Tests for guardrail_step context manager."""

    def test_create_guardrail_step(self) -> None:
        """Should be able to create a GUARDRAIL step."""
        from tracecraft.adapters.guardrails import guardrail_step

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run), guardrail_step("validate_output") as step:
            step.outputs = {"validation_passed": True}

        assert len(run.steps) == 1
        assert run.steps[0].type == StepType.GUARDRAIL
        assert run.steps[0].name == "validate_output"

    def test_guardrail_step_captures_guard_name(self) -> None:
        """Should capture guard_name in inputs."""
        from tracecraft.adapters.guardrails import guardrail_step

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run), guardrail_step("validate", guard_name="OutputValidator"):
            pass

        assert run.steps[0].inputs["guard_name"] == "OutputValidator"

    def test_guardrail_step_captures_inputs(self) -> None:
        """Should capture custom inputs."""
        from tracecraft.adapters.guardrails import guardrail_step

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run), guardrail_step("validate", inputs={"text": "Hello world"}):
            pass

        assert run.steps[0].inputs["text"] == "Hello world"

    def test_guardrail_step_captures_duration(self) -> None:
        """Should capture duration."""
        from tracecraft.adapters.guardrails import guardrail_step

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run), guardrail_step("validate"):
            pass

        assert run.steps[0].end_time is not None
        assert run.steps[0].duration_ms is not None
        assert run.steps[0].duration_ms >= 0

    def test_guardrail_step_captures_error(self) -> None:
        """Should capture errors during validation."""
        from tracecraft.adapters.guardrails import guardrail_step

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run), pytest.raises(ValueError), guardrail_step("validate"):
            raise ValueError("Validation failed")

        assert run.steps[0].error == "Validation failed"
        assert run.steps[0].error_type == "ValueError"

    def test_guardrail_step_without_run_context(self) -> None:
        """Should work without run context (creates dummy step)."""
        from tracecraft.adapters.guardrails import guardrail_step

        # No run context - should not raise
        with guardrail_step("validate") as step:
            step.outputs = {"passed": True}

        assert step.type == StepType.GUARDRAIL
        assert step.outputs["passed"] is True


class TestTrackValidation:
    """Tests for track_validation helper."""

    def test_track_validation_creates_step(self) -> None:
        """Should create a guardrail step with guard name."""
        from tracecraft.adapters.guardrails import track_validation

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run), track_validation("OutputGuard"):
            pass

        assert run.steps[0].type == StepType.GUARDRAIL
        assert run.steps[0].name == "guardrail:OutputGuard"
        assert run.steps[0].inputs["guard_name"] == "OutputGuard"

    def test_track_validation_with_input_text(self) -> None:
        """Should capture input text."""
        from tracecraft.adapters.guardrails import track_validation

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run), track_validation("TextValidator", input_text="Check this text"):
            pass

        assert run.steps[0].inputs["input_text"] == "Check this text"

    def test_track_validation_with_metadata(self) -> None:
        """Should store metadata in attributes."""
        from tracecraft.adapters.guardrails import track_validation

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with (
            run_context(run),
            track_validation("Guard", metadata={"version": "1.0", "mode": "strict"}),
        ):
            pass

        assert run.steps[0].attributes["version"] == "1.0"
        assert run.steps[0].attributes["mode"] == "strict"


class TestRecordValidationResult:
    """Tests for record_validation_result helper."""

    def test_record_passed_validation(self) -> None:
        """Should record passed validation."""
        from tracecraft.adapters.guardrails import (
            guardrail_step,
            record_validation_result,
        )

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run), guardrail_step("validate") as step:
            record_validation_result(
                step=step,
                passed=True,
                validated_output="Clean output",
            )

        assert run.steps[0].outputs["validation_passed"] is True
        assert run.steps[0].outputs["validated_output"] == "Clean output"

    def test_record_failed_validation(self) -> None:
        """Should record failed validation with details."""
        from tracecraft.adapters.guardrails import (
            guardrail_step,
            record_validation_result,
        )

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run), guardrail_step("validate") as step:
            record_validation_result(
                step=step,
                passed=False,
                raw_output="Bad output",
                failed_validations=[{"validator": "no_pii", "message": "PII detected"}],
            )

        assert run.steps[0].outputs["validation_passed"] is False
        assert run.steps[0].outputs["raw_output"] == "Bad output"
        assert run.steps[0].attributes["failed_validations"][0]["validator"] == "no_pii"
        assert run.steps[0].attributes["failure_count"] == 1

    def test_record_validation_with_reasks(self) -> None:
        """Should record reask count."""
        from tracecraft.adapters.guardrails import (
            guardrail_step,
            record_validation_result,
        )

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run), guardrail_step("validate") as step:
            record_validation_result(
                step=step,
                passed=True,
                validated_output="Fixed output",
                reasks=2,
            )

        assert run.steps[0].attributes["reasks"] == 2


class TestWrapGuard:
    """Tests for wrap_guard helper (when guardrails not installed)."""

    def test_wrap_guard_without_guardrails(self) -> None:
        """Should return guard unchanged when guardrails not installed."""
        from tracecraft.adapters.guardrails import wrap_guard

        mock_guard = object()
        result = wrap_guard(mock_guard)

        # Should return the same object unchanged
        assert result is mock_guard
