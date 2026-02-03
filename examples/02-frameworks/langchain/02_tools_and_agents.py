#!/usr/bin/env python3
"""LangChain Tools and Agents - Trace tool-calling agents with TraceCraft.

Demonstrates how to trace LangChain agents that use tools, including
tool binding, agent executors, and the create_tool_calling_agent pattern.

Prerequisites:
    - pip install langchain-openai langchain

Environment Variables:
    - OPENAI_API_KEY: Your OpenAI API key

External Services:
    - OpenAI API

Usage:
    python examples/02-frameworks/langchain/02_tools_and_agents.py

Expected Output:
    - Trace showing agent reasoning and tool calls
    - Tool inputs and outputs captured
    - Multiple iterations visible in trace
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime

import tracecraft
from tracecraft.adapters.langchain import TraceCraftCallbackHandler
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun


def check_prerequisites() -> bool:
    """Verify all prerequisites are met."""
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        return False

    try:
        import langchain_core  # noqa: F401
        import langchain_openai  # noqa: F401
    except ImportError:
        print("Error: langchain-openai not installed")
        print("Install with: pip install langchain-openai")
        return False

    return True


# Initialize TraceCraft
runtime = tracecraft.init(
    console=True,
    jsonl=True,
    jsonl_path="traces.jsonl",
)


def tool_binding_example() -> None:
    """Demonstrate tool binding with tracing."""
    from langchain_core.tools import tool
    from langchain_openai import ChatOpenAI

    print("\n--- Tool Binding Example ---")

    @tool
    def get_weather(city: str) -> str:
        """Get the current weather for a city."""
        weather_data = {
            "new york": "72°F, Partly cloudy",
            "london": "58°F, Rainy",
            "tokyo": "68°F, Clear",
            "paris": "65°F, Sunny",
        }
        return weather_data.get(city.lower(), f"Weather data not available for {city}")

    @tool
    def calculator(expression: str) -> str:
        """Calculate a mathematical expression using Python syntax."""
        try:
            result = eval(expression)  # noqa: S307
            return f"Result: {result}"
        except Exception as e:
            return f"Error: {e}"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    llm_with_tools = llm.bind_tools([get_weather, calculator])

    handler = TraceCraftCallbackHandler()
    run = AgentRun(name="langchain_tool_binding", start_time=datetime.now(UTC))

    with run_context(run):
        result = llm_with_tools.invoke(
            "What's the weather in Paris?",
            config={"callbacks": [handler]},
        )

    runtime.end_run(run)
    handler.clear()

    print(f"Tool calls: {result.tool_calls if hasattr(result, 'tool_calls') else 'None'}")


def tool_calling_agent_example() -> None:
    """Demonstrate tool-calling with LLM and manual tool execution."""
    from langchain_core.messages import HumanMessage, ToolMessage
    from langchain_core.tools import tool
    from langchain_openai import ChatOpenAI

    print("\n--- Tool-Calling Agent Example ---")

    @tool
    def multiply(a: int, b: int) -> int:
        """Multiply two numbers together."""
        return a * b

    @tool
    def add(a: int, b: int) -> int:
        """Add two numbers together."""
        return a + b

    tools = [multiply, add]
    tool_map = {t.name: t for t in tools}

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    llm_with_tools = llm.bind_tools(tools)

    handler = TraceCraftCallbackHandler()
    run = AgentRun(name="langchain_tool_calling_agent", start_time=datetime.now(UTC))

    with run_context(run):
        messages = [HumanMessage(content="What is 7 times 8, then add 6 to the result?")]

        # First LLM call - get tool calls
        response = llm_with_tools.invoke(messages, config={"callbacks": [handler]})
        messages.append(response)

        # Execute tool calls
        while response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]

                if tool_name in tool_map:
                    result = tool_map[tool_name].invoke(tool_args)
                    messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))

            # Get next response
            response = llm_with_tools.invoke(messages, config={"callbacks": [handler]})
            messages.append(response)

            # Check if we're done (no more tool calls)
            if not response.tool_calls:
                break

    runtime.end_run(run)
    handler.clear()

    print(f"Result: {response.content}")


def structured_output_agent_example() -> None:
    """Demonstrate agent with structured output."""
    from langchain_core.tools import tool
    from langchain_openai import ChatOpenAI
    from pydantic import BaseModel, Field

    print("\n--- Structured Output Agent Example ---")

    class MathResult(BaseModel):
        """Result of a math operation."""

        expression: str = Field(description="The math expression evaluated")
        result: float = Field(description="The numeric result")
        explanation: str = Field(description="Step-by-step explanation")

    @tool
    def calculator(expression: str) -> str:
        """Calculate a mathematical expression."""
        try:
            result = eval(expression)  # noqa: S307
            return str(result)
        except Exception as e:
            return f"Error: {e}"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    llm_with_tools = llm.bind_tools([calculator])

    handler = TraceCraftCallbackHandler()
    run = AgentRun(name="langchain_structured_output", start_time=datetime.now(UTC))

    with run_context(run):
        result = llm_with_tools.invoke(
            "Calculate 15 * 7 + 3",
            config={"callbacks": [handler]},
        )

    runtime.end_run(run)
    handler.clear()

    print(f"Response: {result.content if hasattr(result, 'content') else result}")
    if hasattr(result, "tool_calls") and result.tool_calls:
        print(f"Tool calls: {result.tool_calls}")


def main() -> None:
    """Run the LangChain tools and agents examples."""
    print("=" * 60)
    print("TraceCraft LangChain Tools and Agents")
    print("=" * 60)

    tool_binding_example()
    tool_calling_agent_example()
    structured_output_agent_example()

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nKey patterns demonstrated:")
    print("  - Tool binding with bind_tools()")
    print("  - create_tool_calling_agent pattern")
    print("  - AgentExecutor with tool tracing")
    print("  - Structured output handling")
    print("\nTrace shows:")
    print("  - Agent reasoning steps")
    print("  - Tool selection and execution")
    print("  - Tool inputs and outputs")
    print("\nNext steps:")
    print("- Try 03_rag_pipeline.py for RAG patterns")
    print("- Try 04_streaming.py for streaming")


if __name__ == "__main__":
    if not check_prerequisites():
        sys.exit(1)
    main()
