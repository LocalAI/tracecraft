"""
Replay providers for different LLM backends.

Each provider knows how to replay calls to a specific LLM API.
"""

from __future__ import annotations

from tracecraft.playground.providers.anthropic import AnthropicReplayProvider
from tracecraft.playground.providers.base import BaseReplayProvider, ReplayResult
from tracecraft.playground.providers.openai import OpenAIReplayProvider

__all__ = [
    "BaseReplayProvider",
    "ReplayResult",
    "OpenAIReplayProvider",
    "AnthropicReplayProvider",
]
