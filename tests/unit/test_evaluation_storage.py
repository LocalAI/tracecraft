"""Tests for evaluation SQLite storage operations."""

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from tracecraft.storage.sqlite import SQLiteTraceStore


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    store = SQLiteTraceStore(db_path)
    yield store

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def sample_metrics():
    """Sample metrics configuration."""
    return [
        {
            "name": "exact_match",
            "framework": "builtin",
            "metric_type": "exact_match",
            "threshold": 1.0,
        },
        {
            "name": "faithfulness",
            "framework": "deepeval",
            "metric_type": "faithfulness",
            "threshold": 0.8,
        },
    ]


class TestEvaluationSetCRUD:
    """Tests for evaluation set CRUD operations."""

    def test_create_evaluation_set(self, temp_db, sample_metrics):
        """Test creating an evaluation set."""
        set_id = temp_db.create_evaluation_set(
            name="test-set",
            description="Test evaluation set",
            metrics=sample_metrics,
            default_threshold=0.7,
            pass_rate_threshold=0.8,
        )

        assert set_id is not None
        assert len(set_id) == 36  # UUID format

    def test_create_evaluation_set_minimal(self, temp_db):
        """Test creating an evaluation set with minimal fields."""
        set_id = temp_db.create_evaluation_set(name="minimal-set")

        assert set_id is not None

    def test_get_evaluation_set(self, temp_db, sample_metrics):
        """Test retrieving an evaluation set."""
        set_id = temp_db.create_evaluation_set(
            name="test-set",
            description="Test description",
            metrics=sample_metrics,
            default_threshold=0.75,
            pass_rate_threshold=0.85,
        )

        result = temp_db.get_evaluation_set(set_id)

        assert result is not None
        assert result["id"] == set_id
        assert result["name"] == "test-set"
        assert result["description"] == "Test description"
        assert result["default_threshold"] == 0.75
        assert result["pass_rate_threshold"] == 0.85
        assert len(result["metrics"]) == 2

    def test_get_evaluation_set_not_found(self, temp_db):
        """Test retrieving a non-existent evaluation set."""
        result = temp_db.get_evaluation_set(str(uuid4()))
        assert result is None

    def test_list_evaluation_sets(self, temp_db):
        """Test listing evaluation sets."""
        # Create multiple sets
        temp_db.create_evaluation_set(name="set-1")
        temp_db.create_evaluation_set(name="set-2")
        temp_db.create_evaluation_set(name="set-3")

        sets = temp_db.list_evaluation_sets()

        assert len(sets) == 3
        names = [s["name"] for s in sets]
        assert "set-1" in names
        assert "set-2" in names
        assert "set-3" in names

    def test_list_evaluation_sets_empty(self, temp_db):
        """Test listing when no evaluation sets exist."""
        sets = temp_db.list_evaluation_sets()
        assert sets == []

    def test_update_evaluation_set(self, temp_db):
        """Test updating an evaluation set."""
        set_id = temp_db.create_evaluation_set(
            name="original-name",
            description="Original description",
        )

        success = temp_db.update_evaluation_set(
            set_id,
            name="updated-name",
            description="Updated description",
            default_threshold=0.9,
        )

        assert success is True

        result = temp_db.get_evaluation_set(set_id)
        assert result["name"] == "updated-name"
        assert result["description"] == "Updated description"
        assert result["default_threshold"] == 0.9

    def test_update_evaluation_set_not_found(self, temp_db):
        """Test updating a non-existent evaluation set."""
        success = temp_db.update_evaluation_set(
            str(uuid4()),
            name="new-name",
        )
        assert success is False

    def test_delete_evaluation_set(self, temp_db):
        """Test deleting an evaluation set."""
        set_id = temp_db.create_evaluation_set(name="to-delete")

        success = temp_db.delete_evaluation_set(set_id)
        assert success is True

        result = temp_db.get_evaluation_set(set_id)
        assert result is None

    def test_delete_evaluation_set_not_found(self, temp_db):
        """Test deleting a non-existent evaluation set."""
        success = temp_db.delete_evaluation_set(str(uuid4()))
        assert success is False


