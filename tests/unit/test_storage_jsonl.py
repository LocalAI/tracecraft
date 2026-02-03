"""
Tests for JSONL storage backend.
"""

from datetime import UTC, datetime

import pytest

from tracecraft.core.models import AgentRun
from tracecraft.storage.base import TraceQuery
from tracecraft.storage.jsonl import JSONLTraceStore


class TestJSONLStorage:
    """Tests for JSONLTraceStore."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create a temporary JSONL store."""
        jsonl_path = tmp_path / "test.jsonl"
        return JSONLTraceStore(jsonl_path)

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

    def test_save_and_get(self, store, sample_run):
        """Test saving and retrieving a trace."""
        store.save(sample_run)
        retrieved = store.get(str(sample_run.id))

        assert retrieved is not None
        assert retrieved.name == sample_run.name
        assert retrieved.total_tokens == sample_run.total_tokens

    def test_get_nonexistent(self, store):
        """Test getting a nonexistent trace."""
        result = store.get("nonexistent-id")
        assert result is None

    def test_query_by_cost(self, store, sample_run):
        """Test querying by cost."""
        store.save(sample_run)

        cheap = store.query(TraceQuery(max_cost_usd=0.01))
        assert len(cheap) == 0

        expensive = store.query(TraceQuery(min_cost_usd=0.01))
        assert len(expensive) == 1

    def test_query_by_name(self, store, sample_run):
        """Test querying by name."""
        store.save(sample_run)

        exact = store.query(TraceQuery(name="test_run"))
        assert len(exact) == 1

        contains = store.query(TraceQuery(name_contains="test"))
        assert len(contains) == 1

        no_match = store.query(TraceQuery(name="nonexistent"))
        assert len(no_match) == 0

    def test_query_by_error(self, store):
        """Test querying by error status."""
        run_ok = AgentRun(
            name="ok_run",
            start_time=datetime.now(UTC),
            error_count=0,
        )
        run_err = AgentRun(
            name="error_run",
            start_time=datetime.now(UTC),
            error_count=1,
            error="Something failed",
        )
        store.save(run_ok)
        store.save(run_err)

        errors = store.query(TraceQuery(has_error=True))
        assert len(errors) == 1
        assert errors[0].name == "error_run"

        no_errors = store.query(TraceQuery(has_error=False))
        assert len(no_errors) == 1
        assert no_errors[0].name == "ok_run"

    def test_query_by_tags(self, store, sample_run):
        """Test querying by tags."""
        store.save(sample_run)

        with_tag = store.query(TraceQuery(tags=["test"]))
        assert len(with_tag) == 1

        with_both_tags = store.query(TraceQuery(tags=["test", "sample"]))
        assert len(with_both_tags) == 1

        wrong_tag = store.query(TraceQuery(tags=["nonexistent"]))
        assert len(wrong_tag) == 0

    def test_query_pagination(self, store):
        """Test query pagination."""
        for i in range(10):
            run = AgentRun(
                name=f"run_{i}",
                start_time=datetime.now(UTC),
            )
            store.save(run)

        first_page = store.query(TraceQuery(limit=3, offset=0))
        assert len(first_page) == 3

        second_page = store.query(TraceQuery(limit=3, offset=3))
        assert len(second_page) == 3

        all_runs = store.query(TraceQuery(limit=100))
        assert len(all_runs) == 10

    def test_list_all(self, store, sample_run):
        """Test listing all traces."""
        store.save(sample_run)
        all_traces = store.list_all()
        assert len(all_traces) == 1

    def test_delete_not_supported(self, store, sample_run):
        """Test that delete raises NotImplementedError."""
        store.save(sample_run)

        with pytest.raises(NotImplementedError):
            store.delete(str(sample_run.id))

    def test_count(self, store):
        """Test counting traces."""
        assert store.count() == 0

        for i in range(5):
            run = AgentRun(
                name=f"run_{i}",
                start_time=datetime.now(UTC),
            )
            store.save(run)

        assert store.count() == 5

    def test_cache_invalidation(self, store, sample_run):
        """Test that cache is invalidated on save."""
        store.save(sample_run)
        assert store.count() == 1

        # Save another run
        run2 = AgentRun(
            name="run_2",
            start_time=datetime.now(UTC),
        )
        store.save(run2)

        # Should see both runs
        assert store.count() == 2

    def test_get_file_size(self, store, sample_run):
        """Test getting file size."""
        assert store.get_file_size() == 0

        store.save(sample_run)
        assert store.get_file_size() > 0

    def test_get_stats(self, store, sample_run):
        """Test getting storage statistics."""
        store.save(sample_run)

        stats = store.get_stats()
        assert stats["trace_count"] == 1
        assert stats["total_tokens"] == 100
        assert stats["total_cost_usd"] == 0.05
        assert stats["file_size_bytes"] > 0

    def test_creates_parent_directory(self, tmp_path):
        """Test that parent directory is created if needed."""
        nested_path = tmp_path / "nested" / "dir" / "test.jsonl"
        store = JSONLTraceStore(nested_path)

        run = AgentRun(name="test", start_time=datetime.now(UTC))
        store.save(run)

        assert nested_path.exists()

    def test_handles_empty_file(self, tmp_path):
        """Test handling of empty file."""
        jsonl_path = tmp_path / "empty.jsonl"
        jsonl_path.touch()

        store = JSONLTraceStore(jsonl_path)
        assert store.count() == 0

    def test_handles_malformed_lines(self, tmp_path):
        """Test handling of malformed JSON lines."""
        jsonl_path = tmp_path / "malformed.jsonl"

        # Write a valid run and an invalid line
        valid_run = AgentRun(name="valid", start_time=datetime.now(UTC))
        with open(jsonl_path, "w") as f:
            f.write(valid_run.model_dump_json() + "\n")
            f.write("not valid json\n")

        store = JSONLTraceStore(jsonl_path)
        # Should only load the valid run
        assert store.count() == 1
