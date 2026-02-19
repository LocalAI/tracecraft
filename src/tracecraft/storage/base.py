"""
Base protocol for trace storage backends.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun


class TraceQuery:
    """Query parameters for filtering traces."""

    def __init__(
        self,
        *,
        name: str | None = None,
        name_contains: str | None = None,
        has_error: bool | None = None,
        min_duration_ms: float | None = None,
        max_duration_ms: float | None = None,
        min_cost_usd: float | None = None,
        max_cost_usd: float | None = None,
        tags: list[str] | None = None,
        start_time_after: str | None = None,  # ISO format
        start_time_before: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        environment: str | None = None,
        project_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "start_time",
        order_desc: bool = True,
    ) -> None:
        self.name = name
        self.name_contains = name_contains
        self.has_error = has_error
        self.min_duration_ms = min_duration_ms
        self.max_duration_ms = max_duration_ms
        self.min_cost_usd = min_cost_usd
        self.max_cost_usd = max_cost_usd
        self.tags = tags
        self.start_time_after = start_time_after
        self.start_time_before = start_time_before
        self.session_id = session_id
        self.user_id = user_id
        self.environment = environment
        self.project_id = project_id
        self.limit = limit
        self.offset = offset
        self.order_by = order_by
        self.order_desc = order_desc

    def to_dict(self) -> dict[str, Any]:
        """Convert query to dictionary (excluding None values)."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


