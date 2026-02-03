"""
Tests for context-aware executors.

Tests TALContextExecutor that properly propagates contextvars
to thread pool workers.
"""

from __future__ import annotations

import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

import pytest

from tracecraft.core.context import (
    get_current_run,
    get_current_step,
    run_context,
    step_context,
)
from tracecraft.core.models import AgentRun, Step, StepType


class TestTALContextExecutor:
    """Tests for TALContextExecutor."""

    def test_executor_creation(self) -> None:
        """Should create an executor with default thread count."""
        from tracecraft.contrib.executors import TALContextExecutor

        executor = TALContextExecutor()
        assert executor is not None
        executor.shutdown(wait=False)

    def test_executor_with_max_workers(self) -> None:
        """Should accept max_workers parameter."""
        from tracecraft.contrib.executors import TALContextExecutor

        executor = TALContextExecutor(max_workers=4)
        assert executor is not None
        executor.shutdown(wait=False)

    def test_executor_context_manager(self) -> None:
        """Should work as context manager."""
        from tracecraft.contrib.executors import TALContextExecutor

        with TALContextExecutor() as executor:
            assert executor is not None

    def test_submit_without_context(self) -> None:
        """Should work without active context."""
        from tracecraft.contrib.executors import TALContextExecutor

        def task() -> str:
            return "result"

        with TALContextExecutor(max_workers=1) as executor:
            future = executor.submit(task)
            assert future.result() == "result"


class TestContextPropagation:
    """Tests for context propagation to threads."""

    def test_propagates_run_context(self) -> None:
        """Should propagate current run to thread."""
        from tracecraft.contrib.executors import TALContextExecutor

        captured_run: AgentRun | None = None

        def capture_context() -> None:
            nonlocal captured_run
            captured_run = get_current_run()

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run), TALContextExecutor(max_workers=1) as executor:
            future = executor.submit(capture_context)
            future.result()

        assert captured_run is not None
        assert captured_run.name == "test_run"

    def test_propagates_step_context(self) -> None:
        """Should propagate current step to thread."""
        from tracecraft.contrib.executors import TALContextExecutor

        captured_step: Step | None = None

        def capture_context() -> None:
            nonlocal captured_step
            captured_step = get_current_step()

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        step = Step(
            trace_id=run.id,
            type=StepType.WORKFLOW,
            name="test_step",
            start_time=datetime.now(UTC),
        )

        with (
            run_context(run),
            step_context(step),
            TALContextExecutor(max_workers=1) as executor,
        ):
            future = executor.submit(capture_context)
            future.result()

        assert captured_step is not None
        assert captured_step.name == "test_step"

    def test_propagates_both_contexts(self) -> None:
        """Should propagate both run and step context."""
        from tracecraft.contrib.executors import TALContextExecutor

        captured_run: AgentRun | None = None
        captured_step: Step | None = None

        def capture_context() -> None:
            nonlocal captured_run, captured_step
            captured_run = get_current_run()
            captured_step = get_current_step()

        run = AgentRun(name="main_run", start_time=datetime.now(UTC))
        step = Step(
            trace_id=run.id,
            type=StepType.AGENT,
            name="main_step",
            start_time=datetime.now(UTC),
        )

        with (
            run_context(run),
            step_context(step),
            TALContextExecutor(max_workers=1) as executor,
        ):
            future = executor.submit(capture_context)
            future.result()

        assert captured_run is not None
        assert captured_run.name == "main_run"
        assert captured_step is not None
        assert captured_step.name == "main_step"


class TestContextIsolation:
    """Tests for context isolation between tasks."""

    def test_context_snapshot_is_independent(self) -> None:
        """Context changes in thread should not affect main context."""
        from tracecraft.contrib.executors import TALContextExecutor

        main_run_after: AgentRun | None = None

        def task_that_might_modify() -> str:
            # The task can read context but shouldn't affect outer context
            # because contextvars copy_context creates a snapshot
            current = get_current_run()
            return current.name if current else "none"

        run = AgentRun(name="original", start_time=datetime.now(UTC))

        with run_context(run):
            with TALContextExecutor(max_workers=1) as executor:
                future = executor.submit(task_that_might_modify)
                future.result()
            main_run_after = get_current_run()

        # Main context should be unchanged
        assert main_run_after is not None
        assert main_run_after.name == "original"

    def test_concurrent_tasks_isolated(self) -> None:
        """Concurrent tasks should have isolated contexts."""
        from tracecraft.contrib.executors import TALContextExecutor

        results: dict[str, str | None] = {}

        def capture_run_name(task_id: str) -> None:
            # Small delay to ensure concurrency
            time.sleep(0.01)
            run = get_current_run()
            results[task_id] = run.name if run else None

        run = AgentRun(name="shared_run", start_time=datetime.now(UTC))

        with run_context(run), TALContextExecutor(max_workers=4) as executor:
            futures = [executor.submit(capture_run_name, f"task_{i}") for i in range(4)]
            for future in as_completed(futures):
                future.result()

        # All tasks should have seen the same run
        assert len(results) == 4
        for task_id, run_name in results.items():
            assert run_name == "shared_run", f"{task_id} got wrong context"


