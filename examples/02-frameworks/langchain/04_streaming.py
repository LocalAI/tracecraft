#!/usr/bin/env python3
"""LangChain Streaming - Trace streaming responses with TraceCraft.

Demonstrates how to trace LangChain streaming responses, including
token-by-token output and streaming callbacks.

Prerequisites:
    - pip install langchain-openai

Environment Variables:
    - OPENAI_API_KEY: Your OpenAI API key

External Services:
    - OpenAI API

Usage:
    python examples/02-frameworks/langchain/04_streaming.py

Expected Output:
    - Streaming tokens printed in real-time
    - Trace showing streaming flag and collected tokens
    - Complete response captured in trace
"""

from __future__ import annotations

import asyncio
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


def basic_streaming_example() -> None:
    """Demonstrate basic streaming with tracing."""
    from langchain_openai import ChatOpenAI

    print("\n--- Basic Streaming Example ---")
    print("Streaming response: ", end="", flush=True)

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, streaming=True)

    handler = TraceCraftCallbackHandler()
    run = AgentRun(name="langchain_basic_streaming", start_time=datetime.now(UTC))

    collected_tokens = []

    with run_context(run):
        for chunk in llm.stream(
            "Count from 1 to 5, one number per line.",
            config={"callbacks": [handler]},
        ):
            token = chunk.content
            collected_tokens.append(token)
            print(token, end="", flush=True)

    print()  # Newline after streaming

    runtime.end_run(run)
    handler.clear()

    print(f"\nTotal chunks: {len(collected_tokens)}")


def streaming_chain_example() -> None:
    """Demonstrate streaming through a chain."""
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI

    print("\n--- Streaming Chain Example ---")
    print("Streaming chain response: ", end="", flush=True)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a helpful assistant. Be concise."),
            ("human", "{input}"),
        ]
    )
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, streaming=True)
    chain = prompt | llm | StrOutputParser()

    handler = TraceCraftCallbackHandler()
    run = AgentRun(name="langchain_streaming_chain", start_time=datetime.now(UTC))

    collected_output = []

    with run_context(run):
        for chunk in chain.stream(
            {"input": "What are the 3 primary colors?"},
            config={"callbacks": [handler]},
        ):
            collected_output.append(chunk)
            print(chunk, end="", flush=True)

    print()  # Newline after streaming

    runtime.end_run(run)
    handler.clear()

    print(f"Complete response: {''.join(collected_output)}")


async def async_streaming_example() -> None:
    """Demonstrate async streaming with tracing."""
    from langchain_openai import ChatOpenAI

    print("\n--- Async Streaming Example ---")
    print("Async streaming response: ", end="", flush=True)

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, streaming=True)

    handler = TraceCraftCallbackHandler()
    run = AgentRun(name="langchain_async_streaming", start_time=datetime.now(UTC))

    collected_tokens = []

    with run_context(run):
        async for chunk in llm.astream(
            "Name 3 planets in our solar system.",
            config={"callbacks": [handler]},
        ):
            token = chunk.content
            collected_tokens.append(token)
            print(token, end="", flush=True)

    print()  # Newline after streaming

    runtime.end_run(run)
    handler.clear()

    print(f"Total chunks: {len(collected_tokens)}")


def streaming_with_events_example() -> None:
    """Demonstrate streaming with event handling."""
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI

    print("\n--- Streaming with Events Example ---")

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a poet. Write a haiku."),
            ("human", "{topic}"),
        ]
    )
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7, streaming=True)
    chain = prompt | llm | StrOutputParser()

    handler = TraceCraftCallbackHandler()
    run = AgentRun(name="langchain_streaming_events", start_time=datetime.now(UTC))

    print("Haiku: ", end="", flush=True)

    with run_context(run):
        for chunk in chain.stream(
            {"topic": "autumn leaves"},
            config={"callbacks": [handler]},
        ):
            print(chunk, end="", flush=True)

    print()

    runtime.end_run(run)
    handler.clear()


def batch_streaming_example() -> None:
    """Demonstrate batch streaming with multiple inputs."""
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI

    print("\n--- Batch Streaming Example ---")

    prompt = ChatPromptTemplate.from_template("Translate to Spanish: {word}")
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    chain = prompt | llm | StrOutputParser()

    handler = TraceCraftCallbackHandler()
    run = AgentRun(name="langchain_batch_streaming", start_time=datetime.now(UTC))

    words = [{"word": "hello"}, {"word": "world"}, {"word": "goodbye"}]

    with run_context(run):
        # Batch invoke (not streaming, but shows batch tracing)
        results = chain.batch(words, config={"callbacks": [handler]})

    runtime.end_run(run)
    handler.clear()

    for word_dict, translation in zip(words, results):
        print(f"{word_dict['word']} -> {translation}")


def main() -> None:
    """Run the LangChain streaming examples."""
    print("=" * 60)
    print("TraceCraft LangChain Streaming")
    print("=" * 60)

    basic_streaming_example()
    streaming_chain_example()
    asyncio.run(async_streaming_example())
    streaming_with_events_example()
    batch_streaming_example()

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nKey patterns demonstrated:")
    print("  - Basic LLM streaming with .stream()")
    print("  - Chain streaming with output parser")
    print("  - Async streaming with .astream()")
    print("  - Batch processing with tracing")
    print("\nTrace shows:")
    print("  - Streaming flag on LLM steps")
    print("  - Collected streaming chunks")
    print("  - Complete response text")
    print("\nNext steps:")
    print("- Check traces.jsonl for detailed trace data")
    print("- Try ../langgraph/ for agent workflows")


if __name__ == "__main__":
    if not check_prerequisites():
        sys.exit(1)
    main()
