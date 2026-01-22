#!/usr/bin/env python3
"""Context Managers - Sync and async run management.

Learn how to use context managers for grouping traces, handling
async operations, and managing concurrent workloads.

Prerequisites:
    - AgentTrace installed (pip install agenttrace)
    - Completed 01_hello_world.py and 02_decorators.py
    - Basic understanding of Python async/await

Environment Variables:
    - None required

External Services:
    - None required

Usage:
    python examples/01-getting-started/03_context_managers.py

Expected Output:
    - Multiple trace runs in console and JSONL
    - Demonstration of sync and async patterns
"""

from __future__ import annotations

import asyncio

import agenttrace
from agenttrace.instrumentation.decorators import trace_agent, trace_llm, trace_tool

# Initialize AgentTrace
runtime = agenttrace.init(console=True, jsonl=True)


# ============================================================================
# Helper Functions (mocked for demonstration)
# ============================================================================


@trace_tool(name="api_call")
async def async_api_call(endpoint: str) -> dict[str, str]:
    """Simulate an async API call."""
    await asyncio.sleep(0.1)  # Simulate network latency
    return {"endpoint": endpoint, "status": "success"}


@trace_tool(name="db_query")
async def async_db_query(query: str) -> list[str]:
    """Simulate an async database query."""
    await asyncio.sleep(0.05)
    return [f"Row 1 for {query}", f"Row 2 for {query}"]


@trace_llm(name="async_llm", model="gpt-4o-mini", provider="openai")
async def async_llm_call(prompt: str) -> str:
    """Simulate an async LLM call."""
    await asyncio.sleep(0.1)
    return f"Response to: {prompt[:30]}..."


@trace_llm(name="sync_llm", model="gpt-4o-mini", provider="openai")
def sync_llm_call(prompt: str) -> str:
    """Simulate a sync LLM call."""
    return f"Sync response to: {prompt[:30]}..."


# ============================================================================
# Pattern 1: Basic Sync Context Manager
# ============================================================================


def demo_sync_context() -> None:
    """Demonstrate basic synchronous context manager usage.

    The `runtime.run()` context manager:
    - Creates a new trace run
    - Groups all nested operations
    - Automatically exports on exit
    - Captures any exceptions
    """
    print("\n--- Pattern 1: Sync Context Manager ---")

    # Basic usage - all traces inside are grouped
    with runtime.run("sync_example"):
        result1 = sync_llm_call("First question")
        result2 = sync_llm_call("Second question")
        print(f"Results: {result1[:20]}... and {result2[:20]}...")

    # Run is automatically exported when context exits


# ============================================================================
# Pattern 2: Async Context Manager
# ============================================================================


async def demo_async_context() -> None:
    """Demonstrate async context manager usage.

    Use `runtime.run_async()` for async code to ensure
    proper context propagation across await boundaries.
    """
    print("\n--- Pattern 2: Async Context Manager ---")

    async with runtime.run_async("async_example"):
        # Await operations are properly traced
        result1 = await async_llm_call("Async question 1")
        result2 = await async_llm_call("Async question 2")
        print(f"Async results: {result1[:20]}... and {result2[:20]}...")


# ============================================================================
# Pattern 3: Concurrent Operations
# ============================================================================


@trace_agent(name="concurrent_agent")
async def concurrent_agent(topics: list[str]) -> list[str]:
    """Agent that processes multiple items concurrently.

    asyncio.gather() is traced correctly when inside a run context.
    """
    tasks = [async_llm_call(f"Analyze {topic}") for topic in topics]
    results = await asyncio.gather(*tasks)
    return list(results)


async def demo_concurrent_context() -> None:
    """Demonstrate concurrent operations within a context."""
    print("\n--- Pattern 3: Concurrent Operations ---")

    async with runtime.run_async("concurrent_example"):
        # Run multiple API calls in parallel
        api_task = async_api_call("/users")
        db_task = async_db_query("SELECT * FROM data")
        llm_task = async_llm_call("Analyze this")

        # All three run concurrently
        api_result, db_result, llm_result = await asyncio.gather(api_task, db_task, llm_task)

        print(f"API: {api_result['status']}")
        print(f"DB: {len(db_result)} rows")
        print(f"LLM: {llm_result[:20]}...")

        # Also demonstrate agent with concurrent processing
        topics = ["topic1", "topic2", "topic3"]
        agent_results = await concurrent_agent(topics)
        print(f"Agent processed {len(agent_results)} topics")


