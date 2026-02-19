"""
LlamaIndex span handler adapter.

Provides TraceCraftSpanHandler that integrates LlamaIndex with TraceCraft
for unified observability.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import PrivateAttr

from tracecraft.core.context import get_current_run
from tracecraft.core.models import Step, StepType

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun

# Try to import LlamaIndex base classes for proper inheritance
try:
    from llama_index.core.callbacks.base import BaseCallbackHandler
    from llama_index.core.callbacks.schema import CBEventType
    from llama_index.core.instrumentation.span_handlers import BaseSpanHandler

    _HAS_LLAMAINDEX = True
except ImportError:
    # Fallback: create stub base classes when llama-index is not installed
    class BaseSpanHandler:  # type: ignore[no-redef]
        """Stub base class when llama-index is not installed."""

        pass

    class BaseCallbackHandler:  # type: ignore[no-redef]
        """Stub callback handler when llama-index is not installed."""

        def __init__(
            self,
            event_starts_to_ignore: list[str] | None = None,
            event_ends_to_ignore: list[str] | None = None,
        ) -> None:
            self.event_starts_to_ignore = event_starts_to_ignore or []
            self.event_ends_to_ignore = event_ends_to_ignore or []

    class CBEventType:  # type: ignore[no-redef]
        """Stub CBEventType when llama-index is not installed."""

        LLM = "llm"
        EMBEDDING = "embedding"
        RETRIEVE = "retrieve"
        QUERY = "query"

    _HAS_LLAMAINDEX = False


class TraceCraftSpanHandler(BaseSpanHandler):
    """
    LlamaIndex span handler that creates TraceCraft Steps.

    This handler implements the LlamaIndex instrumentor/span handler protocol
    to capture spans from LlamaIndex operations as TraceCraft Steps.

    Usage:
        ```python
        from tracecraft.adapters.llamaindex import TraceCraftSpanHandler
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun
        from llama_index.core import Settings
        from llama_index.core.callbacks import CallbackManager

        handler = TraceCraftSpanHandler()
        Settings.callback_manager = CallbackManager(handlers=[handler])

        run = AgentRun(name="my_run", start_time=datetime.now(UTC))
        with run_context(run):
            # Your LlamaIndex code here
            index.as_query_engine().query("What is the answer?")

        # run.steps now contains the trace
        # Call clear() when done to free memory
        handler.clear()
        ```
    """

    # Private attributes for tracking spans (Pydantic PrivateAttr)
    # Note: _lock is also defined in BaseSpanHandler but set to None,
    # so we override it with a proper Lock instance in __init__
    _steps: dict[str, Step] = PrivateAttr(default_factory=dict)
    _lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)

    def __init__(self) -> None:
        """Initialize the span handler."""
        super().__init__()
        # BaseSpanHandler.__init__ sets _lock = None, so we must reinitialize it
        object.__setattr__(self, "_lock", threading.Lock())

    def clear(self) -> None:
        """Clear tracked steps to free memory. Call after run completes."""
        with self._lock:
            self._steps.clear()

    def _register_step(self, span_id: str, step: Step) -> None:
        """Register a step in the tracking dict (thread-safe)."""
        with self._lock:
            self._steps[span_id] = step

    def _get_step(self, span_id: str) -> Step | None:
        """Get a step from the tracking dict (thread-safe)."""
        with self._lock:
            return self._steps.get(span_id)

    def _pop_step(self, span_id: str) -> Step | None:
        """Remove and return a step from the tracking dict (thread-safe)."""
        with self._lock:
            return self._steps.pop(span_id, None)

    def _get_run(self) -> AgentRun | None:
        """Get the current AgentRun from context."""
        return get_current_run()

    def _infer_step_type(self, instance: Any) -> StepType:
        """Infer StepType from the LlamaIndex component instance."""
        if instance is None:
            return StepType.WORKFLOW

        class_name = type(instance).__name__.lower()
        module_name = (
            type(instance).__module__.lower() if hasattr(type(instance), "__module__") else ""
        )

        # LLM detection
        if "llm" in class_name or "llm" in module_name:
            return StepType.LLM

        # Retriever detection
        if "retriever" in class_name or "retriever" in module_name:
            return StepType.RETRIEVAL

        # Tool detection
        if "tool" in class_name or "tool" in module_name:
            return StepType.TOOL

        # Agent detection
        if "agent" in class_name or "agent" in module_name:
            return StepType.AGENT

        # Query engine - treat as workflow
        if "query" in class_name or "engine" in class_name:
            return StepType.WORKFLOW

        return StepType.WORKFLOW

    def _get_name(self, instance: Any) -> str:
        """Extract name from instance."""
        if instance is None:
            return "unknown"

        # Check for tool metadata with name
        if hasattr(instance, "metadata") and hasattr(instance.metadata, "name"):
            return str(instance.metadata.name)

        # Check for name attribute
        if hasattr(instance, "name"):
            return str(instance.name)

        # Fall back to class name
        return type(instance).__name__

    def _get_model_name(self, instance: Any) -> str | None:
        """Extract model name from LLM instance."""
        if hasattr(instance, "model_name"):
            return str(instance.model_name)
        if hasattr(instance, "model"):
            return str(instance.model)
        return None

    def _extract_inputs(
        self,
        bound_args: Any,
        instance: Any,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Extract inputs from bound arguments.

        Args:
            bound_args: Either a dict or an inspect.BoundArguments object.
            instance: The LlamaIndex component instance.

        Returns:
            Dictionary of extracted input values.
        """
        inputs: dict[str, Any] = {}

        # Handle both dict and BoundArguments
        import inspect

        if isinstance(bound_args, inspect.BoundArguments):
            args_dict = bound_args.arguments
        elif isinstance(bound_args, dict):
            args_dict = bound_args
        else:
            return inputs

        # Query bundle
        if "query_bundle" in args_dict:
            query_bundle = args_dict["query_bundle"]
            if hasattr(query_bundle, "query_str"):
                inputs["query"] = query_bundle.query_str

        # Direct query/prompt
        for key in ["query", "prompt", "input", "task"]:
            if key in args_dict:
                inputs[key] = args_dict[key]

        return inputs

    def _extract_outputs(
        self,
        result: Any,
        step_type: StepType,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Extract outputs from result."""
        outputs: dict[str, Any] = {}

        if result is None:
            return outputs

        # Handle list of nodes (retrieval results)
        if isinstance(result, list):
            docs = []
            for item in result:
                if hasattr(item, "node") and hasattr(item, "score"):
                    # NodeWithScore
                    node = item.node
                    doc: dict[str, Any] = {}
                    if hasattr(node, "get_content"):
                        doc["content"] = node.get_content()
                    elif hasattr(node, "text"):
                        doc["content"] = node.text
                    if hasattr(node, "metadata"):
                        doc["metadata"] = node.metadata
                    doc["score"] = item.score
                    docs.append(doc)
            if docs:
                outputs["documents"] = docs
                return outputs

        # Handle completion response
        if hasattr(result, "text"):
            outputs["text"] = result.text

        # Handle agent response
        if hasattr(result, "response"):
            outputs["response"] = str(result.response)

        # Handle string result
        if isinstance(result, str):
            outputs["result"] = result

        return outputs

    def _extract_token_usage(self, result: Any, step: Step) -> None:
        """Extract token usage from LLM response."""
        if not hasattr(result, "raw"):
            return

        raw = result.raw
        if not isinstance(raw, dict):
            return

        usage = raw.get("usage")
        if not usage:
            return

        if "prompt_tokens" in usage:
            step.input_tokens = usage["prompt_tokens"]
        if "completion_tokens" in usage:
            step.output_tokens = usage["completion_tokens"]

        # Note: Token aggregation is done in runtime._aggregate_metrics()
        # at end_run() time, so no need to update run.total_tokens here

    def _add_step_to_run(self, step: Step, parent_span_id: str | None = None) -> None:
        """Add a step to the current run, handling hierarchy (thread-safe)."""
        run = self._get_run()
        if run is None:
            return

        # Hold lock during entire operation to ensure thread-safety
        # for both parent lookup and list append operations
        with self._lock:
            parent = self._steps.get(parent_span_id) if parent_span_id else None
            if parent:
                step.parent_id = parent.id
                parent.children.append(step)
            else:
                run.steps.append(step)

    def new_span(
        self,
        id_: str,
        bound_args: Any,
        instance: Any = None,
        parent_span_id: str | None = None,
        tags: dict[str, Any] | None = None,  # noqa: ARG002
        **_kwargs: Any,
    ) -> str | None:
        """
        Create a new span.

        Args:
            id_: The span ID.
            bound_args: Arguments passed to the function (dict or BoundArguments).
            instance: The LlamaIndex component instance.
            parent_span_id: Optional parent span ID for nesting.
            tags: Optional tags from dispatcher.

        Returns:
            The span ID if created, None otherwise.
        """
        run = self._get_run()
        if run is None:
            return None

        step_type = self._infer_step_type(instance)
        name = self._get_name(instance)
        model_name = self._get_model_name(instance) if step_type == StepType.LLM else None

        step = Step(
            trace_id=run.id,
            type=step_type,
            name=name,
            start_time=datetime.now(UTC),
            inputs=self._extract_inputs(bound_args, instance),
            model_name=model_name,
        )

        self._register_step(id_, step)
        self._add_step_to_run(step, parent_span_id)

        return id_

    def end_span(
        self,
        id_: str,
        bound_args: Any = None,  # noqa: ARG002
        instance: Any = None,  # noqa: ARG002
        result: Any = None,
        **_kwargs: Any,
    ) -> None:
        """
        End a span successfully.

        Args:
            id_: The span ID to end.
            bound_args: Arguments passed to the function (dict or BoundArguments).
            instance: The LlamaIndex component instance.
            result: The result of the operation.
        """
        step = self._pop_step(id_)
        if step is None:
            return

        end_time = datetime.now(UTC)
        step.end_time = end_time
        step.duration_ms = (end_time - step.start_time).total_seconds() * 1000
        step.outputs = self._extract_outputs(result, step.type)

        # Extract token usage for LLM steps
        if step.type == StepType.LLM:
            self._extract_token_usage(result, step)

    def drop_span(
        self,
        id_: str,
        bound_args: Any = None,  # noqa: ARG002
        instance: Any = None,  # noqa: ARG002
        err: BaseException | None = None,
        **_kwargs: Any,
    ) -> None:
        """
        Drop a span due to error.

        Args:
            id_: The span ID to drop.
            bound_args: Arguments passed to the function (dict or BoundArguments).
            instance: The LlamaIndex component instance.
            err: The exception that caused the drop.
        """
        step = self._pop_step(id_)
        if step is None:
            return

        end_time = datetime.now(UTC)
        step.end_time = end_time
        step.duration_ms = (end_time - step.start_time).total_seconds() * 1000
        if err is not None:
            step.error = str(err)
            step.error_type = type(err).__name__

        # Note: Error aggregation is done in runtime._aggregate_metrics()
        # at end_run() time, so no need to update run.error_count here

    def prepare_to_exit_span(
        self,
        id_: str,  # noqa: ARG002
        bound_args: Any = None,  # noqa: ARG002
        instance: Any = None,  # noqa: ARG002
        result: Any = None,  # noqa: ARG002
        **_kwargs: Any,
    ) -> Any:
        """
        Prepare for span exit (required by BaseSpanHandler).

        This is called before end_span to allow any preprocessing.
        We return the result unchanged.

        Args:
            id_: The span ID.
            bound_args: Arguments passed to the function (dict or BoundArguments).
            instance: The LlamaIndex component instance.
            result: The result of the operation.

        Returns:
            The result unchanged.
        """
        return result

    def prepare_to_drop_span(
        self,
        id_: str,  # noqa: ARG002
        bound_args: Any = None,  # noqa: ARG002
        instance: Any = None,  # noqa: ARG002
        err: BaseException | None = None,  # noqa: ARG002
        **_kwargs: Any,
    ) -> Any:
        """
        Prepare for span drop (required by BaseSpanHandler).

        This is called before drop_span to allow any preprocessing.

        Args:
            id_: The span ID.
            bound_args: Arguments passed to the function (dict or BoundArguments).
            instance: The LlamaIndex component instance.
            err: The exception that caused the drop.

        Returns:
            None (no transformation needed).
        """
        return None

    def on_llm_stream(
        self,
        id_: str,
        chunk: str,
        **_kwargs: Any,
    ) -> None:
        """
        Handle streaming token event.

        This can be called during LLM streaming to capture individual tokens.

        Args:
            id_: The span ID for the LLM call.
            chunk: The streaming token/chunk text.
        """
        with self._lock:
            step = self._steps.get(id_)
            if step is not None:
                step.is_streaming = True
                step.streaming_chunks.append(chunk)

    # =========================================================================
    # CallbackManager compatibility methods (LlamaIndex callback protocol)
    # =========================================================================

    def start_trace(self, trace_id: str | None = None) -> None:
        """
        Start a trace (required by LlamaIndex CallbackManager protocol).

        This is a no-op for TraceCraft since we use the span-based tracing.
        The actual tracing happens in new_span/end_span methods.

        Args:
            trace_id: Optional trace identifier.
        """
        pass

    def end_trace(
        self,
        trace_id: str | None = None,
        trace_map: dict[str, list[str]] | None = None,
    ) -> None:
        """
        End a trace (required by LlamaIndex CallbackManager protocol).

        This is a no-op for TraceCraft since we use the span-based tracing.
        The actual tracing happens in new_span/end_span methods.

        Args:
            trace_id: Optional trace identifier.
            trace_map: Optional mapping of trace relationships.
        """
        pass


class TraceCraftLlamaIndexCallback(BaseCallbackHandler):
    """
    LlamaIndex callback handler for use with CallbackManager.

    This handler implements the LlamaIndex callback protocol to capture
    events from LlamaIndex operations as TraceCraft Steps.

    Usage:
        ```python
        from tracecraft.adapters.llamaindex import TraceCraftLlamaIndexCallback
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun
        from llama_index.core import Settings
        from llama_index.core.callbacks import CallbackManager

        handler = TraceCraftLlamaIndexCallback()
        Settings.callback_manager = CallbackManager(handlers=[handler])

        run = AgentRun(name="my_run", start_time=datetime.now(UTC))
        with run_context(run):
            # Your LlamaIndex code here
            llm.complete("Hello")

        # run.steps now contains the trace
        handler.clear()
        ```
    """

    def __init__(self) -> None:
        """Initialize the callback handler."""
        super().__init__(
            event_starts_to_ignore=[],
            event_ends_to_ignore=[],
        )
        # Maps event_id -> Step for tracking in-progress events
        self._steps: dict[str, Step] = {}
        self._lock = threading.Lock()

    def clear(self) -> None:
        """Clear tracked steps to free memory. Call after run completes."""
        with self._lock:
            self._steps.clear()

    def _get_run(self) -> AgentRun | None:
        """Get the current AgentRun from context."""
        return get_current_run()

    def _infer_step_type(self, event_type: Any) -> StepType:
        """Infer StepType from CBEventType."""
        if not _HAS_LLAMAINDEX:
            return StepType.WORKFLOW

        event_str = str(event_type).lower()

        if "llm" in event_str:
            return StepType.LLM
        if "embedding" in event_str:
            return StepType.LLM  # Embeddings are LLM calls
        if "retriev" in event_str:
            return StepType.RETRIEVAL
        if "query" in event_str:
            return StepType.WORKFLOW
        if "agent" in event_str:
            return StepType.AGENT

        return StepType.WORKFLOW

    def start_trace(self, trace_id: str | None = None) -> None:
        """Start a trace."""
        pass  # No-op - we use run_context for trace management

    def end_trace(
        self,
        trace_id: str | None = None,
        trace_map: dict[str, list[str]] | None = None,
    ) -> None:
        """End a trace."""
        pass  # No-op - we use run_context for trace management

    def on_event_start(
        self,
        event_type: Any,
        payload: dict[str, Any] | None = None,
        event_id: str = "",
        parent_id: str = "",
        **kwargs: Any,
    ) -> str:
        """Handle event start."""
        run = self._get_run()
        if run is None:
            return event_id

        step_type = self._infer_step_type(event_type)
        name = str(event_type).replace("CBEventType.", "")

        # Extract inputs from payload
        inputs: dict[str, Any] = {}
        if payload:
            if "messages" in payload:
                inputs["messages"] = str(payload["messages"])[:500]
            if "prompt" in payload:
                inputs["prompt"] = str(payload["prompt"])[:500]
            if "query_str" in payload:
                inputs["query"] = payload["query_str"]
            if "model_dict" in payload:
                model_dict = payload["model_dict"]
                if isinstance(model_dict, dict) and "model" in model_dict:
                    inputs["model"] = model_dict["model"]

        step = Step(
            trace_id=run.id,
            type=step_type,
            name=name,
            start_time=datetime.now(UTC),
            inputs=inputs,
        )

        # Extract model name for LLM steps
        if payload and step_type == StepType.LLM:
            if "model_dict" in payload:
                model_dict = payload["model_dict"]
                if isinstance(model_dict, dict):
                    step.model_name = model_dict.get("model")

        with self._lock:
            self._steps[event_id] = step

            # Handle parent-child relationship
            parent = self._steps.get(parent_id) if parent_id else None
            if parent:
                step.parent_id = parent.id
                parent.children.append(step)
            else:
                run.steps.append(step)

        return event_id

    def on_event_end(
        self,
        event_type: Any,
        payload: dict[str, Any] | None = None,
        event_id: str = "",
        **kwargs: Any,
    ) -> None:
        """Handle event end."""
        with self._lock:
            step = self._steps.pop(event_id, None)

        if step is None:
            return

        end_time = datetime.now(UTC)
        step.end_time = end_time
        step.duration_ms = (end_time - step.start_time).total_seconds() * 1000

        # Extract outputs from payload
        if payload:
            outputs: dict[str, Any] = {}

            if "response" in payload:
                response = payload["response"]
                if hasattr(response, "text"):
                    outputs["text"] = response.text
                elif isinstance(response, str):
                    outputs["text"] = response

            if "completion" in payload:
                completion = payload["completion"]
                if hasattr(completion, "text"):
                    outputs["text"] = completion.text
                elif isinstance(completion, str):
                    outputs["text"] = completion

            # Extract token usage
            if "token_usage" in payload or "usage" in payload:
                usage = payload.get("token_usage") or payload.get("usage", {})
                if isinstance(usage, dict):
                    step.input_tokens = usage.get("prompt_tokens")
                    step.output_tokens = usage.get("completion_tokens")

            # Also check response object for usage
            if "response" in payload:
                response = payload["response"]
                if hasattr(response, "raw") and isinstance(response.raw, dict):
                    raw_usage = response.raw.get("usage", {})
                    if raw_usage:
                        step.input_tokens = raw_usage.get("prompt_tokens")
                        step.output_tokens = raw_usage.get("completion_tokens")

            if outputs:
                step.outputs = outputs


# Backwards compatibility alias
LlamaIndexCallbackHandler = TraceCraftLlamaIndexCallback
