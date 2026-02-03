"""Integration tests for the evaluation system."""

import asyncio
import tempfile
from pathlib import Path
from uuid import UUID

import pytest

from tracecraft.evaluation import (
    EvaluationCase,
    EvaluationMetricConfig,
    EvaluationRunner,
    EvaluationSet,
    EvaluationStatus,
    MetricFramework,
    run_evaluation_sync,
)
from tracecraft.storage.sqlite import SQLiteTraceStore


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    store = SQLiteTraceStore(db_path)
    yield store

    Path(db_path).unlink(missing_ok=True)


class TestEndToEndEvaluation:
    """End-to-end tests for evaluation workflow."""

    def test_full_evaluation_workflow(self, temp_db):
        """Test complete evaluation workflow: create -> add cases -> run -> results."""
        # Step 1: Create an evaluation set
        set_id = temp_db.create_evaluation_set(
            name="math-baseline",
            description="Test basic math operations",
            metrics=[
                {
                    "name": "exact_match",
                    "framework": "builtin",
                    "metric_type": "exact_match",
                    "threshold": 1.0,
                }
            ],
            default_threshold=0.7,
            pass_rate_threshold=0.8,
        )

        assert set_id is not None

        # Step 2: Add test cases
        case1_id = temp_db.add_evaluation_case(
            set_id=set_id,
            name="addition-test-1",
            input_data={"question": "What is 2+2?"},
            expected_output={"answer": "4"},
        )

        case2_id = temp_db.add_evaluation_case(
            set_id=set_id,
            name="addition-test-2",
            input_data={"question": "What is 3+3?"},
            expected_output={"answer": "6"},
        )

        case3_id = temp_db.add_evaluation_case(
            set_id=set_id,
            name="subtraction-test-1",
            input_data={"question": "What is 5-2?"},
            expected_output={"answer": "3"},
        )

        # Verify cases were added
        cases = temp_db.get_evaluation_cases(set_id)
        assert len(cases) == 3

        # Step 3: Create an evaluation set model for running
        eval_set = EvaluationSet(
            id=UUID(set_id),
            name="math-baseline",
            metrics=[
                EvaluationMetricConfig(
                    name="exact_match",
                    framework=MetricFramework.BUILTIN,
                    metric_type="exact_match",
                    threshold=1.0,
                )
            ],
            pass_rate_threshold=0.8,
            cases=[
                EvaluationCase(
                    id=UUID(case1_id),
                    name="addition-test-1",
                    input={"question": "What is 2+2?"},
                    expected_output={"answer": "4"},
                ),
                EvaluationCase(
                    id=UUID(case2_id),
                    name="addition-test-2",
                    input={"question": "What is 3+3?"},
                    expected_output={"answer": "6"},
                ),
                EvaluationCase(
                    id=UUID(case3_id),
                    name="subtraction-test-1",
                    input={"question": "What is 5-2?"},
                    expected_output={"answer": "3"},
                ),
            ],
        )

        # Step 4: Run evaluation with output generator
        def math_solver(case):
            question = case.input.get("question", "")
            if "2+2" in question:
                return "4"
            elif "3+3" in question:
                return "6"
            elif "5-2" in question:
                return "3"
            return "unknown"

        result = run_evaluation_sync(
            eval_set,
            output_generator=math_solver,
            store=temp_db,
        )

        # Step 5: Verify results
        assert result.status == EvaluationStatus.COMPLETED
        assert result.total_cases == 3
        assert result.passed_cases == 3
        assert result.failed_cases == 0
        assert result.pass_rate == 1.0
        assert result.overall_passed is True

        # Step 6: Verify results are persisted
        stored_run = temp_db.get_evaluation_run(str(result.run_id))
        assert stored_run is not None
        assert stored_run["status"] == "completed"
        assert stored_run["passed_cases"] == 3

        # Step 7: Verify individual results are stored
        stored_results = temp_db.get_evaluation_results(str(result.run_id))
        assert len(stored_results) == 3
        assert all(r["passed"] for r in stored_results)

    def test_evaluation_with_failures(self, temp_db):
        """Test evaluation with some failing cases."""
        # Create eval set
        set_id = temp_db.create_evaluation_set(
            name="quality-check",
            metrics=[
                {
                    "name": "exact_match",
                    "framework": "builtin",
                    "metric_type": "exact_match",
                    "threshold": 1.0,
                }
            ],
            pass_rate_threshold=0.6,  # 60% pass rate required
        )

        # Add cases
        case1_id = temp_db.add_evaluation_case(
            set_id=set_id,
            name="case-1",
            input_data={"q": "Hello"},
            expected_output={"answer": "Hi"},
        )

        case2_id = temp_db.add_evaluation_case(
            set_id=set_id,
            name="case-2",
            input_data={"q": "World"},
            expected_output={"answer": "Earth"},
        )

        eval_set = EvaluationSet(
            id=UUID(set_id),
            name="quality-check",
            metrics=[
                EvaluationMetricConfig(
                    name="exact_match",
                    framework=MetricFramework.BUILTIN,
                    metric_type="exact_match",
                    threshold=1.0,
                )
            ],
            pass_rate_threshold=0.6,
            cases=[
                EvaluationCase(
                    id=UUID(case1_id),
                    name="case-1",
                    input={"q": "Hello"},
                    expected_output={"answer": "Hi"},
                ),
                EvaluationCase(
                    id=UUID(case2_id),
                    name="case-2",
                    input={"q": "World"},
                    expected_output={"answer": "Earth"},
                ),
            ],
        )

        # Output generator that returns wrong answer for second case
        def responder(case):
            if case.input.get("q") == "Hello":
                return "Hi"  # Correct
            return "Wrong"  # Wrong

        result = run_evaluation_sync(
            eval_set,
            output_generator=responder,
            store=temp_db,
        )

        # 50% pass rate doesn't meet 60% threshold
        assert result.total_cases == 2
        assert result.passed_cases == 1
        assert result.failed_cases == 1
        assert result.pass_rate == 0.5
        assert result.overall_passed is False

    def test_evaluation_with_multiple_metrics(self, temp_db):
        """Test evaluation with multiple metrics per case."""
        set_id = temp_db.create_evaluation_set(
            name="multi-metric-test",
            metrics=[
                {
                    "name": "contains",
                    "framework": "builtin",
                    "metric_type": "contains",
                    "threshold": 1.0,
                },
                {
                    "name": "json_valid",
                    "framework": "builtin",
                    "metric_type": "json_valid",
                    "threshold": 1.0,
                },
            ],
        )

        case_id = temp_db.add_evaluation_case(
            set_id=set_id,
            name="json-response-test",
            input_data={"prompt": "Return a JSON with a greeting"},
            expected_output={"answer": "hello"},  # Contains check
        )

        eval_set = EvaluationSet(
            id=UUID(set_id),
            name="multi-metric-test",
            metrics=[
                EvaluationMetricConfig(
                    name="contains",
                    framework=MetricFramework.BUILTIN,
                    metric_type="contains",
                    threshold=1.0,
                ),
                EvaluationMetricConfig(
                    name="json_valid",
                    framework=MetricFramework.BUILTIN,
                    metric_type="json_valid",
                    threshold=1.0,
                ),
            ],
            cases=[
                EvaluationCase(
                    id=UUID(case_id),
                    name="json-response-test",
                    input={"prompt": "Return a JSON with a greeting"},
                    expected_output={"answer": "hello"},
                ),
            ],
        )

        def json_generator(case):
            return '{"message": "hello world"}'

        result = run_evaluation_sync(
            eval_set,
            output_generator=json_generator,
            store=temp_db,
        )

        # Both metrics should pass
        assert result.status == EvaluationStatus.COMPLETED
        assert result.passed_cases == 1
        assert result.overall_passed is True


