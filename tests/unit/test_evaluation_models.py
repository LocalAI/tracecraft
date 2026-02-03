"""Tests for evaluation data models."""

from datetime import UTC, datetime
from uuid import uuid4

from tracecraft.evaluation.models import (
    EvaluationCase,
    EvaluationMetricConfig,
    EvaluationResult,
    EvaluationRun,
    EvaluationRunSummary,
    EvaluationSet,
    EvaluationStatus,
    MetricFramework,
    MetricScore,
)
from tracecraft.evaluation.runner import ProgressInfo


class TestMetricFramework:
    """Tests for MetricFramework enum."""

    def test_builtin_value(self):
        """Test builtin framework value."""
        assert MetricFramework.BUILTIN.value == "builtin"

    def test_deepeval_value(self):
        """Test deepeval framework value."""
        assert MetricFramework.DEEPEVAL.value == "deepeval"

    def test_ragas_value(self):
        """Test ragas framework value."""
        assert MetricFramework.RAGAS.value == "ragas"

    def test_mlflow_value(self):
        """Test mlflow framework value."""
        assert MetricFramework.MLFLOW.value == "mlflow"


class TestEvaluationStatus:
    """Tests for EvaluationStatus enum."""

    def test_all_statuses(self):
        """Test all status values."""
        assert EvaluationStatus.PENDING.value == "pending"
        assert EvaluationStatus.RUNNING.value == "running"
        assert EvaluationStatus.COMPLETED.value == "completed"
        assert EvaluationStatus.FAILED.value == "failed"


class TestEvaluationMetricConfig:
    """Tests for EvaluationMetricConfig model."""

    def test_create_basic_config(self):
        """Test creating a basic metric config."""
        config = EvaluationMetricConfig(
            name="exact_match",
            framework=MetricFramework.BUILTIN,
            metric_type="exact_match",
        )

        assert config.name == "exact_match"
        assert config.framework == MetricFramework.BUILTIN
        assert config.metric_type == "exact_match"
        assert config.threshold == 0.7  # default
        assert config.weight == 1.0  # default
        assert config.parameters == {}  # default

    def test_create_config_with_all_fields(self):
        """Test creating config with all fields."""
        config = EvaluationMetricConfig(
            name="faithfulness",
            framework=MetricFramework.DEEPEVAL,
            metric_type="faithfulness",
            threshold=0.8,
            weight=1.5,
            parameters={"model": "gpt-4"},
        )

        assert config.threshold == 0.8
        assert config.weight == 1.5
        assert config.parameters == {"model": "gpt-4"}

    def test_config_from_dict(self):
        """Test creating config from dict."""
        data = {
            "name": "answer_relevancy",
            "framework": "ragas",
            "metric_type": "answer_relevancy",
            "threshold": 0.75,
        }

        config = EvaluationMetricConfig.model_validate(data)
        assert config.name == "answer_relevancy"
        assert config.framework == MetricFramework.RAGAS

    def test_config_to_dict(self):
        """Test serializing config to dict."""
        config = EvaluationMetricConfig(
            name="test",
            framework=MetricFramework.BUILTIN,
            metric_type="test",
        )

        data = config.model_dump()
        assert data["name"] == "test"
        assert data["framework"] == "builtin"


class TestEvaluationCase:
    """Tests for EvaluationCase model."""

    def test_create_minimal_case(self):
        """Test creating a minimal case."""
        case = EvaluationCase(
            name="test-case",
            input={"prompt": "Hello"},
        )

        assert case.name == "test-case"
        assert case.input == {"prompt": "Hello"}
        assert case.id is not None
        assert case.expected_output is None
        assert case.retrieval_context == []
        assert case.tags == []

    def test_create_full_case(self):
        """Test creating a case with all fields."""
        set_id = uuid4()
        trace_id = uuid4()
        step_id = uuid4()

        case = EvaluationCase(
            id=uuid4(),
            evaluation_set_id=set_id,
            name="full-case",
            input={"question": "What is AI?"},
            expected_output={"answer": "Artificial Intelligence"},
            retrieval_context=["doc1", "doc2"],
            source_trace_id=trace_id,
            source_step_id=step_id,
            tags=["production", "customer-support"],
        )

        assert case.evaluation_set_id == set_id
        assert case.expected_output == {"answer": "Artificial Intelligence"}
        assert len(case.retrieval_context) == 2
        assert case.source_trace_id == trace_id
        assert case.source_step_id == step_id
        assert "production" in case.tags


class TestEvaluationSet:
    """Tests for EvaluationSet model."""

    def test_create_minimal_set(self):
        """Test creating a minimal set."""
        eval_set = EvaluationSet(name="test-set")

        assert eval_set.name == "test-set"
        assert eval_set.id is not None
        assert eval_set.description is None
        assert eval_set.project_id is None
        assert eval_set.metrics == []
        assert eval_set.default_threshold == 0.7
        assert eval_set.pass_rate_threshold == 0.8
        assert eval_set.cases == []

    def test_create_full_set(self):
        """Test creating a set with all fields."""
        metrics = [
            EvaluationMetricConfig(
                name="exact_match",
                framework=MetricFramework.BUILTIN,
                metric_type="exact_match",
            )
        ]

        cases = [EvaluationCase(name="case-1", input={"q": "test"})]

        eval_set = EvaluationSet(
            name="full-set",
            description="Test evaluation set",
            metrics=metrics,
            default_threshold=0.8,
            pass_rate_threshold=0.9,
            cases=cases,
        )

        assert eval_set.description == "Test evaluation set"
        assert len(eval_set.metrics) == 1
        assert len(eval_set.cases) == 1
        assert eval_set.default_threshold == 0.8
        assert eval_set.pass_rate_threshold == 0.9