class BaseTraceStore(ABC):
    """
    Abstract base class for trace storage backends.

    Implementations must support:
    - Writing traces (save)
    - Reading single traces (get)
    - Querying traces (query)
    - Listing all traces (list_all)

    Example implementation:
        class MyTraceStore(BaseTraceStore):
            def save(self, run: AgentRun) -> None:
                # Save to backend
                pass

            def get(self, trace_id: str) -> AgentRun | None:
                # Retrieve by ID
                pass

            def query(self, query: TraceQuery) -> list[AgentRun]:
                # Filter and return matching traces
                pass

            def list_all(self, limit: int = 100, offset: int = 0) -> list[AgentRun]:
                # Return all traces with pagination
                pass

            def delete(self, trace_id: str) -> bool:
                # Delete and return success
                pass

            def count(self, query: TraceQuery | None = None) -> int:
                # Return count
                pass
    """

    @abstractmethod
    def save(self, run: AgentRun, project_id: str | None = None) -> None:
        """Save a trace to storage."""
        pass

    @abstractmethod
    def get(self, trace_id: str) -> AgentRun | None:
        """Get a trace by ID."""
        pass

    @abstractmethod
    def query(self, query: TraceQuery) -> list[AgentRun]:
        """Query traces with filters."""
        pass

    @abstractmethod
    def list_all(self, limit: int = 100, offset: int = 0) -> list[AgentRun]:
        """List all traces with pagination."""
        pass

    @abstractmethod
    def delete(self, trace_id: str) -> bool:
        """Delete a trace by ID. Returns True if deleted."""
        pass

    @abstractmethod
    def count(self, query: TraceQuery | None = None) -> int:
        """Count traces matching query (or all if no query)."""
        pass

    def iter_all(self, batch_size: int = 100) -> Iterator[AgentRun]:
        """Iterate over all traces in batches."""
        offset = 0
        while True:
            batch = self.list_all(limit=batch_size, offset=offset)
            if not batch:
                break
            yield from batch
            offset += batch_size

    # =========================================================================
    # Notes Methods (optional - not all backends support notes)
    # =========================================================================

    def get_notes(self, trace_id: str) -> str | None:
        """
        Get notes for a trace.

        Returns:
            Notes text or None if not found or not set.

        Raises:
            NotImplementedError: If backend does not support notes.
        """
        raise NotImplementedError("Notes not supported by this backend")

    def set_notes(self, trace_id: str, notes: str) -> bool:
        """
        Set notes for a trace.

        Args:
            trace_id: The trace ID.
            notes: The notes text (can be empty string to clear).

        Returns:
            True if trace was updated, False if not found.

        Raises:
            NotImplementedError: If backend does not support notes.
        """
        raise NotImplementedError("Notes not supported by this backend")

    # =========================================================================
    # Archive Methods (optional - not all backends support archiving)
    # =========================================================================

    def archive(self, trace_id: str) -> bool:
        """
        Archive a trace.

        Returns:
            True if trace was archived, False if not found.

        Raises:
            NotImplementedError: If backend does not support archiving.
        """
        raise NotImplementedError("Archiving not supported by this backend")

    def unarchive(self, trace_id: str) -> bool:
        """
        Unarchive a trace.

        Returns:
            True if trace was unarchived, False if not found.

        Raises:
            NotImplementedError: If backend does not support archiving.
        """
        raise NotImplementedError("Archiving not supported by this backend")

    def is_archived(self, trace_id: str) -> bool:
        """
        Check if a trace is archived.

        Returns:
            True if archived, False otherwise.

        Raises:
            NotImplementedError: If backend does not support archiving.
        """
        raise NotImplementedError("Archiving not supported by this backend")

    # =========================================================================
    # Session Management Methods (optional - not all backends support sessions)
    # =========================================================================

    def create_session(
        self,
        name: str,
        project_id: str | None = None,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Create a new session.

        Args:
            name: Session name (unique within a project).
            project_id: Optional project to associate with.
            description: Optional session description.
            metadata: Optional JSON-serializable metadata dict.

        Returns:
            The new session ID.

        Raises:
            NotImplementedError: If backend does not support sessions.
        """
        raise NotImplementedError("Sessions not supported by this backend")

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """
        Get a session by ID.

        Returns:
            Session dict or None if not found.

        Raises:
            NotImplementedError: If backend does not support sessions.
        """
        raise NotImplementedError("Sessions not supported by this backend")

    def get_session_by_name(
        self,
        name: str,
        project_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Get a session by name within a project.

        Returns:
            Session dict or None if not found.

        Raises:
            NotImplementedError: If backend does not support sessions.
        """
        raise NotImplementedError("Sessions not supported by this backend")

    def list_sessions(self, project_id: str | None = None) -> list[dict[str, Any]]:
        """
        List sessions, optionally filtered by project.

        Args:
            project_id: If provided, only return sessions for this project.

        Returns:
            List of session dicts.

        Raises:
            NotImplementedError: If backend does not support sessions.
        """
        raise NotImplementedError("Sessions not supported by this backend")

    def update_session(
        self,
        session_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Update a session.

        Returns:
            True if session was updated, False if not found.

        Raises:
            NotImplementedError: If backend does not support sessions.
        """
        raise NotImplementedError("Sessions not supported by this backend")

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.

        Returns:
            True if deleted, False if not found.

        Raises:
            NotImplementedError: If backend does not support sessions.
        """
        raise NotImplementedError("Sessions not supported by this backend")

    def get_or_create_session(
        self,
        name: str,
        project_id: str | None = None,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> tuple[str, bool]:
        """
        Get an existing session by name or create a new one.

        Returns:
            Tuple of (session_id, created) where created is True if new.

        Raises:
            NotImplementedError: If backend does not support sessions.
        """
        raise NotImplementedError("Sessions not supported by this backend")

    def get_session_stats(self, session_id: str) -> dict[str, Any]:
        """
        Get statistics for a session.

        Returns:
            Dict with trace_count, total_tokens, total_cost_usd, etc.

        Raises:
            NotImplementedError: If backend does not support sessions.
        """
        raise NotImplementedError("Sessions not supported by this backend")

    def assign_trace_to_session(self, trace_id: str, session_id: str | None) -> bool:
        """
        Assign a trace to a session (or unassign if session_id is None).

        Args:
            trace_id: The trace ID to update.
            session_id: Session ID to assign, or None to unassign.

        Returns:
            True if trace was updated, False if trace not found.

        Raises:
            NotImplementedError: If backend does not support sessions.
        """
        raise NotImplementedError("Sessions not supported by this backend")

    # =========================================================================
    # Project Management Methods (optional - not all backends support projects)
    # =========================================================================

    def create_project(
        self,
        name: str,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Create a new project.

        Args:
            name: Unique project name.
            description: Optional project description.
            metadata: Optional JSON-serializable metadata dict.

        Returns:
            The new project ID.

        Raises:
            NotImplementedError: If backend does not support projects.
        """
        raise NotImplementedError("Projects not supported by this backend")

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        """
        Get a project by ID.

        Returns:
            Project dict or None if not found.

        Raises:
            NotImplementedError: If backend does not support projects.
        """
        raise NotImplementedError("Projects not supported by this backend")

    def get_project_by_name(self, name: str) -> dict[str, Any] | None:
        """
        Get a project by name.

        Returns:
            Project dict or None if not found.

        Raises:
            NotImplementedError: If backend does not support projects.
        """
        raise NotImplementedError("Projects not supported by this backend")

    def list_projects(self) -> list[dict[str, Any]]:
        """
        List all projects.

        Returns:
            List of project dicts.

        Raises:
            NotImplementedError: If backend does not support projects.
        """
        raise NotImplementedError("Projects not supported by this backend")

    def close(self) -> None:
        """Close any open connections."""
        pass

    def __enter__(self) -> BaseTraceStore:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
