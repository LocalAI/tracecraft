"""Framework adapters for LangChain, LlamaIndex, PydanticAI, Guardrails, Claude SDK, etc."""

from agenttrace.adapters.claude_sdk import ClaudeAgentTracer
from agenttrace.adapters.guardrails import (
    guardrail_step,
    record_validation_result,
    track_validation,
    wrap_guard,
)
from agenttrace.adapters.langchain import AgentTraceCallbackHandler
from agenttrace.adapters.llamaindex import AgentTraceSpanHandler
from agenttrace.adapters.pydantic_ai import AgentTraceSpanProcessor

__all__ = [
    # LangChain
    "AgentTraceCallbackHandler",
    # LlamaIndex
    "AgentTraceSpanHandler",
    # PydanticAI
    "AgentTraceSpanProcessor",
    # Claude SDK
    "ClaudeAgentTracer",
    # Guardrails
    "guardrail_step",
    "track_validation",
    "record_validation_result",
    "wrap_guard",
]
