"""
JSONL storage backend for TraceCraft.

Simple append-only storage with file watching support.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from tracecraft.storage.base import BaseTraceStore, TraceQuery

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun

logger = logging.getLogger(__name__)


class JSONLTraceStore(BaseTraceStore):
    """
    JSONL-based trace storage.

    Simple, human-readable, and easy to version control.
    Best for small to medium trace volumes.

    Features:
    - Append-only writes (fast)
    - In-memory cache for reads
    - Cache invalidation for watch mode
    - No external dependencies

    Example:
        from tracecraft.storage.jsonl import JSONLTraceStore

        store = JSONLTraceStore("traces/tracecraft.jsonl")

        # Save a trace
        store.save(run)

        # Query traces
        errors = store.query(TraceQuery(has_error=True))

        # Invalidate cache for watch mode
        store.invalidate_cache()
    """

    def __init__(self, path: str | Path) -> None:
        """
        Initialize JSONL storage.

        Args:
            path: Path to JSONL file.
        """
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, AgentRun] | None = None
        self._file_mtime: float | None = None

    def _load_all(self) -> dict[str, AgentRun]:
        """Load all traces from file (cached)."""
        # Check if file has been modified
        if self.path.exists():
            current_mtime = self.path.stat().st_mtime
            if self._cache is not None and self._file_mtime == current_mtime:
                return self._cache

        from tracecraft.core.models import AgentRun

        self._cache = {}
        if not self.path.exists():
            return self._cache

        self._file_mtime = self.path.stat().st_mtime

        with open(self.path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    run = AgentRun.model_validate_json(line)
                    self._cache[str(run.id)] = run
                except Exception as e:
                    logger.warning(f"Failed to parse trace on line {line_num}: {e}")
                    continue

        return self._cache

    def invalidate_cache(self) -> None:
        """Invalidate the cache (for watch mode)."""
        self._cache = None
        self._file_mtime = None

    def save(self, run: AgentRun, project_id: str | None = None) -> None:  # noqa: ARG002
        """Append trace to JSONL file."""
        # Note: project_id is ignored for JSONL storage
        self.invalidate_cache()

        with open(self.path, "a", encoding="utf-8") as f:
            f.write(run.model_dump_json() + "\n")

    def get(self, trace_id: str) -> AgentRun | None:
        """Get trace by ID."""
        return self._load_all().get(trace_id)

    def query(self, query: TraceQuery) -> list[AgentRun]:
        """Query traces with filters."""
        traces = list(self._load_all().values())

        # Apply filters
        if query.name:
            traces = [t for t in traces if t.name == query.name]

        if query.name_contains:
            traces = [t for t in traces if query.name_contains in t.name]

        if query.has_error is not None:
            if query.has_error:
                traces = [t for t in traces if t.error_count > 0]
            else:
                traces = [t for t in traces if t.error_count == 0]

        if query.min_duration_ms is not None:
            traces = [t for t in traces if (t.duration_ms or 0) >= query.min_duration_ms]

        if query.max_duration_ms is not None:
            traces = [t for t in traces if (t.duration_ms or 0) <= query.max_duration_ms]

        if query.min_cost_usd is not None:
            traces = [t for t in traces if (t.total_cost_usd or 0) >= query.min_cost_usd]

        if query.max_cost_usd is not None:
            traces = [t for t in traces if (t.total_cost_usd or 0) <= query.max_cost_usd]

        if query.tags:
            traces = [t for t in traces if all(tag in t.tags for tag in query.tags)]

        if query.session_id:
            traces = [t for t in traces if t.session_id == query.session_id]

        if query.user_id:
            traces = [t for t in traces if t.user_id == query.user_id]

        if query.environment:
            traces = [t for t in traces if t.environment == query.environment]

        if query.start_time_after:
            after = datetime.fromisoformat(query.start_time_after)
            traces = [t for t in traces if t.start_time >= after]

        if query.start_time_before:
            before = datetime.fromisoformat(query.start_time_before)
            traces = [t for t in traces if t.start_time <= before]

        # Sort
        reverse = query.order_desc
        if query.order_by == "start_time":
            traces.sort(key=lambda t: t.start_time, reverse=reverse)
        elif query.order_by == "duration_ms":
            traces.sort(key=lambda t: t.duration_ms or 0, reverse=reverse)
        elif query.order_by == "total_cost_usd":
            traces.sort(key=lambda t: t.total_cost_usd or 0, reverse=reverse)
        elif query.order_by == "name":
            traces.sort(key=lambda t: t.name, reverse=reverse)

        # Pagination
        return traces[query.offset : query.offset + query.limit]

    def list_all(self, limit: int = 100, offset: int = 0) -> list[AgentRun]:
        """List all traces."""
        return self.query(TraceQuery(limit=limit, offset=offset))

    def delete(self, trace_id: str) -> bool:
        """
        Delete not supported for JSONL (would require file rewrite).

        For JSONL, consider using SQLite if you need deletion.
        """
        raise NotImplementedError(
            "JSONL storage does not support deletion. "
            "Use SQLite storage if you need deletion support."
        )

    def count(self, query: TraceQuery | None = None) -> int:
        """Count traces."""
        if query is None:
            return len(self._load_all())
        # For query with filters, we have to fetch all matching
        return len(
            self.query(
                TraceQuery(
                    name=query.name,
                    name_contains=query.name_contains,
                    has_error=query.has_error,
                    min_duration_ms=query.min_duration_ms,
                    max_duration_ms=query.max_duration_ms,
                    min_cost_usd=query.min_cost_usd,
                    max_cost_usd=query.max_cost_usd,
                    tags=query.tags,
                    session_id=query.session_id,
                    user_id=query.user_id,
                    environment=query.environment,
                    start_time_after=query.start_time_after,
                    start_time_before=query.start_time_before,
                    limit=999999,  # Get all for count
                )
            )
        )

    def get_file_size(self) -> int:
        """Get file size in bytes."""
        if self.path.exists():
            return self.path.stat().st_size
        return 0

    def get_stats(self) -> dict[str, object]:
        """Get storage statistics."""
        traces = self._load_all()
        total_tokens = sum(t.total_tokens for t in traces.values())
        total_cost = sum(t.total_cost_usd for t in traces.values())
        file_size = self.get_file_size()

        return {
            "trace_count": len(traces),
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost,
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2),
        }