class TestEvaluationCaseCRUD:
    """Tests for evaluation case CRUD operations."""

    def test_add_evaluation_case(self, temp_db):
        """Test adding an evaluation case."""
        set_id = temp_db.create_evaluation_set(name="test-set")

        case_id = temp_db.add_evaluation_case(
            set_id=set_id,
            name="test-case",
            input_data={"prompt": "What is 2+2?"},
            expected_output={"answer": "4"},
        )

        assert case_id is not None

    def test_add_evaluation_case_with_context(self, temp_db):
        """Test adding a case with retrieval context."""
        set_id = temp_db.create_evaluation_set(name="test-set")

        case_id = temp_db.add_evaluation_case(
            set_id=set_id,
            name="rag-case",
            input_data={"question": "What is AI?"},
            expected_output={"answer": "Artificial Intelligence"},
            retrieval_context=["doc1 content", "doc2 content"],
        )

        cases = temp_db.get_evaluation_cases(set_id)
        assert len(cases) == 1
        assert cases[0]["retrieval_context"] == ["doc1 content", "doc2 content"]

    def test_get_evaluation_cases(self, temp_db):
        """Test getting cases for an evaluation set."""
        set_id = temp_db.create_evaluation_set(name="test-set")

        # Add multiple cases
        temp_db.add_evaluation_case(set_id=set_id, name="case-1", input_data={"q": "1"})
        temp_db.add_evaluation_case(set_id=set_id, name="case-2", input_data={"q": "2"})
        temp_db.add_evaluation_case(set_id=set_id, name="case-3", input_data={"q": "3"})

        cases = temp_db.get_evaluation_cases(set_id)

        assert len(cases) == 3
        names = [c["name"] for c in cases]
        assert "case-1" in names
        assert "case-2" in names
        assert "case-3" in names

    def test_get_evaluation_cases_empty(self, temp_db):
        """Test getting cases when none exist."""
        set_id = temp_db.create_evaluation_set(name="empty-set")
        cases = temp_db.get_evaluation_cases(set_id)
        assert cases == []

    def test_delete_evaluation_case(self, temp_db):
        """Test deleting an evaluation case."""
        set_id = temp_db.create_evaluation_set(name="test-set")
        case_id = temp_db.add_evaluation_case(
            set_id=set_id,
            name="to-delete",
            input_data={"q": "test"},
        )

        success = temp_db.delete_evaluation_case(case_id)
        assert success is True

        cases = temp_db.get_evaluation_cases(set_id)
        assert len(cases) == 0

    def test_create_case_from_trace(self, temp_db):
        """Test creating a case from an existing trace."""
        # Create a trace first
        from tracecraft.core.models import AgentRun

        run = AgentRun(
            name="test-run",
            start_time=datetime.now(UTC),
            input={"prompt": "Hello"},
            output={"response": "Hi there"},
        )
        temp_db.save(run)  # Use save() method

        # Create eval set and case from trace
        set_id = temp_db.create_evaluation_set(name="from-trace-set")
        case_id = temp_db.create_case_from_trace(
            set_id=set_id,
            trace_id=str(run.id),
            name="trace-case",
        )

        assert case_id is not None

        cases = temp_db.get_evaluation_cases(set_id)
        assert len(cases) == 1
        assert cases[0]["source_trace_id"] == str(run.id)


class TestEvaluationRunCRUD:
    """Tests for evaluation run CRUD operations."""

    def test_create_evaluation_run(self, temp_db):
        """Test creating an evaluation run."""
        set_id = temp_db.create_evaluation_set(name="test-set")
        run_id = temp_db.create_evaluation_run(set_id)

        assert run_id is not None

    def test_get_evaluation_run(self, temp_db):
        """Test getting an evaluation run."""
        set_id = temp_db.create_evaluation_set(name="test-set")
        run_id = temp_db.create_evaluation_run(set_id)

        run = temp_db.get_evaluation_run(run_id)

        assert run is not None
        assert run["id"] == run_id
        assert run["evaluation_set_id"] == set_id
        assert run["status"] == "pending"

    def test_update_evaluation_run(self, temp_db):
        """Test updating an evaluation run."""
        set_id = temp_db.create_evaluation_set(name="test-set")
        run_id = temp_db.create_evaluation_run(set_id)

        success = temp_db.update_evaluation_run(
            run_id,
            status="completed",
            passed_cases=8,
            failed_cases=2,
            overall_pass_rate=0.8,
            passed=True,
            duration_ms=1500.0,
        )

        assert success is True

        run = temp_db.get_evaluation_run(run_id)
        assert run["status"] == "completed"
        assert run["passed_cases"] == 8
        assert run["failed_cases"] == 2
        assert run["overall_pass_rate"] == 0.8
        assert run["passed"] == 1 or run["passed"] is True  # SQLite stores bool as int
        assert run["duration_ms"] == 1500.0

    def test_list_evaluation_runs(self, temp_db):
        """Test listing evaluation runs."""
        set_id = temp_db.create_evaluation_set(name="test-set")

        # Create multiple runs
        temp_db.create_evaluation_run(set_id)
        temp_db.create_evaluation_run(set_id)
        temp_db.create_evaluation_run(set_id)

        runs = temp_db.list_evaluation_runs(set_id=set_id)

        assert len(runs) == 3

    def test_list_evaluation_runs_all(self, temp_db):
        """Test listing all evaluation runs."""
        set1_id = temp_db.create_evaluation_set(name="set-1")
        set2_id = temp_db.create_evaluation_set(name="set-2")

        temp_db.create_evaluation_run(set1_id)
        temp_db.create_evaluation_run(set2_id)

        runs = temp_db.list_evaluation_runs()

        assert len(runs) == 2


