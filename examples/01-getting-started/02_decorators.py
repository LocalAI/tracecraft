#!/usr/bin/env python3
"""Decorators - All TraceCraft decorator types explained.

Learn how to use @trace_agent, @trace_llm, @trace_tool, and @trace_retrieval
decorators to instrument your code. This example demonstrates nested decorators,
metadata injection, and error capture.

Prerequisites:
    - TraceCraft installed (pip install tracecraft)
    - Completed 01_hello_world.py

Environment Variables:
    - None required

External Services:
    - None required

Usage:
    python examples/01-getting-started/02_decorators.py

Expected Output:
    - Console output showing nested trace hierarchy
    - JSONL file with all trace data
"""

from __future__ import annotations

import tracecraft
from tracecraft.instrumentation.decorators import (
    trace_agent,
    trace_llm,
    trace_retrieval,
    trace_tool,
)

# Initialize TraceCraft
runtime = tracecraft.init(console=True, jsonl=True)


# ============================================================================
# @trace_tool - For external tools and utilities
# ============================================================================


@trace_tool(name="calculator")
def calculator(expression: str) -> str:
    """A simple calculator tool.

    @trace_tool is used for:
    - External API calls
    - Utility functions
    - Any side-effect operations

    The decorator captures inputs, outputs, and timing.
    """
    try:
        result = eval(expression)  # noqa: S307
        return str(result)
    except Exception as e:
        return f"Error: {e}"


@trace_tool(name="web_search")
def web_search(query: str) -> str:
    """Simulate a web search tool.

    In a real application, this would call a search API like
    Google, Bing, or a custom search service.
    """
    return f"Search results for '{query}': [Result 1, Result 2, Result 3]"


# ============================================================================
# @trace_retrieval - For vector search and document retrieval
# ============================================================================


@trace_retrieval(name="vector_search")
def vector_search(query: str, top_k: int = 3) -> list[dict[str, str]]:
    """Simulate a vector database search.

    @trace_retrieval is specifically for:
    - Vector database queries
    - Document retrieval
    - RAG context fetching

    It captures the query, number of results, and can track
    relevance scores.
    """
    # Simulated vector search results
    return [
        {"id": "doc1", "text": f"Result 1 for {query}", "score": "0.95"},
        {"id": "doc2", "text": f"Result 2 for {query}", "score": "0.87"},
        {"id": "doc3", "text": f"Result 3 for {query}", "score": "0.82"},
    ][:top_k]


# ============================================================================
# @trace_llm - For LLM/model calls
# ============================================================================


@trace_llm(name="reasoning_llm", model="gpt-4o-mini", provider="openai")
def reasoning_llm(prompt: str) -> str:
    """Simulate an LLM call.

    @trace_llm is for any language model invocation:
    - OpenAI, Anthropic, Cohere, etc.
    - Local models
    - Custom model endpoints

    Key parameters:
    - name: Identifies this LLM call in traces
    - model: The model being used
    - provider: The LLM provider

    You can also add token counts and cost in the function:
    """
    # In a real app, call the actual LLM here
    response = f"Analyzed: {prompt[:30]}..."

    # Optional: Add metadata to the current step
    # from tracecraft.core.context import get_current_step
    # step = get_current_step()
    # if step:
    #     step.input_tokens = 100
    #     step.output_tokens = 50
    #     step.cost_usd = 0.001

    return response


@trace_llm(name="synthesis_llm", model="claude-3-sonnet", provider="anthropic")
def synthesis_llm(content: str) -> str:
    """Another LLM call with different model."""
    return f"Synthesized: {content[:20]}..."


# ============================================================================
# @trace_agent - For agent-level orchestration
# ============================================================================


@trace_agent(name="research_agent")
def research_agent(topic: str) -> str:
    """An agent that researches a topic.

    @trace_agent is the top-level decorator for agent workflows.
    It groups all nested calls (tools, LLMs, retrievals) into
    a single agent trace.

    Agent traces show:
    - Total duration
    - All nested operations
    - Error propagation
    - Cost aggregation
    """
    # Step 1: Search for information (uses @trace_tool)
    search_results = web_search(topic)

    # Step 2: Retrieve relevant documents (uses @trace_retrieval)
    docs = vector_search(topic)

    # Step 3: Analyze with LLM (uses @trace_llm)
    analysis = reasoning_llm(f"Analyze: {search_results}\nDocs: {docs}")

    return f"Research complete: {analysis}"


@trace_agent(name="math_agent")
def math_agent(question: str) -> str:
    """An agent that solves math problems."""
    # Parse the question with LLM
    parsed = reasoning_llm(f"Extract math expression from: {question}")

    # Calculate using tool
    result = calculator("2 + 2")

    return f"Parsed: {parsed[:20]}... Answer: {result}"


@trace_agent(name="coordinator_agent")
def coordinator_agent(task: str) -> str:
    """A coordinator that delegates to other agents.

    This demonstrates nested agents - the coordinator
    calls other agents, creating a hierarchical trace.
    """
    # Delegate to specialized agents
    research = research_agent(task)
    math = math_agent(task)

    # Synthesize results
    final = synthesis_llm(f"Combine:\n{research}\n{math}")

    return final


# ============================================================================
# Error Handling
# ============================================================================


@trace_tool(name="failing_tool")
def failing_tool() -> str:
    """A tool that fails to demonstrate error capture."""
    raise ValueError("This tool intentionally fails!")


@trace_agent(name="error_handling_agent")
def error_handling_agent() -> str:
    """Agent that demonstrates error capture in traces."""
    try:
        failing_tool()
        return "Success"
    except ValueError as e:
        # Error is captured in the trace
        return f"Handled error: {e}"


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    """Run the decorators example."""
    print("=" * 60)
    print("TraceCraft Decorators Example")
    print("=" * 60)

    # Example 1: Simple agent workflow
    print("\n--- Example 1: Coordinator Agent ---")
    with runtime.run("decorator_example"):
        result = coordinator_agent("What is the weather and calculate 2+2?")
        print(f"Result: {result[:50]}...")

    # Example 2: Error handling
    print("\n--- Example 2: Error Handling ---")
    with runtime.run("error_example"):
        result = error_handling_agent()
        print(f"Result: {result}")

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nDecorator Summary:")
    print("  @trace_agent     - Top-level agent orchestration")
    print("  @trace_llm       - LLM/model calls")
    print("  @trace_tool      - External tools and utilities")
    print("  @trace_retrieval - Vector search and document retrieval")
    print("\nAll decorators capture:")
    print("  - Inputs and outputs")
    print("  - Duration")
    print("  - Errors (with stack traces)")
    print("  - Custom metadata")
    print("\nNext steps:")
    print("- Try 03_context_managers.py for async patterns")
    print("- Try 04_configuration.py for advanced config")


if __name__ == "__main__":
    main()
