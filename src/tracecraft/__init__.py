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

from typing import Any

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


def init_and_auto_instrument(
    providers: list[str] | None = None,
    **init_kwargs: Any,
) -> TALRuntime:
    """
    Initialize TraceCraft with auto-instrumentation enabled.

    This is a convenience function that combines `init()` with automatic
    instrumentation of LLM providers and frameworks.

    Args:
        providers: List of providers/frameworks to instrument. If None, instruments all.
            Valid options: "openai", "anthropic", "langchain", "llamaindex"
        **init_kwargs: Additional arguments passed to `init()`.

    Returns:
        The TALRuntime instance.

    Example:
        ```python
        import tracecraft

        # Initialize with all auto-instrumentation
        tracecraft.init_and_auto_instrument()

        # Initialize with specific providers only
        tracecraft.init_and_auto_instrument(["openai", "langchain"])

        # Now all calls are automatically traced!
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI()
        llm.invoke("Hello!")  # Automatically traced!
        ```
    """
    return init(auto_instrument=providers if providers else True, **init_kwargs)


# Alias for more descriptive naming
TraceCraftRuntime = TALRuntime

__version__ = "0.1.0"
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
    "init_and_auto_instrument",
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
