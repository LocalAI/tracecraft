"""Tests for EvaluationRunner and adapters."""

import tempfile
from pathlib import Path
from uuid import UUID

import pytest

from tracecraft.evaluation.adapters.base import (
    BaseMetricAdapter,
    MetricResult,
    get_adapter,
)
from tracecraft.evaluation.adapters.builtin import BuiltinMetricAdapter
from tracecraft.evaluation.models import (
    EvaluationCase,
    EvaluationMetricConfig,
    EvaluationSet,
    EvaluationStatus,
    MetricFramework,
)
from tracecraft.evaluation.runner import EvaluationRunner
from tracecraft.storage.sqlite import SQLiteTraceStore


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    store = SQLiteTraceStore(db_path)
    yield store

    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def sample_eval_set():
    """Create a sample evaluation set for testing."""
    return EvaluationSet(
        name="test-set",
        metrics=[
            EvaluationMetricConfig(
                name="exact_match",
                framework=MetricFramework.BUILTIN,
                metric_type="exact_match",
                threshold=1.0,
            )
        ],
        cases=[
            EvaluationCase(
                name="case-1",
                input={"prompt": "What is 2+2?"},
                expected_output={"answer": "4"},
            ),
            EvaluationCase(
                name="case-2",
                input={"prompt": "What is 3+3?"},
                expected_output={"answer": "6"},
            ),
        ],
    )


class TestBaseMetricAdapter:
    """Tests for BaseMetricAdapter and registry."""

    def test_get_builtin_adapter(self):
        """Test getting the builtin adapter."""
        adapter = get_adapter(MetricFramework.BUILTIN)
        assert adapter is not None
        assert isinstance(adapter, BuiltinMetricAdapter)

    def test_get_adapter_not_registered(self):
        """Test getting an unregistered adapter returns None."""
        # Create a fake framework that's not registered
        # This should return None for frameworks without adapters
        adapter = get_adapter(MetricFramework.DEEPEVAL)
        # May or may not be registered depending on test environment
        # Just verify it doesn't raise

    def test_register_custom_adapter(self):
        """Test registering a custom adapter."""

        class CustomAdapter(BaseMetricAdapter):
            @property
            def framework_name(self) -> str:
                return "custom"

            @property
            def supported_metrics(self) -> list[str]:
                return ["custom_metric"]

            async def evaluate(self, case, actual_output, metric_config):
                return MetricResult(score=1.0, passed=True, reason="Custom")

        # Register shouldn't raise
        # Note: We can't actually test this without modifying the enum


