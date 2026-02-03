"""Instrumentation components for TraceCraft."""

from tracecraft.instrumentation.decorators import (
    step,
    trace_agent,
    trace_llm,
    trace_llm_stream,
    trace_retrieval,
    trace_stream,
    trace_tool,
)

# Auto-instrumentation - lazy import to avoid requiring provider SDKs
# Use: from tracecraft.instrumentation.auto import enable_auto_instrumentation

__all__ = [
    # Core decorators
    "trace_agent",
    "trace_tool",
    "trace_llm",
    "trace_retrieval",
    # Streaming decorators
    "trace_llm_stream",
    "trace_stream",
    # Context manager
    "step",
]
