"""
OTel GenAI v1.37+ attribute mapping.

Maps AgentTrace Step attributes to OpenTelemetry GenAI semantic conventions.
Supports both LLM and Agent step types with content recording options.

See:
- https://opentelemetry.io/docs/specs/semconv/gen-ai/
- https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agenttrace.core.models import Step


class OTelGenAIMapper:
    """
    Maps Step attributes to OTel GenAI semantic conventions.

    Follows the OpenTelemetry GenAI semantic conventions v1.37+.
    Supports:
    - LLM steps with model info, tokens, and costs
    - Agent steps with agent identity attributes
    - Optional content recording for prompts/responses

    Usage:
        ```python
        mapper = OTelGenAIMapper()

        # Basic mapping (no content recording)
        attrs = mapper.map_step(step)

        # With content recording enabled
        attrs = mapper.map_step(step, enable_content_recording=True)
        ```
    """

    def __init__(self) -> None:
        """Initialize the mapper."""
        pass

    def map_step(
        self,
        step: Step,
        enable_content_recording: bool = False,
    ) -> dict[str, Any]:
        """
        Map a Step to OTel GenAI attributes.

        Args:
            step: The Step to map.
            enable_content_recording: Whether to record prompt/response content.
                Disabled by default for privacy.

        Returns:
            Dictionary of OTel GenAI attributes.
        """
        from agenttrace.core.models import StepType

        attrs: dict[str, Any] = {}

        # Map agent steps
        if step.type == StepType.AGENT:
            attrs.update(self._map_agent_attrs(step))

        # Map LLM steps
        if step.type == StepType.LLM:
            attrs.update(self._map_llm_attrs(step))

        # Content recording (opt-in for privacy)
        if enable_content_recording:
            attrs.update(self._map_content_attrs(step))

        return attrs

    def _map_agent_attrs(self, step: Step) -> dict[str, Any]:
        """
        Map agent-specific attributes.

        Following OTel GenAI Agent Semantic Conventions:
        - gen_ai.agent.name: Human-readable agent name
        - gen_ai.agent.id: Unique agent identifier
        - gen_ai.agent.description: Free-form description
        - gen_ai.operation.name: "invoke_agent" for agent steps
        """
        attrs: dict[str, Any] = {}

        # gen_ai.agent.name (use step name)
        attrs["gen_ai.agent.name"] = step.name

        # gen_ai.agent.id (from step attributes if available)
        if step.attributes.get("agent_id"):
            attrs["gen_ai.agent.id"] = step.attributes["agent_id"]

        # gen_ai.agent.description (from step attributes if available)
        if step.attributes.get("agent_description"):
            attrs["gen_ai.agent.description"] = step.attributes["agent_description"]

        # gen_ai.operation.name for agent steps
        attrs["gen_ai.operation.name"] = "invoke_agent"

        return attrs

    def _map_llm_attrs(self, step: Step) -> dict[str, Any]:
        """
        Map LLM-specific attributes.

        Following OTel GenAI Semantic Conventions:
        - gen_ai.request.model: Model name
        - gen_ai.system: Provider (openai, anthropic, etc.)
        - gen_ai.operation.name: Operation type (chat, embeddings, etc.)
        - gen_ai.usage.input_tokens: Input token count
        - gen_ai.usage.output_tokens: Output token count
        - gen_ai.usage.cost: USD cost
        """
        attrs: dict[str, Any] = {}

        # gen_ai.request.model
        if step.model_name:
            attrs["gen_ai.request.model"] = step.model_name

        # gen_ai.system (provider)
        if step.model_provider:
            attrs["gen_ai.system"] = step.model_provider

        # gen_ai.operation.name
        attrs["gen_ai.operation.name"] = self._infer_operation_name(step)

        # Token counts
        if step.input_tokens is not None:
            attrs["gen_ai.usage.input_tokens"] = step.input_tokens

        if step.output_tokens is not None:
            attrs["gen_ai.usage.output_tokens"] = step.output_tokens

        # Cost (if available)
        if step.cost_usd is not None:
            attrs["gen_ai.usage.cost"] = step.cost_usd

        return attrs

    def _map_content_attrs(self, step: Step) -> dict[str, Any]:
        """
        Map content recording attributes.

        Only called when enable_content_recording=True.
        Records prompt and response content for debugging.

        WARNING: This may contain sensitive data. Only enable in
        development/debugging scenarios or when data handling
        policies allow it.
        """
        attrs: dict[str, Any] = {}

        # gen_ai.request.messages (input content)
        if step.inputs:
            attrs["gen_ai.request.messages"] = self._serialize_messages(step.inputs)

        # gen_ai.response.messages (output content)
        if step.outputs:
            attrs["gen_ai.response.messages"] = self._serialize_messages(step.outputs)

        return attrs

    def _serialize_messages(self, data: dict[str, Any]) -> str:
        """
        Serialize message data to JSON string.

        Args:
            data: Dictionary of message data.

        Returns:
            JSON string representation.
        """
        try:
            return json.dumps(data, default=str)
        except (TypeError, ValueError):
            # Fallback for non-serializable data
            return str(data)

    def _infer_operation_name(self, step: Step) -> str:
        """
        Infer the GenAI operation name from the step.

        Args:
            step: The Step to analyze.

        Returns:
            Operation name string (chat, embeddings, image_generation).
        """
        name_lower = step.name.lower()

        if "chat" in name_lower or "completion" in name_lower:
            return "chat"
        if "embed" in name_lower:
            return "embeddings"
        if "image" in name_lower or "vision" in name_lower:
            return "image_generation"

        return "chat"  # Default to chat
