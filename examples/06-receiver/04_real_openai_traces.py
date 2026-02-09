#!/usr/bin/env python3
"""Real OpenAI Traces - Send actual LLM traces to the receiver.

This example makes real OpenAI API calls instrumented with OpenTelemetry,
sending traces to the TraceCraft receiver for viewing in the TUI.

Prerequisites:
    - Receiver running (see 01_receiver_demo.py)
    - pip install openai opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http opentelemetry-instrumentation-openai

Environment Variables:
    - OPENAI_API_KEY: Your OpenAI API key

Usage:
    # Terminal 1: Start the receiver
    python examples/06-receiver/01_receiver_demo.py

    # Terminal 2: Run this script
    python examples/06-receiver/04_real_openai_traces.py

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
        print("Or create a .env file with OPENAI_API_KEY=your-key-here")
        return False

    missing = []
    try:
        import openai  # noqa: F401
    except ImportError:
        missing.append("openai")

    try:
        from opentelemetry import trace  # noqa: F401
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # noqa: F401
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.trace import TracerProvider  # noqa: F401
    except ImportError:
        missing.append("opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http")

    try:
        from opentelemetry.instrumentation.openai import OpenAIInstrumentor  # noqa: F401
    except ImportError:
        missing.append("opentelemetry-instrumentation-openai")

    if missing:
        print("Error: Missing dependencies")
        print(f"Install with: pip install {' '.join(missing)}")
        return False

    return True


def setup_telemetry() -> None:
    """Configure OpenTelemetry to send traces to TraceCraft receiver."""
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.openai import OpenAIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    # Create resource with service info
    resource = Resource.create(
        {
            "service.name": "openai-demo-agent",
            "service.version": "1.0.0",
        }
    )

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Configure OTLP exporter to send to TraceCraft receiver
    exporter = OTLPSpanExporter(
        endpoint="http://127.0.0.1:4318/v1/traces",
    )

    # Add batch processor
    provider.add_span_processor(BatchSpanProcessor(exporter))

    # Set as global tracer provider
    trace.set_tracer_provider(provider)

    # Instrument OpenAI SDK
    OpenAIInstrumentor().instrument()

    print("OpenTelemetry configured to send to http://127.0.0.1:4318")


def run_simple_chat() -> str:
    """Make a simple chat completion call."""
    import openai

    client = openai.OpenAI()

    print("\n[1/3] Simple chat completion...")
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant. Be concise."},
            {"role": "user", "content": "What is the capital of France? One word answer."},
        ],
        max_tokens=10,
    )

    result = response.choices[0].message.content or ""
    print(f"  Response: {result}")
    return result


def run_multi_turn_chat() -> str:
    """Make a multi-turn conversation."""
    import openai

    client = openai.OpenAI()

    print("\n[2/3] Multi-turn conversation...")

    messages = [
        {"role": "system", "content": "You are a math tutor. Be very brief."},
        {"role": "user", "content": "What is 2 + 2?"},
    ]

    # First turn
    response1 = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=20,
    )
    answer1 = response1.choices[0].message.content or ""
    print(f"  Turn 1: {answer1}")

    # Add assistant response and follow-up
    messages.append({"role": "assistant", "content": answer1})
    messages.append({"role": "user", "content": "Now multiply that by 3"})

    # Second turn
    response2 = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=20,
    )
    answer2 = response2.choices[0].message.content or ""
    print(f"  Turn 2: {answer2}")

    return answer2


def run_tool_use() -> str:
    """Make a function calling request."""
    import json

    import openai

    client = openai.OpenAI()

    print("\n[3/3] Function calling (tool use)...")

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather in a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city name",
                        },
                    },
                    "required": ["location"],
                },
            },
        }
    ]

    # First call - model decides to use tool
    response1 = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "What's the weather in Tokyo?"}],
        tools=tools,
        tool_choice="auto",
        max_tokens=100,
    )

    message = response1.choices[0].message
    if message.tool_calls:
        tool_call = message.tool_calls[0]
        print(f"  Tool called: {tool_call.function.name}")
        print(f"  Arguments: {tool_call.function.arguments}")

        # Simulate tool response
        tool_result = json.dumps({"temperature": 22, "conditions": "Sunny"})

        # Second call - with tool result
        response2 = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": "What's the weather in Tokyo?"},
                message,
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                },
            ],
            max_tokens=100,
        )

        result = response2.choices[0].message.content or ""
        print(f"  Final response: {result}")
        return result

    return message.content or ""


def main() -> None:
    """Run real OpenAI traces example."""
    print("=" * 60)
    print("TraceCraft Real OpenAI Traces Example")
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

    # Setup OpenTelemetry
    setup_telemetry()

    print("\nRunning OpenAI calls (traces will be sent to receiver)...")
    print("-" * 60)

    # Run examples
    run_simple_chat()
    run_multi_turn_chat()
    run_tool_use()

    # Flush traces
    from opentelemetry import trace

    provider = trace.get_tracer_provider()
    if hasattr(provider, "force_flush"):
        provider.force_flush()

    print("\n" + "=" * 60)
    print("Done! Traces sent to receiver.")
    print("View with: tracecraft ui sqlite://traces/receiver_demo.db")
    print("=" * 60)


if __name__ == "__main__":
    if not check_prerequisites():
        sys.exit(1)
    main()
