#!/usr/bin/env python3
"""LangGraph Multi-Node Graph - Trace complex graphs with conditional routing.

Demonstrates tracing LangGraph graphs with multiple nodes, conditional
edges, and parallel execution paths.

Prerequisites:
    - pip install langgraph langchain-openai

Environment Variables:
    - OPENAI_API_KEY: Your OpenAI API key

External Services:
    - OpenAI API

Usage:
    python examples/02-frameworks/langgraph/02_multi_node_graph.py

Expected Output:
    - Trace showing multi-node execution
    - Conditional routing decisions captured
    - Parallel branches visible in trace
"""

from __future__ import annotations

import operator
import os
import sys
from datetime import UTC, datetime
from typing import Annotated, Literal, TypedDict

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


class RouterState(TypedDict):
    """State for the router graph."""

    query: str
    category: str
    response: str
    messages: Annotated[list[str], operator.add]


def conditional_routing_example() -> None:
    """Demonstrate conditional routing with tracing."""
    from langchain_openai import ChatOpenAI
    from langgraph.graph import END, StateGraph

    print("\n--- Conditional Routing Example ---")

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    # Classifier node
    def classify_query(state: RouterState) -> RouterState:
        """Classify the query into a category."""
        prompt = f"""Classify this query into one of: math, geography, other.
Query: {state["query"]}
Respond with just the category name."""
        response = llm.invoke(prompt)
        category = response.content.strip().lower()
        return {"category": category, "messages": [f"Classified as: {category}"]}

    # Math expert node
    def math_expert(state: RouterState) -> RouterState:
        """Handle math queries."""
        prompt = f"You are a math expert. Answer: {state['query']}"
        response = llm.invoke(prompt)
        return {"response": response.content, "messages": [f"Math: {response.content}"]}

    # Geography expert node
    def geography_expert(state: RouterState) -> RouterState:
        """Handle geography queries."""
        prompt = f"You are a geography expert. Answer: {state['query']}"
        response = llm.invoke(prompt)
        return {"response": response.content, "messages": [f"Geography: {response.content}"]}

    # General node
    def general_assistant(state: RouterState) -> RouterState:
        """Handle other queries."""
        prompt = f"Answer this question: {state['query']}"
        response = llm.invoke(prompt)
        return {"response": response.content, "messages": [f"General: {response.content}"]}

    # Router function
    def route_query(state: RouterState) -> Literal["math", "geography", "general"]:
        """Route to the appropriate expert."""
        category = state.get("category", "other")
        if "math" in category:
            return "math"
        elif "geo" in category:
            return "geography"
        else:
            return "general"

    # Build the graph
    graph = StateGraph(RouterState)

    # Add nodes
    graph.add_node("classifier", classify_query)
    graph.add_node("math", math_expert)
    graph.add_node("geography", geography_expert)
    graph.add_node("general", general_assistant)

    # Set entry point
    graph.set_entry_point("classifier")

    # Add conditional edges from classifier
    graph.add_conditional_edges(
        "classifier",
        route_query,
        {
            "math": "math",
            "geography": "geography",
            "general": "general",
        },
    )

    # All experts go to END
    graph.add_edge("math", END)
    graph.add_edge("geography", END)
    graph.add_edge("general", END)

    app = graph.compile()

    handler = TraceCraftCallbackHandler()

    # Test with different query types
    queries = [
        "What is 15 * 7?",
        "What is the capital of Japan?",
        "What color is the sky?",
    ]

    for query in queries:
        run = AgentRun(name="langgraph_routing", start_time=datetime.now(UTC))

        with run_context(run):
            result = app.invoke(
                {"query": query, "category": "", "response": "", "messages": []},
                config={"callbacks": [handler]},
            )

        runtime.end_run(run)
        handler.clear()

        print(f"Query: {query}")
        print(f"Route: {result['category']}")
        print(f"Response: {result['response'][:100]}...")
        print()


class PipelineState(TypedDict):
    """State for the pipeline graph."""

    text: str
    summary: str
    sentiment: str
    keywords: list[str]
    messages: Annotated[list[str], operator.add]


def pipeline_example() -> None:
    """Demonstrate sequential pipeline with tracing."""
    from langchain_openai import ChatOpenAI
    from langgraph.graph import END, StateGraph

    print("\n--- Sequential Pipeline Example ---")

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    def summarize(state: PipelineState) -> PipelineState:
        """Summarize the text."""
        prompt = f"Summarize in one sentence: {state['text']}"
        response = llm.invoke(prompt)
        return {"summary": response.content, "messages": ["Summarized"]}

    def analyze_sentiment(state: PipelineState) -> PipelineState:
        """Analyze sentiment."""
        prompt = f"What is the sentiment (positive/negative/neutral) of: {state['summary']}"
        response = llm.invoke(prompt)
        return {"sentiment": response.content, "messages": ["Analyzed sentiment"]}

    def extract_keywords(state: PipelineState) -> PipelineState:
        """Extract keywords."""
        prompt = f"List 3 keywords from: {state['text']}. Just the words, comma-separated."
        response = llm.invoke(prompt)
        keywords = [k.strip() for k in response.content.split(",")]
        return {"keywords": keywords, "messages": ["Extracted keywords"]}

    # Build sequential pipeline
    graph = StateGraph(PipelineState)

    graph.add_node("summarize", summarize)
    graph.add_node("sentiment", analyze_sentiment)
    graph.add_node("keywords", extract_keywords)

    graph.set_entry_point("summarize")
    graph.add_edge("summarize", "sentiment")
    graph.add_edge("sentiment", "keywords")
    graph.add_edge("keywords", END)

    app = graph.compile()

    handler = TraceCraftCallbackHandler()

    text = """
    The new AI model achieved remarkable results on all benchmarks,
    surpassing previous state-of-the-art by a significant margin.
    Researchers are excited about its potential applications in healthcare
    and scientific discovery.
    """

    run = AgentRun(name="langgraph_pipeline", start_time=datetime.now(UTC))

    with run_context(run):
        result = app.invoke(
            {"text": text, "summary": "", "sentiment": "", "keywords": [], "messages": []},
            config={"callbacks": [handler]},
        )

    runtime.end_run(run)
    handler.clear()

    print(f"Summary: {result['summary']}")
    print(f"Sentiment: {result['sentiment']}")
    print(f"Keywords: {result['keywords']}")


def main() -> None:
    """Run the multi-node graph examples."""
    print("=" * 60)
    print("TraceCraft LangGraph Multi-Node Graphs")
    print("=" * 60)

    conditional_routing_example()
    pipeline_example()

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nKey patterns demonstrated:")
    print("  - Conditional routing with add_conditional_edges")
    print("  - Sequential pipeline with multiple nodes")
    print("  - Each node's LLM calls traced separately")
    print("  - Routing decisions visible in trace")
    print("\nNext steps:")
    print("- Try 03_react_agent.py for tool-using agents")


if __name__ == "__main__":
    if not check_prerequisites():
        sys.exit(1)
    main()
