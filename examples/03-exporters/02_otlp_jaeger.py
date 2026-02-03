#!/usr/bin/env python3
"""OTLP to Jaeger - Export traces to Jaeger via OTLP.

Demonstrates how to export traces to an OTLP collector like Jaeger,
Grafana Tempo, or any OpenTelemetry-compatible backend.

Prerequisites:
    - Jaeger running with OTLP endpoint

Environment Variables:
    - OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint (default: http://localhost:4317)

External Services:
    - Jaeger with OTLP support

Usage:
    # Start Jaeger first
    docker run -d --name jaeger \
        -p 4317:4317 \
        -p 16686:16686 \
        jaegertracing/all-in-one:latest

    # Run the example
    python examples/03-exporters/02_otlp_jaeger.py

    # View traces
    open http://localhost:16686

Expected Output:
    - Traces visible in Jaeger UI
    - Service name: tracecraft-example
"""

from __future__ import annotations

import os
import sys
import time
from datetime import UTC, datetime

import tracecraft
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from tracecraft.instrumentation.decorators import trace_agent, trace_llm, trace_tool


def check_prerequisites() -> bool:
    """Verify OTLP endpoint is configured."""
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    print(f"Using OTLP endpoint: {endpoint}")
    print("\nTo set up Jaeger locally:")
    print("  docker run -d --name jaeger \\")
    print("    -p 4317:4317 -p 16686:16686 \\")
    print("    jaegertracing/all-in-one:latest")
    print("\nView traces at: http://localhost:16686")
    return True


def main() -> None:
    """Run the OTLP export example."""
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

    print("=" * 60)
    print("TraceCraft OTLP Export to Jaeger")
    print("=" * 60)
    print(f"\nExporting to: {endpoint}")

    # Create OTLP exporter
    from tracecraft.exporters.otlp import OTLPExporter

    otlp_exporter = OTLPExporter(
        endpoint=endpoint,
        service_name="tracecraft-example",
        # Optional: Add authentication headers
        # headers={"Authorization": "Bearer your-token"},
    )

    # Initialize with OTLP export enabled
    runtime = tracecraft.init(
        console=True,
        jsonl=True,
        jsonl_path="traces.jsonl",
        exporters=[otlp_exporter],
    )

    # Define traced functions
    @trace_tool(name="weather_api")
    def get_weather(city: str) -> str:
        """Simulate weather API call."""
        time.sleep(0.1)  # Simulate network latency
        return f"Weather in {city}: 22C, Sunny"

    @trace_tool(name="database")
    def query_database(query: str) -> str:
        """Simulate database query."""
        time.sleep(0.05)
        return f"Results for: {query}"

    @trace_llm(name="gpt4_analysis", model="gpt-4", provider="openai")
    def analyze(data: str) -> str:
        """Simulate LLM analysis."""
        time.sleep(0.2)  # Simulate API call
        return f"Analysis of: {data[:50]}..."

    @trace_agent(name="research_agent")
    def research(topic: str) -> str:
        """Research agent that uses multiple tools."""
        weather = get_weather(topic)
        db_results = query_database(f"SELECT * FROM {topic}")
        analysis = analyze(f"{weather} + {db_results}")
        return analysis

    @trace_agent(name="coordinator")
    def coordinator(task: str) -> str:
        """Coordinator that orchestrates research."""
        result1 = research(task)
        result2 = research(f"{task}_v2")
        final = analyze(f"Combine: {result1} and {result2}")
        return final

    # Create and run the trace
    run = AgentRun(name="otlp_export_demo", start_time=datetime.now(UTC))

    with run_context(run):
        result = coordinator("weather_analysis")

    runtime.end_run(run)

    # Give OTLP exporter time to flush
    print("\nWaiting for traces to export...")
    time.sleep(2)

    print("\n" + "=" * 60)
    print(f"Result: {result}")
    print("=" * 60)
    print("\nExample complete!")
    print("\nTraces exported to OTLP collector!")
    print("View in Jaeger UI: http://localhost:16686")
    print("Look for service: tracecraft-example")
    print("\nKey points:")
    print("  - OTLPExporter converts AgentRun to OpenTelemetry spans")
    print("  - Each step becomes a span in the trace")
    print("  - Parent-child relationships are preserved")


if __name__ == "__main__":
    if not check_prerequisites():
        sys.exit(1)
    main()
