"""
Storage backends for TraceCraft.

Provides pluggable storage for trace persistence:
- JSONL: Simple append-only file storage
- SQLite: Queryable local database storage
- MLflow: Integration with MLflow tracking server
"""

from tracecraft.storage.base import BaseTraceStore, TraceQuery
from tracecraft.storage.jsonl import JSONLTraceStore
from tracecraft.storage.sqlite import SQLiteTraceStore

__all__ = [
    "BaseTraceStore",
    "TraceQuery",
    "JSONLTraceStore",
    "SQLiteTraceStore",
]


def get_mlflow_store(
    tracking_uri: str | None = None,
    experiment_name: str | None = None,
) -> BaseTraceStore:
    """
    Get MLflow trace store (lazy import to avoid dependency).

    Args:
        tracking_uri: MLflow tracking server URI.
        experiment_name: Experiment name.

    Returns:
        MLflowTraceStore instance.

    Raises:
        ImportError: If mlflow is not installed.
    """
    from tracecraft.storage.mlflow import MLflowTraceStore

    return MLflowTraceStore(
        tracking_uri=tracking_uri,
        experiment_name=experiment_name,
    )
