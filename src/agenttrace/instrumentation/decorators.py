"""
Decorators for instrumenting functions (@trace_agent, @trace_tool, etc.).

Provides decorators and context managers for tracing agent executions,
tool calls, LLM invocations, and retrieval operations.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import threading
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from agenttrace.core.context import (
    get_current_run,
    get_current_runtime,
    get_current_step,
    reset_current_step,
    set_current_step,
)
from agenttrace.core.models import Step, StepType

if TYPE_CHECKING:
    from agenttrace.core.runtime import TALRuntime

P = ParamSpec("P")
R = TypeVar("R")

# Default maximum recursion depth for step hierarchy traversal
DEFAULT_MAX_STEP_DEPTH = 100


def _get_max_step_depth() -> int:
    """Get the configured max step depth from current runtime or global config."""
    runtime = get_current_runtime()
    if runtime is not None and runtime._config is not None:
        depth = runtime._config.max_step_depth
        if depth is not None:
            return depth
        return DEFAULT_MAX_STEP_DEPTH

    # Fall back to global config
    try:
        from agenttrace.core.runtime import get_runtime

        global_runtime = get_runtime()
        if global_runtime is not None and global_runtime._config is not None:
            depth = global_runtime._config.max_step_depth
            if depth is not None:
                return depth
    except ImportError:
        pass

    return DEFAULT_MAX_STEP_DEPTH


# Alias for backward compatibility
MAX_STEP_DEPTH = DEFAULT_MAX_STEP_DEPTH

# Lock for protecting step hierarchy modifications (run.steps, step.children)
_hierarchy_lock = threading.Lock()


def _create_step(
    name: str,
    step_type: StepType,
    inputs: dict[str, Any] | None = None,
    model_name: str | None = None,
    model_provider: str | None = None,
) -> Step:
    """Create a new step and link it to the current context."""
    run = get_current_run()
    parent = get_current_step()

    if run is None:
        # Create a step even without a run for testing/debugging
        from uuid import uuid4

        trace_id = uuid4()
    else:
        trace_id = run.id

    step = Step(
        trace_id=trace_id,
        parent_id=parent.id if parent else None,
        type=step_type,
        name=name,
        start_time=datetime.now(UTC),
        inputs=inputs or {},
        model_name=model_name,
        model_provider=model_provider,
    )

    return step


def _finalize_step(
    step: Step,
    result: Any | None = None,
    error: Exception | None = None,
) -> None:
    """Finalize a step with timing and results."""
    step.end_time = datetime.now(UTC)
    step.duration_ms = (step.end_time - step.start_time).total_seconds() * 1000

    if result is not None:
        step.outputs["result"] = result

    if error is not None:
        step.error = str(error)
        step.error_type = type(error).__name__


def _attach_step_to_hierarchy(step: Step) -> None:
    """Attach a finalized step to the parent or run (thread-safe)."""
    run = get_current_run()

    with _hierarchy_lock:
        if (
            step.parent_id is not None
            and run is not None
            and _add_step_to_parent_unlocked(run, step)
        ):
            # Found parent in run.steps
            return
        if step.parent_id is not None:
            # Parent not found in run yet, so find via context's _pending_parents
            parent = _find_parent_by_id(step.parent_id)
            if parent is not None:
                parent.children.append(step)
            elif run is not None:
                # Parent not found anywhere - attach to root as fallback
                # This can happen if depth limit is exceeded or parent finished first
                run.steps.append(step)
        elif run is not None:
            # Add as root step
            run.steps.append(step)


# Track pending parent steps that haven't been finalized yet
# Thread-safe with lock
_pending_parents: dict[str, Step] = {}
_pending_parents_lock = threading.Lock()


def _find_parent_by_id(parent_id: Any) -> Step | None:
    """Find a pending parent step by ID."""
    with _pending_parents_lock:
        return _pending_parents.get(str(parent_id))


def _add_step_to_parent_unlocked(run: Any, step: Step) -> bool:
    """Find parent in run.steps and add step as child (iterative BFS).

    Note: Caller must hold _hierarchy_lock.
    """
    # Use iterative breadth-first search to avoid stack overflow
    queue: list[Step] = list(run.steps)
    depth = 0
    max_depth = _get_max_step_depth()

    while queue and depth < max_depth:
        next_queue: list[Step] = []
        for current in queue:
            if current.id == step.parent_id:
                current.children.append(step)
                return True
            next_queue.extend(current.children)
        queue = next_queue
        depth += 1

    return False


def _get_function_inputs(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    exclude_inputs: list[str] | None = None,
    capture_inputs: bool = True,
) -> dict[str, Any]:
    """Extract function arguments as a dictionary.

    Args:
        func: The function being called.
        args: Positional arguments.
        kwargs: Keyword arguments.
        exclude_inputs: Parameter names to exclude from capture.
            Excluded parameters show as "[EXCLUDED]" placeholder.
        capture_inputs: If False, returns empty dict (no inputs captured).

    Returns:
        Dictionary of argument names to values, with exclusions applied.
    """
    if not capture_inputs:
        return {}

    sig = inspect.signature(func)
    bound = sig.bind(*args, **kwargs)
    bound.apply_defaults()
    inputs = dict(bound.arguments)

    if exclude_inputs:
        for param_name in exclude_inputs:
            if param_name in inputs:
                inputs[param_name] = "[EXCLUDED]"

    return inputs


def _create_trace_decorator(
    step_type: StepType,
    name: str | None = None,
    model_name: str | None = None,
    model_provider: str | None = None,
    exclude_inputs: list[str] | None = None,
    capture_inputs: bool = True,
    runtime: TALRuntime | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Factory function for creating trace decorators.

    Args:
        step_type: Type of step to create.
        name: Name for the step. Defaults to function name.
        model_name: Model name for LLM steps.
        model_provider: Model provider for LLM steps.
        exclude_inputs: Parameter names to exclude from capture.
        capture_inputs: If False, no inputs are captured.
        runtime: Explicit runtime to use. If provided, the decorated function
            will execute within this runtime's context.

    Returns:
        Decorator function.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        actual_name = name or func.__name__

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                async def _execute() -> R:
                    inputs = _get_function_inputs(
                        func,
                        args,
                        kwargs,
                        exclude_inputs=exclude_inputs,
                        capture_inputs=capture_inputs,
                    )
                    step = _create_step(
                        name=actual_name,
                        step_type=step_type,
                        inputs=inputs,
                        model_name=model_name,
                        model_provider=model_provider,
                    )

                    # Register as pending parent so children can find us
                    with _pending_parents_lock:
                        _pending_parents[str(step.id)] = step
                    token = set_current_step(step)
                    try:
                        result = await func(*args, **kwargs)
                        _finalize_step(step, result=result)
                        return result  # type: ignore[no-any-return]
                    except Exception as e:
                        _finalize_step(step, error=e)
                        raise
                    finally:
                        reset_current_step(token)
                        with _pending_parents_lock:
                            _pending_parents.pop(str(step.id), None)
                        _attach_step_to_hierarchy(step)

                # If explicit runtime provided, use its context
                if runtime is not None:
                    with runtime.trace_context():
                        return await _execute()
                return await _execute()

            return async_wrapper  # type: ignore
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                def _execute() -> R:
                    inputs = _get_function_inputs(
                        func,
                        args,
                        kwargs,
                        exclude_inputs=exclude_inputs,
                        capture_inputs=capture_inputs,
                    )
                    step = _create_step(
                        name=actual_name,
                        step_type=step_type,
                        inputs=inputs,
                        model_name=model_name,
                        model_provider=model_provider,
                    )

                    # Register as pending parent so children can find us
                    with _pending_parents_lock:
                        _pending_parents[str(step.id)] = step
                    token = set_current_step(step)
                    try:
                        result = func(*args, **kwargs)
                        _finalize_step(step, result=result)
                        return result
                    except Exception as e:
                        _finalize_step(step, error=e)
                        raise
                    finally:
                        reset_current_step(token)
                        with _pending_parents_lock:
                            _pending_parents.pop(str(step.id), None)
                        _attach_step_to_hierarchy(step)

                # If explicit runtime provided, use its context
                if runtime is not None:
                    with runtime.trace_context():
                        return _execute()
                return _execute()

            return sync_wrapper

    return decorator


def trace_agent(
    name: str | None = None,
    exclude_inputs: list[str] | None = None,
    capture_inputs: bool = True,
    runtime: TALRuntime | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator to trace agent function execution.

    Creates a step of type AGENT and captures inputs, outputs, and timing.

    Args:
        name: Name for the step. Defaults to function name.
        exclude_inputs: Parameter names to exclude from capture.
            Useful for omitting sensitive data like API keys or passwords.
            Excluded parameters show as "[EXCLUDED]" placeholder.
        capture_inputs: If False, no inputs are captured at all.
        runtime: Explicit runtime to use. If provided, the decorated function
            will execute within this runtime's context. Useful for multi-tenant
            scenarios where different runtimes have different configurations.

    Example:
        @trace_agent(name="research_agent")
        def my_agent(query: str) -> str:
            return process(query)

        # Exclude sensitive parameters
        @trace_agent(name="auth_agent", exclude_inputs=["api_key", "password"])
        def auth_agent(user: str, api_key: str, password: str) -> bool:
            return authenticate(user, api_key, password)

        # Use explicit runtime for multi-tenant scenario
        tenant_runtime = TALRuntime(config=tenant_config)
        @trace_agent(name="tenant_agent", runtime=tenant_runtime)
        def tenant_agent(query: str) -> str:
            return process(query)
    """
    return _create_trace_decorator(
        step_type=StepType.AGENT,
        name=name,
        exclude_inputs=exclude_inputs,
        capture_inputs=capture_inputs,
        runtime=runtime,
    )


