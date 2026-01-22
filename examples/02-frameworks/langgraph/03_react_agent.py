#!/usr/bin/env python3
"""LangGraph ReAct Agent - Trace tool-using agents with LangGraph.

Demonstrates tracing LangGraph agents that use tools in a ReAct
(Reasoning + Acting) pattern.

Prerequisites:
    - pip install langgraph langchain-openai

Environment Variables:
    - OPENAI_API_KEY: Your OpenAI API key

External Services:
    - OpenAI API

Usage:
    python examples/02-frameworks/langgraph/03_react_agent.py

Expected Output:
    - Trace showing agent reasoning steps
    - Tool calls captured with inputs/outputs
    - Multiple iterations visible in trace
"""

from __future__ import annotations

import operator
import os
import sys
from datetime import UTC, datetime
from typing import Annotated, TypedDict

import agenttrace
from agenttrace.adapters.langchain import AgentTraceCallbackHandler
from agenttrace.core.context import run_context
from agenttrace.core.models import AgentRun


def check_prerequisites() -> bool:
    """Verify all prerequisites are met."""
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        return False

    try:
        import langchain_openai  # noqa: F401
        import langgraph  # noqa: F401
    except ImportError:
        print("Error: langgraph or langchain-openai not installed")
        print("Install with: pip install langgraph langchain-openai")
        return False

    return True


# Initialize AgentTrace
runtime = agenttrace.init(
    console=True,
    jsonl=True,
    jsonl_path="traces.jsonl",
)


def prebuilt_react_example() -> None:
    """Demonstrate the prebuilt ReAct agent with tracing."""
    from langchain_core.tools import tool
    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent

    print("\n--- Prebuilt ReAct Agent Example ---")

    # Define tools
    @tool
    def calculator(expression: str) -> str:
        """Calculate a mathematical expression. Use Python syntax."""
        try:
            result = eval(expression)  # noqa: S307
            return f"Result: {result}"
        except Exception as e:
            return f"Error: {e}"

    @tool
    def get_weather(city: str) -> str:
        """Get the current weather for a city."""
        # Simulated weather data
        weather_data = {
            "new york": "72°F, Partly cloudy",
            "london": "58°F, Rainy",
            "tokyo": "68°F, Clear",
            "paris": "65°F, Sunny",
        }
        return weather_data.get(city.lower(), f"Weather data not available for {city}")

    @tool
    def search_web(query: str) -> str:
        """Search the web for information."""
        # Simulated search results
        return f"Search results for '{query}': Found 3 relevant articles about {query}."

    # Create the LLM
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    # Create the ReAct agent using the prebuilt function
    agent = create_react_agent(llm, [calculator, get_weather, search_web])

    handler = AgentTraceCallbackHandler()

    # Test queries that require tools
    queries = [
        "What is 25 * 4 + 10?",
        "What's the weather in Paris?",
    ]

    for query in queries:
        run = AgentRun(name="langgraph_react", start_time=datetime.now(UTC))

        with run_context(run):
            result = agent.invoke(
                {"messages": [("user", query)]},
                config={"callbacks": [handler]},
            )

        runtime.end_run(run)
        handler.clear()

        # Extract final response
        final_message = result["messages"][-1]
        print(f"Query: {query}")
        print(f"Response: {final_message.content}")
        print()


class AgentState(TypedDict):
    """State for the custom agent."""

    messages: Annotated[list, operator.add]
    tool_calls: list
    iteration: int


def custom_react_example() -> None:
    """Demonstrate a custom ReAct-style agent with tracing."""
    from langchain_core.messages import HumanMessage, ToolMessage
    from langchain_core.tools import tool
    from langchain_openai import ChatOpenAI
    from langgraph.graph import END, StateGraph

    print("\n--- Custom ReAct Agent Example ---")

    @tool
    def multiply(a: int, b: int) -> int:
        """Multiply two numbers."""
        return a * b

    @tool
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    tools = [multiply, add]
    tool_map = {t.name: t for t in tools}

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools(tools)

    def agent_node(state: AgentState) -> AgentState:
        """The agent decides what to do."""
        response = llm.invoke(state["messages"])
        return {
            "messages": [response],
            "tool_calls": response.tool_calls if hasattr(response, "tool_calls") else [],
            "iteration": state["iteration"] + 1,
        }

    def tool_node(state: AgentState) -> AgentState:
        """Execute the tools."""
        results = []
        for tool_call in state["tool_calls"]:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            if tool_name in tool_map:
                result = tool_map[tool_name].invoke(tool_args)
                results.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))

        return {"messages": results, "tool_calls": [], "iteration": state["iteration"]}

    def should_continue(state: AgentState) -> str:
        """Decide whether to continue or end."""
        if state["tool_calls"] and state["iteration"] < 5:
            return "tools"
        return "end"

    # Build the graph
    graph = StateGraph(AgentState)

    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    graph.set_entry_point("agent")

    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END,
        },
    )

    graph.add_edge("tools", "agent")

    app = graph.compile()

    handler = AgentTraceCallbackHandler()

    query = "What is 7 times 8, then add 6 to the result?"

    run = AgentRun(name="langgraph_custom_react", start_time=datetime.now(UTC))

    with run_context(run):
        result = app.invoke(
            {
                "messages": [HumanMessage(content=query)],
                "tool_calls": [],
                "iteration": 0,
            },
            config={"callbacks": [handler]},
        )

    runtime.end_run(run)
    handler.clear()

    # Get final response
    final_message = result["messages"][-1]
    print(f"Query: {query}")
    print(f"Response: {final_message.content}")
    print(f"Iterations: {result['iteration']}")


def main() -> None:
    """Run the ReAct agent examples."""
    print("=" * 60)
    print("AgentTrace LangGraph ReAct Agents")
    print("=" * 60)

    prebuilt_react_example()
    custom_react_example()

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nKey patterns demonstrated:")
    print("  - Prebuilt ReAct agent with create_react_agent()")
    print("  - Custom ReAct loop with tool execution")
    print("  - Tool calls traced with inputs/outputs")
    print("  - Multiple iterations visible in trace")
    print("\nTrace shows:")
    print("  - Agent reasoning (LLM calls)")
    print("  - Tool selection and execution")
    print("  - Iterative refinement loop")


if __name__ == "__main__":
    if not check_prerequisites():
        sys.exit(1)
    main()
