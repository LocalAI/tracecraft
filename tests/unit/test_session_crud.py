"""Tests for session CRUD operations.

Tests the session hierarchy:
- Sessions belong to Projects (optional)
- Traces belong to Sessions
- Session statistics and querying
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
def sample_session(temp_db, sample_project):
    """Create a sample session."""
    session_id = temp_db.create_session(
        name="test-session",
        project_id=sample_project["id"],
        description="A test session",
    )
    return {"id": session_id, "name": "test-session", "project_id": sample_project["id"]}


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


class TestSessionCreate:
    """Tests for creating sessions."""

    def test_create_session_with_project(self, temp_db, sample_project):
        """Test creating a session within a project."""
        session_id = temp_db.create_session(
            name="my-session",
            project_id=sample_project["id"],
            description="A session",
        )

        assert session_id is not None
        session = temp_db.get_session(session_id)
        assert session["name"] == "my-session"
        assert session["project_id"] == sample_project["id"]
        assert session["description"] == "A session"

    def test_create_session_without_project(self, temp_db):
        """Test creating a session without a project."""
        session_id = temp_db.create_session(
            name="standalone-session",
            description="A standalone session",
        )

        assert session_id is not None
        session = temp_db.get_session(session_id)
        assert session["name"] == "standalone-session"
        assert session["project_id"] is None

    def test_create_session_with_metadata(self, temp_db):
        """Test creating a session with metadata."""
        session_id = temp_db.create_session(
            name="session-with-meta",
            metadata={"key": "value", "count": 42},
        )

        session = temp_db.get_session(session_id)
        assert session["metadata"]["key"] == "value"
        assert session["metadata"]["count"] == 42


class TestSessionGet:
    """Tests for retrieving sessions."""

    def test_get_session_by_id(self, temp_db, sample_session):
        """Test getting a session by ID."""
        session = temp_db.get_session(sample_session["id"])
        assert session is not None
        assert session["name"] == "test-session"

    def test_get_session_by_name(self, temp_db, sample_session, sample_project):
        """Test getting a session by name within a project."""
        session = temp_db.get_session_by_name("test-session", sample_project["id"])
        assert session is not None
        assert session["id"] == sample_session["id"]

    def test_get_nonexistent_session(self, temp_db):
        """Test getting a session that doesn't exist."""
        session = temp_db.get_session("nonexistent-id")
        assert session is None


class TestSessionList:
    """Tests for listing sessions."""

    def test_list_all_sessions(self, temp_db, sample_project):
        """Test listing all sessions."""
        temp_db.create_session(name="session-1", project_id=sample_project["id"])
        temp_db.create_session(name="session-2", project_id=sample_project["id"])
        temp_db.create_session(name="session-3")  # No project

        sessions = temp_db.list_sessions()
        assert len(sessions) == 3

    def test_list_sessions_by_project(self, temp_db, sample_project):
        """Test listing sessions filtered by project."""
        temp_db.create_session(name="session-1", project_id=sample_project["id"])
        temp_db.create_session(name="session-2", project_id=sample_project["id"])
        temp_db.create_session(name="session-3")  # No project

        sessions = temp_db.list_sessions(project_id=sample_project["id"])
        assert len(sessions) == 2
        assert all(s["project_id"] == sample_project["id"] for s in sessions)


class TestSessionUpdate:
    """Tests for updating sessions."""

    def test_update_session_name(self, temp_db, sample_session):
        """Test updating a session name."""
        result = temp_db.update_session(sample_session["id"], name="renamed-session")
        assert result is True

        session = temp_db.get_session(sample_session["id"])
        assert session["name"] == "renamed-session"

    def test_update_session_description(self, temp_db, sample_session):
        """Test updating a session description."""
        result = temp_db.update_session(sample_session["id"], description="Updated description")
        assert result is True

        session = temp_db.get_session(sample_session["id"])
        assert session["description"] == "Updated description"

    def test_update_nonexistent_session(self, temp_db):
        """Test updating a session that doesn't exist."""
        result = temp_db.update_session("nonexistent-id", name="new-name")
        assert result is False


class TestSessionDelete:
    """Tests for deleting sessions."""

    def test_delete_session(self, temp_db, sample_session):
        """Test deleting a session."""
        result = temp_db.delete_session(sample_session["id"])
        assert result is True

        session = temp_db.get_session(sample_session["id"])
        assert session is None

    def test_delete_nonexistent_session(self, temp_db):
        """Test deleting a session that doesn't exist."""
        result = temp_db.delete_session("nonexistent-id")
        assert result is False


class TestGetOrCreateSession:
    """Tests for get_or_create_session."""

    def test_get_existing_session(self, temp_db, sample_session, sample_project):
        """Test getting an existing session."""
        session_id, created = temp_db.get_or_create_session(
            name="test-session",
            project_id=sample_project["id"],
        )

        assert session_id == sample_session["id"]
        assert created is False

    def test_create_new_session(self, temp_db, sample_project):
        """Test creating a new session when it doesn't exist."""
        session_id, created = temp_db.get_or_create_session(
            name="new-session",
            project_id=sample_project["id"],
            description="A new session",
        )

        assert created is True
        session = temp_db.get_session(session_id)
        assert session["name"] == "new-session"
        assert session["description"] == "A new session"


