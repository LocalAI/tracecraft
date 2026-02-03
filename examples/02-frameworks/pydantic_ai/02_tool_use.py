#!/usr/bin/env python3
"""PydanticAI Tool Use - Trace advanced tool patterns with TraceCraft.

Demonstrates how to trace PydanticAI agents with tools, including
context-aware tools, async tools, and multi-tool agents.

Prerequisites:
    - pip install pydantic-ai

Environment Variables:
    - OPENAI_API_KEY: Your OpenAI API key

External Services:
    - OpenAI API

Usage:
    python examples/02-frameworks/pydantic_ai/02_tool_use.py

Expected Output:
    - Traces showing tool invocations
    - Tool inputs and outputs captured
    - Multi-step tool chains visible
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime

import tracecraft
from tracecraft.adapters.pydantic_ai import TraceCraftSpanProcessor
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun


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


# Initialize TraceCraft
runtime = tracecraft.init(
    console=True,
    jsonl=True,
    jsonl_path="traces.jsonl",
)


def basic_tool_example() -> None:
    """Demonstrate basic tool usage with tracing."""
    from pydantic_ai import Agent

    print("\n--- Basic Tool Example ---")

    processor = TraceCraftSpanProcessor()

    agent = Agent(
        "openai:gpt-4o-mini",
        system_prompt="You are a helpful assistant. Use tools when appropriate.",
    )

    @agent.tool_plain
    def get_weather(city: str) -> str:
        """Get the current weather for a city."""
        weather_data = {
            "new york": "72°F, Partly cloudy",
            "london": "58°F, Rainy",
            "tokyo": "68°F, Clear",
            "paris": "65°F, Sunny",
        }
        return weather_data.get(city.lower(), f"Weather data not available for {city}")

    @agent.tool_plain
    def calculator(expression: str) -> str:
        """Calculate a mathematical expression using Python syntax."""
        try:
            result = eval(expression)  # noqa: S307
            return f"Result: {result}"
        except Exception as e:
            return f"Error: {e}"

    run = AgentRun(name="pydantic_ai_basic_tools", start_time=datetime.now(UTC))

    with run_context(run):
        result = agent.run_sync("What's the weather in Paris?")

    runtime.end_run(run)
    processor.clear()

    print(f"Response: {result.output}")


def multiple_tools_example() -> None:
    """Demonstrate agent with multiple tools."""
    from pydantic_ai import Agent

    print("\n--- Multiple Tools Example ---")

    processor = TraceCraftSpanProcessor()

    agent = Agent(
        "openai:gpt-4o-mini",
        system_prompt="You are a helpful assistant with multiple tools. Use them as needed.",
    )

    @agent.tool_plain
    def get_time() -> str:
        """Get the current time."""
        return datetime.now().strftime("%H:%M:%S")

    @agent.tool_plain
    def get_date() -> str:
        """Get the current date."""
        return datetime.now().strftime("%Y-%m-%d")

    @agent.tool_plain
    def search_database(query: str) -> str:
        """Search the database for information."""
        # Simulated database search
        if "user" in query.lower():
            return "Found 3 users matching the query."
        elif "product" in query.lower():
            return "Found 10 products matching the query."
        return "No results found."

    run = AgentRun(name="pydantic_ai_multiple_tools", start_time=datetime.now(UTC))

    with run_context(run):
        result = agent.run_sync("What time is it and what's today's date?")

    runtime.end_run(run)
    processor.clear()

    print(f"Response: {result.output}")


async def async_tools_example() -> None:
    """Demonstrate async tool usage."""
    from pydantic_ai import Agent

    print("\n--- Async Tools Example ---")

    processor = TraceCraftSpanProcessor()

    agent = Agent(
        "openai:gpt-4o-mini",
        system_prompt="You are a helpful assistant with async tools.",
    )

    @agent.tool_plain
    async def async_search(query: str) -> str:
        """Search for information (async)."""
        # Simulate async operation
        await asyncio.sleep(0.1)
        return f"Search results for '{query}': Found 3 relevant articles."

    @agent.tool_plain
    async def async_fetch_data(url: str) -> str:
        """Fetch data from a URL (async)."""
        await asyncio.sleep(0.1)
        return f"Data fetched from {url}: {{status: 'ok', items: 5}}"

    run = AgentRun(name="pydantic_ai_async_tools", start_time=datetime.now(UTC))

    with run_context(run):
        result = await agent.run("Search for information about Python async/await.")

    runtime.end_run(run)
    processor.clear()

    print(f"Response: {result.output}")


def multi_tool_chain_example() -> None:
    """Demonstrate multi-step tool chains."""
    from pydantic_ai import Agent

    print("\n--- Multi-Tool Chain Example ---")

    processor = TraceCraftSpanProcessor()

    agent = Agent(
        "openai:gpt-4o-mini",
        system_prompt="You are a math assistant. Break complex problems into steps using tools.",
    )

    @agent.tool_plain
    def add(a: float, b: float) -> float:
        """Add two numbers."""
        return a + b

    @agent.tool_plain
    def multiply(a: float, b: float) -> float:
        """Multiply two numbers."""
        return a * b

    @agent.tool_plain
    def divide(a: float, b: float) -> str:
        """Divide two numbers."""
        if b == 0:
            return "Error: Division by zero"
        return str(a / b)

    @agent.tool_plain
    def power(base: float, exponent: float) -> float:
        """Raise base to the power of exponent."""
        return base**exponent

    run = AgentRun(name="pydantic_ai_multi_tool_chain", start_time=datetime.now(UTC))

    with run_context(run):
        # This should trigger multiple tool calls
        result = agent.run_sync("Calculate (3 + 4) * 5, then square the result")

    runtime.end_run(run)
    processor.clear()

    print(f"Response: {result.output}")


def structured_tool_output_example() -> None:
    """Demonstrate tools with structured output."""
    from pydantic import BaseModel
    from pydantic_ai import Agent

    print("\n--- Structured Tool Output Example ---")

    class ProductInfo(BaseModel):
        name: str
        price: float
        in_stock: bool
        description: str

    processor = TraceCraftSpanProcessor()

    agent = Agent(
        "openai:gpt-4o-mini",
        output_type=ProductInfo,
        system_prompt="You are a product catalog assistant. Use the search tool and return structured product info.",
    )

    @agent.tool_plain
    def search_product(query: str) -> str:
        """Search for a product in the catalog."""
        products = {
            "laptop": "MacBook Pro M3 - $1999 - In stock - Latest Apple laptop with M3 chip",
            "phone": "iPhone 15 Pro - $999 - In stock - Latest iPhone with titanium design",
            "headphones": "AirPods Pro 2 - $249 - Out of stock - Active noise cancellation",
        }
        for key, value in products.items():
            if key in query.lower():
                return value
        return "Product not found"

    run = AgentRun(name="pydantic_ai_structured_tools", start_time=datetime.now(UTC))

    with run_context(run):
        result = agent.run_sync("Find information about the laptop")

    runtime.end_run(run)
    processor.clear()

    print(f"Product: {result.output.name}")
    print(f"Price: ${result.output.price}")
    print(f"In Stock: {result.output.in_stock}")
    print(f"Description: {result.output.description}")


def main() -> None:
    """Run the PydanticAI tool examples."""
    print("=" * 60)
    print("TraceCraft PydanticAI Tool Use")
    print("=" * 60)

    basic_tool_example()
    multiple_tools_example()
    asyncio.run(async_tools_example())
    multi_tool_chain_example()
    structured_tool_output_example()

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nKey patterns demonstrated:")
    print("  - Basic tool_plain decorator")
    print("  - Multiple tools in one agent")
    print("  - Async tools with await")
    print("  - Multi-tool chains for complex tasks")
    print("  - Structured output with tools")
    print("\nTrace shows:")
    print("  - Tool invocation events")
    print("  - Tool inputs and outputs")
    print("  - Tool execution timing")


if __name__ == "__main__":
    if not check_prerequisites():
        sys.exit(1)
    main()
