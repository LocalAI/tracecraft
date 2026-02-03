"""Contributed utilities and helpers."""

from tracecraft.contrib.async_helpers import (
    create_task_with_context,
    gather_with_context,
    run_in_executor_with_context,
)
from tracecraft.contrib.memory import (
    memory_step,
    track_cache,
    track_conversation_history,
    track_vector_store,
)

# Cloud provider helpers - lazy imports to avoid requiring cloud SDKs
# Use: from tracecraft.contrib.aws import create_xray_exporter
# Use: from tracecraft.contrib.azure import create_appinsights_exporter
# Use: from tracecraft.contrib.gcp import create_cloudtrace_exporter

# Evaluation helpers - lazy import to avoid requiring mlflow
# Use: from tracecraft.contrib.evaluation import evaluation_step

__all__ = [
    # Async helpers
    "gather_with_context",
    "create_task_with_context",
    "run_in_executor_with_context",
    # Memory tracking
    "memory_step",
    "track_vector_store",
    "track_conversation_history",
    "track_cache",
]
