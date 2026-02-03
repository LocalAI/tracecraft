"""Tests for evaluation helpers."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from tracecraft.core.models import AgentRun, Step, StepType


class TestEvaluationStep:
    """Tests for evaluation_step context manager."""

    def test_evaluation_step_creates_step(self):
        """Test evaluation_step creates a Step."""
        from tracecraft.contrib.evaluation import evaluation_step

        with evaluation_step("test_eval") as step:
            assert step.type == StepType.EVALUATION
            assert step.name == "test_eval"
            assert step.start_time is not None

    def test_evaluation_step_with_evaluator_name(self):
        """Test evaluation_step captures evaluator name."""
        from tracecraft.contrib.evaluation import evaluation_step

        with evaluation_step("test_eval", evaluator_name="relevance") as step:
            assert step.inputs["evaluator_name"] == "relevance"

    def test_evaluation_step_with_inputs(self):
        """Test evaluation_step captures inputs."""
        from tracecraft.contrib.evaluation import evaluation_step

        with evaluation_step("test_eval", inputs={"question": "What is AI?"}) as step:
            assert step.inputs["question"] == "What is AI?"

    def test_evaluation_step_captures_error(self):
        """Test evaluation_step captures errors."""
        from tracecraft.contrib.evaluation import evaluation_step

        with pytest.raises(ValueError), evaluation_step("test_eval") as step:
            raise ValueError("Test error")

        assert step.error == "Test error"
        assert step.error_type == "ValueError"

    def test_evaluation_step_sets_duration(self):
        """Test evaluation_step sets duration on exit."""
        from tracecraft.contrib.evaluation import evaluation_step

        with evaluation_step("test_eval") as step:
            pass

        assert step.end_time is not None
        assert step.duration_ms is not None
        assert step.duration_ms >= 0

    def test_evaluation_step_with_run_context(self):
        """Test evaluation_step attaches to run."""
        from tracecraft.contrib.evaluation import evaluation_step
        from tracecraft.core.context import run_context

        run = AgentRun(name="test", start_time=datetime.now(UTC))

        with run_context(run), evaluation_step("test_eval") as step:
            assert step.trace_id == run.id


class TestRecordEvaluationResult:
    """Tests for record_evaluation_result helper."""

    def test_record_scores(self):
        """Test recording evaluation scores."""
        from tracecraft.contrib.evaluation import (
            evaluation_step,
            record_evaluation_result,
        )

        with evaluation_step("test_eval") as step:
            record_evaluation_result(
                step,
                scores={"relevance": 0.85, "coherence": 0.92},
            )

        assert step.outputs["scores"]["relevance"] == 0.85
        assert step.outputs["scores"]["coherence"] == 0.92

    def test_record_passed(self):
        """Test recording pass/fail status."""
        from tracecraft.contrib.evaluation import (
            evaluation_step,
            record_evaluation_result,
        )

        with evaluation_step("test_eval") as step:
            record_evaluation_result(step, scores={"score": 0.9}, passed=True, threshold=0.8)

        assert step.outputs["passed"] is True
        assert step.outputs["threshold"] == 0.8

    def test_record_metadata(self):
        """Test recording metadata."""
        from tracecraft.contrib.evaluation import (
            evaluation_step,
            record_evaluation_result,
        )

        with evaluation_step("test_eval") as step:
            record_evaluation_result(
                step,
                scores={"score": 0.9},
                metadata={"evaluator_version": "1.0"},
            )

        assert step.attributes["evaluator_version"] == "1.0"


class TestCreateTracedEvaluator:
    """Tests for create_traced_evaluator wrapper."""

    def test_wrap_evaluator_function(self):
        """Test wrapping an evaluator function."""
        from tracecraft.contrib.evaluation import create_traced_evaluator

        def my_evaluator(_output: str) -> dict[str, float]:
            return {"score": 0.9}

        traced = create_traced_evaluator(my_evaluator)
        result = traced("test output")

        assert result == {"score": 0.9}

    def test_wrapped_evaluator_has_custom_name(self):
        """Test wrapped evaluator can have custom name."""
        from tracecraft.contrib.evaluation import create_traced_evaluator

        def my_evaluator(_output: str) -> dict[str, float]:
            return {"score": 0.9}

        traced = create_traced_evaluator(my_evaluator, name="custom_eval")

        # Just verify it doesn't raise
        result = traced("test")
        assert result == {"score": 0.9}


class TestHasMLflow:
    """Tests for MLflow availability check."""

    def test_has_mlflow_returns_bool(self):
        """Test has_mlflow returns a boolean."""
        from tracecraft.contrib.evaluation import has_mlflow

        result = has_mlflow()
        assert isinstance(result, bool)


class TestMLflowEvaluationFunctions:
    """Tests for MLflow-specific evaluation functions."""

    def test_evaluate_with_mlflow_raises_when_not_installed(self):
        """Test evaluate_with_mlflow raises when MLflow not installed."""
        from tracecraft.contrib.evaluation import has_mlflow

        if not has_mlflow():
            from tracecraft.contrib.evaluation import evaluate_with_mlflow

            with pytest.raises(ImportError):
                evaluate_with_mlflow(data=None)

    def test_log_evaluation_to_mlflow_raises_when_not_installed(self):
        """Test log_evaluation_to_mlflow raises when MLflow not installed."""
        from tracecraft.contrib.evaluation import has_mlflow

        if not has_mlflow():
            from tracecraft.contrib.evaluation import log_evaluation_to_mlflow

            step = Step(
                trace_id=uuid4(),
                type=StepType.EVALUATION,
                name="test",
                start_time=datetime.now(UTC),
            )

            with pytest.raises(ImportError):
                log_evaluation_to_mlflow(step)