class TestSubmitWithArgs:
    """Tests for submit with arguments."""

    def test_submit_with_positional_args(self) -> None:
        """Should pass positional arguments to task."""
        from tracecraft.contrib.executors import TALContextExecutor

        def add(a: int, b: int) -> int:
            return a + b

        with TALContextExecutor(max_workers=1) as executor:
            future = executor.submit(add, 2, 3)
            assert future.result() == 5

    def test_submit_with_keyword_args(self) -> None:
        """Should pass keyword arguments to task."""
        from tracecraft.contrib.executors import TALContextExecutor

        def greet(name: str, greeting: str = "Hello") -> str:
            return f"{greeting}, {name}!"

        with TALContextExecutor(max_workers=1) as executor:
            future = executor.submit(greet, "World", greeting="Hi")
            assert future.result() == "Hi, World!"

    def test_submit_with_context_and_args(self) -> None:
        """Should pass context and arguments together."""
        from tracecraft.contrib.executors import TALContextExecutor

        def process(data: str) -> str:
            run = get_current_run()
            run_name = run.name if run else "no_run"
            return f"{run_name}: {data}"

        run = AgentRun(name="processor", start_time=datetime.now(UTC))

        with run_context(run), TALContextExecutor(max_workers=1) as executor:
            future = executor.submit(process, "test_data")
            assert future.result() == "processor: test_data"


class TestMapMethod:
    """Tests for map method."""

    def test_map_propagates_context(self) -> None:
        """Should propagate context to all map workers."""
        from tracecraft.contrib.executors import TALContextExecutor

        def process_item(item: int) -> tuple[int, str | None]:
            run = get_current_run()
            run_name = run.name if run else None
            return item * 2, run_name

        run = AgentRun(name="mapper", start_time=datetime.now(UTC))

        with run_context(run), TALContextExecutor(max_workers=2) as executor:
            results = list(executor.map(process_item, [1, 2, 3, 4]))

        assert len(results) == 4
        for _value, run_name in results:
            assert run_name == "mapper"
        assert [r[0] for r in results] == [2, 4, 6, 8]

    def test_map_with_timeout(self) -> None:
        """Should support timeout parameter."""
        from tracecraft.contrib.executors import TALContextExecutor

        def fast_task(x: int) -> int:
            return x * 2

        with TALContextExecutor(max_workers=2) as executor:
            results = list(executor.map(fast_task, [1, 2, 3], timeout=5))
            assert results == [2, 4, 6]


class TestShutdown:
    """Tests for executor shutdown."""

    def test_shutdown_waits_for_tasks(self) -> None:
        """Should wait for pending tasks on shutdown."""
        from tracecraft.contrib.executors import TALContextExecutor

        completed = []

        def slow_task(task_id: int) -> int:
            time.sleep(0.05)
            completed.append(task_id)
            return task_id

        executor = TALContextExecutor(max_workers=2)
        # Submit tasks and ensure they complete via shutdown
        for i in range(3):
            executor.submit(slow_task, i)
        executor.shutdown(wait=True)

        # All tasks should be complete
        assert len(completed) == 3

    def test_shutdown_no_wait(self) -> None:
        """Should return immediately with wait=False."""
        from tracecraft.contrib.executors import TALContextExecutor

        executor = TALContextExecutor(max_workers=1)
        executor.shutdown(wait=False)
        # Should not block


class TestExceptionHandling:
    """Tests for exception handling."""

    def test_exception_in_task(self) -> None:
        """Should propagate exceptions from tasks."""
        from tracecraft.contrib.executors import TALContextExecutor

        def failing_task() -> None:
            raise ValueError("Task failed")

        with TALContextExecutor(max_workers=1) as executor:
            future = executor.submit(failing_task)
            with pytest.raises(ValueError, match="Task failed"):
                future.result()

    def test_exception_preserves_context(self) -> None:
        """Should still have context when task raises."""
        from tracecraft.contrib.executors import TALContextExecutor

        captured_context: str | None = None

        def task_with_error() -> None:
            nonlocal captured_context
            run = get_current_run()
            captured_context = run.name if run else None
            raise RuntimeError("Intentional error")

        run = AgentRun(name="error_test", start_time=datetime.now(UTC))

        with run_context(run), TALContextExecutor(max_workers=1) as executor:
            future = executor.submit(task_with_error)
            with pytest.raises(RuntimeError):
                future.result()

        # Context was captured before error
        assert captured_context == "error_test"


