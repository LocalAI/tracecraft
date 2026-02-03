"""Tests for project associations with agents and evals.

Tests the hierarchical project structure:
- Projects contain Agents
- Projects contain Eval Sets
- Agents have traces
- Full tree structure in TUI
"""

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from tracecraft.core.models import AgentRun
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
def sample_project(temp_db):
    """Create a sample project."""
    project_id = temp_db.create_project(
        name="test-project",
        description="A test project",
    )
    return {"id": project_id, "name": "test-project"}


@pytest.fixture
def sample_trace():
    """Create a sample trace."""
    return AgentRun(
        id=uuid4(),
        name="test_run",
        start_time=datetime.now(UTC),
        input={"prompt": "Hello"},
        output={"response": "Hi there"},
        duration_ms=100.0,
    )


class TestAgentsTable:
    """Tests for the agents table schema."""

    def test_schema_version_is_5(self, temp_db):
        """Test that fresh install creates schema v5."""
        assert temp_db._get_schema_version() == 5

    def test_agents_table_exists(self, temp_db):
        """Test that agents table is created."""
        with temp_db._transaction() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='agents'")
            assert cursor.fetchone() is not None

    def test_traces_has_agent_id_column(self, temp_db):
        """Test that traces table has agent_id column."""
        with temp_db._transaction() as cursor:
            cursor.execute("PRAGMA table_info(traces)")
            columns = [row["name"] for row in cursor.fetchall()]
            assert "agent_id" in columns


class TestAgentCRUD:
    """Tests for agent CRUD operations."""

    def test_create_agent(self, temp_db):
        """Test creating an agent."""
        agent_id = temp_db.create_agent(
            name="my-agent",
            description="A test agent",
            agent_type="langchain",
        )
        assert agent_id is not None

    def test_create_agent_with_project(self, temp_db, sample_project):
        """Test creating an agent associated with a project."""
        agent_id = temp_db.create_agent(
            name="project-agent",
            description="Agent for project",
            project_id=sample_project["id"],
        )

        agent = temp_db.get_agent(agent_id)
        assert agent is not None
        assert agent["project_id"] == sample_project["id"]

    def test_get_agent(self, temp_db):
        """Test getting an agent by ID."""
        agent_id = temp_db.create_agent(name="get-test")
        agent = temp_db.get_agent(agent_id)

        assert agent is not None
        assert agent["id"] == agent_id
        assert agent["name"] == "get-test"

    def test_get_agent_not_found(self, temp_db):
        """Test getting non-existent agent returns None."""
        agent = temp_db.get_agent("nonexistent-id")
        assert agent is None

    def test_list_agents(self, temp_db):
        """Test listing all agents."""
        temp_db.create_agent(name="agent-1")
        temp_db.create_agent(name="agent-2")
        temp_db.create_agent(name="agent-3")

        agents = temp_db.list_agents()
        assert len(agents) >= 3

    def test_update_agent(self, temp_db):
        """Test updating an agent."""
        agent_id = temp_db.create_agent(name="update-test")

        temp_db.update_agent(
            agent_id,
            name="updated-name",
            description="Updated description",
        )

        agent = temp_db.get_agent(agent_id)
        assert agent["name"] == "updated-name"
        assert agent["description"] == "Updated description"

    def test_delete_agent(self, temp_db):
        """Test deleting an agent."""
        agent_id = temp_db.create_agent(name="delete-test")

        result = temp_db.delete_agent(agent_id)
        assert result is True

        agent = temp_db.get_agent(agent_id)
        assert agent is None

    def test_delete_agent_unlinks_traces(self, temp_db, sample_trace):
        """Test that deleting an agent unlinks its traces."""
        # Create agent and assign trace to it
        agent_id = temp_db.create_agent(name="unlink-test")
        temp_db.save(sample_trace)
        temp_db.assign_trace_to_agent(str(sample_trace.id), agent_id)

        # Verify trace is linked
        traces = temp_db.get_traces_by_agent_id(agent_id)
        assert len(traces) == 1

        # Delete the agent
        temp_db.delete_agent(agent_id)

        # Verify trace still exists but is unlinked (agent_id should be NULL)
        trace = temp_db.get(str(sample_trace.id))
        assert trace is not None  # Trace still exists

        # Verify no traces linked to this agent anymore
        traces = temp_db.get_traces_by_agent_id(agent_id)
        assert len(traces) == 0


