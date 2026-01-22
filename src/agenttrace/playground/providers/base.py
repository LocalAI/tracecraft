"""
Base provider interface for LLM replay.

Defines the contract that all replay providers must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agenttrace.core.models import Step


@dataclass
class ReplayResult:
    """Result from replaying an LLM call."""

    output: str
    """The generated output text."""

    raw_response: dict[str, Any] = field(default_factory=dict)
    """Raw response from the LLM API."""

    input_tokens: int = 0
    """Number of input tokens used."""

    output_tokens: int = 0
    """Number of output tokens generated."""

    duration_ms: float = 0.0
    """Time taken for the call in milliseconds."""

    model: str = ""
    """Model used for the call."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    """When the replay was executed."""

    error: str | None = None
    """Error message if the call failed."""

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens

    @property
    def succeeded(self) -> bool:
        """Whether the replay succeeded."""
        return self.error is None


class BaseReplayProvider(ABC):
    """
    Base class for LLM replay providers.

    Each provider implements replay logic for a specific LLM API
    (OpenAI, Anthropic, etc.).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'openai', 'anthropic')."""
        ...

    @property
    @abstractmethod
    def supported_models(self) -> list[str]:
        """List of model name patterns this provider supports."""
        ...

    def can_replay(self, step: Step) -> bool:
        """
        Check if this provider can replay the given step.

        Args:
            step: The step to check.

        Returns:
            True if this provider can replay the step.
        """
        if not step.model_name:
            return False

        model_lower = step.model_name.lower()
        return any(pattern.lower() in model_lower for pattern in self.supported_models)

    @abstractmethod
    async def replay(
        self,
        step: Step,
        modified_prompt: str | None = None,
        **kwargs: Any,
    ) -> ReplayResult:
        """
        Replay an LLM call from a traced step.

        Args:
            step: The traced step to replay.
            modified_prompt: Optional modified system/user prompt.
            **kwargs: Additional provider-specific arguments.

        Returns:
            ReplayResult with the output and metadata.
        """
        ...

    def _extract_messages(self, step: Step) -> list[dict[str, Any]]:
        """
        Extract messages from step inputs.

        Args:
            step: The step to extract from.

        Returns:
            List of message dicts with 'role' and 'content'.
        """
        inputs = step.inputs or {}

        # Try common input formats
        if "messages" in inputs:
            return inputs["messages"]
        if "prompt" in inputs:
            return [{"role": "user", "content": inputs["prompt"]}]
        if "input" in inputs:
            return [{"role": "user", "content": inputs["input"]}]

        # Try to construct from system/user prompts
        messages = []
        if "system_prompt" in inputs or "system" in inputs:
            system = inputs.get("system_prompt") or inputs.get("system")
            messages.append({"role": "system", "content": system})
        if "user_prompt" in inputs or "user" in inputs or "query" in inputs:
            user = inputs.get("user_prompt") or inputs.get("user") or inputs.get("query")
            messages.append({"role": "user", "content": user})

        return messages

    def _extract_model_params(self, step: Step) -> dict[str, Any]:
        """
        Extract model parameters from step inputs.

        Args:
            step: The step to extract from.

        Returns:
            Dict of model parameters (temperature, max_tokens, etc.).
        """
        inputs = step.inputs or {}
        params = {}

        # Common parameters
        param_keys = [
            "temperature",
            "max_tokens",
            "top_p",
            "frequency_penalty",
            "presence_penalty",
            "stop",
            "seed",
        ]

        for key in param_keys:
            if key in inputs:
                params[key] = inputs[key]

        return params
