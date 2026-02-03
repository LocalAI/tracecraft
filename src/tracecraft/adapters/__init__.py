"""Framework adapters for LangChain, LlamaIndex, PydanticAI, Guardrails, Claude SDK, etc."""

from tracecraft.adapters.claude_sdk import ClaudeTraceCraftr
from tracecraft.adapters.guardrails import (
    guardrail_step,
    record_validation_result,
    track_validation,
    wrap_guard,
)
from tracecraft.adapters.langchain import TraceCraftCallbackHandler
from tracecraft.adapters.llamaindex import TraceCraftSpanHandler
from tracecraft.adapters.pydantic_ai import TraceCraftSpanProcessor

__all__ = [
    # LangChain
    "TraceCraftCallbackHandler",
    # LlamaIndex
    "TraceCraftSpanHandler",
    # PydanticAI
    "TraceCraftSpanProcessor",
    # Claude SDK
    "ClaudeTraceCraftr",
    # Guardrails
    "guardrail_step",
    "track_validation",
    "record_validation_result",
    "wrap_guard",
]
