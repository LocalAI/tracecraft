"""
Tests for async helper utilities.

TDD approach: Tests for asyncio context propagation helpers.
"""

from __future__ import annotations

import pytest

from agenttrace.core.context import get_current_run, run_context
from agenttrace.core.models import AgentRun


class TestGatherWithContext:
    """Tests for gather_with_context helper."""

    @pytest.mark.asyncio
    async def test_gather_propagates_context(self, sample_run) -> None:
        """gather_with_context should propagate run context to all tasks."""
        from agenttrace.contrib.async_helpers import gather_with_context

        results = []

        async def check_context(name: str) -> str:
            current = get_current_run()
            if current:
                results.append((name, current.name))
            return name

        with run_context(sample_run):
            await gather_with_context(
                check_context("task1"),
                check_context("task2"),
                check_context("task3"),
            )

        # All tasks should have seen the context
        assert len(results) == 3
        for _name, run_name in results:
            assert run_name == sample_run.name

    @pytest.mark.asyncio
    async def test_gather_returns_results(self, sample_run) -> None:
        """gather_with_context should return task results."""
        from agenttrace.contrib.async_helpers import gather_with_context

        async def compute(x: int) -> int:
            return x * 2

        with run_context(sample_run):
            results = await gather_with_context(
                compute(1),
                compute(2),
                compute(3),
            )

        assert results == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_gather_handles_exceptions(self, sample_run) -> None:
        """gather_with_context should propagate exceptions."""
        from agenttrace.contrib.async_helpers import gather_with_context

        async def fail() -> None:
            raise ValueError("Test error")

        with run_context(sample_run), pytest.raises(ValueError, match="Test error"):
            await gather_with_context(fail())

    @pytest.mark.asyncio
    async def test_gather_return_exceptions(self, sample_run) -> None:
        """gather_with_context should support return_exceptions."""
        from agenttrace.contrib.async_helpers import gather_with_context

        async def succeed() -> str:
            return "ok"

        async def fail() -> None:
            raise ValueError("error")

        with run_context(sample_run):
            results = await gather_with_context(
                succeed(),
                fail(),
                return_exceptions=True,
            )

        assert results[0] == "ok"
        assert isinstance(results[1], ValueError)


class TestTaskWithContext:
    """Tests for create_task_with_context helper."""

    @pytest.mark.asyncio
    async def test_task_propagates_context(self, sample_run) -> None:
        """create_task_with_context should propagate run context."""
        from agenttrace.contrib.async_helpers import create_task_with_context

        result = []

        async def check_context() -> None:
            current = get_current_run()
            if current:
                result.append(current.name)

        with run_context(sample_run):
            task = create_task_with_context(check_context())
            await task

        assert result == [sample_run.name]

    @pytest.mark.asyncio
    async def test_task_with_name(self, sample_run) -> None:
        """create_task_with_context should support task names."""
        from agenttrace.contrib.async_helpers import create_task_with_context

        async def dummy() -> None:
            pass

        with run_context(sample_run):
            task = create_task_with_context(dummy(), name="my_task")

        assert task.get_name() == "my_task"
        await task


class TestRunInExecutorWithContext:
    """Tests for run_in_executor_with_context helper."""

    @pytest.mark.asyncio
    async def test_executor_propagates_context(self, sample_run) -> None:
        """run_in_executor_with_context should propagate context to thread."""
        from agenttrace.contrib.async_helpers import run_in_executor_with_context

        result = []

        def check_context() -> str:
            current = get_current_run()
            if current:
                result.append(current.name)
            return "done"

        with run_context(sample_run):
            value = await run_in_executor_with_context(check_context)

        assert value == "done"
        assert result == [sample_run.name]

    @pytest.mark.asyncio
    async def test_executor_returns_result(self, sample_run) -> None:
        """run_in_executor_with_context should return function result."""
        from agenttrace.contrib.async_helpers import run_in_executor_with_context

        def compute() -> int:
            return 42

        with run_context(sample_run):
            result = await run_in_executor_with_context(compute)

        assert result == 42


class TestAsyncContextCopy:
    """Tests for copying context in async operations."""

    @pytest.mark.asyncio
    async def test_nested_context_isolation(self, sample_run) -> None:
        """Nested async tasks should maintain context isolation."""
        from datetime import UTC, datetime

        from agenttrace.contrib.async_helpers import gather_with_context

        results = []

        async def inner_task(name: str) -> None:
            current = get_current_run()
            results.append((name, current.name if current else None))

        async def outer_task(name: str) -> None:
            # Create a nested run
            nested_run = AgentRun(
                name=f"nested_{name}",
                start_time=datetime.now(UTC),
            )
            with run_context(nested_run):
                await inner_task(f"inner_{name}")

        with run_context(sample_run):
            await gather_with_context(
                outer_task("a"),
                outer_task("b"),
            )

        # Inner tasks should see nested run names
        assert len(results) == 2
        for inner_name, run_name in results:
            expected_outer = inner_name.replace("inner_", "")
            assert run_name == f"nested_{expected_outer}"


# Fixtures
@pytest.fixture
def sample_run() -> AgentRun:
    """Create a sample run for testing."""
    from datetime import UTC, datetime

    return AgentRun(
        name="test_run",
        start_time=datetime.now(UTC),
    )
