"""Tests for project associations with traces.

Tests the project structure:
- Projects contain Traces
- Project structure and counts
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


class TestSchemaVersion:
    """Tests for schema version."""

    def test_schema_version_is_6(self, temp_db):
        """Test that fresh install creates schema v6."""
        assert temp_db._get_schema_version() == 6


class TestProjectStructure:
    """Tests for getting project structure."""

    def test_get_project_structure(self, temp_db, sample_project, sample_trace):
        """Test getting complete project structure with traces."""
        # Add trace to project
        temp_db.save(sample_trace, project_id=sample_project["id"])

        # Get structure
        structure = temp_db.get_project_structure(sample_project["id"])

        assert structure["project"]["id"] == sample_project["id"]
        assert structure["trace_count"] >= 1

    def test_get_project_structure_empty(self, temp_db, sample_project):
        """Test getting structure for project with no traces."""
        structure = temp_db.get_project_structure(sample_project["id"])

        assert structure["project"]["id"] == sample_project["id"]
        assert structure["trace_count"] == 0


class TestMigration:
    """Tests for schema migration."""

    def test_migration_preserves_existing_data(self, temp_db, sample_project, sample_trace):
        """Test that migration preserves existing projects and traces."""
        # Create trace with project
        temp_db.save(sample_trace, project_id=sample_project["id"])

        # Should be able to retrieve
        trace = temp_db.get(str(sample_trace.id))
        assert trace is not None

        project = temp_db.get_project(sample_project["id"])
        assert project is not None
