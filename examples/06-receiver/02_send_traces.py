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

import json
import random
import time
import uuid

import requests

# OTLP receiver endpoint
RECEIVER_URL = "http://127.0.0.1:4318/v1/traces"

# Sample data for variety
QUERIES = [
    ("What is the weather in San Francisco?", "get_weather", "San Francisco"),
    ("Search for Python async tutorials", "web_search", "Python async tutorials"),
    ("Calculate the square root of 144", "calculator", "sqrt(144)"),
    ("Find restaurants near Times Square", "places_search", "Times Square restaurants"),
    ("What's the stock price of AAPL?", "stock_lookup", "AAPL"),
]

MODELS = [
    ("gpt-4o-mini", "openai", 0.15, 0.60),  # model, provider, input_cost/1M, output_cost/1M
    ("gpt-4o", "openai", 2.50, 10.00),
    ("claude-3-haiku", "anthropic", 0.25, 1.25),
    ("claude-3-sonnet", "anthropic", 3.00, 15.00),
    ("gemini-1.5-flash", "google", 0.075, 0.30),
]

AGENT_NAMES = [
    "ResearchAssistant",
    "DataAnalyst",
    "CodeHelper",
    "TaskPlanner",
    "ContentWriter",
]


def generate_trace_id() -> str:
    """Generate a 32-character hex trace ID."""
    return uuid.uuid4().hex


def generate_span_id() -> str:
    """Generate a 16-character hex span ID."""
    return uuid.uuid4().hex[:16]


