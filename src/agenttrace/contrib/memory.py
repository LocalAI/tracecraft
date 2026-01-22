"""
Memory and state tracking utilities.

Provides context managers and helpers for tracking memory operations
like vector store interactions, conversation history, caching, etc.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from agenttrace.core.context import get_current_run
from agenttrace.core.models import Step, StepType

if TYPE_CHECKING:
    pass


@contextmanager
def memory_step(
    name: str,
    inputs: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Generator[Step, None, None]:
    """
    Context manager for tracking memory operations.

    Creates a MEMORY step and tracks its inputs, outputs, and duration.

    Usage:
        ```python
        from agenttrace.contrib.memory import memory_step

        with run_context(run):
            with memory_step("store_embeddings") as step:
                step.inputs = {"documents": docs}
                result = vector_store.add(docs)
                step.outputs = {"ids": result}
        ```

    Args:
        name: Name of the memory operation.
        inputs: Optional initial inputs dict.
        metadata: Optional metadata dict (stored in step.attributes).

    Yields:
        The Step object being tracked.
    """
    from uuid import uuid4 as make_uuid

    run = get_current_run()
    if run is None:
        # Create a dummy step that won't be tracked (needs a trace_id)
        step = Step(
            trace_id=make_uuid(),
            type=StepType.MEMORY,
            name=name,
            start_time=datetime.now(UTC),
            inputs=inputs or {},
            attributes=metadata or {},
        )
        yield step
        return

    step = Step(
        trace_id=run.id,
        type=StepType.MEMORY,
        name=name,
        start_time=datetime.now(UTC),
        inputs=inputs or {},
        attributes=metadata or {},
    )

    # Find parent step if any (for nesting)
    parent_step = None
    if run.steps:
        # Look for an in-progress step to be the parent
        # (simplified: use last step that doesn't have end_time)
        for s in reversed(run.steps):
            if s.end_time is None:
                parent_step = s
                break
            # Also check children recursively
            for child in s.children:
                if child.end_time is None:
                    parent_step = child
                    break

    if parent_step:
        step.parent_id = parent_step.id
        parent_step.children.append(step)
    else:
        run.steps.append(step)

    try:
        yield step
    except BaseException as e:
        step.error = str(e)
        step.error_type = type(e).__name__
        raise
    finally:
        step.end_time = datetime.now(UTC)
        step.duration_ms = (step.end_time - step.start_time).total_seconds() * 1000


@contextmanager
def track_vector_store(
    operation: str,
    store_name: str,
    document_count: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> Generator[Step, None, None]:
    """
    Track a vector store operation.

    Args:
        operation: The operation type (e.g., "upsert", "query", "delete").
        store_name: Name of the vector store.
        document_count: Number of documents involved.
        metadata: Additional metadata.

    Yields:
        The Step object being tracked.
    """
    inputs: dict[str, Any] = {
        "store_name": store_name,
        "operation": operation,
    }
    if document_count is not None:
        inputs["document_count"] = document_count

    with memory_step(
        name=f"vector_store:{operation}",
        inputs=inputs,
        metadata=metadata,
    ) as step:
        yield step


@contextmanager
def track_conversation_history(
    operation: str,
    message_count: int | None = None,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Generator[Step, None, None]:
    """
    Track a conversation history operation.

    Args:
        operation: The operation type (e.g., "append", "clear", "load").
        message_count: Number of messages involved.
        session_id: Optional session identifier.
        metadata: Additional metadata.

    Yields:
        The Step object being tracked.
    """
    inputs: dict[str, Any] = {"operation": operation}
    if message_count is not None:
        inputs["message_count"] = message_count
    if session_id is not None:
        inputs["session_id"] = session_id

    with memory_step(
        name=f"conversation_history:{operation}",
        inputs=inputs,
        metadata=metadata,
    ) as step:
        yield step


@contextmanager
def track_cache(
    operation: str,
    cache_key: str,
    hit: bool | None = None,
    ttl_seconds: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> Generator[Step, None, None]:
    """
    Track a cache operation.

    Args:
        operation: The operation type (e.g., "get", "set", "delete").
        cache_key: The cache key.
        hit: Whether the cache was hit (for get operations).
        ttl_seconds: TTL for set operations.
        metadata: Additional metadata.

    Yields:
        The Step object being tracked.
    """
    inputs: dict[str, Any] = {
        "cache_key": cache_key,
        "operation": operation,
    }
    if ttl_seconds is not None:
        inputs["ttl_seconds"] = ttl_seconds

    with memory_step(
        name=f"cache:{operation}",
        inputs=inputs,
        metadata=metadata,
    ) as step:
        # Set hit status in outputs
        if hit is not None:
            step.outputs = {"hit": hit}
        yield step