class TestMetricScore:
    """Tests for MetricScore model."""

    def test_create_score(self):
        """Test creating a metric score."""
        score = MetricScore(
            metric_name="faithfulness",
            framework=MetricFramework.DEEPEVAL,
            score=0.85,
            passed=True,
            threshold=0.7,
        )

        assert score.metric_name == "faithfulness"
        assert score.score == 0.85
        assert score.passed is True
        assert score.threshold == 0.7
        assert score.reason is None
        assert score.details == {}

    def test_create_score_with_reason(self):
        """Test creating a score with reason."""
        score = MetricScore(
            metric_name="exact_match",
            framework=MetricFramework.BUILTIN,
            score=0.0,
            passed=False,
            threshold=1.0,
            reason="Output does not match expected",
        )

        assert score.passed is False
        assert score.reason == "Output does not match expected"


class TestEvaluationResult:
    """Tests for EvaluationResult model."""

    def test_create_result(self):
        """Test creating an evaluation result."""
        run_id = uuid4()
        case_id = uuid4()

        scores = [
            MetricScore(
                metric_name="test",
                framework=MetricFramework.BUILTIN,
                score=0.9,
                passed=True,
                threshold=0.7,
            )
        ]

        result = EvaluationResult(
            evaluation_run_id=run_id,
            evaluation_case_id=case_id,
            scores=scores,
            overall_score=0.9,
            passed=True,
        )

        assert result.evaluation_run_id == run_id
        assert result.evaluation_case_id == case_id
        assert len(result.scores) == 1
        assert result.overall_score == 0.9
        assert result.passed is True

    def test_result_with_actual_output(self):
        """Test result with actual output captured."""
        result = EvaluationResult(
            evaluation_run_id=uuid4(),
            evaluation_case_id=uuid4(),
            actual_output={"response": "The answer is 42"},
            scores=[],
            passed=True,
        )

        assert result.actual_output == {"response": "The answer is 42"}


class TestEvaluationRun:
    """Tests for EvaluationRun model."""

    def test_create_run(self):
        """Test creating an evaluation run."""
        set_id = uuid4()
        run = EvaluationRun(
            evaluation_set_id=set_id,
            total_cases=10,
        )

        assert run.evaluation_set_id == set_id
        assert run.status == EvaluationStatus.PENDING
        assert run.total_cases == 10
        assert run.passed_cases == 0
        assert run.failed_cases == 0
        assert run.started_at is not None

    def test_run_completed(self):
        """Test a completed run."""
        run = EvaluationRun(
            evaluation_set_id=uuid4(),
            status=EvaluationStatus.COMPLETED,
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
            overall_pass_rate=0.8,
            passed=True,
            completed_at=datetime.now(UTC),
            duration_ms=1500.0,
        )

        assert run.status == EvaluationStatus.COMPLETED
        assert run.passed_cases == 8
        assert run.failed_cases == 2
        assert run.overall_pass_rate == 0.8
        assert run.passed is True
        assert run.completed_at is not None
        assert run.duration_ms == 1500.0


class TestEvaluationRunSummary:
    """Tests for EvaluationRunSummary model."""

    def test_create_summary(self):
        """Test creating a run summary."""
        summary = EvaluationRunSummary(
            id=uuid4(),
            evaluation_set_id=uuid4(),
            evaluation_set_name="test-set",
            status=EvaluationStatus.COMPLETED,
            total_cases=10,
            passed_cases=9,
            failed_cases=1,
            overall_pass_rate=0.9,
            passed=True,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            duration_ms=1500.0,
        )

        assert summary.total_cases == 10
        assert summary.passed_cases == 9
        assert summary.overall_pass_rate == 0.9
        assert summary.passed is True

    def test_summary_with_none_values(self):
        """Test summary with optional None values."""
        summary = EvaluationRunSummary(
            id=uuid4(),
            evaluation_set_id=uuid4(),
            evaluation_set_name="test-set",
            status=EvaluationStatus.PENDING,
            total_cases=5,
            passed_cases=0,
            failed_cases=0,
            overall_pass_rate=None,
            passed=None,
            started_at=datetime.now(UTC),
            completed_at=None,
            duration_ms=None,
        )

        assert summary.overall_pass_rate is None
        assert summary.passed is None


class TestProgressInfo:
    """Tests for ProgressInfo dataclass."""

    def test_create_progress_info(self):
        """Test creating progress info."""
        info = ProgressInfo(
            total_cases=10,
            completed_cases=5,
            passed_cases=4,
            failed_cases=1,
        )

        assert info.total_cases == 10
        assert info.completed_cases == 5
        assert info.passed_cases == 4
        assert info.failed_cases == 1
        # progress_percent is a computed property
        assert info.progress_percent == 50.0

    def test_progress_with_current_info(self):
        """Test progress with current case info."""
        info = ProgressInfo(
            total_cases=10,
            completed_cases=3,
            passed_cases=3,
            failed_cases=0,
            current_case="test-case-4",
            current_metric="faithfulness",
        )

        assert info.current_case == "test-case-4"
        assert info.current_metric == "faithfulness"
        # progress_percent is computed from completed/total
        assert info.progress_percent == 30.0