def trace_tool(
    name: str | None = None,
    exclude_inputs: list[str] | None = None,
    capture_inputs: bool = True,
    runtime: TALRuntime | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator to trace tool function execution.

    Creates a step of type TOOL and captures inputs, outputs, and timing.

    Args:
        name: Name for the step. Defaults to function name.
        exclude_inputs: Parameter names to exclude from capture.
            Excluded parameters show as "[EXCLUDED]" placeholder.
        capture_inputs: If False, no inputs are captured at all.
        runtime: Explicit runtime to use. If provided, the decorated function
            will execute within this runtime's context.

    Example:
        @trace_tool(name="web_search")
        def search(query: str) -> list[str]:
            return fetch_results(query)

        # Exclude sensitive parameters
        @trace_tool(name="db_query", exclude_inputs=["connection_string"])
        def query_db(sql: str, connection_string: str) -> list[dict]:
            return execute_query(sql, connection_string)
    """
    return _create_trace_decorator(
        step_type=StepType.TOOL,
        name=name,
        exclude_inputs=exclude_inputs,
        capture_inputs=capture_inputs,
        runtime=runtime,
    )


def trace_llm(
    name: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    exclude_inputs: list[str] | None = None,
    capture_inputs: bool = True,
    runtime: TALRuntime | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator to trace LLM function execution.

    Creates a step of type LLM and captures inputs, outputs, timing,
    and model metadata.

    Args:
        name: Name for the step. Defaults to function name.
        model: Model name (e.g., "gpt-4", "claude-3-opus").
        provider: Model provider (e.g., "openai", "anthropic").
        exclude_inputs: Parameter names to exclude from capture.
            Excluded parameters show as "[EXCLUDED]" placeholder.
        capture_inputs: If False, no inputs are captured at all.
        runtime: Explicit runtime to use. If provided, the decorated function
            will execute within this runtime's context.

    Example:
        @trace_llm(name="chat_completion", model="gpt-4", provider="openai")
        def call_llm(prompt: str) -> str:
            return openai.chat.completions.create(...)

        # Exclude API key from traces
        @trace_llm(model="gpt-4", exclude_inputs=["api_key"])
        def call_llm(prompt: str, api_key: str) -> str:
            return openai.chat.completions.create(...)
    """
    return _create_trace_decorator(
        step_type=StepType.LLM,
        name=name,
        model_name=model,
        model_provider=provider,
        exclude_inputs=exclude_inputs,
        capture_inputs=capture_inputs,
        runtime=runtime,
    )


def trace_retrieval(
    name: str | None = None,
    exclude_inputs: list[str] | None = None,
    capture_inputs: bool = True,
    runtime: TALRuntime | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator to trace retrieval function execution.

    Creates a step of type RETRIEVAL and captures inputs, outputs, and timing.

    Args:
        name: Name for the step. Defaults to function name.
        exclude_inputs: Parameter names to exclude from capture.
            Excluded parameters show as "[EXCLUDED]" placeholder.
        capture_inputs: If False, no inputs are captured at all.
        runtime: Explicit runtime to use. If provided, the decorated function
            will execute within this runtime's context.

    Example:
        @trace_retrieval(name="vector_search")
        def search_docs(query: str) -> list[Document]:
            return vector_store.search(query)

        # Exclude embeddings from traces (they're large)
        @trace_retrieval(name="similarity_search", exclude_inputs=["embedding"])
        def search_by_embedding(query: str, embedding: list[float]) -> list[Document]:
            return vector_store.search_by_embedding(embedding)
    """
    return _create_trace_decorator(
        step_type=StepType.RETRIEVAL,
        name=name,
        exclude_inputs=exclude_inputs,
        capture_inputs=capture_inputs,
        runtime=runtime,
    )


@contextmanager
def step(
    name: str,
    type: StepType = StepType.WORKFLOW,
) -> Generator[Step, None, None]:
    """
    Context manager for creating a traced step.

    Creates a step with the given name and type, sets it as the current
    step, and finalizes it on exit.

    Args:
        name: Name for the step.
        type: Type of step (default: WORKFLOW).

    Example:
        with step("data_processing", type=StepType.WORKFLOW) as s:
            process_data()
            s.attributes["processed_count"] = 100
    """
    step_obj = _create_step(name=name, step_type=type)

    # Register as pending parent so children can find us
    with _pending_parents_lock:
        _pending_parents[str(step_obj.id)] = step_obj
    token = set_current_step(step_obj)

    try:
        yield step_obj
        _finalize_step(step_obj)
    except Exception as e:
        _finalize_step(step_obj, error=e)
        raise
    finally:
        reset_current_step(token)
        with _pending_parents_lock:
            _pending_parents.pop(str(step_obj.id), None)
        _attach_step_to_hierarchy(step_obj)


def trace_llm_stream(
    name: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    exclude_inputs: list[str] | None = None,
    capture_inputs: bool = True,
    runtime: TALRuntime | None = None,
) -> Callable[[Callable[P, AsyncGenerator[str, None]]], Callable[P, AsyncGenerator[str, None]]]:
    """
    Decorator for streaming LLM calls.

    Handles async generator functions that yield tokens incrementally.
    Aggregates all tokens and captures timing for the full stream.
    The complete output is stored in step.outputs["result"] after
    the stream completes.

    Args:
        name: Name for the step. Defaults to function name.
        model: Model name (e.g., "gpt-4o", "claude-3.5-sonnet").
        provider: Model provider (e.g., "openai", "anthropic").
        exclude_inputs: Parameter names to exclude from capture.
            Excluded parameters show as "[EXCLUDED]" placeholder.
        capture_inputs: If False, no inputs are captured at all.
        runtime: Explicit runtime to use. If provided, the decorated function
            will execute within this runtime's context.

    Example:
        ```python
        @trace_llm_stream(name="chat_stream", model="gpt-4o", provider="openai")
        async def stream_chat(prompt: str) -> AsyncGenerator[str, None]:
            async for chunk in client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                stream=True
            ):
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        ```
    """

    def decorator(
        func: Callable[P, AsyncGenerator[str, None]],
    ) -> Callable[P, AsyncGenerator[str, None]]:
        actual_name = name or func.__name__

        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> AsyncGenerator[str, None]:
            # Set up runtime context if explicit runtime provided
            from agenttrace.core.context import reset_current_runtime, set_current_runtime

            runtime_token = None
            if runtime is not None:
                runtime_token = set_current_runtime(runtime)

            try:
                inputs = _get_function_inputs(
                    func,
                    args,
                    kwargs,
                    exclude_inputs=exclude_inputs,
                    capture_inputs=capture_inputs,
                )
                step_obj = _create_step(
                    name=actual_name,
                    step_type=StepType.LLM,
                    inputs=inputs,
                    model_name=model,
                    model_provider=provider,
                )

                # Mark as streaming
                step_obj.attributes["is_streaming"] = True

                # Register as pending parent
                with _pending_parents_lock:
                    _pending_parents[str(step_obj.id)] = step_obj
                token = set_current_step(step_obj)

                collected_tokens: list[str] = []

                try:
                    async for chunk in func(*args, **kwargs):
                        collected_tokens.append(chunk)
                        yield chunk

                    # Aggregate output
                    full_output = "".join(collected_tokens)
                    step_obj.outputs["result"] = full_output
                    step_obj.attributes["token_count"] = len(collected_tokens)

                    _finalize_step(step_obj)

                except Exception as e:
                    # Still capture partial output on error
                    if collected_tokens:
                        step_obj.outputs["partial_result"] = "".join(collected_tokens)
                        step_obj.attributes["token_count"] = len(collected_tokens)
                    _finalize_step(step_obj, error=e)
                    raise

                finally:
                    reset_current_step(token)
                    with _pending_parents_lock:
                        _pending_parents.pop(str(step_obj.id), None)
                    _attach_step_to_hierarchy(step_obj)

            finally:
                if runtime_token is not None:
                    reset_current_runtime(runtime_token)

        return wrapper

    return decorator


def trace_stream(
    name: str | None = None,
    step_type: StepType = StepType.WORKFLOW,
    exclude_inputs: list[str] | None = None,
    capture_inputs: bool = True,
    runtime: TALRuntime | None = None,
) -> Callable[[Callable[P, AsyncGenerator[Any, None]]], Callable[P, AsyncGenerator[Any, None]]]:
    """
    General decorator for streaming operations.

    Handles async generator functions and collects all yielded values.
    Works with any step type, not just LLM calls.

    Args:
        name: Name for the step. Defaults to function name.
        step_type: Type of step (default: WORKFLOW).
        exclude_inputs: Parameter names to exclude from capture.
            Excluded parameters show as "[EXCLUDED]" placeholder.
        capture_inputs: If False, no inputs are captured at all.
        runtime: Explicit runtime to use. If provided, the decorated function
            will execute within this runtime's context.

    Example:
        ```python
        @trace_stream(name="process_stream", step_type=StepType.WORKFLOW)
        async def process_items() -> AsyncGenerator[dict, None]:
            async for item in fetch_items():
                processed = transform(item)
                yield processed
        ```
    """

    def decorator(
        func: Callable[P, AsyncGenerator[Any, None]],
    ) -> Callable[P, AsyncGenerator[Any, None]]:
        actual_name = name or func.__name__

        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> AsyncGenerator[Any, None]:
            # Set up runtime context if explicit runtime provided
            from agenttrace.core.context import reset_current_runtime, set_current_runtime

            runtime_token = None
            if runtime is not None:
                runtime_token = set_current_runtime(runtime)

            try:
                inputs = _get_function_inputs(
                    func,
                    args,
                    kwargs,
                    exclude_inputs=exclude_inputs,
                    capture_inputs=capture_inputs,
                )
                step_obj = _create_step(
                    name=actual_name,
                    step_type=step_type,
                    inputs=inputs,
                )

                # Mark as streaming
                step_obj.attributes["is_streaming"] = True

                # Register as pending parent
                with _pending_parents_lock:
                    _pending_parents[str(step_obj.id)] = step_obj
                token = set_current_step(step_obj)

                collected_items: list[Any] = []

                try:
                    async for item in func(*args, **kwargs):
                        collected_items.append(item)
                        yield item

                    step_obj.outputs["item_count"] = len(collected_items)
                    _finalize_step(step_obj)

                except Exception as e:
                    step_obj.outputs["partial_item_count"] = len(collected_items)
                    _finalize_step(step_obj, error=e)
                    raise

                finally:
                    reset_current_step(token)
                    with _pending_parents_lock:
                        _pending_parents.pop(str(step_obj.id), None)
                    _attach_step_to_hierarchy(step_obj)

            finally:
                if runtime_token is not None:
                    reset_current_runtime(runtime_token)

        return wrapper

    return decorator
