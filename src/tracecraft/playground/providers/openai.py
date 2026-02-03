"""
OpenAI replay provider.

Replays traced OpenAI API calls with optional prompt modifications.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from tracecraft.playground.providers.base import BaseReplayProvider, ReplayResult

if TYPE_CHECKING:
    from tracecraft.core.models import Step


class OpenAIReplayProvider(BaseReplayProvider):
    """
    Replay provider for OpenAI API calls.

    Supports GPT-4, GPT-3.5, and other OpenAI models.

    Example:
        from tracecraft.playground.providers import OpenAIReplayProvider

        provider = OpenAIReplayProvider()
        result = await provider.replay(step)
        print(result.output)
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        organization: str | None = None,
    ) -> None:
        """
        Initialize the OpenAI replay provider.

        Args:
            api_key: OpenAI API key. If not provided, uses OPENAI_API_KEY env var.
            base_url: Optional base URL for API calls.
            organization: Optional organization ID.
        """
        self._api_key = api_key
        self._base_url = base_url
        self._organization = organization
        self._client: Any = None

    @property
    def name(self) -> str:
        return "openai"

    @property
    def supported_models(self) -> list[str]:
        return [
            "gpt-4",
            "gpt-3.5",
            "gpt-4o",
            "gpt-4-turbo",
            "o1",
            "o1-mini",
            "o1-preview",
            "chatgpt",
        ]

    def _get_client(self) -> Any:
        """Get or create the OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise ImportError("openai package required. Install with: pip install openai")

            kwargs: dict[str, Any] = {}
            if self._api_key:
                kwargs["api_key"] = self._api_key
            if self._base_url:
                kwargs["base_url"] = self._base_url
            if self._organization:
                kwargs["organization"] = self._organization

            self._client = AsyncOpenAI(**kwargs)

        return self._client

    async def replay(
        self,
        step: Step,
        modified_prompt: str | None = None,
        **kwargs: Any,
    ) -> ReplayResult:
        """
        Replay an OpenAI call from a traced step.

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
            # Extract messages from step
            messages = self._extract_messages(step)

            # Apply modified prompt if provided
            if modified_prompt is not None:
                messages = self._apply_modified_prompt(messages, modified_prompt)

            # Extract model parameters
            params = self._extract_model_params(step)
            params.update(kwargs)

            # Get model name
            model = step.model_name or "gpt-4o"

            # Make the API call
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                **params,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000

            # Extract output
            output = response.choices[0].message.content or ""

            # Extract token usage
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0

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

    def _apply_modified_prompt(
        self,
        messages: list[dict[str, Any]],
        modified_prompt: str,
    ) -> list[dict[str, Any]]:
        """
        Apply a modified prompt to the messages.

        If a system message exists, replaces it. Otherwise, prepends one.
        """
        messages = [m.copy() for m in messages]

        # Find and replace system message
        for i, msg in enumerate(messages):
            if msg.get("role") == "system":
                messages[i]["content"] = modified_prompt
                return messages

        # No system message found, prepend one
        messages.insert(0, {"role": "system", "content": modified_prompt})
        return messages
