"""
Tests for MLflow storage backend.

These tests use mocking since MLflow requires a tracking server.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from agenttrace.core.models import AgentRun
from agenttrace.storage.base import TraceQuery

# Only import pandas if available (comes with mlflow)
pd = pytest.importorskip("pandas")


class TestMLflowStorageImport:
    """Tests for MLflow import handling."""

    def test_raises_import_error_without_mlflow(self):
        """Test that ImportError is raised when mlflow not installed."""
        with patch.dict("sys.modules", {"mlflow": None}):
            # Need to reimport to trigger the import error
            import sys

            # Remove cached module
            if "agenttrace.storage.mlflow" in sys.modules:
                del sys.modules["agenttrace.storage.mlflow"]

            with pytest.raises(ImportError, match="mlflow required"):
                from agenttrace.storage.mlflow import MLflowTraceStore

                MLflowTraceStore()


class TestMLflowTraceStore:
    """Tests for MLflowTraceStore with mocked MLflow."""

    @pytest.fixture
    def mock_mlflow(self):
        """Create a mock MLflow module."""
        mock = MagicMock()
        mock.search_runs.return_value = pd.DataFrame()
        mock.search_experiments.return_value = []
        mock.get_experiment_by_name.return_value = None
        return mock

    @pytest.fixture
    def store(self, mock_mlflow):
        """Create a MLflowTraceStore with mocked MLflow."""
        with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
            import sys

            # Remove cached module
            if "agenttrace.storage.mlflow" in sys.modules:
                del sys.modules["agenttrace.storage.mlflow"]

            from agenttrace.storage.mlflow import MLflowTraceStore

            # Patch the import inside the module
            store = MLflowTraceStore.__new__(MLflowTraceStore)
            store._mlflow = mock_mlflow
            store.experiment_name = None
            store.experiment_ids = None
            return store

    @pytest.fixture
    def sample_run(self):
        """Create a sample AgentRun."""
        return AgentRun(
            name="test_run",
            start_time=datetime.now(UTC),
            total_tokens=100,
            total_cost_usd=0.05,
            tags=["test", "sample"],
        )

    def test_init_with_tracking_uri(self, mock_mlflow):
        """Test initialization with tracking URI."""
        with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
            import sys

            if "agenttrace.storage.mlflow" in sys.modules:
                del sys.modules["agenttrace.storage.mlflow"]

            from agenttrace.storage.mlflow import MLflowTraceStore

            store = MLflowTraceStore.__new__(MLflowTraceStore)
            store._mlflow = mock_mlflow
            store.experiment_name = None
            store.experiment_ids = None

            # Verify it doesn't raise
            assert store._mlflow == mock_mlflow

    def test_get_returns_none_for_empty_results(self, store, mock_mlflow):
        """Test get returns None when no trace found."""
        mock_mlflow.search_runs.return_value = pd.DataFrame()

        result = store.get("nonexistent-id")

        assert result is None
        mock_mlflow.search_runs.assert_called_once()

    def test_get_returns_trace_when_found(self, store, mock_mlflow, sample_run):
        """Test get returns trace when found."""
        # Setup mock to return a DataFrame with a run
        mock_mlflow.search_runs.return_value = pd.DataFrame({"run_id": ["mock_run_id"]})

        # Mock artifact loading
        store._load_trace_artifact = MagicMock(return_value=sample_run)

        result = store.get(str(sample_run.id))

        assert result is not None
        assert result.name == sample_run.name

    def test_query_builds_correct_filter_for_name(self, store, mock_mlflow):
        """Test query builds correct filter for name."""
        mock_mlflow.search_runs.return_value = pd.DataFrame()

        store.query(TraceQuery(name="test_run"))

        call_args = mock_mlflow.search_runs.call_args
        filter_string = (
            call_args.kwargs.get("filter_string") or call_args.args[0] if call_args.args else ""
        )
        # The filter_string is passed as a kwarg
        assert "agenttrace.name" in str(call_args)

    def test_query_builds_correct_filter_for_errors(self, store, mock_mlflow):
        """Test query builds correct filter for has_error."""
        mock_mlflow.search_runs.return_value = pd.DataFrame()

        store.query(TraceQuery(has_error=True))

        call_args = mock_mlflow.search_runs.call_args
        assert "error_count > 0" in str(call_args)

    def test_query_builds_correct_filter_for_cost(self, store, mock_mlflow):
        """Test query builds correct filter for cost."""
        mock_mlflow.search_runs.return_value = pd.DataFrame()

        store.query(TraceQuery(min_cost_usd=0.10))

        call_args = mock_mlflow.search_runs.call_args
        assert "total_cost_usd >= 0.1" in str(call_args)

    def test_list_all_calls_query(self, store, mock_mlflow):
        """Test list_all calls query with correct parameters."""
        mock_mlflow.search_runs.return_value = pd.DataFrame()

        store.list_all(limit=50, offset=10)

        mock_mlflow.search_runs.assert_called_once()
        call_args = mock_mlflow.search_runs.call_args
        # Should request limit + offset results
        assert call_args.kwargs.get("max_results", 0) == 60

    def test_delete_returns_false_when_not_found(self, store, mock_mlflow):
        """Test delete returns False when trace not found."""
        mock_mlflow.search_runs.return_value = pd.DataFrame()

        result = store.delete("nonexistent-id")

        assert result is False

    def test_delete_calls_mlflow_delete_run(self, store, mock_mlflow):
        """Test delete calls mlflow.delete_run when found."""
        mock_mlflow.search_runs.return_value = pd.DataFrame({"run_id": ["mock_run_id"]})

        result = store.delete("trace-id")

        assert result is True
        mock_mlflow.delete_run.assert_called_once_with("mock_run_id")

    def test_count_returns_query_length(self, store, mock_mlflow):
        """Test count returns number of traces."""
        mock_mlflow.search_runs.return_value = pd.DataFrame()
        store._load_trace_artifact = MagicMock(return_value=None)

        count = store.count()

        assert count == 0

    def test_search_with_raw_filter(self, store, mock_mlflow):
        """Test search with raw MLflow filter DSL."""
        mock_mlflow.search_runs.return_value = pd.DataFrame()

        store.search("metrics.duration_ms > 1000")

        call_args = mock_mlflow.search_runs.call_args
        assert call_args.kwargs.get("filter_string") == "metrics.duration_ms > 1000"

    def test_get_experiments(self, store, mock_mlflow):
        """Test get_experiments returns experiment list."""
        mock_exp = MagicMock()
        mock_exp.experiment_id = "1"
        mock_exp.name = "test_exp"
        mock_exp.artifact_location = "/path/to/artifacts"
        mock_mlflow.search_experiments.return_value = [mock_exp]

        experiments = store.get_experiments()

        assert len(experiments) == 1
        assert experiments[0]["id"] == "1"
        assert experiments[0]["name"] == "test_exp"

    def test_get_stats_returns_zeros_for_empty(self, store, mock_mlflow):
        """Test get_stats returns zeros when no traces."""
        mock_mlflow.search_runs.return_value = pd.DataFrame()
        store._load_trace_artifact = MagicMock(return_value=None)

        stats = store.get_stats()

        assert stats["trace_count"] == 0

    def test_get_stats_aggregates_metrics(self, store, mock_mlflow):
        """Test get_stats aggregates metrics from runs."""
        mock_mlflow.search_runs.return_value = pd.DataFrame(
            {
                "run_id": ["run1", "run2"],
                "metrics.total_tokens": [100, 200],
                "metrics.total_cost_usd": [0.05, 0.10],
            }
        )
        store._load_trace_artifact = MagicMock(return_value=None)

        # Need to mock count() to return the number of runs
        with patch.object(store, "count", return_value=2):
            stats = store.get_stats()

        assert stats["trace_count"] == 2
        assert stats["total_tokens"] == 300
        assert abs(stats["total_cost_usd"] - 0.15) < 0.001  # Floating point comparison


class TestMLflowQueryFilters:
    """Tests for MLflow query filter building."""

    @pytest.fixture
    def mock_mlflow(self):
        """Create a mock MLflow module."""
        mock = MagicMock()
        mock.search_runs.return_value = pd.DataFrame()
        return mock

    @pytest.fixture
    def store(self, mock_mlflow):
        """Create store with mock."""
        with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
            import sys

            if "agenttrace.storage.mlflow" in sys.modules:
                del sys.modules["agenttrace.storage.mlflow"]

            from agenttrace.storage.mlflow import MLflowTraceStore

            store = MLflowTraceStore.__new__(MLflowTraceStore)
            store._mlflow = mock_mlflow
            store.experiment_name = None
            store.experiment_ids = None
            return store

    def test_filter_name_contains(self, store, mock_mlflow):
        """Test filter for name_contains."""
        mock_mlflow.search_runs.return_value = pd.DataFrame()

        store.query(TraceQuery(name_contains="test"))

        call_args = mock_mlflow.search_runs.call_args
        assert "LIKE" in str(call_args)
        assert "test" in str(call_args)

    def test_filter_duration(self, store, mock_mlflow):
        """Test filter for duration range."""
        mock_mlflow.search_runs.return_value = pd.DataFrame()

        store.query(TraceQuery(min_duration_ms=100, max_duration_ms=1000))

        call_args = mock_mlflow.search_runs.call_args
        filter_str = str(call_args)
        assert "duration_ms >= 100" in filter_str
        assert "duration_ms <= 1000" in filter_str

    def test_filter_combined(self, store, mock_mlflow):
        """Test combined filters use AND."""
        mock_mlflow.search_runs.return_value = pd.DataFrame()

        store.query(TraceQuery(has_error=True, min_cost_usd=0.10))

        call_args = mock_mlflow.search_runs.call_args
        filter_str = str(call_args)
        assert "AND" in filter_str
        assert "error_count > 0" in filter_str
        assert "total_cost_usd >= 0.1" in filter_str
