#!/usr/bin/env python3
"""LangGraph Simple Graph - Trace basic LangGraph state graphs.

Demonstrates how to trace LangGraph state graphs using the existing
TraceCraftCallbackHandler. LangGraph uses the same callback system
as LangChain, so no additional adapter is needed.

Prerequisites:
    - pip install langgraph langchain-openai

Environment Variables:
    - OPENAI_API_KEY: Your OpenAI API key

External Services:
    - OpenAI API

Usage:
    python examples/02-frameworks/langgraph/01_simple_graph.py

Expected Output:
    - Trace showing graph execution with node calls
    - LLM calls within nodes captured
"""

from __future__ import annotations

import operator
import os
import sys
from datetime import UTC, datetime
from typing import Annotated, TypedDict

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
        import langchain_openai  # noqa: F401
        import langgraph  # noqa: F401
    except ImportError:
        print("Error: langgraph or langchain-openai not installed")
        print("Install with: pip install langgraph langchain-openai")
        return False

    return True


# Initialize TraceCraft
runtime = tracecraft.init(
    console=True,
    jsonl=True,
    jsonl_path="traces.jsonl",
)


# Define the state schema
class State(TypedDict):
    """State for the simple graph."""

    messages: Annotated[list[str], operator.add]
    response: str


def simple_graph_example() -> None:
    """Demonstrate simple graph tracing."""
    from langchain_openai import ChatOpenAI
    from langgraph.graph import END, StateGraph

    print("\n--- Simple Graph Example ---")

    # Create the LLM
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    # Define a simple node that calls the LLM
    def chat_node(state: State) -> State:
        """Process messages with LLM."""
        messages = state["messages"]
        prompt = messages[-1] if messages else "Hello"

        response = llm.invoke(prompt)
        return {"messages": [response.content], "response": response.content}

    # Build the graph
    graph = StateGraph(State)
    graph.add_node("chat", chat_node)
    graph.set_entry_point("chat")
    graph.add_edge("chat", END)

    app = graph.compile()

    # Set up TraceCraft callback handler
    handler = TraceCraftCallbackHandler()

    run = AgentRun(name="langgraph_simple", start_time=datetime.now(UTC))

    with run_context(run):
        # Run the graph with tracing
        result = app.invoke(
            {"messages": ["What is the capital of France? One word only."], "response": ""},
            config={"callbacks": [handler]},
        )

    runtime.end_run(run)
    handler.clear()

    print(f"Response: {result['response']}")


def multi_turn_example() -> None:
    """Demonstrate multi-turn conversation tracing."""
    from langchain_openai import ChatOpenAI
    from langgraph.graph import END, StateGraph

    print("\n--- Multi-Turn Conversation Example ---")

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    def chat_node(state: State) -> State:
        """Process messages with LLM."""
        # Build conversation context
        context = "\n".join(state["messages"])
        response = llm.invoke(f"Continue this conversation:\n{context}")
        return {"messages": [response.content], "response": response.content}

    graph = StateGraph(State)
    graph.add_node("chat", chat_node)
    graph.set_entry_point("chat")
    graph.add_edge("chat", END)

    app = graph.compile()

    handler = TraceCraftCallbackHandler()

    run = AgentRun(name="langgraph_multi_turn", start_time=datetime.now(UTC))

    with run_context(run):
        # First turn
        result = app.invoke(
            {"messages": ["User: What is 2+2?"], "response": ""},
            config={"callbacks": [handler]},
        )

        # Second turn - continue conversation
        result = app.invoke(
            {"messages": result["messages"] + ["User: And what is that times 3?"], "response": ""},
            config={"callbacks": [handler]},
        )

    runtime.end_run(run)
    handler.clear()

    print(f"Final response: {result['response']}")


def main() -> None:
    """Run the LangGraph examples."""
    print("=" * 60)
    print("TraceCraft LangGraph Integration")
    print("=" * 60)

    simple_graph_example()
    multi_turn_example()

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nKey points:")
    print("  - LangGraph uses LangChain's callback system")
    print("  - Use TraceCraftCallbackHandler (same as LangChain)")
    print("  - Pass handler via config={'callbacks': [handler]}")
    print("  - Graph nodes and LLM calls are traced automatically")
    print("\nNext steps:")
    print("- Try 02_multi_node_graph.py for conditional routing")
    print("- Try 03_react_agent.py for tool-using agents")


if __name__ == "__main__":
    if not check_prerequisites():
        sys.exit(1)
    main()
