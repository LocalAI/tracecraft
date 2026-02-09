#!/usr/bin/env python3
"""Real Anthropic Traces - Send actual Claude traces to the receiver.

This example makes real Anthropic API calls instrumented with OpenTelemetry,
sending traces to the TraceCraft receiver for viewing in the TUI.

Prerequisites:
    - Receiver running (see 01_receiver_demo.py)
    - pip install anthropic opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http opentelemetry-instrumentation-anthropic

Environment Variables:
    - ANTHROPIC_API_KEY: Your Anthropic API key

Usage:
    # Terminal 1: Start the receiver
    python examples/06-receiver/01_receiver_demo.py

    # Terminal 2: Run this script
    python examples/06-receiver/05_real_anthropic_traces.py

    # Terminal 3: View in TUI
    tracecraft ui sqlite://traces/receiver_demo.db
"""

from __future__ import annotations

import os
import sys


def check_prerequisites() -> bool:
    """Verify all prerequisites are met."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        print("Set it with: export ANTHROPIC_API_KEY='your-key-here'")
        print("Or create a .env file with ANTHROPIC_API_KEY=your-key-here")
        return False

    missing = []
    try:
        import anthropic  # noqa: F401
    except ImportError:
        missing.append("anthropic")

    try:
        from opentelemetry import trace  # noqa: F401
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # noqa: F401
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.trace import TracerProvider  # noqa: F401
    except ImportError:
        missing.append("opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http")

    if missing:
        print("Error: Missing dependencies")
        print(f"Install with: pip install {' '.join(missing)}")
        return False

    return True


def setup_telemetry() -> None:
    """Configure OpenTelemetry to send traces to TraceCraft receiver."""
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    # Create resource with service info
    resource = Resource.create(
        {
            "service.name": "anthropic-demo-agent",
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

    # Try to instrument Anthropic if instrumentation available
    try:
        from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor

        AnthropicInstrumentor().instrument()
        print("Anthropic auto-instrumentation enabled")
    except ImportError:
        print("Note: opentelemetry-instrumentation-anthropic not installed")
        print("Using manual instrumentation instead")

    print("OpenTelemetry configured to send to http://127.0.0.1:4318")


def get_tracer():
    """Get the OpenTelemetry tracer."""
    from opentelemetry import trace

    return trace.get_tracer("anthropic-demo")


def run_simple_chat() -> str:
    """Make a simple message call."""
    import anthropic

    tracer = get_tracer()

    print("\n[1/3] Simple message...")

    with tracer.start_as_current_span("claude_simple_chat") as span:
        span.set_attribute("gen_ai.system", "anthropic")
        span.set_attribute("gen_ai.request.model", "claude-3-haiku-20240307")

        client = anthropic.Anthropic()

        message = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=50,
            messages=[{"role": "user", "content": "What is the capital of Japan? One word."}],
        )

        result = message.content[0].text
        print(f"  Response: {result}")

        # Add usage info
        span.set_attribute("gen_ai.usage.input_tokens", message.usage.input_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", message.usage.output_tokens)
        span.set_attribute("output.value", result)

        return result


def run_multi_turn_chat() -> str:
    """Make a multi-turn conversation."""
    import anthropic

    tracer = get_tracer()

    print("\n[2/3] Multi-turn conversation...")

    with tracer.start_as_current_span("claude_multi_turn") as parent_span:
        parent_span.set_attribute("gen_ai.system", "anthropic")
        parent_span.set_attribute("tracecraft.step.type", "WORKFLOW")

        client = anthropic.Anthropic()
        messages = []

        # First turn
        with tracer.start_as_current_span("turn_1") as span:
            span.set_attribute("gen_ai.request.model", "claude-3-haiku-20240307")

            messages.append({"role": "user", "content": "What is 5 + 5?"})

            response1 = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=50,
                messages=messages,
            )

            answer1 = response1.content[0].text
            messages.append({"role": "assistant", "content": answer1})
            print(f"  Turn 1: {answer1}")

            span.set_attribute("gen_ai.usage.input_tokens", response1.usage.input_tokens)
            span.set_attribute("gen_ai.usage.output_tokens", response1.usage.output_tokens)

        # Second turn
        with tracer.start_as_current_span("turn_2") as span:
            span.set_attribute("gen_ai.request.model", "claude-3-haiku-20240307")

            messages.append({"role": "user", "content": "Double that result"})

            response2 = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=50,
                messages=messages,
            )

            answer2 = response2.content[0].text
            print(f"  Turn 2: {answer2}")

            span.set_attribute("gen_ai.usage.input_tokens", response2.usage.input_tokens)
            span.set_attribute("gen_ai.usage.output_tokens", response2.usage.output_tokens)

        return answer2


def run_tool_use() -> str:
    """Make a tool use request."""
    import json

    import anthropic

    tracer = get_tracer()

    print("\n[3/3] Tool use...")

    with tracer.start_as_current_span("claude_tool_use") as parent_span:
        parent_span.set_attribute("gen_ai.system", "anthropic")
        parent_span.set_attribute("tracecraft.step.type", "AGENT")

        client = anthropic.Anthropic()

        tools = [
            {
                "name": "get_weather",
                "description": "Get the current weather in a location",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city name",
                        },
                    },
                    "required": ["location"],
                },
            }
        ]

        # First call - model decides to use tool
        with tracer.start_as_current_span("llm_call_1") as span:
            span.set_attribute("gen_ai.request.model", "claude-3-haiku-20240307")

            response1 = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=200,
                tools=tools,
                messages=[{"role": "user", "content": "What's the weather in Paris?"}],
            )

            span.set_attribute("gen_ai.usage.input_tokens", response1.usage.input_tokens)
            span.set_attribute("gen_ai.usage.output_tokens", response1.usage.output_tokens)

        # Check if tool was called
        tool_use = None
        for block in response1.content:
            if block.type == "tool_use":
                tool_use = block
                break

        if tool_use:
            # Simulate tool execution
            with tracer.start_as_current_span("tool_get_weather") as span:
                span.set_attribute("tool.name", "get_weather")
                span.set_attribute("tracecraft.step.type", "TOOL")
                span.set_attribute("tool.parameters", json.dumps(tool_use.input))

                tool_result = {"temperature": 18, "conditions": "Cloudy"}
                print(f"  Tool called: {tool_use.name}({tool_use.input})")
                print(f"  Tool result: {tool_result}")

                span.set_attribute("output.value", json.dumps(tool_result))

            # Second call with tool result
            with tracer.start_as_current_span("llm_call_2") as span:
                span.set_attribute("gen_ai.request.model", "claude-3-haiku-20240307")

                response2 = client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=200,
                    tools=tools,
                    messages=[
                        {"role": "user", "content": "What's the weather in Paris?"},
                        {"role": "assistant", "content": response1.content},
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_use.id,
                                    "content": json.dumps(tool_result),
                                }
                            ],
                        },
                    ],
                )

                result = response2.content[0].text
                print(f"  Final response: {result}")

                span.set_attribute("gen_ai.usage.input_tokens", response2.usage.input_tokens)
                span.set_attribute("gen_ai.usage.output_tokens", response2.usage.output_tokens)
                span.set_attribute("output.value", result)

                return result

        return response1.content[0].text if response1.content else ""


def main() -> None:
    """Run real Anthropic traces example."""
    print("=" * 60)
    print("TraceCraft Real Anthropic/Claude Traces Example")
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

    print("\nRunning Claude calls (traces will be sent to receiver)...")
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