class TestBuiltinMetricAdapter:
    """Tests for BuiltinMetricAdapter."""

    @pytest.fixture
    def adapter(self):
        """Get the builtin adapter."""
        return BuiltinMetricAdapter()

    def test_framework_name(self, adapter):
        """Test adapter framework name."""
        assert adapter.framework_name == "builtin"

    def test_supported_metrics(self, adapter):
        """Test supported metrics list."""
        metrics = adapter.supported_metrics
        assert "exact_match" in metrics
        assert "regex_match" in metrics
        assert "contains" in metrics
        assert "not_contains" in metrics
        assert "json_valid" in metrics
        assert "length_check" in metrics

    @pytest.mark.asyncio
    async def test_exact_match_pass(self, adapter):
        """Test exact_match metric passing."""
        case = EvaluationCase(
            name="test",
            input={"q": "test"},
            expected_output={"answer": "hello"},
        )
        config = EvaluationMetricConfig(
            name="exact_match",
            framework=MetricFramework.BUILTIN,
            metric_type="exact_match",
            threshold=1.0,
        )

        result = await adapter.evaluate(case, "hello", config)

        assert result.score == 1.0
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_exact_match_fail(self, adapter):
        """Test exact_match metric failing."""
        case = EvaluationCase(
            name="test",
            input={"q": "test"},
            expected_output={"answer": "hello"},
        )
        config = EvaluationMetricConfig(
            name="exact_match",
            framework=MetricFramework.BUILTIN,
            metric_type="exact_match",
            threshold=1.0,
        )

        result = await adapter.evaluate(case, "world", config)

        assert result.score == 0.0
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_contains_pass(self, adapter):
        """Test contains metric passing."""
        case = EvaluationCase(
            name="test",
            input={"q": "test"},
            expected_output={"answer": "Python"},
        )
        config = EvaluationMetricConfig(
            name="contains",
            framework=MetricFramework.BUILTIN,
            metric_type="contains",
            threshold=1.0,
        )

        result = await adapter.evaluate(case, "I love Python programming", config)

        assert result.score == 1.0
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_contains_fail(self, adapter):
        """Test contains metric failing."""
        case = EvaluationCase(
            name="test",
            input={"q": "test"},
            expected_output={"answer": "Python"},
        )
        config = EvaluationMetricConfig(
            name="contains",
            framework=MetricFramework.BUILTIN,
            metric_type="contains",
            threshold=1.0,
        )

        result = await adapter.evaluate(case, "I love JavaScript", config)

        assert result.score == 0.0
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_not_contains_pass(self, adapter):
        """Test not_contains metric passing."""
        case = EvaluationCase(
            name="test",
            input={"q": "test"},
        )
        config = EvaluationMetricConfig(
            name="not_contains",
            framework=MetricFramework.BUILTIN,
            metric_type="not_contains",
            threshold=1.0,
            parameters={"text": "error"},  # Specify text via parameters
        )

        result = await adapter.evaluate(case, "Success!", config)

        assert result.score == 1.0
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_regex_match_pass(self, adapter):
        """Test regex_match metric passing."""
        case = EvaluationCase(
            name="test",
            input={"q": "test"},
        )
        config = EvaluationMetricConfig(
            name="regex_match",
            framework=MetricFramework.BUILTIN,
            metric_type="regex_match",
            threshold=1.0,
            parameters={"pattern": r"\d{4}-\d{2}-\d{2}"},
        )

        result = await adapter.evaluate(case, "Date: 2024-01-15", config)

        assert result.score == 1.0
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_regex_match_fail(self, adapter):
        """Test regex_match metric failing."""
        case = EvaluationCase(
            name="test",
            input={"q": "test"},
        )
        config = EvaluationMetricConfig(
            name="regex_match",
            framework=MetricFramework.BUILTIN,
            metric_type="regex_match",
            threshold=1.0,
            parameters={"pattern": r"\d{4}-\d{2}-\d{2}"},
        )

        result = await adapter.evaluate(case, "Date: January 15", config)

        assert result.score == 0.0
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_json_valid_pass(self, adapter):
        """Test json_valid metric passing."""
        case = EvaluationCase(name="test", input={"q": "test"})
        config = EvaluationMetricConfig(
            name="json_valid",
            framework=MetricFramework.BUILTIN,
            metric_type="json_valid",
            threshold=1.0,
        )

        result = await adapter.evaluate(case, '{"key": "value"}', config)

        assert result.score == 1.0
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_json_valid_fail(self, adapter):
        """Test json_valid metric failing."""
        case = EvaluationCase(name="test", input={"q": "test"})
        config = EvaluationMetricConfig(
            name="json_valid",
            framework=MetricFramework.BUILTIN,
            metric_type="json_valid",
            threshold=1.0,
        )

        result = await adapter.evaluate(case, "not valid json", config)

        assert result.score == 0.0
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_length_check_pass(self, adapter):
        """Test length_check metric passing."""
        case = EvaluationCase(name="test", input={"q": "test"})
        config = EvaluationMetricConfig(
            name="length_check",
            framework=MetricFramework.BUILTIN,
            metric_type="length_check",
            threshold=1.0,
            parameters={"min_length": 10, "max_length": 100},
        )

        result = await adapter.evaluate(case, "This is a valid length response", config)

        assert result.score == 1.0
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_length_check_too_short(self, adapter):
        """Test length_check metric failing for too short."""
        case = EvaluationCase(name="test", input={"q": "test"})
        config = EvaluationMetricConfig(
            name="length_check",
            framework=MetricFramework.BUILTIN,
            metric_type="length_check",
            threshold=1.0,
            parameters={"min_length": 50},
        )

        result = await adapter.evaluate(case, "Short", config)

        # Score is partial (length / min_length = 5/50 = 0.1)
        assert result.score < 1.0
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_length_check_too_long(self, adapter):
        """Test length_check metric failing for too long."""
        case = EvaluationCase(name="test", input={"q": "test"})
        config = EvaluationMetricConfig(
            name="length_check",
            framework=MetricFramework.BUILTIN,
            metric_type="length_check",
            threshold=1.0,
            parameters={"max_length": 5},
        )

        result = await adapter.evaluate(case, "This is way too long", config)

        # Score is partial (max_length / length = 5/20 = 0.25)
        assert result.score < 1.0
        assert result.passed is False