class TestEvaluationResultCRUD:
    """Tests for evaluation result CRUD operations."""

    def test_save_evaluation_result(self, temp_db):
        """Test saving an evaluation result."""
        set_id = temp_db.create_evaluation_set(name="test-set")
        case_id = temp_db.add_evaluation_case(
            set_id=set_id,
            name="test-case",
            input_data={"q": "test"},
        )
        run_id = temp_db.create_evaluation_run(set_id)

        scores = [
            {
                "metric_name": "exact_match",
                "framework": "builtin",
                "score": 1.0,
                "passed": True,
            }
        ]

        result_id = temp_db.save_evaluation_result(
            run_id=run_id,
            case_id=case_id,
            scores=scores,
            passed=True,
            overall_score=1.0,
        )

        assert result_id is not None

    def test_get_evaluation_results(self, temp_db):
        """Test getting results for a run."""
        set_id = temp_db.create_evaluation_set(name="test-set")
        case1_id = temp_db.add_evaluation_case(set_id=set_id, name="case-1", input_data={"q": "1"})
        case2_id = temp_db.add_evaluation_case(set_id=set_id, name="case-2", input_data={"q": "2"})
        run_id = temp_db.create_evaluation_run(set_id)

        # Save results
        temp_db.save_evaluation_result(
            run_id=run_id,
            case_id=case1_id,
            scores=[{"metric_name": "test", "score": 0.9, "passed": True}],
            passed=True,
            overall_score=0.9,
        )
        temp_db.save_evaluation_result(
            run_id=run_id,
            case_id=case2_id,
            scores=[{"metric_name": "test", "score": 0.5, "passed": False}],
            passed=False,
            overall_score=0.5,
        )

        results = temp_db.get_evaluation_results(run_id)

        assert len(results) == 2


class TestEvaluationSetStats:
    """Tests for evaluation set statistics."""

    def test_get_evaluation_set_stats(self, temp_db):
        """Test getting stats for an evaluation set."""
        set_id = temp_db.create_evaluation_set(name="test-set")

        # Add cases
        case1_id = temp_db.add_evaluation_case(set_id=set_id, name="case-1", input_data={"q": "1"})
        case2_id = temp_db.add_evaluation_case(set_id=set_id, name="case-2", input_data={"q": "2"})

        # Create a completed run
        run_id = temp_db.create_evaluation_run(set_id)
        temp_db.update_evaluation_run(
            run_id,
            status="completed",
            passed_cases=1,
            failed_cases=1,
            overall_pass_rate=0.5,
            passed=False,
        )

        # Save results
        temp_db.save_evaluation_result(
            run_id=run_id,
            case_id=case1_id,
            scores=[],
            passed=True,
            overall_score=0.9,
        )
        temp_db.save_evaluation_result(
            run_id=run_id,
            case_id=case2_id,
            scores=[],
            passed=False,
            overall_score=0.3,
        )

        stats = temp_db.get_evaluation_set_stats(set_id)

        assert stats["case_count"] == 2
        assert stats["run_count"] == 1


class TestCascadeDelete:
    """Tests for cascade delete behavior."""

    def test_delete_set_cascades_to_cases(self, temp_db):
        """Test that deleting a set cascades to cases."""
        set_id = temp_db.create_evaluation_set(name="test-set")

        # Add cases
        temp_db.add_evaluation_case(set_id=set_id, name="case-1", input_data={"q": "1"})
        temp_db.add_evaluation_case(set_id=set_id, name="case-2", input_data={"q": "2"})

        # Delete set
        temp_db.delete_evaluation_set(set_id)

        # Cases should be gone
        cases = temp_db.get_evaluation_cases(set_id)
        assert len(cases) == 0

    def test_delete_set_cascades_to_runs(self, temp_db):
        """Test that deleting a set cascades to runs."""
        set_id = temp_db.create_evaluation_set(name="test-set")
        run_id = temp_db.create_evaluation_run(set_id)

        # Delete set
        temp_db.delete_evaluation_set(set_id)

        # Run should be gone
        run = temp_db.get_evaluation_run(run_id)
        assert run is None
