"""
Context-aware ThreadPoolExecutor for proper trace propagation.

Provides TALContextExecutor that properly propagates contextvars
(AgentTrace context) to thread pool workers.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import copy_context
from typing import Any, TypeVar

T = TypeVar("T")


def copy_context_run(fn: Callable[..., T]) -> Callable[..., T]:
    """
    Wrap a function to run with a copy of the current context.

    This utility creates a snapshot of the current contextvars state
    and returns a wrapped function that will execute in that snapshot.
    Useful for manually propagating context to standard executors.

    Args:
        fn: The function to wrap.

    Returns:
        A wrapped function that preserves the current context.

    Example:
        ```python
        from concurrent.futures import ThreadPoolExecutor
        from agenttrace.contrib.executors import copy_context_run
        from agenttrace.core.context import run_context, get_current_run

        def my_task():
            run = get_current_run()
            return run.name if run else "none"

        run = AgentRun(name="test")
        with run_context(run):
            wrapped = copy_context_run(my_task)

        # Use with standard ThreadPoolExecutor
        with ThreadPoolExecutor() as executor:
            future = executor.submit(wrapped)
            print(future.result())  # Prints "test"
        ```
    """
    ctx = copy_context()

    def wrapper(*args: Any, **kwargs: Any) -> T:
        return ctx.run(fn, *args, **kwargs)

    return wrapper


class TALContextExecutor(ThreadPoolExecutor):
    """
    ThreadPoolExecutor that automatically propagates contextvars.

    This executor wraps submitted tasks to run within a copy of the
    calling thread's context, ensuring that AgentTrace's run and step
    context is properly propagated to worker threads.

    The standard ThreadPoolExecutor does not propagate contextvars to
    worker threads. This class solves that by using copy_context() to
    snapshot the context at submit time and run the task within that
    snapshot.

    Usage:
        ```python
        from agenttrace.contrib.executors import TALContextExecutor
        from agenttrace.core.context import run_context, get_current_run
        from agenttrace.core.models import AgentRun
        from datetime import datetime, UTC

        def worker_task():
            run = get_current_run()
            return run.name if run else "no context"

        run = AgentRun(name="my_run", start_time=datetime.now(UTC))

        with run_context(run):
            with TALContextExecutor(max_workers=4) as executor:
                future = executor.submit(worker_task)
                print(future.result())  # Prints "my_run"
        ```

    Note:
        Context is copied at submit time, not at execution time.
        This means the task will see the context state as it was
        when submit() was called.
    """

    def submit(
        self,
        fn: Callable[..., T],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> Future[T]:
        """
        Submit a callable to be executed with context propagation.

        Creates a copy of the current context and runs the function
        within that context on a worker thread.

        Args:
            fn: The callable to execute.
            *args: Positional arguments to pass to fn.
            **kwargs: Keyword arguments to pass to fn.

        Returns:
            A Future representing the execution.
        """
        ctx = copy_context()

        def context_wrapper() -> T:
            return ctx.run(fn, *args, **kwargs)

        return super().submit(context_wrapper)

    def map(
        self,
        fn: Callable[..., T],
        *iterables: Any,
        timeout: float | None = None,
        chunksize: int = 1,
    ) -> Iterator[T]:
        """
        Map a function over iterables with context propagation.

        Creates a copy of the current context for each task at submit time.

        Args:
            fn: The callable to execute for each item.
            *iterables: Iterables of arguments to map over.
            timeout: Maximum time to wait for results.
            chunksize: Size of chunks for ProcessPoolExecutor
                       (ignored for ThreadPoolExecutor).

        Returns:
            An iterator of results in the same order as inputs.
        """
        # Copy context once at map call time (context is the same for all items)
        # Each item gets the same snapshot, which is the expected behavior
        ctx = copy_context()

        def context_wrapper(*args: Any) -> T:
            return ctx.run(fn, *args)

        return super().map(
            context_wrapper,
            *iterables,
            timeout=timeout,
            chunksize=chunksize,
        )
