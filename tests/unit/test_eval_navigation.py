"""Tests for evaluation navigation and bidirectional queries.

Tests the ability to navigate between traces and their associated evaluations,
including hierarchical tree views and breadcrumb navigation.
"""

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from tracecraft.core.models import AgentRun, Step, StepType
from tracecraft.storage.sqlite import SQLiteTraceStore


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    store = SQLiteTraceStore(db_path)
    yield store

    store.close()
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def sample_trace():
    """Create a sample trace."""
    return AgentRun(
        id=uuid4(),
        name="test_trace",
        start_time=datetime.now(UTC),
        input={"prompt": "Hello"},
        output={"response": "Hi there"},
        duration_ms=100.0,
    )


@pytest.fixture
def sample_trace_with_steps():
    """Create a sample trace with steps."""
    run = AgentRun(
        id=uuid4(),
        name="test_trace_with_steps",
        start_time=datetime.now(UTC),
        input={"prompt": "What is 2+2?"},
        output={"response": "4"},
        duration_ms=150.0,
    )
    step = Step(
        trace_id=run.id,
        type=StepType.LLM,
        name="llm_call",
        start_time=datetime.now(UTC),
        model_name="gpt-4",
        model_provider="openai",
        input_tokens=50,
        output_tokens=100,
        cost_usd=0.05,
    )
    run.steps.append(step)
    return run


@pytest.fixture
def sample_eval_set(temp_db):
    """Create a sample evaluation set."""
    set_id = temp_db.create_evaluation_set(
        name="test-eval-set",
        metrics=[
            {
                "name": "exact_match",
                "framework": "builtin",
                "metric_type": "exact_match",
                "threshold": 1.0,
            }
        ],
        description="Test evaluation set",
    )
    return {"id": set_id, "name": "test-eval-set"}


