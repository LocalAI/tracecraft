#!/usr/bin/env python3
"""Send Traces to OTLP Receiver - Simulates an instrumented application.

This example sends OTLP traces to the TraceCraft receiver, simulating
what an OpenTelemetry-instrumented application would do.

Prerequisites:
    - Receiver running (see 01_receiver_demo.py)
    - requests library: pip install requests

Usage:
    # First start the receiver in another terminal:
    python examples/06-receiver/01_receiver_demo.py

    # Then run this script:
    python examples/06-receiver/02_send_traces.py

Expected Output:
    - Traces sent successfully to the receiver
    - View in TUI: tracecraft ui sqlite://traces/receiver_demo.db
"""

from __future__ import annotations

import time
import uuid

import requests

# OTLP receiver endpoint
RECEIVER_URL = "http://127.0.0.1:4318/v1/traces"


def generate_trace_id() -> str:
    """Generate a 32-character hex trace ID."""
    return uuid.uuid4().hex


def generate_span_id() -> str:
    """Generate a 16-character hex span ID."""
    return uuid.uuid4().hex[:16]


def create_agent_trace() -> dict:
    """Create an OTLP trace payload simulating an AI agent run."""
    trace_id = generate_trace_id()
    now_ns = int(time.time() * 1_000_000_000)

    # Agent span (root)
    agent_span_id = generate_span_id()
    agent_start = now_ns
    agent_end = now_ns + 5_000_000_000  # 5 seconds

    # LLM call span (child of agent)
    llm_span_id = generate_span_id()
    llm_start = now_ns + 100_000_000  # 100ms after start
    llm_end = now_ns + 2_000_000_000  # 2 seconds

    # Tool call span (child of agent)
    tool_span_id = generate_span_id()
    tool_start = now_ns + 2_500_000_000  # 2.5 seconds
    tool_end = now_ns + 3_500_000_000  # 3.5 seconds

    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "demo-agent"}},
                        {"key": "service.version", "value": {"stringValue": "1.0.0"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "tracecraft-demo"},
                        "spans": [
                            # Agent span (root)
                            {
                                "traceId": trace_id,
                                "spanId": agent_span_id,
                                "name": "research_assistant",
                                "kind": 1,  # INTERNAL
                                "startTimeUnixNano": str(agent_start),
                                "endTimeUnixNano": str(agent_end),
                                "attributes": [
                                    {
                                        "key": "gen_ai.agent.name",
                                        "value": {"stringValue": "ResearchAssistant"},
                                    },
                                    {
                                        "key": "tracecraft.step.type",
                                        "value": {"stringValue": "AGENT"},
                                    },
                                    {
                                        "key": "input.value",
                                        "value": {
                                            "stringValue": '{"query": "What is the weather in San Francisco?"}'
                                        },
                                    },
                                    {
                                        "key": "output.value",
                                        "value": {
                                            "stringValue": '{"answer": "The weather in San Francisco is 68°F and partly cloudy."}'
                                        },
                                    },
                                ],
                            },
                            # LLM call span
                            {
                                "traceId": trace_id,
                                "spanId": llm_span_id,
                                "parentSpanId": agent_span_id,
                                "name": "gpt-4o-mini",
                                "kind": 3,  # CLIENT
                                "startTimeUnixNano": str(llm_start),
                                "endTimeUnixNano": str(llm_end),
                                "attributes": [
                                    {
                                        "key": "gen_ai.request.model",
                                        "value": {"stringValue": "gpt-4o-mini"},
                                    },
                                    {
                                        "key": "gen_ai.system",
                                        "value": {"stringValue": "openai"},
                                    },
                                    {
                                        "key": "gen_ai.usage.input_tokens",
                                        "value": {"intValue": "1250"},
                                    },
                                    {
                                        "key": "gen_ai.usage.output_tokens",
                                        "value": {"intValue": "380"},
                                    },
                                    {
                                        "key": "gen_ai.usage.cost",
                                        "value": {"doubleValue": 0.0024},
                                    },
                                    {
                                        "key": "input.value",
                                        "value": {
                                            "stringValue": '{"prompt": "What is the weather in San Francisco?"}'
                                        },
                                    },
                                    {
                                        "key": "output.value",
                                        "value": {
                                            "stringValue": '{"response": "I\'ll check the weather for you using the weather tool."}'
                                        },
                                    },
                                ],
                            },
                            # Tool call span
                            {
                                "traceId": trace_id,
                                "spanId": tool_span_id,
                                "parentSpanId": agent_span_id,
                                "name": "get_weather",
                                "kind": 1,  # INTERNAL
                                "startTimeUnixNano": str(tool_start),
                                "endTimeUnixNano": str(tool_end),
                                "attributes": [
                                    {
                                        "key": "tool.name",
                                        "value": {"stringValue": "get_weather"},
                                    },
                                    {
                                        "key": "tracecraft.step.type",
                                        "value": {"stringValue": "TOOL"},
                                    },
                                    {
                                        "key": "tool.parameters",
                                        "value": {
                                            "stringValue": '{"city": "San Francisco", "units": "fahrenheit"}'
                                        },
                                    },
                                    {
                                        "key": "output.value",
                                        "value": {
                                            "stringValue": '{"temperature": 68, "conditions": "Partly cloudy"}'
                                        },
                                    },
                                ],
                            },
                        ],
                    }
                ],
            }
        ]
    }


def main() -> None:
    """Send demo traces to the receiver."""
    print("=" * 60)
    print("TraceCraft Trace Sender Demo")
    print("=" * 60)

    # Check if receiver is running
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
    print("-" * 60)

    # Send traces
    for i in range(3):
        print(f"\nSending trace {i + 1}/3...")
        payload = create_agent_trace()

        response = requests.post(
            RECEIVER_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            print(f"  Status: {data['status']}")
            print(f"  Traces received: {data['traces_received']}")
            print(f"  Traces saved: {data['traces_saved']}")
        else:
            print(f"  Error: {response.status_code}")
            print(f"  {response.text}")

        time.sleep(0.5)  # Small delay between traces

    print("\n" + "=" * 60)
    print("Done! View traces with:")
    print("  tracecraft ui sqlite://traces/receiver_demo.db")
    print("=" * 60)


if __name__ == "__main__":
    main()