def create_agent_trace(trace_num: int) -> dict:
    """Create an OTLP trace payload simulating an AI agent run."""
    # Pick random variety for this trace
    query, tool_name, tool_arg = random.choice(QUERIES)
    model_name, provider, input_cost, output_cost = random.choice(MODELS)
    agent_name = random.choice(AGENT_NAMES)

    # Randomize token counts
    input_tokens = random.randint(200, 2000)
    output_tokens = random.randint(50, 500)
    cost = (input_tokens * input_cost / 1_000_000) + (output_tokens * output_cost / 1_000_000)

    # Randomize timing (1-8 seconds total)
    total_duration_ns = random.randint(1_000_000_000, 8_000_000_000)
    llm_duration_ns = int(total_duration_ns * random.uniform(0.3, 0.5))
    tool_duration_ns = int(total_duration_ns * random.uniform(0.1, 0.3))

    trace_id = generate_trace_id()
    now_ns = int(time.time() * 1_000_000_000)

    # Agent span (root)
    agent_span_id = generate_span_id()
    agent_start = now_ns
    agent_end = now_ns + total_duration_ns

    # LLM call span (child of agent)
    llm_span_id = generate_span_id()
    llm_start = now_ns + 100_000_000  # 100ms after start
    llm_end = llm_start + llm_duration_ns

    # Tool call span (child of agent)
    tool_span_id = generate_span_id()
    tool_start = llm_end + 100_000_000  # 100ms after LLM
    tool_end = tool_start + tool_duration_ns

    # Generate dynamic output based on tool
    tool_outputs = {
        "get_weather": {
            "temperature": random.randint(45, 95),
            "conditions": random.choice(["Sunny", "Cloudy", "Rainy", "Partly cloudy"]),
        },
        "web_search": {
            "results": random.randint(5, 50),
            "top_result": "https://example.com/result",
        },
        "calculator": {"result": 12.0, "expression": "sqrt(144)"},
        "places_search": {"count": random.randint(3, 20), "nearest": "0.2 miles"},
        "stock_lookup": {
            "price": round(random.uniform(100, 250), 2),
            "change": round(random.uniform(-5, 5), 2),
        },
    }
    tool_output = tool_outputs.get(tool_name, {"status": "success"})
    tool_output_json = json.dumps(tool_output)

    # Pre-build JSON strings to avoid f-string quote issues
    agent_input_json = json.dumps({"query": query})
    agent_output_json = json.dumps(
        {"answer": f"Completed task using {tool_name}", "tool_result": tool_output}
    )
    llm_input_json = json.dumps({"prompt": query})
    llm_output_json = json.dumps({"response": f"I'll use the {tool_name} tool to help with this."})
    tool_params_json = json.dumps({"query": tool_arg})

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
                                "name": f"{agent_name.lower()}_run",
                                "kind": 1,  # INTERNAL
                                "startTimeUnixNano": str(agent_start),
                                "endTimeUnixNano": str(agent_end),
                                "attributes": [
                                    {
                                        "key": "gen_ai.agent.name",
                                        "value": {"stringValue": agent_name},
                                    },
                                    {
                                        "key": "tracecraft.step.type",
                                        "value": {"stringValue": "AGENT"},
                                    },
                                    {
                                        "key": "input.value",
                                        "value": {"stringValue": agent_input_json},
                                    },
                                    {
                                        "key": "output.value",
                                        "value": {"stringValue": agent_output_json},
                                    },
                                ],
                            },
                            # LLM call span
                            {
                                "traceId": trace_id,
                                "spanId": llm_span_id,
                                "parentSpanId": agent_span_id,
                                "name": model_name,
                                "kind": 3,  # CLIENT
                                "startTimeUnixNano": str(llm_start),
                                "endTimeUnixNano": str(llm_end),
                                "attributes": [
                                    {
                                        "key": "gen_ai.request.model",
                                        "value": {"stringValue": model_name},
                                    },
                                    {
                                        "key": "gen_ai.system",
                                        "value": {"stringValue": provider},
                                    },
                                    {
                                        "key": "gen_ai.usage.input_tokens",
                                        "value": {"intValue": str(input_tokens)},
                                    },
                                    {
                                        "key": "gen_ai.usage.output_tokens",
                                        "value": {"intValue": str(output_tokens)},
                                    },
                                    {
                                        "key": "gen_ai.usage.cost",
                                        "value": {"doubleValue": round(cost, 6)},
                                    },
                                    {
                                        "key": "input.value",
                                        "value": {"stringValue": llm_input_json},
                                    },
                                    {
                                        "key": "output.value",
                                        "value": {"stringValue": llm_output_json},
                                    },
                                ],
                            },
                            # Tool call span
                            {
                                "traceId": trace_id,
                                "spanId": tool_span_id,
                                "parentSpanId": agent_span_id,
                                "name": tool_name,
                                "kind": 1,  # INTERNAL
                                "startTimeUnixNano": str(tool_start),
                                "endTimeUnixNano": str(tool_end),
                                "attributes": [
                                    {
                                        "key": "tool.name",
                                        "value": {"stringValue": tool_name},
                                    },
                                    {
                                        "key": "tracecraft.step.type",
                                        "value": {"stringValue": "TOOL"},
                                    },
                                    {
                                        "key": "tool.parameters",
                                        "value": {"stringValue": tool_params_json},
                                    },
                                    {
                                        "key": "output.value",
                                        "value": {"stringValue": tool_output_json},
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

    # Send traces with variety
    num_traces = 5
    for i in range(num_traces):
        print(f"\nSending trace {i + 1}/{num_traces}...")
        payload = create_agent_trace(i)

        # Extract some info for display
        spans = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
        agent_span = spans[0]
        llm_span = spans[1]
        agent_name = next(
            (
                a["value"]["stringValue"]
                for a in agent_span["attributes"]
                if a["key"] == "gen_ai.agent.name"
            ),
            "Unknown",
        )
        model = next(
            (
                a["value"]["stringValue"]
                for a in llm_span["attributes"]
                if a["key"] == "gen_ai.request.model"
            ),
            "Unknown",
        )

        response = requests.post(
            RECEIVER_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            print(f"  Agent: {agent_name} | Model: {model}")
            print(f"  Status: {data['status']} | Saved: {data['traces_saved']}")
        else:
            print(f"  Error: {response.status_code}")
            print(f"  {response.text}")

        time.sleep(0.3)  # Small delay between traces

    print("\n" + "=" * 60)
    print(f"Done! Sent {num_traces} unique traces.")
    print("View with: tracecraft ui sqlite://traces/receiver_demo.db")
    print("=" * 60)


if __name__ == "__main__":
    main()
