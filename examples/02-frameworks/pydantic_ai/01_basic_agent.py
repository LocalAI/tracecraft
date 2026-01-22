#!/usr/bin/env python3
"""PydanticAI Basic Agent - Trace PydanticAI agents with AgentTrace.

Demonstrates how to use the AgentTrace span processor to automatically trace
PydanticAI agents including structured output and tool use.

Prerequisites:
    - Basic PydanticAI knowledge
    - pip install pydantic-ai

Environment Variables:
    - OPENAI_API_KEY: Your OpenAI API key

External Services:
    - OpenAI API

Usage:
    python examples/02-frameworks/pydantic_ai/01_basic_agent.py

Expected Output:
    - Traces showing agent runs with model info
    - Structured output and tool calls captured
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime

import agenttrace
from agenttrace.adapters.pydantic_ai import AgentTraceSpanProcessor
from agenttrace.core.context import run_context
from agenttrace.core.models import AgentRun


def check_prerequisites() -> bool:
    """Verify all prerequisites are met."""
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        return False

    try:
        import pydantic_ai  # noqa: F401
    except ImportError:
        print("Error: pydantic-ai not installed")
        print("Install with: pip install pydantic-ai")
        return False

    return True


# Initialize AgentTrace
runtime = agenttrace.init(
    console=True,
    jsonl=True,
    jsonl_path="traces.jsonl",
)


def simple_agent_example() -> None:
    """Demonstrate simple agent tracing."""
    from pydantic_ai import Agent

    print("\n--- Simple Agent Example ---")

    # Create span processor (integrates with PydanticAI's OpenTelemetry)
    processor = AgentTraceSpanProcessor()

    # Create agent
    agent = Agent(
        "openai:gpt-4o-mini",
        system_prompt="You are a helpful assistant. Be very concise.",
    )

    run = AgentRun(name="pydantic_ai_simple", start_time=datetime.now(UTC))

    with run_context(run):
        result = agent.run_sync("What is the capital of France? One word only.")

    runtime.end_run(run)
    processor.clear()

    print(f"Response: {result.output}")


def structured_output_example() -> None:
    """Demonstrate structured output tracing.

    PydanticAI excels at type-safe structured output.
    """
    from pydantic import BaseModel
    from pydantic_ai import Agent

    print("\n--- Structured Output Example ---")

    class CityInfo(BaseModel):
        name: str
        country: str
        population_millions: float

    processor = AgentTraceSpanProcessor()

    agent = Agent(
        "openai:gpt-4o-mini",
        output_type=CityInfo,
        system_prompt="Extract city information from the query.",
    )

    run = AgentRun(name="pydantic_ai_structured", start_time=datetime.now(UTC))

    with run_context(run):
        result = agent.run_sync("Tell me about Paris")

    runtime.end_run(run)
    processor.clear()

    print(f"City: {result.output.name}")
    print(f"Country: {result.output.country}")
    print(f"Population: {result.output.population_millions}M")


def agent_with_tools_example() -> None:
    """Demonstrate agent with tools tracing."""
    from pydantic_ai import Agent

    print("\n--- Agent with Tools Example ---")

    processor = AgentTraceSpanProcessor()

    agent = Agent(
        "openai:gpt-4o-mini",
        system_prompt="You are a helpful calculator. Use the calculator tool.",
    )

    @agent.tool_plain
    def calculator(expression: str) -> str:
        """Calculate a math expression."""
        try:
            return str(eval(expression))  # noqa: S307
        except Exception as e:
            return f"Error: {e}"

    run = AgentRun(name="pydantic_ai_tools", start_time=datetime.now(UTC))

    with run_context(run):
        result = agent.run_sync("What is 7 * 8?")

    runtime.end_run(run)
    processor.clear()

    print(f"Response: {result.output}")


async def async_agent_example() -> None:
    """Demonstrate async agent tracing."""
    from pydantic_ai import Agent

    print("\n--- Async Agent Example ---")

    processor = AgentTraceSpanProcessor()

    agent = Agent(
        "openai:gpt-4o-mini",
        system_prompt="Be very concise.",
    )

    run = AgentRun(name="pydantic_ai_async", start_time=datetime.now(UTC))

    with run_context(run):
        result = await agent.run("Say 'async works' exactly.")

    runtime.end_run(run)
    processor.clear()

    print(f"Response: {result.output}")


async def streaming_example() -> None:
    """Demonstrate streaming agent tracing."""
    from pydantic_ai import Agent

    print("\n--- Streaming Example ---")

    processor = AgentTraceSpanProcessor()

    agent = Agent(
        "openai:gpt-4o-mini",
        system_prompt="Be concise.",
    )

    run = AgentRun(name="pydantic_ai_streaming", start_time=datetime.now(UTC))

    chunks = []
    with run_context(run):
        async with agent.run_stream("Count from 1 to 5.") as stream:
            async for chunk in stream.stream_text():
                chunks.append(chunk)

    runtime.end_run(run)
    processor.clear()

    print(f"Response: {''.join(chunks)}")


def main() -> None:
    """Run the PydanticAI examples."""
    print("=" * 60)
    print("AgentTrace PydanticAI Integration")
    print("=" * 60)

    simple_agent_example()
    structured_output_example()
    agent_with_tools_example()

    # Run async examples
    asyncio.run(async_agent_example())
    asyncio.run(streaming_example())

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nKey points:")
    print("  - Use AgentTraceSpanProcessor for automatic tracing")
    print("  - Structured output and tools are captured")
    print("  - Both sync and async agents work")
    print("\nNext steps:")
    print("- Try 02_tool_use.py for advanced tool patterns")


if __name__ == "__main__":
    if not check_prerequisites():
        sys.exit(1)
    main()
