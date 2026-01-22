"""
Async helper utilities for context propagation.

Provides utilities for maintaining trace context across asyncio operations
like gather, create_task, and run_in_executor.

Features:
    - Propagates run, step, and runtime context across async boundaries
    - TraceContext dataclass for capturing and restoring full context
    - Helper functions for complex async patterns

Example:
    ```python
    from agenttrace.contrib.async_helpers import (
        gather_with_context,
        capture_context,
        restore_context,
    )

    # Option 1: Use helper functions directly
    async with run_context(my_run):
        results = await gather_with_context(task1(), task2())

    # Option 2: Manual context management
    ctx = capture_context()
    async def worker():
        with restore_context(ctx):
            # Full trace context available here
            process()
    ```
"""

from __future__ import annotations

import asyncio
import contextvars
from collections.abc import Callable, Coroutine, Generator
from concurrent.futures import Executor
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

from agenttrace.core.context import (
    _current_run,
    _current_runtime,
    _current_step,
    get_current_run,
    get_current_runtime,
    get_current_step,
)

if TYPE_CHECKING:
    from agenttrace.core.models import AgentRun, Step
    from agenttrace.core.runtime import TALRuntime

T = TypeVar("T")


@dataclass
class TraceContext:
    """Captures the full AgentTrace context for propagation.

    This dataclass stores references to the current run, step, and runtime
    so they can be restored in another async task or thread.

    Attributes:
        run: The current AgentRun, if any.
        step: The current Step, if any.
        runtime: The current TALRuntime, if any.

    Example:
        ```python
        from agenttrace.contrib.async_helpers import capture_context, restore_context

        # Capture current context
        ctx = capture_context()

        # Later, in another task
        async def worker():
            with restore_context(ctx):
                # All context is restored here
                run = get_current_run()
                step = get_current_step()
        ```
    """

    run: AgentRun | None = None
    step: Step | None = None
    runtime: TALRuntime | None = None

    def is_empty(self) -> bool:
        """Check if this context has no values set."""
        return self.run is None and self.step is None and self.runtime is None


def capture_context() -> TraceContext:
    """
    Capture the current trace context for propagation.

    This captures the current run, step, and runtime context so they can
    be restored in another async task, thread, or callback.

    Returns:
        TraceContext containing all current context values.

    Example:
        ```python
        from agenttrace.contrib.async_helpers import capture_context, restore_context

        # In your main code
        ctx = capture_context()

        # Pass ctx to a worker thread/task
        def worker():
            with restore_context(ctx):
                # Context is available here
                process_data()
        ```
    """
    return TraceContext(
        run=get_current_run(),
        step=get_current_step(),
        runtime=get_current_runtime(),
    )


@contextmanager
def restore_context(ctx: TraceContext) -> Generator[TraceContext, None, None]:
    """
    Restore a previously captured trace context.

    This context manager restores the run, step, and runtime context
    captured by capture_context(). On exit, the previous context is restored.

    Args:
        ctx: The TraceContext to restore.

    Yields:
        The restored TraceContext.

    Example:
        ```python
        ctx = capture_context()

        async def worker():
            with restore_context(ctx):
                # Context is restored here
                run = get_current_run()
                step = get_current_step()
        ```
    """
    # Save current state
    run_token = None
    step_token = None
    runtime_token = None

    try:
        # Restore captured context
        if ctx.run is not None:
            run_token = _current_run.set(ctx.run)
        if ctx.step is not None:
            step_token = _current_step.set(ctx.step)
        if ctx.runtime is not None:
            runtime_token = _current_runtime.set(ctx.runtime)

        yield ctx

    finally:
        # Restore previous state
        if run_token is not None:
            _current_run.reset(run_token)
        if step_token is not None:
            _current_step.reset(step_token)
        if runtime_token is not None:
            _current_runtime.reset(runtime_token)


