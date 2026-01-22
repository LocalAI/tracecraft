#!/usr/bin/env python3
"""OTLP Export to Grafana Tempo - Distributed tracing with Grafana stack.

Demonstrates exporting traces to Grafana Tempo via OTLP for visualization
in Grafana with support for trace correlation and log linking.

Prerequisites:
    - AgentTrace installed
    - Docker (for Tempo and Grafana)

Environment Variables:
    - None required (uses local Tempo)

External Services:
    - Grafana Tempo (via Docker)
    - Grafana (optional, for visualization)

Usage:
    # Start Tempo and Grafana:
    # docker run -d --name tempo -p 4317:4317 -p 3200:3200 grafana/tempo:latest
    # docker run -d --name grafana -p 3000:3000 grafana/grafana:latest

    python examples/03-exporters/03_otlp_tempo.py

Expected Output:
    - Console trace summary
    - Traces visible in Grafana Tempo at http://localhost:3000
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import agenttrace
from agenttrace.core.context import run_context
from agenttrace.core.models import AgentRun
from agenttrace.exporters.otlp import OTLPExporter
from agenttrace.instrumentation.decorators import trace_agent, trace_llm, trace_tool


def get_tempo_endpoint() -> str:
    """Get Tempo OTLP endpoint from environment or use default."""
    return os.getenv("TEMPO_OTLP_ENDPOINT", "http://localhost:4317")


# Initialize with OTLP exporter for Tempo
otlp_exporter = OTLPExporter(
    endpoint=get_tempo_endpoint(),
    service_name="agenttrace-tempo-example",
    protocol="grpc",
)

runtime = agenttrace.init(
    console=True,
    jsonl=False,  # Disable JSONL, only export to Tempo
    exporters=[otlp_exporter],
)


@trace_tool(name="search_documents")
def search_documents(query: str) -> list[str]:
    """Search for relevant documents."""
    return [
        f"Document 1: Information about {query}",
        f"Document 2: More details on {query}",
        f"Document 3: Related topic to {query}",
    ]


@trace_llm(name="generate_answer", model="gpt-4", provider="openai")
def generate_answer(question: str, context: list[str]) -> str:
    """Generate an answer based on context (simulated)."""
    return f"Based on the context about '{question}', the answer is: [Simulated response using {len(context)} documents]"


@trace_agent(name="qa_agent")
def qa_agent(question: str) -> str:
    """Question-answering agent with RAG pattern."""
    # Retrieve relevant documents
    docs = search_documents(question)

    # Generate answer
    answer = generate_answer(question, docs)

    return answer


def main() -> None:
    """Run the Tempo export example."""
    print("=" * 60)
    print("AgentTrace OTLP Export to Grafana Tempo")
    print("=" * 60)

    tempo_endpoint = get_tempo_endpoint()
    print(f"\nTempo endpoint: {tempo_endpoint}")
    print("\nTo view traces:")
    print(
        "  1. Start Tempo: docker run -d --name tempo -p 4317:4317 -p 3200:3200 grafana/tempo:latest"
    )
    print("  2. Start Grafana: docker run -d --name grafana -p 3000:3000 grafana/grafana:latest")
    print("  3. Configure Tempo datasource in Grafana at http://localhost:3000")
    print("  4. Run this example")
    print("  5. View traces in Grafana Explore")

    # Create and execute a run
    run = AgentRun(
        name="tempo_qa_example",
        start_time=datetime.now(UTC),
    )

    with run_context(run):
        result = qa_agent("What is distributed tracing?")

    runtime.end_run(run)

    print("\n" + "=" * 60)
    print("Results:")
    print("  Question: What is distributed tracing?")
    print(f"  Answer: {result[:80]}...")
    print("=" * 60)

    print(f"\nTrace ID: {run.run_id}")
    print(f"Duration: {run.duration_ms:.2f}ms")
    print(f"Steps: {len(run.steps)}")

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nKey patterns demonstrated:")
    print("  - OTLP gRPC export to Tempo")
    print("  - Service name tagging")
    print("  - Trace ID for correlation")
    print("  - Integration with Grafana stack")


if __name__ == "__main__":
    main()
