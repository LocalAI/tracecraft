"""
OpenInference attribute mapping (for Arize Phoenix compatibility).

Maps TraceCraft Step attributes to OpenInference semantic conventions.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tracecraft.core.models import Step


class OpenInferenceMapper:
    """
    Maps Step attributes to OpenInference semantic conventions.

    Follows the OpenInference spec for compatibility with Arize Phoenix.
    See: https://github.com/Arize-ai/openinference
    """

    def map_step(self, step: Step) -> dict[str, Any]:
        """
        Map a Step to OpenInference attributes.

        Args:
            step: The Step to map.

        Returns:
            Dictionary of OpenInference attributes.
        """
        from tracecraft.core.models import StepType

        attrs: dict[str, Any] = {}

        # Input/Output (applies to all step types)
        if step.inputs:
            attrs["input.value"] = self._serialize_value(step.inputs)

        if step.outputs:
            attrs["output.value"] = self._serialize_value(step.outputs)

        # Type-specific attributes
        if step.type == StepType.LLM:
            self._map_llm_attrs(step, attrs)
        elif step.type == StepType.TOOL:
            self._map_tool_attrs(step, attrs)
        elif step.type == StepType.RETRIEVAL:
            self._map_retrieval_attrs(step, attrs)

        return attrs

    def _map_llm_attrs(self, step: Step, attrs: dict[str, Any]) -> None:
        """Map LLM-specific attributes."""
        # Model name
        if step.model_name:
            attrs["llm.model_name"] = step.model_name

        # Token counts
        if step.input_tokens is not None:
            attrs["llm.token_count.prompt"] = step.input_tokens

        if step.output_tokens is not None:
            attrs["llm.token_count.completion"] = step.output_tokens

        if step.input_tokens is not None and step.output_tokens is not None:
            attrs["llm.token_count.total"] = step.input_tokens + step.output_tokens

        # Provider
        if step.model_provider:
            attrs["llm.provider"] = step.model_provider

    def _map_tool_attrs(self, step: Step, attrs: dict[str, Any]) -> None:
        """Map tool-specific attributes."""
        attrs["tool.name"] = step.name

        if step.inputs:
            attrs["tool.parameters"] = self._serialize_value(step.inputs)

    def _map_retrieval_attrs(self, step: Step, attrs: dict[str, Any]) -> None:
        """Map retrieval-specific attributes."""
        # Query
        if step.inputs and "query" in step.inputs:
            attrs["retrieval.query"] = step.inputs["query"]

        # Documents
        if step.outputs:
            docs = step.outputs.get("documents") or step.outputs.get("results")
            if docs:
                attrs["retrieval.documents"] = self._serialize_value(docs)

    def _serialize_value(self, value: Any) -> str:
        """Serialize a value to JSON string if needed."""
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value)
        except (TypeError, ValueError):
            return str(value)