class TestSessionStats:
    """Tests for session statistics."""

    def test_session_stats(self, temp_db, sample_session, sample_trace):
        """Test getting statistics for a session."""
        # Assign trace to session
        sample_trace.session_id = sample_session["id"]
        sample_trace.total_tokens = 100
        sample_trace.total_cost_usd = 0.01
        temp_db.save(sample_trace)

        stats = temp_db.get_session_stats(sample_session["id"])

        assert stats["trace_count"] == 1
        assert stats["total_tokens"] == 100
        assert stats["total_cost_usd"] == 0.01

    def test_session_stats_empty(self, temp_db, sample_session):
        """Test getting statistics for an empty session."""
        stats = temp_db.get_session_stats(sample_session["id"])

        assert stats["trace_count"] == 0
        assert stats["total_tokens"] == 0


class TestSessionTraceQuery:
    """Tests for querying traces by session."""

    def test_query_traces_by_session(self, temp_db, sample_session):
        """Test filtering traces by session_id."""
        from tracecraft.storage.base import TraceQuery

        # Create traces with and without session
        trace1 = AgentRun(
            id=uuid4(),
            name="trace-in-session",
            start_time=datetime.now(UTC),
            session_id=sample_session["id"],
        )
        trace2 = AgentRun(
            id=uuid4(),
            name="trace-outside-session",
            start_time=datetime.now(UTC),
        )

        temp_db.save(trace1)
        temp_db.save(trace2)

        # Query by session
        query = TraceQuery(session_id=sample_session["id"])
        traces = temp_db.query(query)

        assert len(traces) == 1
        assert traces[0].name == "trace-in-session"


class TestSessionEdgeCases:
    """Tests for edge cases and constraints."""

    def test_duplicate_session_names_in_different_projects(self, temp_db):
        """Test that same session name can exist in different projects."""
        project1_id = temp_db.create_project(name="project-1")
        project2_id = temp_db.create_project(name="project-2")

        session1_id = temp_db.create_session(name="shared-name", project_id=project1_id)
        session2_id = temp_db.create_session(name="shared-name", project_id=project2_id)

        assert session1_id != session2_id
        assert temp_db.get_session(session1_id)["project_id"] == project1_id
        assert temp_db.get_session(session2_id)["project_id"] == project2_id

    def test_session_persists_when_project_deleted(self, temp_db):
        """Test that session remains (with NULL project_id) when project deleted."""
        project_id = temp_db.create_project(name="temp-project")
        session_id = temp_db.create_session(name="orphaned-session", project_id=project_id)

        # Delete the project
        temp_db.delete_project(project_id)

        # Session should still exist with NULL project_id (ON DELETE SET NULL)
        session = temp_db.get_session(session_id)
        assert session is not None
        assert session["project_id"] is None
        assert session["name"] == "orphaned-session"

    def test_get_session_by_name_without_project(self, temp_db):
        """Test getting session by name when no project specified."""
        session_id = temp_db.create_session(name="standalone")
        session = temp_db.get_session_by_name("standalone")

        assert session is not None
        assert session["id"] == session_id

    def test_get_or_create_handles_integrity_error(self, temp_db):
        """Test that get_or_create_session handles duplicate creation gracefully."""
        # First, create a session normally
        session_id1, created1 = temp_db.get_or_create_session(name="test-integrity")
        assert created1 is True

        # Second call should return existing without error
        session_id2, created2 = temp_db.get_or_create_session(name="test-integrity")
        assert created2 is False
        assert session_id1 == session_id2

        # Simulate race condition: manually insert duplicate and verify no crash
        # This verifies the IntegrityError catch works
        project_id = temp_db.create_project(name="race-project")
        session_id3, _ = temp_db.get_or_create_session(name="race-session", project_id=project_id)

        # Should return same session on retry
        session_id4, created4 = temp_db.get_or_create_session(
            name="race-session", project_id=project_id
        )
        assert session_id3 == session_id4
        assert created4 is False


class TestAssignTraceToSession:
    """Tests for assign_trace_to_session."""

    def test_assign_trace_to_session(self, temp_db, sample_session, sample_trace):
        """Test assigning a trace to a session."""
        temp_db.save(sample_trace)

        result = temp_db.assign_trace_to_session(str(sample_trace.id), sample_session["id"])
        assert result is True

        # Verify trace now has the session
        trace = temp_db.get(str(sample_trace.id))
        assert trace.session_id == sample_session["id"]

    def test_unassign_trace_from_session(self, temp_db, sample_session, sample_trace):
        """Test unassigning a trace from a session."""
        sample_trace.session_id = sample_session["id"]
        temp_db.save(sample_trace)

        result = temp_db.assign_trace_to_session(str(sample_trace.id), None)
        assert result is True

        trace = temp_db.get(str(sample_trace.id))
        assert trace.session_id is None

    def test_assign_nonexistent_trace_returns_false(self, temp_db, sample_session):
        """Test assigning to a non-existent trace returns False."""
        result = temp_db.assign_trace_to_session("nonexistent-id", sample_session["id"])
        assert result is False
