#!/usr/bin/env python3
"""Hello World - The simplest possible AgentTrace example.

This is the absolute minimum code needed to start tracing with AgentTrace.
No API keys or external services required - everything is mocked.

Prerequisites:
    - AgentTrace installed (pip install agenttrace)

Environment Variables:
    - None required

External Services:
    - None required

Usage:
    python examples/01-getting-started/01_hello_world.py

Expected Output:
    - Console output showing the trace tree
    - JSONL file at traces/agenttrace.jsonl
"""

from __future__ import annotations

import agenttrace
from agenttrace.instrumentation.decorators import trace_llm


def main() -> None:
    """Run the Hello World example."""
    print("=" * 60)
    print("AgentTrace Hello World")
    print("=" * 60)

    # Step 1: Initialize AgentTrace
    # This sets up console and JSONL exporters by default
    runtime = agenttrace.init(
        console=True,  # Show traces in terminal
        jsonl=True,  # Save traces to JSONL file
    )

    # Step 2: Create a traced function using the @trace_llm decorator
    @trace_llm(name="my_llm", model="gpt-4o-mini")
    def call_llm(prompt: str) -> str:
        """A simple function that would normally call an LLM.

        The @trace_llm decorator captures:
        - Function name
        - Model name
        - Inputs and outputs
        - Duration
        - Any errors
        """
        # In a real app, this would call OpenAI, Anthropic, etc.
        return f"Hello! You said: {prompt}"

    # Step 3: Use the runtime's run context to group traces
    with runtime.run("hello_world_run"):
        # Call the traced function
        response = call_llm("Hello, AgentTrace!")
        print(f"\nLLM Response: {response}")

    # The trace is automatically exported when the context exits

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nWhat just happened:")
    print("1. AgentTrace initialized with console + JSONL exporters")
    print("2. @trace_llm decorator captured the LLM call")
    print("3. runtime.run() grouped traces into a single run")
    print("4. Traces were exported to console and traces/agenttrace.jsonl")
    print("\nNext steps:")
    print("- Try 02_decorators.py to learn about all decorator types")
    print("- Try 03_context_managers.py for async patterns")


if __name__ == "__main__":
    main()