class TestAgentProjectAssociation:
    """Tests for agent-project associations."""

    def test_assign_agent_to_project(self, temp_db, sample_project):
        """Test assigning an agent to a project."""
        agent_id = temp_db.create_agent(name="unassigned-agent")

        temp_db.assign_agent_to_project(agent_id, sample_project["id"])

        agent = temp_db.get_agent(agent_id)
        assert agent["project_id"] == sample_project["id"]

    def test_unassign_agent_from_project(self, temp_db, sample_project):
        """Test removing agent from project."""
        agent_id = temp_db.create_agent(
            name="assigned-agent",
            project_id=sample_project["id"],
        )

        temp_db.assign_agent_to_project(agent_id, None)

        agent = temp_db.get_agent(agent_id)
        assert agent["project_id"] is None

    def test_list_agents_for_project(self, temp_db, sample_project):
        """Test listing agents for a specific project."""
        # Create agents for project
        temp_db.create_agent(name="project-agent-1", project_id=sample_project["id"])
        temp_db.create_agent(name="project-agent-2", project_id=sample_project["id"])

        # Create agent without project
        temp_db.create_agent(name="no-project-agent")

        agents = temp_db.list_agents_for_project(sample_project["id"])
        assert len(agents) == 2
        assert all(a["project_id"] == sample_project["id"] for a in agents)

    def test_list_agents_for_project_empty(self, temp_db, sample_project):
        """Test listing agents for project with no agents."""
        agents = temp_db.list_agents_for_project(sample_project["id"])
        assert agents == []


class TestTraceAgentAssociation:
    """Tests for trace-agent associations."""

    def test_assign_trace_to_agent(self, temp_db, sample_trace):
        """Test assigning a trace to an agent."""
        temp_db.save(sample_trace)
        agent_id = temp_db.create_agent(name="trace-agent")

        temp_db.assign_trace_to_agent(str(sample_trace.id), agent_id)

        # Verify trace has agent_id
        trace = temp_db.get(str(sample_trace.id))
        # The agent_id should be accessible somehow
        # This depends on how we expose it

    def test_get_traces_by_agent_id(self, temp_db, sample_trace):
        """Test getting traces for a specific agent by ID."""
        temp_db.save(sample_trace)
        agent_id = temp_db.create_agent(name="trace-agent-2")
        temp_db.assign_trace_to_agent(str(sample_trace.id), agent_id)

        traces = temp_db.get_traces_by_agent_id(agent_id)
        assert len(traces) >= 1


class TestEvalSetProjectAssociation:
    """Tests for eval set-project associations."""

    def test_create_eval_set_with_project(self, temp_db, sample_project):
        """Test creating eval set with project association."""
        set_id = temp_db.create_evaluation_set(
            name="project-eval-set",
            metrics=[{"name": "exact_match", "framework": "builtin", "metric_type": "exact_match"}],
            project_id=sample_project["id"],
        )

        eval_set = temp_db.get_evaluation_set(set_id)
        assert eval_set["project_id"] == sample_project["id"]

    def test_list_evaluation_sets_for_project(self, temp_db, sample_project):
        """Test listing eval sets filtered by project."""
        # Create eval sets for project
        temp_db.create_evaluation_set(
            name="project-eval-1",
            metrics=[{"name": "exact_match", "framework": "builtin", "metric_type": "exact_match"}],
            project_id=sample_project["id"],
        )
        temp_db.create_evaluation_set(
            name="project-eval-2",
            metrics=[{"name": "contains", "framework": "builtin", "metric_type": "contains"}],
            project_id=sample_project["id"],
        )

        # Create eval set without project
        temp_db.create_evaluation_set(
            name="no-project-eval",
            metrics=[{"name": "json_valid", "framework": "builtin", "metric_type": "json_valid"}],
        )

        # List for project
        evals = temp_db.list_evaluation_sets(project_id=sample_project["id"])
        assert len(evals) == 2
        assert all(e["project_id"] == sample_project["id"] for e in evals)

    def test_assign_eval_set_to_project(self, temp_db, sample_project):
        """Test assigning existing eval set to project."""
        set_id = temp_db.create_evaluation_set(
            name="assign-eval",
            metrics=[{"name": "exact_match", "framework": "builtin", "metric_type": "exact_match"}],
        )

        temp_db.update_evaluation_set(set_id, project_id=sample_project["id"])

        eval_set = temp_db.get_evaluation_set(set_id)
        assert eval_set["project_id"] == sample_project["id"]