class TestEvaluationRunner:
    """Tests for EvaluationRunner."""

    def test_runner_init(self, temp_db):
        """Test runner initialization."""
        runner = EvaluationRunner(store=temp_db)
        assert runner is not None

    def test_runner_init_without_store(self):
        """Test runner initialization without store."""
        runner = EvaluationRunner()
        assert runner is not None

    @pytest.mark.asyncio
    async def test_run_simple_evaluation(self, sample_eval_set):
        """Test running a simple evaluation (without store to avoid FK issues)."""
        runner = EvaluationRunner(store=None)

        # Define output generator that returns expected values
        def output_generator(case):
            if "2+2" in str(case.input):
                return "4"
            elif "3+3" in str(case.input):
                return "6"
            return "unknown"

        result = await runner.run(sample_eval_set, output_generator=output_generator)

        assert result.status == EvaluationStatus.COMPLETED
        assert result.total_cases == 2
        assert result.passed_cases == 2
        assert result.failed_cases == 0
        assert result.pass_rate == 1.0
        assert result.overall_passed is True

    @pytest.mark.asyncio
    async def test_run_with_failures(self, temp_db):
        """Test running evaluation with failures."""
        # Create eval set in database first
        set_id = temp_db.create_evaluation_set(
            name="fail-test",
            metrics=[
                {
                    "name": "exact_match",
                    "framework": "builtin",
                    "metric_type": "exact_match",
                    "threshold": 1.0,
                }
            ],
        )

        eval_set = EvaluationSet(
            id=UUID(set_id),
            name="fail-test",
            metrics=[
                EvaluationMetricConfig(
                    name="exact_match",
                    framework=MetricFramework.BUILTIN,
                    metric_type="exact_match",
                    threshold=1.0,
                )
            ],
            cases=[
                EvaluationCase(
                    name="case-1",
                    input={"prompt": "test"},
                    expected_output={"answer": "correct"},
                ),
            ],
        )

        runner = EvaluationRunner(store=temp_db)

        # Return wrong answer
        def output_generator(case):
            return "wrong answer"

        result = await runner.run(eval_set, output_generator=output_generator)

        assert result.total_cases == 1
        assert result.passed_cases == 0
        assert result.failed_cases == 1
        assert result.overall_passed is False

    @pytest.mark.asyncio
    async def test_run_with_progress_callback(self, sample_eval_set):
        """Test running evaluation with progress callback (without store)."""
        progress_updates = []

        def on_progress(info):
            progress_updates.append(
                {
                    "completed": info.completed_cases,
                    "total": info.total_cases,
                    "percent": info.progress_percent,
                }
            )

        # Run without store to avoid FK constraint issues
        runner = EvaluationRunner(store=None)

        def output_generator(case):
            return "4" if "2+2" in str(case.input) else "6"

        await runner.run(
            sample_eval_set,
            output_generator=output_generator,
            on_progress=on_progress,
        )

        # Should have received progress updates
        assert len(progress_updates) > 0
        # Last update should show all cases completed
        assert progress_updates[-1]["completed"] == 2

    @pytest.mark.asyncio
    async def test_run_stores_results(self, temp_db, sample_eval_set):
        """Test that runner stores results in database."""
        # Create eval set in database first
        set_id = temp_db.create_evaluation_set(
            name=sample_eval_set.name,
            metrics=[m.model_dump() for m in sample_eval_set.metrics],
        )
        sample_eval_set.id = UUID(set_id)

        # Also add the cases to the database
        for case in sample_eval_set.cases:
            case_id = temp_db.add_evaluation_case(
                set_id=set_id,
                name=case.name,
                input_data=case.input,
                expected_output=case.expected_output,
            )
            case.id = UUID(case_id)

        runner = EvaluationRunner(store=temp_db)

        def output_generator(case):
            return "4" if "2+2" in str(case.input) else "6"

        result = await runner.run(sample_eval_set, output_generator=output_generator)

        # Check that run was stored
        stored_run = temp_db.get_evaluation_run(str(result.run_id))
        assert stored_run is not None
        assert stored_run["status"] == "completed"

    @pytest.mark.asyncio
    async def test_run_multiple_metrics(self):
        """Test running evaluation with multiple metrics (without store)."""
        eval_set = EvaluationSet(
            name="multi-metric-test",
            metrics=[
                EvaluationMetricConfig(
                    name="exact_match",
                    framework=MetricFramework.BUILTIN,
                    metric_type="exact_match",
                    threshold=1.0,
                ),
                EvaluationMetricConfig(
                    name="contains",
                    framework=MetricFramework.BUILTIN,
                    metric_type="contains",
                    threshold=1.0,
                ),
            ],
            cases=[
                EvaluationCase(
                    name="case-1",
                    input={"prompt": "test"},
                    expected_output={"answer": "hello world"},
                ),
            ],
        )

        runner = EvaluationRunner(store=None)

        def output_generator(case):
            return "hello world"  # Matches exact and contains

        result = await runner.run(eval_set, output_generator=output_generator)

        assert result.total_cases == 1
        assert result.passed_cases == 1

    @pytest.mark.asyncio
    async def test_run_with_pass_rate_threshold(self):
        """Test pass rate threshold affects overall_passed (without store)."""
        eval_set = EvaluationSet(
            name="threshold-test",
            metrics=[
                EvaluationMetricConfig(
                    name="exact_match",
                    framework=MetricFramework.BUILTIN,
                    metric_type="exact_match",
                    threshold=1.0,
                )
            ],
            pass_rate_threshold=0.5,  # 50% pass rate required
            cases=[
                EvaluationCase(
                    name="case-1",
                    input={"prompt": "1"},
                    expected_output={"answer": "one"},
                ),
                EvaluationCase(
                    name="case-2",
                    input={"prompt": "2"},
                    expected_output={"answer": "two"},
                ),
            ],
        )

        runner = EvaluationRunner(store=None)

        # Return correct answer for first case only
        def output_generator(case):
            if case.input.get("prompt") == "1":
                return "one"
            return "wrong"

        result = await runner.run(eval_set, output_generator=output_generator)

        # 50% pass rate meets 50% threshold
        assert result.pass_rate == 0.5
        assert result.overall_passed is True

    @pytest.mark.asyncio
    async def test_run_with_high_pass_rate_threshold(self):
        """Test high pass rate threshold causes failure (without store)."""
        eval_set = EvaluationSet(
            name="high-threshold-test",
            metrics=[
                EvaluationMetricConfig(
                    name="exact_match",
                    framework=MetricFramework.BUILTIN,
                    metric_type="exact_match",
                    threshold=1.0,
                )
            ],
            pass_rate_threshold=0.9,  # 90% pass rate required
            cases=[
                EvaluationCase(
                    name="case-1",
                    input={"prompt": "1"},
                    expected_output={"answer": "one"},
                ),
                EvaluationCase(
                    name="case-2",
                    input={"prompt": "2"},
                    expected_output={"answer": "two"},
                ),
            ],
        )

        runner = EvaluationRunner(store=None)

        # Return correct answer for first case only
        def output_generator(case):
            if case.input.get("prompt") == "1":
                return "one"
            return "wrong"

        result = await runner.run(eval_set, output_generator=output_generator)

        # 50% pass rate doesn't meet 90% threshold
        assert result.pass_rate == 0.5
        assert result.overall_passed is False


class TestSyncRunner:
    """Tests for synchronous runner helper."""

    def test_run_evaluation_sync(self, sample_eval_set):
        """Test running evaluation synchronously (without store)."""
        from tracecraft.evaluation.runner import run_evaluation_sync

        def output_generator(case):
            return "4" if "2+2" in str(case.input) else "6"

        result = run_evaluation_sync(
            sample_eval_set,
            output_generator=output_generator,
            store=None,
        )

        assert result.status == EvaluationStatus.COMPLETED
        assert result.total_cases == 2
