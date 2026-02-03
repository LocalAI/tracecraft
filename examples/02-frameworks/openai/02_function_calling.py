#!/usr/bin/env python3
"""OpenAI Function Calling - Trace function calls with TraceCraft.

Demonstrates how to trace OpenAI function calling (tool use) patterns
using TraceCraft decorators.

Prerequisites:
    - pip install openai

Environment Variables:
    - OPENAI_API_KEY: Your OpenAI API key

External Services:
    - OpenAI API

Usage:
    python examples/02-frameworks/openai/02_function_calling.py

Expected Output:
    - Traces showing LLM calls with function definitions
    - Function execution captured separately
    - Multi-turn tool use visible in trace
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime

import tracecraft
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from tracecraft.instrumentation.decorators import trace_agent, trace_llm, trace_tool


def check_prerequisites() -> bool:
    """Verify all prerequisites are met."""
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        return False

    try:
        import openai  # noqa: F401
    except ImportError:
        print("Error: openai not installed")
        print("Install with: pip install openai")
        return False

    return True


# Initialize TraceCraft
runtime = tracecraft.init(
    console=True,
    jsonl=True,
    jsonl_path="traces.jsonl",
)


# Define tools
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The city name",
                    },
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Perform a mathematical calculation",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "The math expression to evaluate",
                    },
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search for products in the catalog",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 3,
                    },
                },
                "required": ["query"],
            },
        },
    },
]


@trace_tool(name="get_weather")
def get_weather(city: str) -> str:
    """Get simulated weather data for a city."""
    weather_data = {
        "new york": {"temp": 72, "condition": "Partly cloudy"},
        "london": {"temp": 58, "condition": "Rainy"},
        "tokyo": {"temp": 68, "condition": "Clear"},
        "paris": {"temp": 65, "condition": "Sunny"},
    }
    data = weather_data.get(city.lower())
    if data:
        return json.dumps(
            {"city": city, "temperature": data["temp"], "condition": data["condition"]}
        )
    return json.dumps({"error": f"Weather data not available for {city}"})


@trace_tool(name="calculator")
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression."""
    try:
        result = eval(expression)  # noqa: S307
        return json.dumps({"expression": expression, "result": result})
    except Exception as e:
        return json.dumps({"error": str(e)})


@trace_tool(name="search_products")
def search_products(query: str, max_results: int = 3) -> str:
    """Search for products (simulated)."""
    all_products = [
        {"name": "MacBook Pro", "price": 1999, "category": "laptop"},
        {"name": "Dell XPS 15", "price": 1499, "category": "laptop"},
        {"name": "iPhone 15 Pro", "price": 999, "category": "phone"},
        {"name": "Galaxy S24", "price": 899, "category": "phone"},
        {"name": "iPad Pro", "price": 799, "category": "tablet"},
    ]

    # Simple keyword matching
    results = [
        p
        for p in all_products
        if query.lower() in p["name"].lower() or query.lower() in p["category"].lower()
    ]
    return json.dumps({"query": query, "results": results[:max_results]})


def execute_tool_call(tool_name: str, arguments: dict) -> str:
    """Execute a tool call and return the result."""
    if tool_name == "get_weather":
        return get_weather(**arguments)
    elif tool_name == "calculator":
        return calculator(**arguments)
    elif tool_name == "search_products":
        return search_products(**arguments)
    else:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})


@trace_llm(name="function_call", model="gpt-4o-mini", provider="openai")
def call_with_tools(messages: list, tools: list) -> dict:
    """Make an OpenAI API call with tools."""
    import openai

    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )
    return response


@trace_agent(name="tool_agent")
def tool_agent(user_query: str) -> str:
    """An agent that uses tools to answer queries."""
    messages = [{"role": "user", "content": user_query}]

    # Initial call to get tool selection
    response = call_with_tools(messages, TOOLS)
    assistant_message = response.choices[0].message

    # If no tool calls, return direct response
    if not assistant_message.tool_calls:
        return assistant_message.content or "No response"

    # Process tool calls
    messages.append(assistant_message)

    for tool_call in assistant_message.tool_calls:
        tool_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)

        # Execute the tool
        tool_result = execute_tool_call(tool_name, arguments)

        # Add tool result to messages
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result,
            }
        )

    # Get final response
    final_response = call_with_tools(messages, TOOLS)
    return final_response.choices[0].message.content or "No response"


def single_tool_example() -> None:
    """Demonstrate single tool call."""
    print("\n--- Single Tool Call Example ---")

    run = AgentRun(name="openai_single_tool", start_time=datetime.now(UTC))

    with run_context(run):
        result = tool_agent("What's the weather in Paris?")

    runtime.end_run(run)
    print(f"Response: {result}")


def multi_tool_example() -> None:
    """Demonstrate multiple tool calls."""
    print("\n--- Multi-Tool Call Example ---")

    run = AgentRun(name="openai_multi_tool", start_time=datetime.now(UTC))

    with run_context(run):
        result = tool_agent("Calculate 25 * 4 + 10")

    runtime.end_run(run)
    print(f"Response: {result}")


def parallel_tool_example() -> None:
    """Demonstrate parallel tool calls."""
    print("\n--- Parallel Tool Call Example ---")

    run = AgentRun(name="openai_parallel_tools", start_time=datetime.now(UTC))

    with run_context(run):
        # This query might trigger parallel tool calls
        result = tool_agent("What's the weather in Tokyo and what laptops do you have?")

    runtime.end_run(run)
    print(f"Response: {result}")


def main() -> None:
    """Run the OpenAI function calling examples."""
    print("=" * 60)
    print("TraceCraft OpenAI Function Calling")
    print("=" * 60)

    single_tool_example()
    multi_tool_example()
    parallel_tool_example()

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nKey patterns demonstrated:")
    print("  - Tool definition with JSON schema")
    print("  - @trace_tool decorator for tool execution")
    print("  - Multi-turn conversation with tools")
    print("  - Parallel tool calls")
    print("\nTrace shows:")
    print("  - LLM calls with tool definitions")
    print("  - Tool execution with inputs/outputs")
    print("  - Complete conversation flow")
    print("\nNext steps:")
    print("- Try 03_streaming.py for streaming traces")


if __name__ == "__main__":
    if not check_prerequisites():
        sys.exit(1)
    main()
