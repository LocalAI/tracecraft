"""
TraceCraft - Vendor-neutral LLM observability SDK.

Instrument once, observe anywhere.

Example:
    import tracecraft
    tracecraft.init()

    @tracecraft.trace_agent(name="research_agent")
    async def research(query: str) -> str:
        results = await search(query)
        return synthesize(results)

Zero-code auto-instrumentation example:
    import tracecraft
    tracecraft.init(auto_instrument=True)

    # Now all LLM calls (OpenAI, Anthropic) and frameworks
    # (LangChain, LlamaIndex) are automatically traced!
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI()
    llm.invoke("Hello!")  # Automatically traced!

Multi-tenant example with explicit runtime:
    from tracecraft import TraceCraftRuntime, TraceCraftConfig

    # Create tenant-specific runtimes
    tenant_a_runtime = TraceCraftRuntime(config=tenant_a_config)
    tenant_b_runtime = TraceCraftRuntime(config=tenant_b_config)

    # Use context manager for scoped runtime selection
    with tenant_a_runtime.trace_context():
        process_tenant_a_request()

    # Or use explicit runtime parameter in decorators
    @tracecraft.trace_agent(name="agent", runtime=tenant_a_runtime)
    def tenant_a_agent():
        ...
"""

from tracecraft.core.config import TraceCraftConfig
from tracecraft.core.context import runtime_context
from tracecraft.core.models import AgentRun, Step, StepType
from tracecraft.core.runtime import TALRuntime, get_runtime, init
from tracecraft.instrumentation.decorators import (
    step,
    trace_agent,
    trace_llm,
    trace_retrieval,
    trace_tool,
)

# Alias for more descriptive naming
TraceCraftRuntime = TALRuntime

__version__ = "0.2.1"
__all__ = [
    # Core models
    "AgentRun",
    "Step",
    "StepType",
    # Configuration
    "TraceCraftConfig",
    # Runtime
    "TALRuntime",
    "TraceCraftRuntime",  # Alias
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
    "ClaudeTraceCraftr",
    # Version
    "__version__",
]


def __getattr__(name: str):
    """Lazy load adapters to avoid import overhead."""
    if name == "ClaudeTraceCraftr":
        from tracecraft.adapters.claude_sdk import ClaudeTraceCraftr

        return ClaudeTraceCraftr
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
