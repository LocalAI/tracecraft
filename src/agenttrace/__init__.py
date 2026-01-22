"""
AgentTrace TAL - Vendor-neutral LLM observability SDK.

Instrument once, observe anywhere.

Example:
    import agenttrace
    agenttrace.init()

    @agenttrace.trace_agent(name="research_agent")
    async def research(query: str) -> str:
        results = await search(query)
        return synthesize(results)

Multi-tenant example with explicit runtime:
    from agenttrace import AgentTraceRuntime, AgentTraceConfig

    # Create tenant-specific runtimes
    tenant_a_runtime = AgentTraceRuntime(config=tenant_a_config)
    tenant_b_runtime = AgentTraceRuntime(config=tenant_b_config)

    # Use context manager for scoped runtime selection
    with tenant_a_runtime.trace_context():
        process_tenant_a_request()

    # Or use explicit runtime parameter in decorators
    @agenttrace.trace_agent(name="agent", runtime=tenant_a_runtime)
    def tenant_a_agent():
        ...
"""

from agenttrace.core.context import runtime_context
from agenttrace.core.models import AgentRun, Step, StepType
from agenttrace.core.runtime import TALRuntime, get_runtime, init
from agenttrace.instrumentation.decorators import (
    step,
    trace_agent,
    trace_llm,
    trace_retrieval,
    trace_tool,
)

# Alias for more descriptive naming
AgentTraceRuntime = TALRuntime

__version__ = "0.1.0"
__all__ = [
    # Core models
    "AgentRun",
    "Step",
    "StepType",
    # Runtime
    "TALRuntime",
    "AgentTraceRuntime",  # Alias
    "init",
    "get_runtime",
    "runtime_context",
    # Decorators
    "trace_agent",
    "trace_tool",
    "trace_llm",
    "trace_retrieval",
    "step",
    # Adapters (lazy loaded)
    "ClaudeAgentTracer",
    # Version
    "__version__",
]


def __getattr__(name: str):
    """Lazy load adapters to avoid import overhead."""
    if name == "ClaudeAgentTracer":
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        return ClaudeAgentTracer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
