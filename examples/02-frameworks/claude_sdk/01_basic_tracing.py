#!/usr/bin/env python3
"""
Claude Agent SDK - Basic Tracing Example

Demonstrates basic integration of TraceCraft with Claude Agent SDK.

Prerequisites:
    - pip install tracecraft claude-code-sdk
    - ANTHROPIC_API_KEY environment variable

Usage:
    python examples/02-frameworks/claude_sdk/01_basic_tracing.py

Expected Output:
    - Console trace tree showing tool executions
    - JSONL file with detailed trace data
"""

from __future__ import annotations

import asyncio
import os

from tracecraft import TraceCraftRuntime
from tracecraft.adapters.claude_sdk import ClaudeTraceCraftr


async def main() -> None:
    """Run Claude agent with basic tracing."""
    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY to run this example")
        print("\nThis example demonstrates the ClaudeTraceCraftr API:")
        print_api_demo()
        return

    # Import Claude SDK (optional dependency)
    try:
        from claude_code_sdk import query
    except ImportError:
        print("Install claude-code-sdk: pip install claude-code-sdk")
        print("\nThis example demonstrates the ClaudeTraceCraftr API:")
        print_api_demo()
        return

    # Initialize tracing
    runtime = TraceCraftRuntime(console=True, jsonl=True)
    tracer = ClaudeTraceCraftr(runtime=runtime)

    # Trace an agent task
    print("Running Claude agent with tracing...")
    print("=" * 60)

    with runtime.run("code_analysis") as run:
        async for message in query(
            prompt="List the Python files in the current directory",
            options=tracer.get_options(
                allowed_tools=["Glob", "Read"],
                max_turns=3,
            ),
        ):
            # Print streamed output
            if hasattr(message, "content"):
                print(message.content)

    print("=" * 60)
    print("\nTrace Summary:")
    print(f"  Steps captured: {len(run.steps)}")
    print(f"  Total duration: {run.duration_ms:.0f}ms")

    # Show step breakdown
    print("\nSteps:")
    for i, step in enumerate(run.steps, 1):
        print(f"  {i}. {step.name} ({step.type.value}) - {step.duration_ms:.0f}ms")


def print_api_demo() -> None:
    """Print API demonstration without requiring Claude SDK."""
    print(
        """
ClaudeTraceCraftr API Demo
==========================

1. Basic Usage:
   ```python
   from tracecraft import TraceCraftRuntime
   from tracecraft.adapters.claude_sdk import ClaudeTraceCraftr

   runtime = TraceCraftRuntime(console=True, jsonl=True)
   tracer = ClaudeTraceCraftr(runtime=runtime)

   with runtime.run("my_task") as run:
       async for message in query(
           prompt="Your prompt here",
           options=tracer.get_options(
               allowed_tools=["Read", "Glob", "Grep"]
           )
       ):
           print(message)
   ```

2. Using the trace() context manager:
   ```python
   tracer = ClaudeTraceCraftr()  # Creates runtime automatically

   with tracer.trace("my_task") as run:
       async for message in query(
           prompt="Your prompt",
           options=tracer.get_options()
       ):
           print(message)
   ```

3. Tool Type Mapping:
"""
    )

    # Demonstrate tool type inference
    from tracecraft.adapters.claude_sdk import ClaudeTraceCraftr

    tracer = ClaudeTraceCraftr()

    tool_names = [
        "Read",
        "Write",
        "Bash",
        "Glob",
        "Grep",
        "WebSearch",
        "Task",
        "EnterPlanMode",
        "mcp__github__list_issues",
    ]

    for tool_name in tool_names:
        step_type = tracer._infer_step_type(tool_name)
        print(f"   {tool_name:30} -> {step_type.value}")


if __name__ == "__main__":
    asyncio.run(main())
