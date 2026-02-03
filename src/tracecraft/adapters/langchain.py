"""
LangChain callback handler adapter.

Provides TraceCraftCallbackHandler that integrates LangChain with TraceCraft
for unified observability.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from tracecraft.core.context import get_current_run
from tracecraft.core.models import Step, StepType

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun

# Try to import BaseCallbackHandler for proper inheritance
try:
    from langchain_core.callbacks import BaseCallbackHandler

    _HAS_LANGCHAIN = True
except ImportError:
    # Fallback: create a stub base class for when langchain is not installed
    class BaseCallbackHandler:  # type: ignore[no-redef]
        """Stub base class when langchain is not installed."""

        pass

    _HAS_LANGCHAIN = False


class TraceCraftCallbackHandler(BaseCallbackHandler):
    """
    LangChain callback handler that creates TraceCraft Steps.

    This handler implements the LangChain callback protocol to capture
    chain, LLM, tool, and retriever events as TraceCraft Steps.

    Usage:
        ```python
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler
        from tracecraft.core.context import run_context
        from tracecraft.core.models import AgentRun

        handler = TraceCraftCallbackHandler()
        run = AgentRun(name="my_run", start_time=datetime.now(UTC))

        with run_context(run):
            chain.invoke({"query": "hello"}, config={"callbacks": [handler]})

        # run.steps now contains the trace
        # Call clear() when done to free memory
        handler.clear()
        ```
    """

    def __init__(self) -> None:
        """Initialize the callback handler."""
        super().__init__()
        # Maps run_id -> Step for tracking in-progress operations
        self._steps: dict[UUID, Step] = {}
        self._lock = threading.Lock()

    def clear(self) -> None:
        """Clear tracked steps to free memory. Call after run completes."""
        with self._lock:
            self._steps.clear()

    def _register_step(self, run_id: UUID, step: Step) -> None:
        """Register a step in the tracking dict (thread-safe)."""
        with self._lock:
            self._steps[run_id] = step

    def _get_step(self, run_id: UUID) -> Step | None:
        """Get a step from the tracking dict (thread-safe)."""
        with self._lock:
            return self._steps.get(run_id)

    def _get_run(self) -> AgentRun | None:
        """Get the current AgentRun from context."""
        return get_current_run()

    def _get_name(self, serialized: dict[str, Any] | None) -> str:
        """Extract name from serialized dict."""
        if serialized is None:
            return "unknown"
        # Try name field first
        if name := serialized.get("name"):
            return str(name)
        # Try extracting from id list (e.g., ["langchain", "chains", "RetrievalQA"])
        id_list = serialized.get("id")
        if isinstance(id_list, list) and id_list:
            return str(id_list[-1])
        return "unknown"

    def _add_step_to_run(self, step: Step, parent_run_id: UUID | None = None) -> None:
        """Add a step to the current run, handling hierarchy (thread-safe)."""
        run = self._get_run()
        if run is None:
            return

        # Hold lock during entire operation to ensure thread-safety
        # for both parent lookup and list append operations
        with self._lock:
            parent = self._steps.get(parent_run_id) if parent_run_id else None
            if parent:
                step.parent_id = parent.id
                parent.children.append(step)
            else:
                run.steps.append(step)

    def _complete_step(
        self,
        run_id: UUID,
        outputs: dict[str, Any] | None = None,
        error: BaseException | None = None,
    ) -> None:
        """Complete a step with outputs or error."""
        with self._lock:
            step = self._steps.pop(run_id, None)
        if step is None:
            return

        end_time = datetime.now(UTC)
        step.end_time = end_time
        step.duration_ms = (end_time - step.start_time).total_seconds() * 1000

        if outputs:
            step.outputs = outputs
        else:
            step.outputs = {}

        if error:
            step.error = str(error)
            step.error_type = type(error).__name__
            # Note: Error aggregation is done in runtime._aggregate_metrics()
            # at end_run() time, so no need to update run.error_count here

    # ============================================================
    # Chain callbacks
    # ============================================================

    def on_chain_start(
        self,
        serialized: dict[str, Any] | None,
        inputs: dict[str, Any] | None,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **_kwargs: Any,
    ) -> None:
        """Handle chain start event."""
        run = self._get_run()
        if run is None:
            return

        step = Step(
            trace_id=run.id,
            type=StepType.WORKFLOW,
            name=self._get_name(serialized),
            start_time=datetime.now(UTC),
            inputs=inputs or {},
        )
        self._register_step(run_id, step)
        self._add_step_to_run(step, parent_run_id)

    def _make_serializable(self, obj: Any) -> Any:
        """Convert an object to a JSON-serializable form."""
        if obj is None:
            return None
        if isinstance(obj, str | int | float | bool):
            return obj
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        if isinstance(obj, list | tuple):
            return [self._make_serializable(item) for item in obj]
        # For unknown types, convert to string representation
        try:
            # Try to get a useful string representation
            return str(obj)
        except Exception:
            return f"<{type(obj).__name__}>"

    def on_chain_end(
        self,
        outputs: dict[str, Any] | None,
        *,
        run_id: UUID,
        **_kwargs: Any,
    ) -> None:
        """Handle chain end event."""
        # Make outputs serializable to handle LangGraph-specific types
        serializable_outputs = self._make_serializable(outputs) if outputs else {}
        # Ensure outputs is always a dict (Step.outputs requires dict[str, Any])
        if not isinstance(serializable_outputs, dict):
            serializable_outputs = {"output": serializable_outputs}
        self._complete_step(run_id, outputs=serializable_outputs)

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **_kwargs: Any,
    ) -> None:
        """Handle chain error event."""
        self._complete_step(run_id, error=error)

    # ============================================================
    # LLM callbacks
    # ============================================================

    def on_llm_start(
        self,
        serialized: dict[str, Any] | None,
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        invocation_params: dict[str, Any] | None = None,
        **_kwargs: Any,
    ) -> None:
        """Handle LLM start event."""
        run = self._get_run()
        if run is None:
            return

        model_name = None
        if invocation_params:
            model_name = invocation_params.get("model_name") or invocation_params.get("model")

        step = Step(
            trace_id=run.id,
            type=StepType.LLM,
            name=self._get_name(serialized),
            start_time=datetime.now(UTC),
            inputs={"prompts": prompts},
            model_name=model_name,
        )
        self._register_step(run_id, step)
        self._add_step_to_run(step, parent_run_id)

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: UUID,
        **_kwargs: Any,
    ) -> None:
        """Handle LLM end event."""
        step = self._get_step(run_id)
        if step is None:
            return

        outputs: dict[str, Any] = {}

        # Extract text from generations
        if hasattr(response, "generations") and response.generations:
            first_gen = response.generations[0]
            if first_gen and hasattr(first_gen[0], "text"):
                outputs["text"] = first_gen[0].text

        # Extract token counts
        if hasattr(response, "llm_output") and response.llm_output:
            token_usage = response.llm_output.get("token_usage")
            if token_usage:
                prompt_tokens = token_usage.get("prompt_tokens")
                completion_tokens = token_usage.get("completion_tokens")

                if prompt_tokens is not None:
                    step.input_tokens = prompt_tokens
                if completion_tokens is not None:
                    step.output_tokens = completion_tokens

                # Note: Token aggregation is done in runtime._aggregate_metrics()
                # at end_run() time, so no need to update run.total_tokens here

        self._complete_step(run_id, outputs=outputs)

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **_kwargs: Any,
    ) -> None:
        """Handle LLM error event."""
        self._complete_step(run_id, error=error)

    # ============================================================
    # Chat model callbacks
    # ============================================================

    def on_chat_model_start(
        self,
        serialized: dict[str, Any] | None,
        messages: list[list[Any]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        invocation_params: dict[str, Any] | None = None,
        **_kwargs: Any,
    ) -> None:
        """Handle chat model start event."""
        run = self._get_run()
        if run is None:
            return

        model_name = None
        if invocation_params:
            model_name = invocation_params.get("model_name") or invocation_params.get("model")

        # Convert messages to serializable format
        serialized_messages: list[list[dict[str, Any] | str]] = []
        for message_list in messages:
            msg_batch: list[dict[str, Any] | str] = []
            for msg in message_list:
                if hasattr(msg, "type") and hasattr(msg, "content"):
                    msg_batch.append({"type": msg.type, "content": msg.content})
                else:
                    msg_batch.append(str(msg))
            serialized_messages.append(msg_batch)

        step = Step(
            trace_id=run.id,
            type=StepType.LLM,
            name=self._get_name(serialized),
            start_time=datetime.now(UTC),
            inputs={"messages": serialized_messages},
            model_name=model_name,
        )
        self._register_step(run_id, step)
        self._add_step_to_run(step, parent_run_id)

    # ============================================================
    # Tool callbacks
    # ============================================================

    def _extract_tool_schema(self, serialized: dict[str, Any] | None) -> dict[str, Any] | None:
        """Extract tool schema from serialized tool data."""
        if serialized is None:
            return None
        schema: dict[str, Any] = {}

        # Try to get description
        if "description" in serialized:
            schema["description"] = serialized["description"]

        # Try to get args_schema from serialized tool
        if "args_schema" in serialized:
            args_schema = serialized["args_schema"]
            if isinstance(args_schema, dict):
                schema["args_schema"] = args_schema
            elif hasattr(args_schema, "schema"):
                # Pydantic model
                schema["args_schema"] = args_schema.schema()

        # Try to get args from tool definition
        if "args" in serialized:
            schema["args"] = serialized["args"]

        # Try to get return type
        if "return_type" in serialized:
            schema["return_type"] = serialized["return_type"]

        # Try to get function signature if available
        if "func" in serialized and callable(serialized["func"]):
            func = serialized["func"]
            if hasattr(func, "__doc__") and func.__doc__:
                schema["docstring"] = func.__doc__

        return schema if schema else None

    def on_tool_start(
        self,
        serialized: dict[str, Any] | None,
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **_kwargs: Any,
    ) -> None:
        """Handle tool start event."""
        run = self._get_run()
        if run is None:
            return

        # Build inputs dict with tool input and optional schema
        inputs: dict[str, Any] = {"input": input_str}

        # Extract and include tool schema if available
        tool_schema = self._extract_tool_schema(serialized)
        if tool_schema:
            inputs["tool_schema"] = tool_schema

        step = Step(
            trace_id=run.id,
            type=StepType.TOOL,
            name=self._get_name(serialized),
            start_time=datetime.now(UTC),
            inputs=inputs,
        )
        self._register_step(run_id, step)
        self._add_step_to_run(step, parent_run_id)

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        **_kwargs: Any,
    ) -> None:
        """Handle tool end event."""
        self._complete_step(run_id, outputs={"output": output})

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **_kwargs: Any,
    ) -> None:
        """Handle tool error event."""
        self._complete_step(run_id, error=error)

    # ============================================================
    # Retriever callbacks
    # ============================================================

    def on_retriever_start(
        self,
        serialized: dict[str, Any] | None,
        query: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **_kwargs: Any,
    ) -> None:
        """Handle retriever start event."""
        run = self._get_run()
        if run is None:
            return

        step = Step(
            trace_id=run.id,
            type=StepType.RETRIEVAL,
            name=self._get_name(serialized),
            start_time=datetime.now(UTC),
            inputs={"query": query},
        )
        self._register_step(run_id, step)
        self._add_step_to_run(step, parent_run_id)

    def on_retriever_end(
        self,
        documents: list[Any],
        *,
        run_id: UUID,
        **_kwargs: Any,
    ) -> None:
        """Handle retriever end event."""
        # Convert documents to serializable format
        serialized_docs: list[dict[str, Any] | str] = []
        for doc in documents:
            if hasattr(doc, "page_content"):
                doc_dict: dict[str, Any] = {"content": doc.page_content}
                if hasattr(doc, "metadata"):
                    doc_dict["metadata"] = doc.metadata
                serialized_docs.append(doc_dict)
            else:
                serialized_docs.append(str(doc))

        self._complete_step(run_id, outputs={"documents": serialized_docs})

    def on_retriever_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **_kwargs: Any,
    ) -> None:
        """Handle retriever error event."""
        self._complete_step(run_id, error=error)

    # ============================================================
    # Agent callbacks
    # ============================================================

    def on_agent_action(
        self,
        action: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **_kwargs: Any,
    ) -> None:
        """Handle agent action event."""
        run = self._get_run()
        if run is None:
            return

        inputs: dict[str, Any] = {}
        if hasattr(action, "tool"):
            inputs["tool"] = action.tool
        if hasattr(action, "tool_input"):
            inputs["tool_input"] = action.tool_input
        if hasattr(action, "log"):
            inputs["log"] = action.log

        step = Step(
            trace_id=run.id,
            type=StepType.AGENT,
            name="agent_action",
            start_time=datetime.now(UTC),
            inputs=inputs,
        )
        self._register_step(run_id, step)
        self._add_step_to_run(step, parent_run_id)

    def on_agent_finish(
        self,
        finish: Any,
        *,
        run_id: UUID,
        **_kwargs: Any,
    ) -> None:
        """Handle agent finish event."""
        outputs: dict[str, Any] = {}
        if hasattr(finish, "return_values"):
            outputs["return_values"] = finish.return_values
        if hasattr(finish, "log"):
            outputs["log"] = finish.log

        self._complete_step(run_id, outputs=outputs)

    # ============================================================
    # Text callbacks (no-ops for now)
    # ============================================================

    def on_text(
        self,
        text: str,
        *,
        run_id: UUID,
        **_kwargs: Any,
    ) -> None:
        """Handle text event (no-op)."""
        pass

    def on_llm_new_token(
        self,
        token: str,
        *,
        run_id: UUID,
        **_kwargs: Any,
    ) -> None:
        """Handle streaming token event."""
        with self._lock:
            step = self._steps.get(run_id)
            if step is not None:
                step.is_streaming = True
                step.streaming_chunks.append(token)