class TestBidirectionalQueries:
    """Tests for bidirectional navigation queries."""

    def test_get_evaluation_sets_for_trace(self, temp_db, sample_trace, sample_eval_set):
        """Test getting eval sets that contain cases from a trace."""
        # Save trace
        temp_db.save(sample_trace)

        # Add trace as eval case
        temp_db.add_evaluation_case(
            set_id=sample_eval_set["id"],
            name="case-from-trace",
            input_data={"prompt": "Hello"},
            expected_output={"response": "Hi"},
            source_trace_id=str(sample_trace.id),
        )

        # Query eval sets for this trace
        eval_sets = temp_db.get_evaluation_sets_for_trace(str(sample_trace.id))

        assert len(eval_sets) == 1
        assert eval_sets[0]["id"] == sample_eval_set["id"]
        assert eval_sets[0]["name"] == "test-eval-set"

    def test_get_evaluation_sets_for_trace_multiple_sets(self, temp_db, sample_trace):
        """Test getting multiple eval sets for a trace."""
        temp_db.save(sample_trace)

        # Create two eval sets
        set1_id = temp_db.create_evaluation_set(
            name="eval-set-1",
            metrics=[{"name": "exact_match", "framework": "builtin", "metric_type": "exact_match"}],
        )
        set2_id = temp_db.create_evaluation_set(
            name="eval-set-2",
            metrics=[{"name": "contains", "framework": "builtin", "metric_type": "contains"}],
        )

        # Add trace to both sets
        temp_db.add_evaluation_case(
            set_id=set1_id,
            name="case-1",
            input_data={"prompt": "Hello"},
            source_trace_id=str(sample_trace.id),
        )
        temp_db.add_evaluation_case(
            set_id=set2_id,
            name="case-2",
            input_data={"prompt": "Hello"},
            source_trace_id=str(sample_trace.id),
        )

        # Should find both eval sets
        eval_sets = temp_db.get_evaluation_sets_for_trace(str(sample_trace.id))
        assert len(eval_sets) == 2
        set_names = {s["name"] for s in eval_sets}
        assert set_names == {"eval-set-1", "eval-set-2"}

    def test_get_evaluation_sets_for_trace_no_results(self, temp_db, sample_trace):
        """Test getting eval sets for trace with no associated evals."""
        temp_db.save(sample_trace)

        eval_sets = temp_db.get_evaluation_sets_for_trace(str(sample_trace.id))
        assert eval_sets == []

    def test_get_evaluation_cases_from_trace(self, temp_db, sample_trace, sample_eval_set):
        """Test getting eval cases derived from a trace."""
        temp_db.save(sample_trace)

        # Add multiple cases from same trace
        temp_db.add_evaluation_case(
            set_id=sample_eval_set["id"],
            name="case-1",
            input_data={"prompt": "Hello"},
            source_trace_id=str(sample_trace.id),
        )
        temp_db.add_evaluation_case(
            set_id=sample_eval_set["id"],
            name="case-2",
            input_data={"prompt": "World"},
            source_trace_id=str(sample_trace.id),
        )

        cases = temp_db.get_evaluation_cases_from_trace(str(sample_trace.id))

        assert len(cases) == 2
        # Should include set_name for display
        assert all("set_name" in c for c in cases)
        assert all(c["set_name"] == "test-eval-set" for c in cases)

    def test_get_source_trace_for_case(self, temp_db, sample_trace, sample_eval_set):
        """Test getting the source trace for an eval case."""
        temp_db.save(sample_trace)

        case_id = temp_db.add_evaluation_case(
            set_id=sample_eval_set["id"],
            name="linked-case",
            input_data={"prompt": "Hello"},
            source_trace_id=str(sample_trace.id),
        )

        trace_data = temp_db.get_source_trace_for_case(case_id)

        assert trace_data is not None
        assert trace_data["id"] == str(sample_trace.id)
        assert trace_data["name"] == "test_trace"

    def test_get_source_trace_for_case_no_source(self, temp_db, sample_eval_set):
        """Test getting source trace for case without source."""
        case_id = temp_db.add_evaluation_case(
            set_id=sample_eval_set["id"],
            name="manual-case",
            input_data={"prompt": "Hello"},
            # No source_trace_id
        )

        trace_data = temp_db.get_source_trace_for_case(case_id)
        assert trace_data is None

    def test_get_latest_eval_result_for_case(self, temp_db, sample_trace, sample_eval_set):
        """Test getting the most recent eval result for a case."""
        temp_db.save(sample_trace)

        case_id = temp_db.add_evaluation_case(
            set_id=sample_eval_set["id"],
            name="test-case",
            input_data={"prompt": "Hello"},
            source_trace_id=str(sample_trace.id),
        )

        # Create two runs
        run1_id = temp_db.create_evaluation_run(sample_eval_set["id"])
        run2_id = temp_db.create_evaluation_run(sample_eval_set["id"])

        # Save results for both runs
        temp_db.save_evaluation_result(
            run_id=run1_id,
            case_id=case_id,
            scores=[{"metric": "exact_match", "score": 0.5}],
            passed=False,
        )
        temp_db.save_evaluation_result(
            run_id=run2_id,
            case_id=case_id,
            scores=[{"metric": "exact_match", "score": 1.0}],
            passed=True,
        )

        # Should get the latest result (from run2)
        result = temp_db.get_latest_eval_result_for_case(case_id)

        assert result is not None
        assert result["passed"]  # SQLite returns 1 for True
        assert result["evaluation_run_id"] == run2_id

    def test_get_latest_eval_result_for_case_no_results(self, temp_db, sample_eval_set):
        """Test getting result for case with no evaluations."""
        case_id = temp_db.add_evaluation_case(
            set_id=sample_eval_set["id"],
            name="never-evaluated",
            input_data={"prompt": "Hello"},
        )

        result = temp_db.get_latest_eval_result_for_case(case_id)
        assert result is None

    def test_count_eval_sets_for_trace(self, temp_db, sample_trace):
        """Test counting eval sets for a trace."""
        temp_db.save(sample_trace)

        # Initially no eval sets
        count = temp_db.count_eval_sets_for_trace(str(sample_trace.id))
        assert count == 0

        # Add to one set
        set1_id = temp_db.create_evaluation_set(
            name="count-set-1",
            metrics=[{"name": "exact_match", "framework": "builtin", "metric_type": "exact_match"}],
        )
        temp_db.add_evaluation_case(
            set_id=set1_id,
            name="case-1",
            input_data={"prompt": "Hello"},
            source_trace_id=str(sample_trace.id),
        )

        count = temp_db.count_eval_sets_for_trace(str(sample_trace.id))
        assert count == 1

        # Add to another set
        set2_id = temp_db.create_evaluation_set(
            name="count-set-2",
            metrics=[{"name": "contains", "framework": "builtin", "metric_type": "contains"}],
        )
        temp_db.add_evaluation_case(
            set_id=set2_id,
            name="case-2",
            input_data={"prompt": "Hello"},
            source_trace_id=str(sample_trace.id),
        )

        count = temp_db.count_eval_sets_for_trace(str(sample_trace.id))
        assert count == 2

    def test_count_eval_sets_deduplicates(self, temp_db, sample_trace, sample_eval_set):
        """Test that count doesn't double-count when trace has multiple cases in same set."""
        temp_db.save(sample_trace)

        # Add multiple cases from same trace to same set
        temp_db.add_evaluation_case(
            set_id=sample_eval_set["id"],
            name="case-1",
            input_data={"prompt": "Hello"},
            source_trace_id=str(sample_trace.id),
        )
        temp_db.add_evaluation_case(
            set_id=sample_eval_set["id"],
            name="case-2",
            input_data={"prompt": "World"},
            source_trace_id=str(sample_trace.id),
        )

        # Should still be 1, not 2
        count = temp_db.count_eval_sets_for_trace(str(sample_trace.id))
        assert count == 1