async def gather_with_context(
    *coros: Coroutine[Any, Any, T],
    return_exceptions: bool = False,
) -> list[T | BaseException]:
    """
    Like asyncio.gather but propagates full AgentTrace context to all coroutines.

    This ensures that all gathered tasks see the current run, step, and runtime context.

    Usage:
        ```python
        from agenttrace.contrib.async_helpers import gather_with_context
        from agenttrace.core.context import run_context

        async def task1():
            # Can access get_current_run(), get_current_step() here
            pass

        async def task2():
            # Also has access to the same context
            pass

        with run_context(my_run):
            results = await gather_with_context(task1(), task2())
        ```

    Args:
        *coros: Coroutines to run concurrently.
        return_exceptions: If True, exceptions are returned as results.

    Returns:
        List of results from all coroutines.
    """
    # Capture full context
    ctx = capture_context()

    async def wrapped_coro(coro: Coroutine[Any, Any, T]) -> T:
        # Restore full context in this task
        with restore_context(ctx):
            return await coro

    wrapped = [wrapped_coro(coro) for coro in coros]
    return await asyncio.gather(*wrapped, return_exceptions=return_exceptions)


def create_task_with_context(
    coro: Coroutine[Any, Any, T],
    *,
    name: str | None = None,
) -> asyncio.Task[T]:
    """
    Like asyncio.create_task but propagates full AgentTrace context.

    Usage:
        ```python
        from agenttrace.contrib.async_helpers import create_task_with_context

        async def my_task():
            # Has access to run, step, and runtime context
            pass

        with run_context(my_run):
            task = create_task_with_context(my_task())
            await task
        ```

    Args:
        coro: Coroutine to run as a task.
        name: Optional task name.

    Returns:
        The created Task.
    """
    ctx = capture_context()

    async def wrapped() -> T:
        with restore_context(ctx):
            return await coro

    return asyncio.create_task(wrapped(), name=name)


async def run_in_executor_with_context(
    func: Callable[..., T],
    *args: Any,
    executor: Executor | None = None,
) -> T:
    """
    Like loop.run_in_executor but propagates full AgentTrace context to the thread.

    Usage:
        ```python
        from agenttrace.contrib.async_helpers import run_in_executor_with_context

        def cpu_bound_work():
            # Has access to run, step, and runtime context
            return heavy_computation()

        with run_context(my_run):
            result = await run_in_executor_with_context(cpu_bound_work)
        ```

    Args:
        func: Function to run in executor.
        *args: Arguments to pass to function.
        executor: Optional executor to use.

    Returns:
        Result of the function.
    """
    ctx = capture_context()

    def wrapped() -> T:
        with restore_context(ctx):
            return func(*args)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, wrapped)


def copy_context() -> contextvars.Context:
    """
    Copy the current context for use in another thread or task.

    This is a thin wrapper around contextvars.copy_context() for
    convenience when doing low-level context management.

    Returns:
        A copy of the current context.
    """
    return contextvars.copy_context()


def run_with_context(ctx: contextvars.Context, func: Callable[..., T], *args: Any) -> T:
    """
    Run a function with a specific contextvars.Context.

    This is useful for low-level context propagation when you need
    to run a function with a previously copied context.

    Args:
        ctx: The contextvars.Context to run in.
        func: The function to run.
        *args: Arguments to pass to function.

    Returns:
        Result of the function.
    """
    return ctx.run(func, *args)


async def wrap_async_generator_with_context(
    gen: Any,
) -> Any:
    """
    Wrap an async generator to propagate context across yields.

    This ensures that the full trace context is maintained throughout
    the lifetime of an async generator, even if it's consumed in a
    different task.

    Args:
        gen: The async generator to wrap.

    Yields:
        Items from the wrapped generator.

    Example:
        ```python
        async def my_generator():
            for i in range(10):
                yield i

        # Wrap to propagate context
        ctx = capture_context()
        async for item in wrap_async_generator_with_context(my_generator()):
            process(item)
        ```
    """
    ctx = capture_context()

    async for item in gen:
        with restore_context(ctx):
            yield item
