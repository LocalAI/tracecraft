#!/usr/bin/env python3
"""LlamaIndex Agents - Trace agent workflows with AgentTrace.

Demonstrates how to trace LlamaIndex agent patterns including
tool-using agents, ReAct agents, and multi-step reasoning.

Prerequisites:
    - pip install llama-index-core llama-index-llms-openai llama-index-agent-openai

Environment Variables:
    - OPENAI_API_KEY: Your OpenAI API key

External Services:
    - OpenAI API

Usage:
    python examples/02-frameworks/llamaindex/03_agents.py

Expected Output:
    - Traces showing agent reasoning steps
    - Tool calls captured with inputs/outputs
    - Multi-step execution visible in trace
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime

import agenttrace
from agenttrace.adapters.llamaindex import AgentTraceLlamaIndexCallback
from agenttrace.core.context import run_context
from agenttrace.core.models import AgentRun


def check_prerequisites() -> bool:
    """Verify all prerequisites are met."""
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        return False

    try:
        import llama_index.core  # noqa: F401
        import llama_index.llms.openai  # noqa: F401
    except ImportError:
        print("Error: llama-index packages not installed")
        print("Install with: pip install llama-index-core llama-index-llms-openai")
        return False

    return True


# Initialize AgentTrace
runtime = agenttrace.init(
    console=True,
    jsonl=True,
    jsonl_path="traces.jsonl",
)


def function_tool_agent_example() -> None:
    """Demonstrate agent with function tools."""
    from llama_index.core import Settings
    from llama_index.core.agent import ReActAgent
    from llama_index.core.callbacks import CallbackManager
    from llama_index.core.tools import FunctionTool
    from llama_index.llms.openai import OpenAI

    print("\n--- Function Tool Agent Example ---")

    handler = AgentTraceLlamaIndexCallback()
    Settings.callback_manager = CallbackManager(handlers=[handler])

    # Define tools
    def multiply(a: int, b: int) -> int:
        """Multiply two integers and return the result."""
        return a * b

    def add(a: int, b: int) -> int:
        """Add two integers and return the result."""
        return a + b

    def get_weather(city: str) -> str:
        """Get the current weather for a city."""
        weather_data = {
            "new york": "72°F, Partly cloudy",
            "london": "58°F, Rainy",
            "tokyo": "68°F, Clear",
            "paris": "65°F, Sunny",
        }
        return weather_data.get(city.lower(), f"Weather data not available for {city}")

    multiply_tool = FunctionTool.from_defaults(fn=multiply)
    add_tool = FunctionTool.from_defaults(fn=add)
    weather_tool = FunctionTool.from_defaults(fn=get_weather)

    llm = OpenAI(model="gpt-4o-mini", temperature=0)
    agent = ReActAgent.from_tools(
        [multiply_tool, add_tool, weather_tool],
        llm=llm,
        verbose=False,
    )

    run = AgentRun(name="llamaindex_function_agent", start_time=datetime.now(UTC))

    with run_context(run):
        response = agent.chat("What is 7 times 8, then add 6 to the result?")

    runtime.end_run(run)
    handler.clear()

    print(f"Response: {response.response}")


def query_engine_tool_agent_example() -> None:
    """Demonstrate agent using a query engine as a tool."""
    from llama_index.core import Document, Settings, VectorStoreIndex
    from llama_index.core.agent import ReActAgent
    from llama_index.core.callbacks import CallbackManager
    from llama_index.core.tools import QueryEngineTool, ToolMetadata
    from llama_index.llms.openai import OpenAI

    print("\n--- Query Engine Tool Agent Example ---")

    handler = AgentTraceLlamaIndexCallback()
    Settings.callback_manager = CallbackManager(handlers=[handler])

    llm = OpenAI(model="gpt-4o-mini", temperature=0)
    Settings.llm = llm
    Settings.chunk_size = 256

    # Create a knowledge base about a product
    product_docs = [
        Document(text="CloudSync Pro offers 100GB free storage and 1TB for premium users."),
        Document(text="CloudSync Pro supports Windows, macOS, Linux, iOS, and Android."),
        Document(text="Premium plans cost $9.99/month with priority support."),
        Document(text="End-to-end encryption is enabled by default on all plans."),
    ]

    product_index = VectorStoreIndex.from_documents(product_docs)
    product_query_engine = product_index.as_query_engine()

    # Create query engine tool
    product_tool = QueryEngineTool(
        query_engine=product_query_engine,
        metadata=ToolMetadata(
            name="product_knowledge",
            description="Provides information about CloudSync Pro product features and pricing.",
        ),
    )

    agent = ReActAgent.from_tools(
        [product_tool],
        llm=llm,
        verbose=False,
    )

    run = AgentRun(name="llamaindex_query_tool_agent", start_time=datetime.now(UTC))

    with run_context(run):
        response = agent.chat("How much does CloudSync Pro cost and what storage do I get?")

    runtime.end_run(run)
    handler.clear()

    print(f"Response: {response.response}")


def multi_tool_agent_example() -> None:
    """Demonstrate agent with multiple specialized tools."""
    from llama_index.core import Settings
    from llama_index.core.agent import ReActAgent
    from llama_index.core.callbacks import CallbackManager
    from llama_index.core.tools import FunctionTool
    from llama_index.llms.openai import OpenAI

    print("\n--- Multi-Tool Agent Example ---")

    handler = AgentTraceLlamaIndexCallback()
    Settings.callback_manager = CallbackManager(handlers=[handler])

    # Calculator tools
    def calculator(expression: str) -> str:
        """Evaluate a mathematical expression. Use Python syntax."""
        try:
            result = eval(expression)  # noqa: S307
            return f"Result: {result}"
        except Exception as e:
            return f"Error: {e}"

    # Unit converter
    def convert_temperature(value: float, from_unit: str, to_unit: str) -> str:
        """Convert temperature between Celsius and Fahrenheit."""
        if from_unit.lower() == "c" and to_unit.lower() == "f":
            result = (value * 9 / 5) + 32
            return f"{value}°C = {result:.1f}°F"
        elif from_unit.lower() == "f" and to_unit.lower() == "c":
            result = (value - 32) * 5 / 9
            return f"{value}°F = {result:.1f}°C"
        else:
            return "Error: Use 'C' for Celsius and 'F' for Fahrenheit"

    # Date tool
    def get_current_date() -> str:
        """Get the current date and time."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    calc_tool = FunctionTool.from_defaults(fn=calculator, name="calculator")
    temp_tool = FunctionTool.from_defaults(fn=convert_temperature, name="temperature_converter")
    date_tool = FunctionTool.from_defaults(fn=get_current_date, name="current_date")

    llm = OpenAI(model="gpt-4o-mini", temperature=0)
    agent = ReActAgent.from_tools(
        [calc_tool, temp_tool, date_tool],
        llm=llm,
        verbose=False,
    )

    run = AgentRun(name="llamaindex_multi_tool_agent", start_time=datetime.now(UTC))

    with run_context(run):
        # Multi-step task
        response = agent.chat("What is 25 * 4? Also convert 100 degrees Fahrenheit to Celsius.")

    runtime.end_run(run)
    handler.clear()

    print(f"Response: {response.response}")


