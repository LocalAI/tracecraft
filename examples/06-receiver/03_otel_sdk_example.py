#!/usr/bin/env python3
"""OpenTelemetry SDK Example - Use standard OTel SDK to send traces.

This example shows how to use the standard OpenTelemetry Python SDK
to send traces to TraceCraft's receiver. This is how real applications
would typically be instrumented.

Prerequisites:
    - Receiver running (see 01_receiver_demo.py)
    - OpenTelemetry SDK: pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http

Usage:
    # First start the receiver in another terminal:
    python examples/06-receiver/01_receiver_demo.py

    # Then run this script:
    python examples/06-receiver/03_otel_sdk_example.py

Expected Output:
    - Traces sent via OTel SDK to the receiver
    - View in TUI: tracecraft ui sqlite://traces/receiver_demo.db
"""

from __future__ import annotations

import time


def main() -> None:
    """Send traces using the OpenTelemetry SDK."""
    print("=" * 60)
    print("OpenTelemetry SDK Example")
    print("=" * 60)

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        print("\nError: OpenTelemetry SDK not installed!")
        print("Install with:")
        print(
            "  pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http"
        )
        return

    # Configure the tracer provider
    resource = Resource.create(
        {
            "service.name": "otel-demo-agent",
            "service.version": "1.0.0",
        }
    )

    provider = TracerProvider(resource=resource)

    # Configure OTLP exporter to send to TraceCraft receiver
    exporter = OTLPSpanExporter(
        endpoint="http://127.0.0.1:4318/v1/traces",
    )

    # Use batch processor for efficiency
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    # Set as global tracer provider
    trace.set_tracer_provider(provider)

    # Get a tracer
    tracer = trace.get_tracer("demo-tracer")

    print("\nSending traces via OpenTelemetry SDK...")
    print("-" * 60)

    # Create a trace with nested spans (simulating an agent run)
    with tracer.start_as_current_span("agent_run") as agent_span:
        agent_span.set_attribute("gen_ai.agent.name", "DataAnalyst")
        agent_span.set_attribute("tracecraft.step.type", "AGENT")

        print("Started agent_run span")

        # Simulate an LLM call
        with tracer.start_as_current_span("llm_call") as llm_span:
            llm_span.set_attribute("gen_ai.request.model", "claude-3-sonnet")
            llm_span.set_attribute("gen_ai.system", "anthropic")
            llm_span.set_attribute("gen_ai.usage.input_tokens", 500)
            llm_span.set_attribute("gen_ai.usage.output_tokens", 150)
            llm_span.set_attribute("input.value", '{"prompt": "Analyze this dataset"}')
            llm_span.set_attribute(
                "output.value", '{"response": "I will analyze the data using Python."}'
            )

            print("  Completed llm_call span")
            time.sleep(0.1)  # Simulate work

        # Simulate a tool call
        with tracer.start_as_current_span("tool_call") as tool_span:
            tool_span.set_attribute("tool.name", "python_executor")
            tool_span.set_attribute("tracecraft.step.type", "TOOL")
            tool_span.set_attribute(
                "tool.parameters", '{"code": "import pandas as pd\\ndf.describe()"}'
            )
            tool_span.set_attribute(
                "output.value", '{"result": "Dataset has 1000 rows, 5 columns"}'
            )

            print("  Completed tool_call span")
            time.sleep(0.1)  # Simulate work

    # Force flush to ensure spans are sent
    provider.force_flush()

    print("\n" + "=" * 60)
    print("Traces sent successfully!")
    print("View with: tracecraft ui sqlite://traces/receiver_demo.db")
    print("=" * 60)


if __name__ == "__main__":
    main()
