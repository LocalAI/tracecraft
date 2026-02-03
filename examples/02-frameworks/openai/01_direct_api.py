#!/usr/bin/env python3
"""OpenAI Direct API - Trace OpenAI SDK calls with decorators.

Demonstrates how to trace direct OpenAI API calls using TraceCraft decorators.
This approach works for any LLM provider where you're making direct API calls.

Prerequisites:
    - pip install openai

Environment Variables:
    - OPENAI_API_KEY: Your OpenAI API key

External Services:
    - OpenAI API

Usage:
    python examples/02-frameworks/openai/01_direct_api.py

Expected Output:
    - Trace showing LLM calls with model info and timing
    - Streaming call captured as single trace
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime

import tracecraft
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from tracecraft.instrumentation.decorators import trace_agent, trace_llm


def check_prerequisites() -> bool:
    """Verify all prerequisites are met."""
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Set it with: export OPENAI_API_KEY='your-key-here'")
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


@trace_llm(name="chat_completion", model="gpt-4o-mini", provider="openai")
def chat_completion(prompt: str, max_tokens: int = 100) -> str:
    """Make a chat completion call to OpenAI.

    The @trace_llm decorator captures:
    - Function name and model info
    - Input prompt
    - Output response
    - Duration
    - Any errors
    """
    import openai

    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


@trace_llm(name="streaming_chat", model="gpt-4o-mini", provider="openai")
def streaming_chat(prompt: str, max_tokens: int = 100) -> str:
    """Make a streaming chat completion call.

    For streaming, the decorator captures the aggregated response.
    For token-level streaming traces, see 09-advanced/01_streaming_traces.py
    """
    import openai

    client = openai.OpenAI()
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        stream=True,
    )

    chunks = []
    for chunk in stream:
        if chunk.choices[0].delta.content:
            chunks.append(chunk.choices[0].delta.content)

    return "".join(chunks)


@trace_agent(name="chat_agent")
def chat_agent(question: str) -> str:
    """An agent that uses OpenAI for chat.

    The @trace_agent decorator groups all nested calls
    into a single agent trace.
    """
    # First call: Analyze the question
    analysis = chat_completion(f"Briefly analyze this question: {question}")

    # Second call: Generate answer with streaming
    answer = streaming_chat(f"Answer concisely: {question}")

    return f"Analysis: {analysis}\n\nAnswer: {answer}"


def main() -> None:
    """Run the OpenAI direct API example."""
    print("=" * 60)
    print("TraceCraft OpenAI Direct API Example")
    print("=" * 60)

    run = AgentRun(name="openai_example", start_time=datetime.now(UTC))

    with run_context(run):
        result = chat_agent("What is the capital of France?")

    runtime.end_run(run)

    print("\n" + "=" * 60)
    print("Result:")
    print(result)
    print("=" * 60)
    print("\nKey points:")
    print("  - @trace_llm captures model, provider, and call details")
    print("  - @trace_agent groups nested LLM calls")
    print("  - Streaming calls are captured as complete responses")
    print("\nNext steps:")
    print("- Try 02_function_calling.py for tool use")
    print("- Try 03_streaming.py for token-level tracing")


if __name__ == "__main__":
    if not check_prerequisites():
        sys.exit(1)
    main()
