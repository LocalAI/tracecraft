#!/usr/bin/env python3
"""Simple setup example using tracecraft.otel.setup_exporter().

This example demonstrates the streamlined API for configuring OpenTelemetry
to send traces to the TraceCraft receiver. Compare this to the manual setup
in 04_real_openai_traces.py to see the difference!

Prerequisites:
    - Receiver running (see 01_receiver_demo.py)
    - pip install openai opentelemetry-instrumentation-openai

Environment Variables:
    - OPENAI_API_KEY: Your OpenAI API key

Usage:
    # Terminal 1: Start the receiver
    python examples/06-receiver/01_receiver_demo.py

    # Terminal 2: Run this script
    python examples/06-receiver/06_simple_setup.py

    # Terminal 3: View in TUI
    tracecraft ui sqlite://traces/receiver_demo.db
"""

from __future__ import annotations

import os
import sys


def check_prerequisites() -> bool:
    """Verify all prerequisites are met."""
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Set it with: export OPENAI_API_KEY='your-key-here'")
        return False

    try:
        import openai  # noqa: F401
    except ImportError:
        print("Error: openai not installed. Install with: pip install openai")
        return False

    return True


def main() -> None:
    """Run the simple setup example."""
    print("=" * 60)
    print("TraceCraft Simple Setup Example")
    print("=" * 60)

    # Check receiver is running
    import requests

    try:
        health = requests.get("http://127.0.0.1:4318/health", timeout=2)
        if health.status_code != 200:
            print("\nError: Receiver not healthy")
            return
    except requests.ConnectionError:
        print("\nError: Receiver not running!")
        print("Start the receiver first:")
        print("  python examples/06-receiver/01_receiver_demo.py")
        return

    print("\nReceiver is healthy!")

    # ========================================================================
    # THE MAGIC: Just 3 lines to configure everything!
    # ========================================================================
    from tracecraft.otel import setup_exporter

    tracer = setup_exporter(
        endpoint="http://localhost:4318",
        service_name="simple-demo-agent",
        instrument=["openai"],  # Auto-instrument OpenAI SDK
    )
    # ========================================================================

    print("\nOpenTelemetry configured with tracecraft.otel.setup_exporter()!")
    print("Compare this to the 20+ lines in 04_real_openai_traces.py\n")

    # Now make some OpenAI calls - they're automatically traced!
    import openai

    client = openai.OpenAI()

    print("Running OpenAI calls (automatically traced)...")
    print("-" * 60)

    # Example 1: Simple question
    print("\n[1/2] Simple question...")
    with tracer.start_as_current_span("SimpleQuestion") as span:
        span.set_attribute("tracecraft.step.type", "AGENT")
        span.set_attribute("input.value", '{"question": "What is 2+2?"}')

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": "What is 2+2? One word answer."},
            ],
            max_tokens=10,
        )
        result = response.choices[0].message.content or ""
        span.set_attribute("output.value", f'{{"answer": "{result}"}}')
        print(f"  Answer: {result}")

    # Example 2: Multi-turn conversation
    print("\n[2/2] Multi-turn conversation...")
    with tracer.start_as_current_span("Conversation") as span:
        span.set_attribute("tracecraft.step.type", "AGENT")
        span.set_attribute("input.value", '{"task": "Brief conversation"}')

        messages = [
            {"role": "system", "content": "You are helpful. Be very brief."},
            {"role": "user", "content": "Name a color."},
        ]

        response1 = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=10,
        )
        color = response1.choices[0].message.content or ""
        print(f"  Color: {color}")

        messages.append({"role": "assistant", "content": color})
        messages.append({"role": "user", "content": "Name something that color."})

        response2 = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=20,
        )
        thing = response2.choices[0].message.content or ""
        span.set_attribute("output.value", f'{{"color": "{color}", "thing": "{thing}"}}')
        print(f"  Thing: {thing}")

    # Flush traces before exit
    from tracecraft.otel import flush_traces

    flush_traces()

    print("\n" + "=" * 60)
    print("Done! Traces sent to receiver.")
    print("View with: tracecraft ui sqlite://traces/receiver_demo.db")
    print("=" * 60)


if __name__ == "__main__":
    if not check_prerequisites():
        sys.exit(1)
    main()