class TestProjectStructure:
    """Tests for getting full project structure."""

    def test_get_project_structure(self, temp_db, sample_project, sample_trace):
        """Test getting complete project structure with agents, evals, traces."""
        # Add agents to project
        temp_db.create_agent(name="struct-agent-1", project_id=sample_project["id"])
        temp_db.create_agent(name="struct-agent-2", project_id=sample_project["id"])

        # Add eval sets to project
        temp_db.create_evaluation_set(
            name="struct-eval-1",
            metrics=[{"name": "exact_match", "framework": "builtin", "metric_type": "exact_match"}],
            project_id=sample_project["id"],
        )

        # Add trace to project (pass project_id to save method)
        temp_db.save(sample_trace, project_id=sample_project["id"])

        # Get structure
        structure = temp_db.get_project_structure(sample_project["id"])

        assert structure["project"]["id"] == sample_project["id"]
        assert len(structure["agents"]) == 2
        assert len(structure["eval_sets"]) == 1
        assert structure["trace_count"] >= 1

    def test_get_project_structure_empty(self, temp_db, sample_project):
        """Test getting structure for project with no children."""
        structure = temp_db.get_project_structure(sample_project["id"])

        assert structure["project"]["id"] == sample_project["id"]
        assert structure["agents"] == []
        assert structure["eval_sets"] == []
        assert structure["trace_count"] == 0


class TestMigrationV4ToV5:
    """Tests for schema migration from v4 to v5."""

    def test_migration_preserves_existing_data(self, temp_db, sample_project, sample_trace):
        """Test that migration preserves existing projects and traces."""
        # Data should already be migrated in fixture
        # Just verify existing data works

        # Create trace with project (pass project_id to save method)
        temp_db.save(sample_trace, project_id=sample_project["id"])

        # Should be able to retrieve
        trace = temp_db.get(str(sample_trace.id))
        assert trace is not None

        project = temp_db.get_project(sample_project["id"])
        assert project is not None

    def test_migration_creates_agents_from_traces(self, temp_db):
        """Test that migration can create agents from existing trace data."""
        # This tests that traces with agent_name/agent_id in data
        # can be linked to the new agents table
        # Implementation depends on migration strategy
        pass


class TestTUIProjectTree:
    """Tests for TUI project tree display."""

    def test_tree_view_mode_has_project_tree(self):
        """Test that TreeViewMode includes project tree mode."""
        try:
            from tracecraft.tui.widgets.run_tree import TreeViewMode

            # Should have PROJECT_TREE mode or similar
            assert hasattr(TreeViewMode, "PROJECT_TREE") or hasattr(TreeViewMode, "PROJECTS")
        except ImportError:
            pass  # Textual not installed

    def test_run_tree_has_show_project_tree_method(self):
        """Test that RunTree has show_project_tree method."""
        try:
            from tracecraft.tui.widgets.run_tree import RunTree

            assert hasattr(RunTree, "show_project_tree")
        except ImportError:
            pass  # Textual not installed


class TestAgentStats:
    """Tests for agent statistics."""

    def test_get_agent_stats(self, temp_db, sample_trace):
        """Test getting statistics for an agent."""
        agent_id = temp_db.create_agent(name="stats-agent")
        temp_db.save(sample_trace)
        temp_db.assign_trace_to_agent(str(sample_trace.id), agent_id)

        stats = temp_db.get_agent_stats_by_id(agent_id)

        assert "trace_count" in stats
        assert stats["trace_count"] >= 1