class TestEvaluationListAndStats:
    """Tests for listing and statistics."""

    def test_list_multiple_eval_sets(self, temp_db):
        """Test listing multiple evaluation sets."""
        # Create several eval sets
        temp_db.create_evaluation_set(name="set-1")
        temp_db.create_evaluation_set(name="set-2")
        temp_db.create_evaluation_set(name="set-3")

        sets = temp_db.list_evaluation_sets()

        assert len(sets) == 3
        names = [s["name"] for s in sets]
        assert "set-1" in names
        assert "set-2" in names
        assert "set-3" in names

    def test_evaluation_history(self, temp_db):
        """Test multiple runs of the same evaluation set."""
        set_id = temp_db.create_evaluation_set(name="history-test")

        case_id = temp_db.add_evaluation_case(
            set_id=set_id,
            name="test-case",
            input_data={"q": "test"},
            expected_output={"answer": "response"},
        )

        eval_set = EvaluationSet(
            id=UUID(set_id),
            name="history-test",
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
                    id=UUID(case_id),
                    name="test-case",
                    input={"q": "test"},
                    expected_output={"answer": "response"},
                ),
            ],
        )

        # Run 1: Fail
        def fail_generator(case):
            return "wrong"

        result1 = run_evaluation_sync(
            eval_set,
            output_generator=fail_generator,
            store=temp_db,
        )
        assert result1.overall_passed is False

        # Run 2: Pass
        def pass_generator(case):
            return "response"

        result2 = run_evaluation_sync(
            eval_set,
            output_generator=pass_generator,
            store=temp_db,
        )
        assert result2.overall_passed is True

        # Check history
        runs = temp_db.list_evaluation_runs(set_id=set_id)
        assert len(runs) == 2

        # Most recent should be first
        assert runs[0]["passed"] == 1 or runs[0]["passed"] is True


