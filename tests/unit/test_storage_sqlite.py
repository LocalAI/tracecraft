"""
Tests for SQLite storage backend.
"""

from datetime import UTC, datetime

import pytest

from tracecraft.core.models import AgentRun, Step, StepType
from tracecraft.storage.base import TraceQuery
from tracecraft.storage.sqlite import SQLiteTraceStore


class TestSQLiteStorage:
    """Tests for SQLiteTraceStore."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create a temporary SQLite store."""
        db_path = tmp_path / "test.db"
        store = SQLiteTraceStore(db_path)
        yield store
        store.close()

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

    @pytest.fixture
    def sample_run_with_steps(self):
        """Create a sample AgentRun with steps."""
        run = AgentRun(
            name="test_run_with_steps",
            start_time=datetime.now(UTC),
            total_tokens=200,
            total_cost_usd=0.10,
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

    def test_delete(self, store, sample_run):
        """Test deleting a trace."""
        store.save(sample_run)
        assert store.count() == 1

        deleted = store.delete(str(sample_run.id))
        assert deleted is True
        assert store.count() == 0

        # Delete nonexistent
        deleted_again = store.delete(str(sample_run.id))
        assert deleted_again is False

    def test_count(self, store):
        """Test counting traces."""
        assert store.count() == 0

        for i in range(5):
            run = AgentRun(
                name=f"run_{i}",
                start_time=datetime.now(UTC),
                error_count=1 if i % 2 == 0 else 0,
            )
            store.save(run)

        assert store.count() == 5
        assert store.count(TraceQuery(has_error=True)) == 3
        assert store.count(TraceQuery(has_error=False)) == 2

    def test_raw_sql_query(self, store, sample_run):
        """Test raw SQL queries."""
        store.save(sample_run)

        results = store.execute_sql(
            "SELECT name, total_cost_usd FROM traces WHERE total_cost_usd > ?",
            (0.01,),
        )
        assert len(results) == 1
        assert results[0]["name"] == "test_run"
        assert results[0]["total_cost_usd"] == 0.05

    def test_steps_stored(self, store, sample_run_with_steps):
        """Test that steps are stored correctly."""
        store.save(sample_run_with_steps)

        # Query steps table directly
        results = store.execute_sql(
            "SELECT name, model_name FROM steps WHERE trace_id = ?",
            (str(sample_run_with_steps.id),),
        )
        assert len(results) == 1
        assert results[0]["name"] == "llm_call"
        assert results[0]["model_name"] == "gpt-4"

    def test_get_stats(self, store, sample_run):
        """Test getting storage statistics."""
        store.save(sample_run)

        stats = store.get_stats()
        assert stats["trace_count"] == 1
        assert stats["total_tokens"] == 100
        assert stats["total_cost_usd"] == 0.05

    def test_wal_mode(self, tmp_path):
        """Test WAL mode is enabled by default."""
        db_path = tmp_path / "wal_test.db"
        store = SQLiteTraceStore(db_path, wal_mode=True)

        # WAL mode creates additional files
        store.save(AgentRun(name="test", start_time=datetime.now(UTC)))

        # Check journal mode
        results = store.execute_sql("PRAGMA journal_mode")
        assert results[0]["journal_mode"] == "wal"

        store.close()

    def test_context_manager(self, tmp_path):
        """Test using store as context manager."""
        db_path = tmp_path / "context_test.db"

        with SQLiteTraceStore(db_path) as store:
            store.save(AgentRun(name="test", start_time=datetime.now(UTC)))
            assert store.count() == 1


class TestProjectManagement:
    """Tests for project management methods."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create a temporary SQLite store."""
        db_path = tmp_path / "test_projects.db"
        store = SQLiteTraceStore(db_path)
        yield store
        store.close()

    def test_create_project(self, store):
        """Test creating a project."""
        project_id = store.create_project(
            name="Test Project",
            description="A test project",
            settings={"key": "value"},
        )

        assert project_id is not None
        assert len(project_id) == 36  # UUID length

    def test_create_project_duplicate_name_fails(self, store):
        """Test that duplicate project names fail."""
        store.create_project(name="Unique Name")

        with pytest.raises(Exception):  # sqlite3.IntegrityError
            store.create_project(name="Unique Name")

    def test_get_project(self, store):
        """Test getting a project by ID."""
        project_id = store.create_project(
            name="My Project",
            description="Description",
            settings={"theme": "dark"},
        )

        project = store.get_project(project_id)
        assert project is not None
        assert project["name"] == "My Project"
        assert project["description"] == "Description"
        assert project["settings"] == {"theme": "dark"}

    def test_get_project_nonexistent(self, store):
        """Test getting a nonexistent project."""
        project = store.get_project("nonexistent-id")
        assert project is None

    def test_get_project_by_name(self, store):
        """Test getting a project by name."""
        store.create_project(name="Named Project")

        project = store.get_project_by_name("Named Project")
        assert project is not None
        assert project["name"] == "Named Project"

        no_project = store.get_project_by_name("Nonexistent")
        assert no_project is None

    def test_list_projects(self, store):
        """Test listing all projects."""
        store.create_project(name="Project A")
        store.create_project(name="Project B")
        store.create_project(name="Project C")

        projects = store.list_projects()
        assert len(projects) == 3
        # Should be sorted by name
        names = [p["name"] for p in projects]
        assert names == ["Project A", "Project B", "Project C"]

    def test_update_project(self, store):
        """Test updating a project."""
        project_id = store.create_project(name="Old Name", description="Old desc")

        updated = store.update_project(
            project_id,
            name="New Name",
            description="New desc",
            settings={"updated": True},
        )
        assert updated is True

        project = store.get_project(project_id)
        assert project["name"] == "New Name"
        assert project["description"] == "New desc"
        assert project["settings"] == {"updated": True}

    def test_update_nonexistent_project(self, store):
        """Test updating a nonexistent project."""
        updated = store.update_project("nonexistent-id", name="New Name")
        assert updated is False

    def test_delete_project(self, store):
        """Test deleting a project."""
        project_id = store.create_project(name="To Delete")

        deleted = store.delete_project(project_id)
        assert deleted is True

        project = store.get_project(project_id)
        assert project is None

    def test_delete_nonexistent_project(self, store):
        """Test deleting a nonexistent project."""
        deleted = store.delete_project("nonexistent-id")
        assert deleted is False

    def test_assign_trace_to_project(self, store):
        """Test assigning a trace to a project."""
        project_id = store.create_project(name="My Project")

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        store.save(run)

        # Assign to project
        assigned = store.assign_trace_to_project(str(run.id), project_id)
        assert assigned is True

        # Query by project
        traces = store.query(TraceQuery(project_id=project_id))
        assert len(traces) == 1
        assert traces[0].name == "test_run"

    def test_unassign_trace_from_project(self, store):
        """Test unassigning a trace from a project."""
        project_id = store.create_project(name="My Project")

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        store.save(run, project_id=project_id)

        # Unassign
        store.assign_trace_to_project(str(run.id), None)

        # Should no longer be in project
        traces = store.query(TraceQuery(project_id=project_id))
        assert len(traces) == 0

    def test_query_by_project(self, store):
        """Test querying traces by project_id."""
        project_a = store.create_project(name="Project A")
        project_b = store.create_project(name="Project B")

        run_a = AgentRun(name="run_a", start_time=datetime.now(UTC))
        run_b = AgentRun(name="run_b", start_time=datetime.now(UTC))
        run_none = AgentRun(name="run_none", start_time=datetime.now(UTC))

        store.save(run_a, project_id=project_a)
        store.save(run_b, project_id=project_b)
        store.save(run_none)

        traces_a = store.query(TraceQuery(project_id=project_a))
        assert len(traces_a) == 1
        assert traces_a[0].name == "run_a"

        traces_b = store.query(TraceQuery(project_id=project_b))
        assert len(traces_b) == 1
        assert traces_b[0].name == "run_b"

        # All traces
        all_traces = store.query(TraceQuery())
        assert len(all_traces) == 3

    def test_get_project_stats(self, store):
        """Test getting project statistics."""
        project_id = store.create_project(name="Stats Project")

        run1 = AgentRun(
            name="run1",
            start_time=datetime.now(UTC),
            total_tokens=100,
            total_cost_usd=0.05,
            error_count=0,
        )
        run2 = AgentRun(
            name="run2",
            start_time=datetime.now(UTC),
            total_tokens=200,
            total_cost_usd=0.10,
            error_count=1,
        )

        store.save(run1, project_id=project_id)
        store.save(run2, project_id=project_id)

        stats = store.get_project_stats(project_id)
        assert stats["trace_count"] == 2
        assert stats["total_tokens"] == 300
        assert stats["total_cost_usd"] == pytest.approx(0.15)
        assert stats["error_count"] == 1


class TestVersioning:
    """Tests for trace versioning methods."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create a temporary SQLite store."""
        db_path = tmp_path / "test_versions.db"
        store = SQLiteTraceStore(db_path)
        yield store
        store.close()

    @pytest.fixture
    def sample_run(self):
        """Create a sample AgentRun."""
        return AgentRun(
            name="test_run",
            start_time=datetime.now(UTC),
            total_tokens=100,
        )

    def test_create_version(self, store, sample_run):
        """Test creating a version."""
        store.save(sample_run)

        version_id = store.create_version(
            str(sample_run.id),
            version_type="original",
            notes="Initial version",
        )

        assert version_id is not None
        assert len(version_id) == 36

    def test_create_version_auto_increment(self, store, sample_run):
        """Test version numbers auto-increment."""
        store.save(sample_run)

        v1_id = store.create_version(str(sample_run.id), version_type="original")
        v2_id = store.create_version(str(sample_run.id), version_type="playground")
        v3_id = store.create_version(str(sample_run.id), version_type="manual")

        versions = store.list_versions(str(sample_run.id))
        assert len(versions) == 3
        assert versions[0]["version_number"] == 1
        assert versions[1]["version_number"] == 2
        assert versions[2]["version_number"] == 3

    def test_get_version(self, store, sample_run):
        """Test getting a version as AgentRun."""
        store.save(sample_run)
        version_id = store.create_version(str(sample_run.id))

        retrieved = store.get_version(version_id)
        assert retrieved is not None
        assert retrieved.name == sample_run.name
        assert retrieved.total_tokens == sample_run.total_tokens

    def test_get_version_nonexistent(self, store):
        """Test getting a nonexistent version."""
        result = store.get_version("nonexistent-id")
        assert result is None

    def test_get_version_metadata(self, store, sample_run):
        """Test getting version metadata."""
        store.save(sample_run)
        version_id = store.create_version(
            str(sample_run.id),
            version_type="playground",
            notes="Test notes",
            created_by="user123",
        )

        metadata = store.get_version_metadata(version_id)
        assert metadata is not None
        assert metadata["version_type"] == "playground"
        assert metadata["notes"] == "Test notes"
        assert metadata["created_by"] == "user123"

    def test_list_versions(self, store, sample_run):
        """Test listing all versions for a trace."""
        store.save(sample_run)
        store.create_version(str(sample_run.id), version_type="original", notes="v1")
        store.create_version(str(sample_run.id), version_type="playground", notes="v2")

        versions = store.list_versions(str(sample_run.id))
        assert len(versions) == 2
        assert versions[0]["notes"] == "v1"
        assert versions[1]["notes"] == "v2"

    def test_get_latest_version(self, store, sample_run):
        """Test getting the latest version."""
        store.save(sample_run)
        store.create_version(str(sample_run.id), notes="first")
        store.create_version(str(sample_run.id), notes="second")
        store.create_version(str(sample_run.id), notes="latest")

        latest = store.get_latest_version(str(sample_run.id))
        assert latest is not None
        assert latest["notes"] == "latest"
        assert latest["version_number"] == 3

    def test_get_latest_version_none(self, store, sample_run):
        """Test getting latest version when none exist."""
        store.save(sample_run)

        latest = store.get_latest_version(str(sample_run.id))
        assert latest is None

    def test_delete_version(self, store, sample_run):
        """Test deleting a version."""
        store.save(sample_run)
        version_id = store.create_version(str(sample_run.id))

        deleted = store.delete_version(version_id)
        assert deleted is True

        version = store.get_version(version_id)
        assert version is None

    def test_delete_nonexistent_version(self, store):
        """Test deleting a nonexistent version."""
        deleted = store.delete_version("nonexistent-id")
        assert deleted is False

    def test_create_version_with_modified_run(self, store, sample_run):
        """Test creating a version with modified data."""
        store.save(sample_run)

        # Create modified version
        modified_run = AgentRun(
            id=sample_run.id,
            name="modified_name",
            start_time=sample_run.start_time,
            total_tokens=500,
        )

        version_id = store.create_version(
            str(sample_run.id),
            version_type="playground",
            modified_run=modified_run,
        )

        # Retrieved version should have modified data
        retrieved = store.get_version(version_id)
        assert retrieved.name == "modified_name"
        assert retrieved.total_tokens == 500


class TestPlaygroundIterations:
    """Tests for playground iteration methods."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create a temporary SQLite store."""
        db_path = tmp_path / "test_iterations.db"
        store = SQLiteTraceStore(db_path)
        yield store
        store.close()

    @pytest.fixture
    def sample_run(self):
        """Create a sample AgentRun with a step."""
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        step = Step(
            trace_id=run.id,
            type=StepType.LLM,
            name="llm_step",
            start_time=datetime.now(UTC),
        )
        run.steps.append(step)
        return run

    def test_save_iteration(self, store, sample_run):
        """Test saving an iteration."""
        store.save(sample_run)
        step_id = str(sample_run.steps[0].id)

        iteration_id = store.save_iteration(
            trace_id=str(sample_run.id),
            step_id=step_id,
            prompt="Test prompt",
            output="Test output",
            input_tokens=10,
            output_tokens=20,
            duration_ms=100.5,
            notes="First iteration",
        )

        assert iteration_id is not None
        assert len(iteration_id) == 36

    def test_get_iteration(self, store, sample_run):
        """Test getting a single iteration."""
        store.save(sample_run)
        step_id = str(sample_run.steps[0].id)

        iteration_id = store.save_iteration(
            trace_id=str(sample_run.id),
            step_id=step_id,
            prompt="My prompt",
            output="My output",
            input_tokens=5,
            output_tokens=15,
            duration_ms=50.0,
            notes="Test note",
        )

        iteration = store.get_iteration(iteration_id)
        assert iteration is not None
        assert iteration["prompt"] == "My prompt"
        assert iteration["output"] == "My output"
        assert iteration["input_tokens"] == 5
        assert iteration["output_tokens"] == 15
        assert iteration["duration_ms"] == 50.0
        assert iteration["notes"] == "Test note"
        assert iteration["is_best"] is False

    def test_get_iterations(self, store, sample_run):
        """Test getting all iterations for a trace."""
        store.save(sample_run)
        step_id = str(sample_run.steps[0].id)
        trace_id = str(sample_run.id)

        store.save_iteration(trace_id, step_id, "prompt1", "output1")
        store.save_iteration(trace_id, step_id, "prompt2", "output2")
        store.save_iteration(trace_id, step_id, "prompt3", "output3")

        iterations = store.get_iterations(trace_id)
        assert len(iterations) == 3
        assert iterations[0]["iteration_number"] == 1
        assert iterations[1]["iteration_number"] == 2
        assert iterations[2]["iteration_number"] == 3

    def test_get_iterations_by_step(self, store, sample_run):
        """Test getting iterations filtered by step_id."""
        store.save(sample_run)
        step_id = str(sample_run.steps[0].id)
        trace_id = str(sample_run.id)

        store.save_iteration(trace_id, step_id, "prompt1", "output1")
        store.save_iteration(trace_id, "other_step", "prompt2", "output2")
        store.save_iteration(trace_id, step_id, "prompt3", "output3")

        # Filter by step_id
        iterations = store.get_iterations(trace_id, step_id=step_id)
        assert len(iterations) == 2
        assert all(it["step_id"] == step_id for it in iterations)

    def test_mark_best_iteration(self, store, sample_run):
        """Test marking an iteration as best."""
        store.save(sample_run)
        step_id = str(sample_run.steps[0].id)
        trace_id = str(sample_run.id)

        id1 = store.save_iteration(trace_id, step_id, "prompt1", "output1")
        id2 = store.save_iteration(trace_id, step_id, "prompt2", "output2")

        # Mark second as best
        result = store.mark_best_iteration(id2)
        assert result is True

        it2 = store.get_iteration(id2)
        assert it2["is_best"] is True

        it1 = store.get_iteration(id1)
        assert it1["is_best"] is False

    def test_mark_best_clears_previous(self, store, sample_run):
        """Test that marking best clears previous best for same step."""
        store.save(sample_run)
        step_id = str(sample_run.steps[0].id)
        trace_id = str(sample_run.id)

        id1 = store.save_iteration(trace_id, step_id, "prompt1", "output1")
        id2 = store.save_iteration(trace_id, step_id, "prompt2", "output2")

        # Mark first as best
        store.mark_best_iteration(id1)
        assert store.get_iteration(id1)["is_best"] is True

        # Now mark second as best - should clear first
        store.mark_best_iteration(id2)
        assert store.get_iteration(id2)["is_best"] is True
        assert store.get_iteration(id1)["is_best"] is False

    def test_get_best_iteration(self, store, sample_run):
        """Test getting the best iteration for a step."""
        store.save(sample_run)
        step_id = str(sample_run.steps[0].id)
        trace_id = str(sample_run.id)

        store.save_iteration(trace_id, step_id, "prompt1", "output1")
        id2 = store.save_iteration(trace_id, step_id, "prompt2", "output2")
        store.save_iteration(trace_id, step_id, "prompt3", "output3")

        # No best yet
        best = store.get_best_iteration(trace_id, step_id)
        assert best is None

        # Mark one as best
        store.mark_best_iteration(id2)

        best = store.get_best_iteration(trace_id, step_id)
        assert best is not None
        assert best["prompt"] == "prompt2"

    def test_delete_iteration(self, store, sample_run):
        """Test deleting an iteration."""
        store.save(sample_run)
        step_id = str(sample_run.steps[0].id)
        trace_id = str(sample_run.id)

        iteration_id = store.save_iteration(trace_id, step_id, "prompt", "output")

        deleted = store.delete_iteration(iteration_id)
        assert deleted is True

        iteration = store.get_iteration(iteration_id)
        assert iteration is None

    def test_delete_nonexistent_iteration(self, store):
        """Test deleting a nonexistent iteration."""
        deleted = store.delete_iteration("nonexistent-id")
        assert deleted is False

    def test_iteration_number_per_step(self, store, sample_run):
        """Test iteration numbers are per trace/step combination."""
        store.save(sample_run)
        step_id = str(sample_run.steps[0].id)
        trace_id = str(sample_run.id)

        # Iterations for step_id
        store.save_iteration(trace_id, step_id, "p1", "o1")
        store.save_iteration(trace_id, step_id, "p2", "o2")

        # Iterations for different step
        store.save_iteration(trace_id, "other_step", "p3", "o3")
        store.save_iteration(trace_id, "other_step", "p4", "o4")

        # Check iteration numbers are separate
        step_iterations = store.get_iterations(trace_id, step_id=step_id)
        assert step_iterations[0]["iteration_number"] == 1
        assert step_iterations[1]["iteration_number"] == 2

        other_iterations = store.get_iterations(trace_id, step_id="other_step")
        assert other_iterations[0]["iteration_number"] == 1
        assert other_iterations[1]["iteration_number"] == 2


class TestSchemaMigration:
    """Tests for schema migration."""

    def test_fresh_install_creates_v6(self, tmp_path):
        """Test that fresh installation creates schema v6."""
        db_path = tmp_path / "fresh.db"
        store = SQLiteTraceStore(db_path)

        # Check schema version
        results = store.execute_sql("SELECT version FROM schema_version")
        assert results[0]["version"] == 6

        # Check new tables exist (v2 tables)
        tables = store.execute_sql("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = {t["name"] for t in tables}
        assert "projects" in table_names
        assert "trace_versions" in table_names
        assert "playground_iterations" in table_names
        # Evaluation and agents tables should NOT exist (removed in v6)
        assert "evaluation_sets" not in table_names
        assert "evaluation_cases" not in table_names
        assert "evaluation_runs" not in table_names
        assert "evaluation_results" not in table_names
        assert "agents" not in table_names

        store.close()

    def test_v1_to_v6_migration(self, tmp_path):
        """Test migration from v1 to v6 schema."""
        import sqlite3

        db_path = tmp_path / "migrate.db"

        # Create a v1 database manually
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Create v1 schema (without new tables)
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS traces (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_ms REAL,
                session_id TEXT,
                user_id TEXT,
                environment TEXT,
                total_tokens INTEGER DEFAULT 0,
                total_cost_usd REAL DEFAULT 0.0,
                error_count INTEGER DEFAULT 0,
                error TEXT,
                error_type TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                data JSON NOT NULL
            );

            CREATE TABLE IF NOT EXISTS trace_tags (
                trace_id TEXT NOT NULL,
                tag TEXT NOT NULL,
                PRIMARY KEY (trace_id, tag),
                FOREIGN KEY (trace_id) REFERENCES traces(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS steps (
                id TEXT PRIMARY KEY,
                trace_id TEXT NOT NULL,
                parent_id TEXT,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_ms REAL,
                model_name TEXT,
                model_provider TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                cost_usd REAL,
                error TEXT,
                error_type TEXT,
                FOREIGN KEY (trace_id) REFERENCES traces(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            );

            INSERT INTO schema_version (version) VALUES (1);
        """)

        # Add a test trace
        cursor.execute(
            "INSERT INTO traces (id, name, start_time, data) VALUES (?, ?, ?, ?)",
            ("test-id", "test_trace", "2024-01-01T00:00:00", "{}"),
        )
        conn.commit()
        conn.close()

        # Now open with SQLiteTraceStore - should trigger migration
        store = SQLiteTraceStore(db_path)

        # Check schema version is now 6
        results = store.execute_sql("SELECT version FROM schema_version")
        assert results[0]["version"] == 6

        # Check new tables exist (v2 tables)
        tables = store.execute_sql("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = {t["name"] for t in tables}
        assert "projects" in table_names
        assert "trace_versions" in table_names
        assert "playground_iterations" in table_names
        # Evaluation and agents tables should NOT exist (removed in v6)
        assert "evaluation_sets" not in table_names
        assert "evaluation_cases" not in table_names
        assert "evaluation_runs" not in table_names
        assert "evaluation_results" not in table_names
        assert "agents" not in table_names

        # Check traces table has project_id column (agent_id removed in v6)
        columns = store.execute_sql("PRAGMA table_info(traces)")
        column_names = {c["name"] for c in columns}
        assert "project_id" in column_names

        # Check existing data is preserved
        results = store.execute_sql("SELECT name FROM traces")
        assert results[0]["name"] == "test_trace"

        store.close()
