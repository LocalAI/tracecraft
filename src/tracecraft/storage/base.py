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
    def save(self, run: AgentRun) -> None:
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

    def close(self) -> None:
        """Close any open connections."""
        pass

    def __enter__(self) -> BaseTraceStore:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