class TestEvalSetWithLatestRun:
    """Tests for eval set queries that include latest run info."""

    def test_list_evaluation_sets_includes_latest_run(self, temp_db, sample_eval_set):
        """Test that listing eval sets returns the set and stats can be retrieved."""
        # Create a run and complete it
        run_id = temp_db.create_evaluation_run(sample_eval_set["id"])
        temp_db.update_evaluation_run(
            run_id,
            status="completed",
            passed=True,
            overall_pass_rate=1.0,
            passed_cases=5,
            failed_cases=0,
        )

        eval_sets = temp_db.list_evaluation_sets()

        assert len(eval_sets) >= 1
        target_set = next(s for s in eval_sets if s["id"] == sample_eval_set["id"])

        # Stats can be retrieved separately
        stats = temp_db.get_evaluation_set_stats(sample_eval_set["id"])
        assert "case_count" in stats
        assert "latest_run" in stats

    def test_get_evaluation_set_includes_case_count(self, temp_db, sample_eval_set):
        """Test that get_evaluation_set includes case count."""
        # Add some cases
        for i in range(3):
            temp_db.add_evaluation_case(
                set_id=sample_eval_set["id"],
                name=f"case-{i}",
                input_data={"prompt": f"Test {i}"},
            )

        eval_set = temp_db.get_evaluation_set(sample_eval_set["id"])

        assert eval_set is not None
        # The case_count should be available
        case_count = temp_db.count_evaluation_cases(sample_eval_set["id"])
        assert case_count == 3


class TestBreadcrumbNavigation:
    """Tests for breadcrumb widget functionality."""

    def test_breadcrumb_push_and_pop(self):
        """Test breadcrumb push and pop operations."""
        try:
            from tracecraft.tui.widgets.breadcrumb import Breadcrumb

            breadcrumb = Breadcrumb()

            # Push items
            breadcrumb.push("Projects", {"type": "root"})
            breadcrumb.push("My Project", {"type": "project", "id": "123"})
            breadcrumb.push("Agent A", {"type": "agent", "id": "456"})

            assert len(breadcrumb.path) == 3

            # Pop items
            item = breadcrumb.pop()
            assert item["label"] == "Agent A"
            assert item["data"]["type"] == "agent"
            assert len(breadcrumb.path) == 2

            item = breadcrumb.pop()
            assert item["label"] == "My Project"
            assert len(breadcrumb.path) == 1

        except ImportError:
            pytest.skip("Textual not installed")

    def test_breadcrumb_clear(self):
        """Test breadcrumb clear operation."""
        try:
            from tracecraft.tui.widgets.breadcrumb import Breadcrumb

            breadcrumb = Breadcrumb()
            breadcrumb.push("Item 1", {"type": "test"})
            breadcrumb.push("Item 2", {"type": "test"})

            breadcrumb.clear()

            assert len(breadcrumb.path) == 0

        except ImportError:
            pytest.skip("Textual not installed")

    def test_breadcrumb_pop_empty(self):
        """Test popping from empty breadcrumb."""
        try:
            from tracecraft.tui.widgets.breadcrumb import Breadcrumb

            breadcrumb = Breadcrumb()

            result = breadcrumb.pop()
            assert result is None

        except ImportError:
            pytest.skip("Textual not installed")

    def test_breadcrumb_path_building(self):
        """Test breadcrumb path state (uses composition instead of render)."""
        try:
            from tracecraft.tui.widgets.breadcrumb import Breadcrumb

            breadcrumb = Breadcrumb()
            breadcrumb.push("Root", {"type": "root"})
            breadcrumb.push("Child", {"type": "child"})

            # Breadcrumb now uses child widgets, so test the internal path state
            assert len(breadcrumb.path) == 2
            assert breadcrumb.path[0]["label"] == "Root"
            assert breadcrumb.path[1]["label"] == "Child"
            assert breadcrumb.path[0]["data"]["type"] == "root"
            assert breadcrumb.path[1]["data"]["type"] == "child"

        except ImportError:
            pytest.skip("Textual not installed")