# ============================================================================
# Pattern 4: Nested Contexts
# ============================================================================


async def demo_nested_contexts() -> None:
    """Demonstrate nested run contexts.

    You can nest contexts for sub-workflows, but typically
    you want to use @trace_agent for nested operations instead.
    """
    print("\n--- Pattern 4: Nested Contexts ---")

    async with runtime.run_async("outer_run"):
        result1 = await async_llm_call("Outer operation 1")

        # Nested context for a sub-workflow
        async with runtime.run_async("inner_run"):
            result2 = await async_llm_call("Inner operation")
            print(f"Inner: {result2[:20]}...")

        result3 = await async_llm_call("Outer operation 2")
        print(f"Outer: {result1[:20]}... and {result3[:20]}...")


# ============================================================================
# Pattern 5: Error Handling
# ============================================================================


@trace_tool(name="failing_operation")
async def failing_operation() -> str:
    """An operation that fails."""
    await asyncio.sleep(0.05)
    raise ValueError("Something went wrong!")


async def demo_error_handling() -> None:
    """Demonstrate error capture in contexts.

    Errors are captured in the trace with full stack traces.
    The run is still exported even when an error occurs.
    """
    print("\n--- Pattern 5: Error Handling ---")

    try:
        async with runtime.run_async("error_example"):
            result = await async_llm_call("Before error")
            print(f"Success: {result[:20]}...")

            # This will fail
            await failing_operation()

            # This won't run
            await async_llm_call("After error")

    except ValueError as e:
        print(f"Caught error: {e}")
        # The run is still exported with the error captured


# ============================================================================
# Pattern 6: Manual Run Management
# ============================================================================


def demo_manual_management() -> None:
    """Demonstrate manual run management (less common).

    For complex flows where context managers don't fit,
    you can manually create and manage runs.
    """
    print("\n--- Pattern 6: Manual Run Management ---")

    from datetime import UTC, datetime

    from agenttrace.core.context import run_context
    from agenttrace.core.models import AgentRun

    # Create a run manually
    run = AgentRun(name="manual_example", start_time=datetime.now(UTC))

    # Use run_context to set as current
    with run_context(run):
        result = sync_llm_call("Manual operation")
        print(f"Manual: {result[:20]}...")

    # Manually end and export
    runtime.end_run(run)
    print("Run manually exported")


# ============================================================================
# Pattern 7: Rate-Limited Concurrency
# ============================================================================


@trace_agent(name="rate_limited_agent")
async def rate_limited_agent(items: list[str], max_concurrent: int = 3) -> list[str]:
    """Agent with rate-limited concurrency using semaphore."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_with_limit(item: str) -> str:
        async with semaphore:
            return await async_llm_call(f"Process: {item}")

    tasks = [process_with_limit(item) for item in items]
    return list(await asyncio.gather(*tasks))


async def demo_rate_limited() -> None:
    """Demonstrate rate-limited concurrent processing."""
    print("\n--- Pattern 7: Rate-Limited Concurrency ---")

    async with runtime.run_async("rate_limited_example"):
        items = [f"item_{i}" for i in range(10)]
        results = await rate_limited_agent(items, max_concurrent=3)
        print(f"Processed {len(results)} items (max 3 concurrent)")


# ============================================================================
# Main
# ============================================================================


async def run_all_demos() -> None:
    """Run all async demonstrations."""
    await demo_async_context()
    await demo_concurrent_context()
    await demo_nested_contexts()
    await demo_error_handling()
    await demo_rate_limited()


def main() -> None:
    """Run the context managers example."""
    print("=" * 60)
    print("AgentTrace Context Managers Example")
    print("=" * 60)

    # Sync patterns
    demo_sync_context()
    demo_manual_management()

    # Async patterns
    asyncio.run(run_all_demos())

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nContext Manager Summary:")
    print("  runtime.run('name')       - Sync context manager")
    print("  runtime.run_async('name') - Async context manager")
    print("  run_context(run)          - Low-level manual management")
    print("\nKey patterns:")
    print("  - Use async context for async code")
    print("  - asyncio.gather() works correctly inside contexts")
    print("  - Errors are captured and runs still export")
    print("  - Use semaphores for rate limiting")
    print("\nNext steps:")
    print("- Try 04_configuration.py for advanced config")
    print("- Try 02-frameworks/ for framework integrations")


if __name__ == "__main__":
    main()
