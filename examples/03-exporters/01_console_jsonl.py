#!/usr/bin/env python3
"""Console and JSONL - Default exporters in TraceCraft.

Demonstrates the built-in Console and JSONL exporters that come
with TraceCraft by default.

Prerequisites:
    - TraceCraft installed

Environment Variables:
    - TRACECRAFT_CONSOLE_ENABLED: Enable/disable console (default: true)
    - TRACECRAFT_JSONL_ENABLED: Enable/disable JSONL (default: true)
    - TRACECRAFT_JSONL_PATH: Custom path for JSONL file

External Services:
    - None

Usage:
    python examples/03-exporters/01_console_jsonl.py

Expected Output:
    - Rich tree output in console
    - JSONL file at traces/tracecraft.jsonl
"""

from __future__ import annotations

import json
from pathlib import Path

import tracecraft
from tracecraft.instrumentation.decorators import trace_agent, trace_llm, trace_tool


def main() -> None:
    """Demonstrate console and JSONL exporters."""
    print("=" * 60)
    print("TraceCraft Console and JSONL Exporters")
    print("=" * 60)

    # By default, both console and JSONL are enabled
    runtime = tracecraft.init(
        console=True,  # Rich tree output in terminal
        jsonl=True,  # JSONL file output
        jsonl_path="traces/example_traces.jsonl",  # Custom path
    )

    @trace_tool(name="calculator")
    def calculator(expression: str) -> str:
        """A calculator tool."""
        return str(eval(expression))  # noqa: S307

    @trace_llm(name="reasoner", model="gpt-4o-mini", provider="openai")
    def reason(prompt: str) -> str:
        """Simulate reasoning."""
        return f"Thought about: {prompt}"

    @trace_agent(name="math_agent")
    def math_agent(question: str) -> str:
        """Agent that solves math problems."""
        thought = reason(f"How to solve: {question}")
        result = calculator("2 + 2")
        return f"{thought} Answer: {result}"

    # Run with tracing
    print("\n--- Running traced workflow ---\n")

    with runtime.run("console_jsonl_demo"):
        result = math_agent("What is 2 + 2?")
        print(f"\nAgent result: {result}")

    print("\n--- Console output shown above ---")

    # Show JSONL contents
    print("\n--- JSONL file contents ---")
    jsonl_path = Path("traces/example_traces.jsonl")
    if jsonl_path.exists():
        with open(jsonl_path) as f:
            for line in f:
                data = json.loads(line)
                print(f"Trace: {data.get('name', 'unknown')}")
                print(f"  ID: {data.get('id', 'N/A')}")
                print(f"  Duration: {data.get('duration_ms', 0):.2f}ms")
                print(f"  Steps: {len(data.get('steps', []))}")
    else:
        print(f"  File not found: {jsonl_path}")

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nConsole Exporter:")
    print("  - Rich tree visualization of traces")
    print("  - Shows hierarchy, timing, and errors")
    print("  - Disable with TRACECRAFT_CONSOLE=false")
    print("\nJSONL Exporter:")
    print("  - One JSON object per line (newline-delimited)")
    print("  - Easy to parse with standard tools")
    print("  - Great for log aggregation")
    print("  - Disable with TRACECRAFT_JSONL=false")
    print("\nNext steps:")
    print("- Try 02_otlp_jaeger.py for distributed tracing")
    print("- Try 04_html_reports.py for shareable reports")


if __name__ == "__main__":
    main()