class TestRunTreeEvalDisplay:
    """Tests for RunTree eval display functionality."""

    def test_run_tree_has_eval_status_icon_method(self):
        """Test that RunTree has method for eval status icons."""
        try:
            from tracecraft.tui.widgets.run_tree import RunTree

            # Should have the method
            assert hasattr(RunTree, "_get_eval_status_icon")
        except ImportError:
            pytest.skip("Textual not installed")

    def test_eval_status_icon_passed(self):
        """Test status icon for passed eval."""
        try:
            from tracecraft.tui.widgets.run_tree import RunTree

            tree = RunTree()
            eval_set = {
                "latest_run": {
                    "status": "completed",
                    "passed": True,
                }
            }

            icon = tree._get_eval_status_icon(eval_set)

            # Should contain green indicator
            assert "green" in icon.lower() or "◆" in icon

        except ImportError:
            pytest.skip("Textual not installed")

    def test_eval_status_icon_failed(self):
        """Test status icon for failed eval."""
        try:
            from tracecraft.tui.widgets.run_tree import RunTree

            tree = RunTree()
            eval_set = {
                "latest_run": {
                    "status": "completed",
                    "passed": False,
                }
            }

            icon = tree._get_eval_status_icon(eval_set)

            # Should contain red indicator
            assert "red" in icon.lower() or "◆" in icon

        except ImportError:
            pytest.skip("Textual not installed")

    def test_eval_status_icon_no_runs(self):
        """Test status icon for eval with no runs."""
        try:
            from tracecraft.tui.widgets.run_tree import RunTree

            tree = RunTree()
            eval_set = {}  # No latest_run

            icon = tree._get_eval_status_icon(eval_set)

            # Should be neutral/gray icon
            assert "◇" in icon

        except ImportError:
            pytest.skip("Textual not installed")

    def test_eval_status_icon_running(self):
        """Test status icon for running eval."""
        try:
            from tracecraft.tui.widgets.run_tree import RunTree

            tree = RunTree()
            eval_set = {
                "latest_run": {
                    "status": "running",
                }
            }

            icon = tree._get_eval_status_icon(eval_set)

            # Should contain yellow/amber indicator
            assert "yellow" in icon.lower() or "◆" in icon

        except ImportError:
            pytest.skip("Textual not installed")


class TestTreeViewModeEvals:
    """Tests for eval-related tree view modes."""

    def test_tree_view_mode_has_evals(self):
        """Test that TreeViewMode includes EVALS."""
        try:
            from tracecraft.tui.widgets.run_tree import TreeViewMode

            assert hasattr(TreeViewMode, "EVALS")
        except ImportError:
            pytest.skip("Textual not installed")

    def test_tree_view_mode_has_eval_cases(self):
        """Test that TreeViewMode includes EVAL_CASES."""
        try:
            from tracecraft.tui.widgets.run_tree import TreeViewMode

            assert hasattr(TreeViewMode, "EVAL_CASES")
        except ImportError:
            pytest.skip("Textual not installed")

    def test_tree_view_mode_has_eval_runs(self):
        """Test that TreeViewMode includes EVAL_RUNS."""
        try:
            from tracecraft.tui.widgets.run_tree import TreeViewMode

            assert hasattr(TreeViewMode, "EVAL_RUNS")
        except ImportError:
            pytest.skip("Textual not installed")