def conversational_agent_example() -> None:
    """Demonstrate conversational agent with memory."""
    from llama_index.core import Settings
    from llama_index.core.agent import ReActAgent
    from llama_index.core.callbacks import CallbackManager
    from llama_index.core.tools import FunctionTool
    from llama_index.llms.openai import OpenAI

    print("\n--- Conversational Agent Example ---")

    handler = AgentTraceLlamaIndexCallback()
    Settings.callback_manager = CallbackManager(handlers=[handler])

    def search_products(query: str) -> str:
        """Search for products in the catalog."""
        products = {
            "laptop": "MacBook Pro - $1999, Dell XPS - $1499",
            "phone": "iPhone 15 - $999, Galaxy S24 - $899",
            "tablet": "iPad Pro - $799, Galaxy Tab - $649",
        }
        for key, value in products.items():
            if key in query.lower():
                return value
        return "No products found matching your query."

    search_tool = FunctionTool.from_defaults(fn=search_products, name="product_search")

    llm = OpenAI(model="gpt-4o-mini", temperature=0)
    agent = ReActAgent.from_tools(
        [search_tool],
        llm=llm,
        verbose=False,
    )

    run = AgentRun(name="llamaindex_conversational_agent", start_time=datetime.now(UTC))

    with run_context(run):
        # First turn
        response1 = agent.chat("Show me laptops")
        print(f"Turn 1: {response1.response}")

        # Follow-up (agent has memory)
        response2 = agent.chat("Which one is cheaper?")
        print(f"Turn 2: {response2.response}")

    runtime.end_run(run)
    handler.clear()


def main() -> None:
    """Run the LlamaIndex agent examples."""
    print("=" * 60)
    print("AgentTrace LlamaIndex Agents")
    print("=" * 60)

    function_tool_agent_example()
    query_engine_tool_agent_example()
    multi_tool_agent_example()
    conversational_agent_example()

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nKey patterns demonstrated:")
    print("  - ReAct agent with function tools")
    print("  - Query engine as agent tool")
    print("  - Multi-tool agent workflows")
    print("  - Conversational agent with memory")
    print("\nTrace shows:")
    print("  - Agent reasoning steps")
    print("  - Tool selection decisions")
    print("  - Tool inputs and outputs")
    print("  - Multi-turn conversation flow")


if __name__ == "__main__":
    if not check_prerequisites():
        sys.exit(1)
    main()
