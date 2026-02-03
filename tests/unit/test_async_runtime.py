"""
Tests for async runtime features.

TDD approach: Tests for async context manager and async patterns.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest


class TestAsyncContextManager:
    """Tests for the async run context manager."""

    @pytest.mark.asyncio
    async def test_async_run_context_manager_basic(self) -> None:
        """Async context manager should create and manage a run."""
        from tracecraft.core.runtime import TALRuntime

        runtime = TALRuntime(console=False, jsonl=False)

        async with runtime.run_async("test_async_run") as run:
            assert run is not None
            assert run.name == "test_async_run"
            assert run.start_time is not None

    @pytest.mark.asyncio
    async def test_async_run_sets_end_time(self) -> None:
        """Async context manager should set end_time on exit."""
        from tracecraft.core.runtime import TALRuntime

        runtime = TALRuntime(console=False, jsonl=False)

        async with runtime.run_async("test_run") as run:
            pass

        assert run.end_time is not None
        assert run.duration_ms is not None
        assert run.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_async_run_exports_on_exit(self) -> None:
        """Async context manager should export run on exit."""
        from tracecraft.core.runtime import TALRuntime

        mock_exporter = MagicMock()
        runtime = TALRuntime(console=False, jsonl=False, exporters=[mock_exporter])

        async with runtime.run_async("test_run") as _run:
            pass

        mock_exporter.export.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_run_captures_exception(self) -> None:
        """Async context manager should capture exception info."""
        from tracecraft.core.runtime import TALRuntime

        runtime = TALRuntime(console=False, jsonl=False)

        with pytest.raises(ValueError):
            async with runtime.run_async("test_run") as run:
                raise ValueError("Test error")

        assert run.error == "Test error"
        assert run.error_type == "ValueError"

    @pytest.mark.asyncio
    async def test_async_run_exports_even_on_exception(self) -> None:
        """Async context manager should export even when exception occurs."""
        from tracecraft.core.runtime import TALRuntime

        mock_exporter = MagicMock()
        runtime = TALRuntime(console=False, jsonl=False, exporters=[mock_exporter])

        with pytest.raises(ValueError):
            async with runtime.run_async("test_run") as _run:
                raise ValueError("Test error")

        mock_exporter.export.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_run_sets_context(self) -> None:
        """Async context manager should set current run context."""
        from tracecraft.core.context import get_current_run
        from tracecraft.core.runtime import TALRuntime

        runtime = TALRuntime(console=False, jsonl=False)

        async with runtime.run_async("test_run") as run:
            current = get_current_run()
            assert current is run

    @pytest.mark.asyncio
    async def test_async_run_clears_context_on_exit(self) -> None:
        """Async context manager should clear context on exit."""
        from tracecraft.core.context import get_current_run
        from tracecraft.core.runtime import TALRuntime

        runtime = TALRuntime(console=False, jsonl=False)

        async with runtime.run_async("test_run"):
            pass

        # Context should be cleared after exit
        current = get_current_run()
        assert current is None

    @pytest.mark.asyncio
    async def test_async_run_with_metadata(self) -> None:
        """Async context manager should accept run metadata."""
        from tracecraft.core.runtime import TALRuntime

        runtime = TALRuntime(console=False, jsonl=False)

        async with runtime.run_async(
            "test_run",
            description="Test description",
            session_id="session-123",
            user_id="user-456",
            tags=["test", "async"],
            input={"query": "hello"},
        ) as run:
            assert run.description == "Test description"
            assert run.session_id == "session-123"
            assert run.user_id == "user-456"
            assert run.tags == ["test", "async"]
            assert run.input == {"query": "hello"}


class TestAsyncContextPropagation:
    """Tests for context propagation in async code."""

    @pytest.mark.asyncio
    async def test_context_propagates_through_await(self) -> None:
        """Context should propagate through await calls."""
        from tracecraft.core.context import get_current_run
        from tracecraft.core.runtime import TALRuntime

        runtime = TALRuntime(console=False, jsonl=False)

        async def inner_func():
            return get_current_run()

        async with runtime.run_async("test_run") as run:
            inner_run = await inner_func()
            assert inner_run is run

    @pytest.mark.asyncio
    async def test_concurrent_runs_isolated(self) -> None:
        """Concurrent async runs should have isolated contexts."""
        from tracecraft.core.context import get_current_run
        from tracecraft.core.runtime import TALRuntime

        runtime = TALRuntime(console=False, jsonl=False)
        results = []

        async def run_with_name(name: str):
            async with runtime.run_async(name) as _run:
                await asyncio.sleep(0.01)  # Small delay
                current = get_current_run()
                results.append((name, current.name if current else None))

        await asyncio.gather(
            run_with_name("run_1"),
            run_with_name("run_2"),
            run_with_name("run_3"),
        )

        # Each run should have seen its own context
        for name, current_name in results:
            assert name == current_name


class TestAsyncRunWithDecorators:
    """Tests for async runs with decorators."""

    @pytest.mark.asyncio
    async def test_async_run_with_async_decorator(self) -> None:
        """Async decorated functions should work within async run."""
        from tracecraft.core.runtime import TALRuntime
        from tracecraft.instrumentation.decorators import trace_agent

        runtime = TALRuntime(console=False, jsonl=False)

        @trace_agent(name="async_agent")
        async def async_agent():
            await asyncio.sleep(0.01)
            return "result"

        async with runtime.run_async("test_run") as run:
            result = await async_agent()

        assert result == "result"
        # Should have captured the step
        assert len(run.steps) > 0
        assert run.steps[0].name == "async_agent"
