"""
Tests for multi-source TraceLoader.
"""

from datetime import UTC, datetime

import pytest

from agenttrace.core.models import AgentRun
from agenttrace.storage.base import TraceQuery
from agenttrace.tui.data.loader import TraceLoader, get_loader_for_env


class TestTraceLoader:
    """Tests for TraceLoader."""

    @pytest.fixture
    def sample_runs(self):
        """Create sample AgentRun objects."""
        return [
            AgentRun(
                name=f"run_{i}",
                start_time=datetime.now(UTC),
                total_tokens=100 * (i + 1),
                total_cost_usd=0.01 * (i + 1),
            )
            for i in range(5)
        ]

    @pytest.fixture
    def jsonl_store(self, tmp_path, sample_runs):
        """Create a JSONL file with sample runs."""
        jsonl_path = tmp_path / "traces.jsonl"
        from agenttrace.storage.jsonl import JSONLTraceStore

        store = JSONLTraceStore(jsonl_path)
        for run in sample_runs:
            store.save(run)
        return str(jsonl_path)

    @pytest.fixture
    def sqlite_store(self, tmp_path, sample_runs):
        """Create a SQLite database with sample runs."""
        db_path = tmp_path / "traces.db"
        from agenttrace.storage.sqlite import SQLiteTraceStore

        store = SQLiteTraceStore(db_path)
        for run in sample_runs:
            store.save(run)
        store.close()
        return str(db_path)

    def test_from_source_jsonl_extension(self, jsonl_store):
        """Test loading from .jsonl file."""
        loader = TraceLoader.from_source(jsonl_store)
        assert loader.count() == 5

    def test_from_source_db_extension(self, sqlite_store):
        """Test loading from .db file."""
        loader = TraceLoader.from_source(sqlite_store)
        assert loader.count() == 5

    def test_from_source_sqlite_prefix(self, sqlite_store):
        """Test loading with sqlite:// prefix."""
        loader = TraceLoader.from_source(f"sqlite://{sqlite_store}")
        assert loader.count() == 5

    def test_list_traces(self, jsonl_store):
        """Test listing traces."""
        loader = TraceLoader.from_source(jsonl_store)
        traces = loader.list_traces()
        assert len(traces) == 5

    def test_list_traces_with_limit(self, jsonl_store):
        """Test listing traces with limit."""
        loader = TraceLoader.from_source(jsonl_store)
        traces = loader.list_traces(limit=3)
        assert len(traces) == 3

    def test_query_traces(self, sqlite_store):
        """Test querying traces."""
        loader = TraceLoader.from_source(sqlite_store)
        traces = loader.query_traces(TraceQuery(min_cost_usd=0.03))
        assert len(traces) == 3  # runs 3, 4, 5 have cost >= 0.03

    def test_get_trace(self, jsonl_store, sample_runs):
        """Test getting a specific trace."""
        loader = TraceLoader.from_source(jsonl_store)
        run_id = str(sample_runs[0].id)
        trace = loader.get_trace(run_id)
        assert trace is not None
        assert trace.name == sample_runs[0].name

    def test_get_trace_not_found(self, jsonl_store):
        """Test getting nonexistent trace."""
        loader = TraceLoader.from_source(jsonl_store)
        trace = loader.get_trace("nonexistent-id")
        assert trace is None

    def test_count(self, jsonl_store):
        """Test counting traces."""
        loader = TraceLoader.from_source(jsonl_store)
        assert loader.count() == 5

    def test_refresh(self, tmp_path):
        """Test refreshing loader."""
        jsonl_path = tmp_path / "refresh.jsonl"
        from agenttrace.storage.jsonl import JSONLTraceStore

        # Create initial file
        store = JSONLTraceStore(jsonl_path)
        store.save(AgentRun(name="run_1", start_time=datetime.now(UTC)))

        loader = TraceLoader.from_source(str(jsonl_path))
        assert loader.count() == 1

        # Add more runs
        store.save(AgentRun(name="run_2", start_time=datetime.now(UTC)))

        # Refresh should pick up new runs
        loader.refresh()
        assert loader.count() == 2

    def test_get_stats(self, sqlite_store):
        """Test getting statistics."""
        loader = TraceLoader.from_source(sqlite_store)
        stats = loader.get_stats()
        assert stats["trace_count"] == 5
        assert stats["total_tokens"] == 1500  # 100+200+300+400+500

    def test_source_property(self, jsonl_store):
        """Test source property."""
        loader = TraceLoader.from_source(jsonl_store)
        assert loader.source == jsonl_store

    def test_context_manager(self, sqlite_store):
        """Test using loader as context manager."""
        with TraceLoader.from_source(sqlite_store) as loader:
            assert loader.count() == 5

    def test_from_directory(self, tmp_path):
        """Test loading from directory."""
        # Create traces directory with JSONL file
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()
        jsonl_path = traces_dir / "agenttrace.jsonl"

        from agenttrace.storage.jsonl import JSONLTraceStore

        store = JSONLTraceStore(jsonl_path)
        store.save(AgentRun(name="test", start_time=datetime.now(UTC)))

        # Load from parent directory
        loader = TraceLoader.from_source(str(tmp_path / "traces"))
        assert loader.count() == 1

    def test_from_nonexistent_defaults_to_jsonl(self, tmp_path):
        """Test that loading nonexistent path defaults to JSONL."""
        # For nonexistent paths, TraceLoader defaults to JSONLTraceStore
        # which will create the file when traces are saved
        loader = TraceLoader.from_source(str(tmp_path / "nonexistent.jsonl"))
        assert loader.count() == 0  # Empty store

        from agenttrace.storage.jsonl import JSONLTraceStore

        assert isinstance(loader.store, JSONLTraceStore)


class TestGetLoaderForEnv:
    """Tests for get_loader_for_env function."""

    def test_default_jsonl(self, tmp_path, monkeypatch):
        """Test default returns JSONL loader."""
        # Create default trace file
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()
        jsonl_path = traces_dir / "agenttrace.jsonl"
        jsonl_path.touch()

        monkeypatch.chdir(tmp_path)

        # Reset config to use defaults
        from agenttrace.core.env_config import reset_config

        reset_config()

        loader = get_loader_for_env()
        assert "jsonl" in loader.source.lower() or loader.source.endswith(".jsonl")