class TestAsyncRunner:
    """Tests for async evaluation runner."""

    @pytest.mark.asyncio
    async def test_async_runner_with_async_generator(self):
        """Test running with an async output generator."""
        eval_set = EvaluationSet(
            name="async-test",
            metrics=[
                EvaluationMetricConfig(
                    name="contains",
                    framework=MetricFramework.BUILTIN,
                    metric_type="contains",
                    threshold=1.0,
                )
            ],
            cases=[
                EvaluationCase(
                    name="case-1",
                    input={"prompt": "Say hello"},
                    expected_output={"answer": "hello"},
                ),
            ],
        )

        # Async output generator
        async def async_generator(case):
            await asyncio.sleep(0.01)  # Simulate async work
            return "hello world"

        runner = EvaluationRunner(store=None)
        result = await runner.run(eval_set, output_generator=async_generator)

        assert result.status == EvaluationStatus.COMPLETED
        assert result.passed_cases == 1

    @pytest.mark.asyncio
    async def test_async_runner_with_progress(self):
        """Test async runner with progress callbacks."""
        eval_set = EvaluationSet(
            name="progress-test",
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
                    input={"q": "1"},
                    expected_output={"answer": "one"},
                ),
                EvaluationCase(
                    name="case-2",
                    input={"q": "2"},
                    expected_output={"answer": "two"},
                ),
                EvaluationCase(
                    name="case-3",
                    input={"q": "3"},
                    expected_output={"answer": "three"},
                ),
            ],
        )

        progress_updates = []

        def on_progress(info):
            progress_updates.append(info.progress_percent)

        def generator(case):
            q = case.input.get("q")
            return {"1": "one", "2": "two", "3": "three"}.get(q, "unknown")

        runner = EvaluationRunner(store=None)
        await runner.run(eval_set, output_generator=generator, on_progress=on_progress)

        # Should have progress updates
        assert len(progress_updates) > 0
        # Final progress should reach 100%
        assert max(progress_updates) == 100.0
