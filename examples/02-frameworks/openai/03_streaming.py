#!/usr/bin/env python3
"""OpenAI Streaming - Trace streaming responses with AgentTrace.

Demonstrates how to trace OpenAI streaming responses at the token level
using AgentTrace decorators.

Prerequisites:
    - pip install openai

Environment Variables:
    - OPENAI_API_KEY: Your OpenAI API key

External Services:
    - OpenAI API

Usage:
    python examples/02-frameworks/openai/03_streaming.py

Expected Output:
    - Streaming tokens printed in real-time
    - Traces capturing streaming flag and timing
    - Complete response in trace
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime

import agenttrace
from agenttrace.core.context import run_context
from agenttrace.core.models import AgentRun
from agenttrace.instrumentation.decorators import trace_llm


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


# Initialize AgentTrace
runtime = agenttrace.init(
    console=True,
    jsonl=True,
    jsonl_path="traces.jsonl",
)


@trace_llm(name="basic_stream", model="gpt-4o-mini", provider="openai")
def basic_streaming(prompt: str) -> str:
    """Demonstrate basic streaming with tracing."""
    import openai

    client = openai.OpenAI()
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        max_tokens=100,
    )

    chunks = []
    for chunk in stream:
        if chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            chunks.append(content)
            print(content, end="", flush=True)

    print()  # Newline
    return "".join(chunks)


@trace_llm(name="stream_with_usage", model="gpt-4o-mini", provider="openai")
def streaming_with_usage(prompt: str) -> tuple[str, dict]:
    """Demonstrate streaming with usage statistics."""
    import openai

    client = openai.OpenAI()
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        stream_options={"include_usage": True},
        max_tokens=100,
    )

    chunks = []
    usage = None

    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            chunks.append(content)
            print(content, end="", flush=True)

        # Usage comes in the final chunk
        if chunk.usage:
            usage = {
                "prompt_tokens": chunk.usage.prompt_tokens,
                "completion_tokens": chunk.usage.completion_tokens,
                "total_tokens": chunk.usage.total_tokens,
            }

    print()  # Newline
    return "".join(chunks), usage or {}


async def async_streaming_helper(prompt: str) -> str:
    """Helper for async streaming."""
    import openai

    client = openai.AsyncOpenAI()
    stream = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        max_tokens=100,
    )

    chunks = []
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            chunks.append(content)
            print(content, end="", flush=True)

    print()  # Newline
    return "".join(chunks)


@trace_llm(name="async_stream", model="gpt-4o-mini", provider="openai")
def async_streaming(prompt: str) -> str:
    """Demonstrate async streaming with tracing."""
    return asyncio.run(async_streaming_helper(prompt))


@trace_llm(name="system_stream", model="gpt-4o-mini", provider="openai")
def streaming_with_system(system: str, user: str) -> str:
    """Demonstrate streaming with system message."""
    import openai

    client = openai.OpenAI()
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        stream=True,
        max_tokens=150,
    )

    chunks = []
    for chunk in stream:
        if chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            chunks.append(content)
            print(content, end="", flush=True)

    print()
    return "".join(chunks)


@trace_llm(name="multi_turn_stream", model="gpt-4o-mini", provider="openai")
def multi_turn_streaming(messages: list) -> str:
    """Demonstrate multi-turn streaming."""
    import openai

    client = openai.OpenAI()
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        stream=True,
        max_tokens=100,
    )

    chunks = []
    for chunk in stream:
        if chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            chunks.append(content)
            print(content, end="", flush=True)

    print()
    return "".join(chunks)


def basic_streaming_example() -> None:
    """Run basic streaming example."""
    print("\n--- Basic Streaming Example ---")
    print("Response: ", end="", flush=True)

    run = AgentRun(name="openai_basic_streaming", start_time=datetime.now(UTC))

    with run_context(run):
        result = basic_streaming("Count from 1 to 5, one number per line.")

    runtime.end_run(run)


def usage_streaming_example() -> None:
    """Run streaming with usage example."""
    print("\n--- Streaming with Usage Example ---")
    print("Response: ", end="", flush=True)

    run = AgentRun(name="openai_streaming_usage", start_time=datetime.now(UTC))

    with run_context(run):
        result, usage = streaming_with_usage("What are the three primary colors?")

    runtime.end_run(run)

    if usage:
        print(
            f"Tokens - Prompt: {usage.get('prompt_tokens')}, "
            f"Completion: {usage.get('completion_tokens')}, "
            f"Total: {usage.get('total_tokens')}"
        )


def async_streaming_example() -> None:
    """Run async streaming example."""
    print("\n--- Async Streaming Example ---")
    print("Response: ", end="", flush=True)

    run = AgentRun(name="openai_async_streaming", start_time=datetime.now(UTC))

    with run_context(run):
        result = async_streaming("Name three planets in our solar system.")

    runtime.end_run(run)


def system_message_example() -> None:
    """Run streaming with system message."""
    print("\n--- Streaming with System Message ---")
    print("Response: ", end="", flush=True)

    run = AgentRun(name="openai_system_streaming", start_time=datetime.now(UTC))

    with run_context(run):
        result = streaming_with_system(
            system="You are a pirate. Speak like one.",
            user="Tell me about the ocean.",
        )

    runtime.end_run(run)


def multi_turn_example() -> None:
    """Run multi-turn streaming example."""
    print("\n--- Multi-Turn Streaming Example ---")

    run = AgentRun(name="openai_multi_turn_streaming", start_time=datetime.now(UTC))

    messages = [
        {"role": "user", "content": "What is 2 + 2?"},
    ]

    with run_context(run):
        print("Turn 1: ", end="", flush=True)
        response1 = multi_turn_streaming(messages)

        messages.append({"role": "assistant", "content": response1})
        messages.append({"role": "user", "content": "And what is that times 3?"})

        print("Turn 2: ", end="", flush=True)
        response2 = multi_turn_streaming(messages)

    runtime.end_run(run)


def main() -> None:
    """Run the OpenAI streaming examples."""
    print("=" * 60)
    print("AgentTrace OpenAI Streaming")
    print("=" * 60)

    basic_streaming_example()
    usage_streaming_example()
    async_streaming_example()
    system_message_example()
    multi_turn_example()

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nKey patterns demonstrated:")
    print("  - Basic streaming with real-time output")
    print("  - Streaming with usage statistics")
    print("  - Async streaming with asyncio")
    print("  - System message with streaming")
    print("  - Multi-turn conversation streaming")
    print("\nTrace shows:")
    print("  - Streaming flag on LLM steps")
    print("  - Complete aggregated response")
    print("  - Token counts (when available)")


if __name__ == "__main__":
    if not check_prerequisites():
        sys.exit(1)
    main()