class TestAsCompletedIntegration:
    """Tests for as_completed usage."""

    def test_works_with_as_completed(self) -> None:
        """Should work correctly with as_completed."""
        from tracecraft.contrib.executors import TALContextExecutor

        def task(delay: float, value: str) -> str:
            time.sleep(delay)
            run = get_current_run()
            run_name = run.name if run else "none"
            return f"{run_name}:{value}"

        run = AgentRun(name="async_run", start_time=datetime.now(UTC))

        with run_context(run), TALContextExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(task, 0.01, "fast"),
                executor.submit(task, 0.02, "medium"),
                executor.submit(task, 0.03, "slow"),
            ]
            results = [f.result() for f in as_completed(futures)]

        # All should have proper context
        assert all("async_run:" in r for r in results)
        assert {r.split(":")[1] for r in results} == {"fast", "medium", "slow"}


class TestContextCopyFunction:
    """Tests for the copy_context_run utility function."""

    def test_copy_context_run_available(self) -> None:
        """Should export copy_context_run helper."""
        from tracecraft.contrib.executors import copy_context_run

        def simple_task() -> str:
            return "done"

        # Should work without active context
        wrapped = copy_context_run(simple_task)
        assert wrapped() == "done"

    def test_copy_context_run_with_args(self) -> None:
        """Should pass args through copy_context_run."""
        from tracecraft.contrib.executors import copy_context_run

        def task_with_args(a: int, b: int) -> int:
            return a + b

        wrapped = copy_context_run(task_with_args)
        assert wrapped(2, 3) == 5

    def test_copy_context_run_preserves_context(self) -> None:
        """Should preserve context when used manually."""
        from tracecraft.contrib.executors import copy_context_run

        captured: str | None = None

        def capture_task() -> None:
            nonlocal captured
            run = get_current_run()
            captured = run.name if run else None

        run = AgentRun(name="manual_test", start_time=datetime.now(UTC))

        with run_context(run):
            wrapped = copy_context_run(capture_task)

        # Execute outside of context
        wrapped()

        # Context was captured at wrap time
        assert captured == "manual_test"

    def test_copy_context_run_with_standard_executor(self) -> None:
        """Should work with standard ThreadPoolExecutor."""
        from tracecraft.contrib.executors import copy_context_run

        captured: str | None = None

        def capture_task() -> None:
            nonlocal captured
            run = get_current_run()
            captured = run.name if run else None

        run = AgentRun(name="standard_executor_test", start_time=datetime.now(UTC))

        with run_context(run):
            wrapped = copy_context_run(capture_task)
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(wrapped)
                future.result()

        assert captured == "standard_executor_test"


class TestNestedContexts:
    """Tests for nested context scenarios."""

    def test_nested_executors(self) -> None:
        """Should work with nested executor calls."""
        from tracecraft.contrib.executors import TALContextExecutor

        inner_results: list[str] = []

        def outer_task(task_id: str) -> str:
            run = get_current_run()

            def inner_task() -> str:
                inner_run = get_current_run()
                return inner_run.name if inner_run else "none"

            with TALContextExecutor(max_workers=1) as inner_executor:
                future = inner_executor.submit(inner_task)
                inner_result = future.result()
                inner_results.append(inner_result)

            return f"{task_id}:{run.name if run else 'none'}"

        run = AgentRun(name="outer_run", start_time=datetime.now(UTC))

        with run_context(run), TALContextExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(outer_task, "task1"),
                executor.submit(outer_task, "task2"),
            ]
            results = [f.result() for f in futures]

        # Outer tasks got context
        assert all("outer_run" in r for r in results)
        # Inner tasks also got context
        assert all(r == "outer_run" for r in inner_results)


class TestExecutorProtocol:
    """Tests for Executor protocol compliance."""

    def test_is_executor_subclass(self) -> None:
        """Should be a subclass of Executor."""
        from concurrent.futures import Executor

        from tracecraft.contrib.executors import TALContextExecutor

        assert issubclass(TALContextExecutor, Executor)

    def test_submit_returns_future(self) -> None:
        """Should return Future from submit."""
        from tracecraft.contrib.executors import TALContextExecutor

        with TALContextExecutor(max_workers=1) as executor:
            future = executor.submit(lambda: 42)
            assert isinstance(future, Future)
            assert future.result() == 42

    def test_map_returns_iterator(self) -> None:
        """Should return iterator from map."""
        from tracecraft.contrib.executors import TALContextExecutor

        with TALContextExecutor(max_workers=1) as executor:
            result = executor.map(lambda x: x * 2, [1, 2, 3])
            # map returns an iterator
            assert hasattr(result, "__iter__")
            assert list(result) == [2, 4, 6]
