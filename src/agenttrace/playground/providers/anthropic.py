"""
Anthropic replay provider.

Replays traced Anthropic API calls with optional prompt modifications.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from agenttrace.playground.providers.base import BaseReplayProvider, ReplayResult

if TYPE_CHECKING:
    from agenttrace.core.models import Step


class AnthropicReplayProvider(BaseReplayProvider):
    """
    Replay provider for Anthropic API calls.

    Supports Claude 3.x and Claude 4.x models.

    Example:
        from agenttrace.playground.providers import AnthropicReplayProvider

        provider = AnthropicReplayProvider()
        result = await provider.replay(step)
        print(result.output)
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """
        Initialize the Anthropic replay provider.

        Args:
            api_key: Anthropic API key. If not provided, uses ANTHROPIC_API_KEY env var.
            base_url: Optional base URL for API calls.
        """
        self._api_key = api_key
        self._base_url = base_url
        self._client: Any = None

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def supported_models(self) -> list[str]:
        return [
            "claude-3",
            "claude-3.5",
            "claude-opus",
            "claude-sonnet",
            "claude-haiku",
            "claude-4",
        ]

    def _get_client(self) -> Any:
        """Get or create the Anthropic client."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
            except ImportError:
                raise ImportError("anthropic package required. Install with: pip install anthropic")

            kwargs: dict[str, Any] = {}
            if self._api_key:
                kwargs["api_key"] = self._api_key
            if self._base_url:
                kwargs["base_url"] = self._base_url

            self._client = AsyncAnthropic(**kwargs)

        return self._client

    async def replay(
        self,
        step: Step,
        modified_prompt: str | None = None,
        **kwargs: Any,
    ) -> ReplayResult:
        """
        Replay an Anthropic call from a traced step.

        Args:
            step: The traced step to replay.
            modified_prompt: Optional modified system prompt to use.
            **kwargs: Additional arguments passed to the API.

        Returns:
            ReplayResult with output and metadata.
        """
        client = self._get_client()
        start_time = time.perf_counter()

        try:
            # Extract messages and system prompt
            messages, system_prompt = self._extract_anthropic_messages(step)

            # Apply modified prompt if provided
            if modified_prompt is not None:
                system_prompt = modified_prompt

            # Extract model parameters
            params = self._extract_model_params(step)
            params.update(kwargs)

            # Get model name
            model = step.model_name or "claude-sonnet-4-20250514"

            # Ensure max_tokens is set (required by Anthropic)
            if "max_tokens" not in params:
                params["max_tokens"] = 4096

            # Build API call kwargs
            api_kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                **params,
            }
            if system_prompt:
                api_kwargs["system"] = system_prompt

            # Make the API call
            response = await client.messages.create(**api_kwargs)

            duration_ms = (time.perf_counter() - start_time) * 1000

            # Extract output
            output = ""
            for block in response.content:
                if hasattr(block, "text"):
                    output += block.text

            # Extract token usage
            usage = response.usage
            input_tokens = usage.input_tokens if usage else 0
            output_tokens = usage.output_tokens if usage else 0

            return ReplayResult(
                output=output,
                raw_response=response.model_dump(),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=duration_ms,
                model=model,
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ReplayResult(
                output="",
                duration_ms=duration_ms,
                model=step.model_name or "unknown",
                error=str(e),
            )

    def _extract_anthropic_messages(
        self,
        step: Step,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Extract messages in Anthropic format.

        Anthropic uses a separate 'system' parameter, not a system message.

        Returns:
            Tuple of (messages, system_prompt).
        """
        inputs = step.inputs or {}
        system_prompt = None
        messages = []

        # Check for direct Anthropic format
        if "system" in inputs:
            system_prompt = inputs["system"]

        # Extract messages
        if "messages" in inputs:
            raw_messages = inputs["messages"]
            for msg in raw_messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                # Anthropic doesn't use 'system' role in messages
                if role == "system":
                    system_prompt = content
                else:
                    messages.append({"role": role, "content": content})
        else:
            # Try to construct from common formats
            if "system_prompt" in inputs:
                system_prompt = inputs["system_prompt"]

            user_content = (
                inputs.get("prompt")
                or inputs.get("user_prompt")
                or inputs.get("user")
                or inputs.get("query")
                or inputs.get("input")
            )
            if user_content:
                messages.append({"role": "user", "content": user_content})

        return messages, system_prompt
