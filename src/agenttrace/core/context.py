"""
Context propagation for AgentTrace using contextvars.

Provides async-safe context propagation for tracking the current step
and run throughout an agent's execution, including nested async calls
and concurrent tasks.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agenttrace.core.models import AgentRun, Step
    from agenttrace.core.runtime import TALRuntime

# Context variables for current step, run, and runtime
_current_step: ContextVar[Step | None] = ContextVar("current_step", default=None)
_current_run: ContextVar[AgentRun | None] = ContextVar("current_run", default=None)
_current_runtime: ContextVar[TALRuntime | None] = ContextVar("current_runtime", default=None)


def get_current_step() -> Step | None:
    """
    Get the current step from context.

    Returns:
        The current Step, or None if no step is active.
    """
    return _current_step.get()


def set_current_step(step: Step | None) -> Token[Step | None]:
    """
    Set the current step in context.

    Args:
        step: The Step to set as current, or None to clear.

    Returns:
        A token that can be used to reset to the previous value.
    """
    return _current_step.set(step)


def reset_current_step(token: Token[Step | None]) -> None:
    """
    Reset the current step to a previous value using a token.

    Args:
        token: The token returned from a previous set_current_step call.
    """
    _current_step.reset(token)


def get_current_run() -> AgentRun | None:
    """
    Get the current run from context.

    Returns:
        The current AgentRun, or None if no run is active.
    """
    return _current_run.get()


def set_current_run(run: AgentRun | None) -> Token[AgentRun | None]:
    """
    Set the current run in context.

    Args:
        run: The AgentRun to set as current, or None to clear.

    Returns:
        A token that can be used to reset to the previous value.
    """
    return _current_run.set(run)


def reset_current_run(token: Token[AgentRun | None]) -> None:
    """
    Reset the current run to a previous value using a token.

    Args:
        token: The token returned from a previous set_current_run call.
    """
    _current_run.reset(token)


@contextmanager
def step_context(step: Step) -> Generator[Step, None, None]:
    """
    Context manager for setting the current step.

    Sets the step on entry and restores the previous value on exit,
    even if an exception occurs.

    Args:
        step: The Step to set as current.

    Yields:
        The step that was set.

    Example:
        with step_context(my_step):
            # my_step is now the current step
            do_work()
        # Previous step is restored
    """
    token = set_current_step(step)
    try:
        yield step
    finally:
        reset_current_step(token)


@contextmanager
def run_context(run: AgentRun) -> Generator[AgentRun, None, None]:
    """
    Context manager for setting the current run.

    Sets the run on entry and restores the previous value on exit,
    even if an exception occurs.

    Args:
        run: The AgentRun to set as current.

    Yields:
        The run that was set.

    Example:
        with run_context(my_run):
            # my_run is now the current run
            do_work()
        # Previous run is restored
    """
    token = set_current_run(run)
    try:
        yield run
    finally:
        reset_current_run(token)


def get_current_runtime() -> TALRuntime | None:
    """
    Get the current runtime from context.

    Returns:
        The current TALRuntime, or None if no runtime is scoped.
    """
    return _current_runtime.get()


def set_current_runtime(runtime: TALRuntime | None) -> Token[TALRuntime | None]:
    """
    Set the current runtime in context.

    Args:
        runtime: The TALRuntime to set as current, or None to clear.

    Returns:
        A token that can be used to reset to the previous value.
    """
    return _current_runtime.set(runtime)


def reset_current_runtime(token: Token[TALRuntime | None]) -> None:
    """
    Reset the current runtime to a previous value using a token.

    Args:
        token: The token returned from a previous set_current_runtime call.
    """
    _current_runtime.reset(token)


@contextmanager
def runtime_context(runtime: TALRuntime) -> Generator[TALRuntime, None, None]:
    """
    Context manager for setting the current runtime.

    Sets the runtime on entry and restores the previous value on exit.
    This is useful for multi-tenant scenarios where different runtimes
    have different configurations.

    Args:
        runtime: The TALRuntime to set as current.

    Yields:
        The runtime that was set.

    Example:
        runtime_a = TALRuntime(config=config_a)
        runtime_b = TALRuntime(config=config_b)

        with runtime_context(runtime_a):
            # Decorators will use runtime_a
            my_agent()

        with runtime_context(runtime_b):
            # Decorators will use runtime_b
            my_agent()
    """
    token = set_current_runtime(runtime)
    try:
        yield runtime
    finally:
        reset_current_runtime(token)
