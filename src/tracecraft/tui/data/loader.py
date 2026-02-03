"""
Multi-source trace loader for TUI.

Supports loading traces from:
- JSONL files
- SQLite databases
- MLflow tracking servers
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from tracecraft.storage.base import BaseTraceStore, TraceQuery

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun

logger = logging.getLogger(__name__)


class TraceLoader:
    """
    Unified trace loader supporting multiple sources.

    Provides a consistent interface for loading traces from various backends,
    making it easy to switch between local files and remote services.

    Examples:
        # Auto-detect from file extension
        loader = TraceLoader.from_source("traces.jsonl")
        loader = TraceLoader.from_source("traces.db")

        # Explicit source type
        loader = TraceLoader.from_source("sqlite:///traces.db")
        loader = TraceLoader.from_source("mlflow://localhost:5000/my_experiment")

        # Load traces
        traces = loader.list_traces(limit=50)
        errors = loader.query_traces(TraceQuery(has_error=True))
    """

    def __init__(self, store: BaseTraceStore) -> None:
        """
        Initialize loader with a storage backend.

        Args:
            store: Storage backend to use for loading traces.
        """
        self.store = store
        self._source_str: str = ""

    @classmethod
    def from_source(cls, source: str) -> TraceLoader:
        """
        Create loader from source string.

        Supported formats:
        - file.jsonl - JSONL file
        - file.db or sqlite:///path - SQLite database
        - mlflow://host:port/experiment - MLflow server
        - mlflow:experiment_name - MLflow with default server

        Args:
            source: Source string specifying where to load traces from.

        Returns:
            TraceLoader instance configured for the source.

        Raises:
            ValueError: If source format is not recognized.
            ImportError: If required backend is not installed.
        """
        loader: TraceLoader

        # Parse source string
        if source.startswith("sqlite://"):
            path = source.replace("sqlite://", "")
            from tracecraft.storage.sqlite import SQLiteTraceStore

            loader = cls(SQLiteTraceStore(path))
            loader._source_str = source
            return loader

        elif source.startswith("mlflow://"):
            # Format: mlflow://host:port/experiment or mlflow://host:port
            parsed = urlparse(source)
            tracking_uri = f"http://{parsed.netloc}"
            experiment_name = parsed.path.lstrip("/") or None

            from tracecraft.storage.mlflow import MLflowTraceStore

            loader = cls(
                MLflowTraceStore(
                    tracking_uri=tracking_uri,
                    experiment_name=experiment_name,
                )
            )
            loader._source_str = source
            return loader

        elif source.startswith("mlflow:"):
            # Format: mlflow:experiment_name (uses default tracking URI)
            experiment_name = source.replace("mlflow:", "")

            from tracecraft.storage.mlflow import MLflowTraceStore

            loader = cls(MLflowTraceStore(experiment_name=experiment_name))
            loader._source_str = source
            return loader

        else:
            # Auto-detect from extension
            path = Path(source)

            if path.suffix in (".db", ".sqlite", ".sqlite3"):
                from tracecraft.storage.sqlite import SQLiteTraceStore

                loader = cls(SQLiteTraceStore(path))
                loader._source_str = source
                return loader

            elif path.suffix in (".jsonl", ".json", ".ndjson"):
                from tracecraft.storage.jsonl import JSONLTraceStore

                loader = cls(JSONLTraceStore(path))
                loader._source_str = source
                return loader

            elif path.is_dir():
                # Directory - look for JSONL file
                jsonl_path = path / "tracecraft.jsonl"
                if jsonl_path.exists():
                    from tracecraft.storage.jsonl import JSONLTraceStore

                    loader = cls(JSONLTraceStore(jsonl_path))
                    loader._source_str = str(jsonl_path)
                    return loader
                # Try default traces directory
                traces_path = path / "traces" / "tracecraft.jsonl"
                if traces_path.exists():
                    from tracecraft.storage.jsonl import JSONLTraceStore

                    loader = cls(JSONLTraceStore(traces_path))
                    loader._source_str = str(traces_path)
                    return loader
                raise ValueError(f"No trace files found in directory: {source}")

            else:
                # Default to JSONL for unknown extensions
                from tracecraft.storage.jsonl import JSONLTraceStore

                loader = cls(JSONLTraceStore(path))
                loader._source_str = source
                return loader

    @property
    def source(self) -> str:
        """Get the source string."""
        return self._source_str

    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite backend."""
        from tracecraft.storage.sqlite import SQLiteTraceStore

        return isinstance(self.store, SQLiteTraceStore)

    def list_traces(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AgentRun]:
        """
        List traces with pagination.

        Args:
            limit: Maximum number of traces to return.
            offset: Number of traces to skip.

        Returns:
            List of AgentRun objects.
        """
        return self.store.list_all(limit=limit, offset=offset)

    def query_traces(self, query: TraceQuery) -> list[AgentRun]:
        """
        Query traces with filters.

        Args:
            query: TraceQuery with filter criteria.

        Returns:
            List of matching AgentRun objects.
        """
        return self.store.query(query)

    def get_trace(self, trace_id: str) -> AgentRun | None:
        """
        Get single trace by ID.

        Args:
            trace_id: UUID of the trace.

        Returns:
            AgentRun if found, None otherwise.
        """
        return self.store.get(trace_id)

    def count(self, query: TraceQuery | None = None) -> int:
        """
        Count total traces.

        Args:
            query: Optional query to filter count.

        Returns:
            Number of traces.
        """
        return self.store.count(query)

    def refresh(self) -> None:
        """Refresh data (invalidate caches)."""
        if hasattr(self.store, "invalidate_cache"):
            self.store.invalidate_cache()

    def get_stats(self) -> dict[str, Any]:
        """
        Get storage statistics.

        Returns:
            Dictionary with statistics about the storage.
        """
        if hasattr(self.store, "get_stats"):
            return self.store.get_stats()
        # Fallback
        count = self.count()
        return {"trace_count": count}

    def close(self) -> None:
        """Close connections."""
        self.store.close()

    def __enter__(self) -> TraceLoader:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


def get_loader_for_env(env: str | None = None) -> TraceLoader:
    """
    Get a TraceLoader configured from environment settings.

    Args:
        env: Environment name (development, staging, production, test).
             If None, uses TRACECRAFT_ENV environment variable.

    Returns:
        TraceLoader configured according to environment settings.
    """
    from tracecraft.core.env_config import load_config

    config = load_config(env=env)
    settings = config.get_settings()

    if settings.storage.type == "sqlite" and settings.storage.sqlite_path:
        source = f"sqlite://{settings.storage.sqlite_path}"
    elif settings.storage.type == "mlflow":
        if settings.storage.mlflow_tracking_uri:
            # Parse tracking URI to extract host
            parsed = urlparse(settings.storage.mlflow_tracking_uri)
            host = parsed.netloc or parsed.path
            exp = settings.storage.mlflow_experiment_name or "tracecraft"
            source = f"mlflow://{host}/{exp}"
        else:
            exp = settings.storage.mlflow_experiment_name or "tracecraft"
            source = f"mlflow:{exp}"
    elif settings.storage.type == "jsonl" and settings.storage.jsonl_path:
        source = settings.storage.jsonl_path
    else:
        # Default to standard JSONL path
        source = "traces/tracecraft.jsonl"

    return TraceLoader.from_source(source)
