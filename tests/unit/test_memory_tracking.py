"""
Tests for memory and state tracking.

TDD approach: Tests for tracking memory operations like vector store
reads/writes, conversation history, etc.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agenttrace.core.context import run_context
from agenttrace.core.models import AgentRun, StepType


class TestMemoryStep:
    """Tests for memory step creation."""

    def test_create_memory_step(self) -> None:
        """Should be able to create a MEMORY step."""
        from agenttrace.contrib.memory import memory_step

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run), memory_step("store_embeddings") as step:
            step.inputs = {"documents": ["doc1", "doc2"]}

        assert len(run.steps) == 1
        assert run.steps[0].type == StepType.MEMORY
        assert run.steps[0].name == "store_embeddings"

    def test_memory_step_captures_inputs(self) -> None:
        """Memory step should capture inputs."""
        from agenttrace.contrib.memory import memory_step

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run), memory_step("retrieve", inputs={"query": "test"}):
            pass

        assert run.steps[0].inputs == {"query": "test"}

    def test_memory_step_captures_outputs(self) -> None:
        """Memory step should capture outputs."""
        from agenttrace.contrib.memory import memory_step

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run), memory_step("retrieve") as step:
            step.outputs = {"results": ["match1", "match2"]}

        assert run.steps[0].outputs == {"results": ["match1", "match2"]}

    def test_memory_step_captures_duration(self) -> None:
        """Memory step should capture duration."""
        from agenttrace.contrib.memory import memory_step

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run), memory_step("operation"):
            pass

        assert run.steps[0].end_time is not None
        assert run.steps[0].duration_ms is not None
        assert run.steps[0].duration_ms >= 0

    def test_memory_step_captures_error(self) -> None:
        """Memory step should capture errors."""
        from agenttrace.contrib.memory import memory_step

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run), pytest.raises(ValueError), memory_step("failing_operation"):
            raise ValueError("Store failed")

        assert run.steps[0].error == "Store failed"
        assert run.steps[0].error_type == "ValueError"

    def test_memory_step_with_metadata(self) -> None:
        """Memory step should support metadata (stored as attributes)."""
        from agenttrace.contrib.memory import memory_step

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with (
            run_context(run),
            memory_step(
                "vector_store",
                metadata={"store_type": "pinecone", "namespace": "docs"},
            ),
        ):
            pass

        assert run.steps[0].attributes == {"store_type": "pinecone", "namespace": "docs"}


class TestMemoryOperations:
    """Tests for common memory operation helpers."""

    def test_track_vector_store(self) -> None:
        """Should track vector store operations."""
        from agenttrace.contrib.memory import track_vector_store

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with (
            run_context(run),
            track_vector_store(
                operation="upsert",
                store_name="my_store",
                document_count=5,
            ),
        ):
            pass

        assert run.steps[0].type == StepType.MEMORY
        assert run.steps[0].name == "vector_store:upsert"
        assert run.steps[0].inputs["store_name"] == "my_store"
        assert run.steps[0].inputs["document_count"] == 5

    def test_track_conversation_history(self) -> None:
        """Should track conversation history operations."""
        from agenttrace.contrib.memory import track_conversation_history

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with (
            run_context(run),
            track_conversation_history(
                operation="append",
                message_count=2,
            ),
        ):
            pass

        assert run.steps[0].type == StepType.MEMORY
        assert run.steps[0].name == "conversation_history:append"
        assert run.steps[0].inputs["message_count"] == 2

    def test_track_cache_operation(self) -> None:
        """Should track cache operations."""
        from agenttrace.contrib.memory import track_cache

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with (
            run_context(run),
            track_cache(
                operation="get",
                cache_key="user:123",
                hit=True,
            ),
        ):
            pass

        assert run.steps[0].type == StepType.MEMORY
        assert run.steps[0].name == "cache:get"
        assert run.steps[0].inputs["cache_key"] == "user:123"
        assert run.steps[0].outputs["hit"] is True


class TestNestedMemorySteps:
    """Tests for nested memory operations."""

    def test_nested_memory_steps(self) -> None:
        """Memory steps can be nested."""
        from agenttrace.contrib.memory import memory_step

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run), memory_step("outer"), memory_step("inner"):
            pass

        # Both steps should be created
        assert len(run.steps) == 1  # Outer is at root
        assert len(run.steps[0].children) == 1  # Inner is child
        assert run.steps[0].name == "outer"
        assert run.steps[0].children[0].name == "inner"
