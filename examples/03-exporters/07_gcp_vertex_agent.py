#!/usr/bin/env python3
"""GCP Vertex AI Agent Builder - Export traces to Cloud Trace.

Demonstrates how to export traces to GCP Cloud Trace with Vertex AI
Agent Builder integration, GenAI semantic conventions, and content recording.

Prerequisites:
    - GCP project with Cloud Trace API enabled
    - Application Default Credentials configured

Environment Variables:
    - GOOGLE_CLOUD_PROJECT: Required. GCP project ID.
    - TRACECRAFT_GCP_SESSION_ID: Optional session ID for multi-turn tracking
    - TRACECRAFT_GCP_AGENT_NAME: Agent name for metadata
    - TRACECRAFT_GCP_CONTENT_RECORDING: Enable content recording (true/false)
    - TRACECRAFT_GCP_REASONING_ENGINE_ID: Reasoning Engine ID (if applicable)

Usage:
    # Set project ID
    export GOOGLE_CLOUD_PROJECT="your-project-id"

    # Authenticate (if not already)
    gcloud auth application-default login

    # Run the example
    python examples/03-exporters/07_gcp_vertex_agent.py

    # View traces in GCP Console
    # Navigate to Cloud Trace > Trace List

Expected Output:
    - Traces visible in GCP Cloud Trace
    - Agent spans with gen_ai.agent.* attributes
    - Cloud Trace headers for context propagation
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
    """Verify GCP project ID is available."""
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")

    if not project_id:
        print("ERROR: GOOGLE_CLOUD_PROJECT not set")
        print("\nTo set up GCP Cloud Trace:")
        print("  1. Enable Cloud Trace API in GCP Console")
        print("  2. Configure Application Default Credentials:")
        print("     gcloud auth application-default login")
        print("  3. Set environment variable:")
        print('     export GOOGLE_CLOUD_PROJECT="your-project-id"')
        return False

    print(f"Using GCP project: {project_id}")
    return True


def main() -> None:
    """Run the GCP Vertex AI Agent Builder export example."""
    print("=" * 60)
    print("TraceCraft GCP Vertex AI Agent Builder Export")
    print("=" * 60)

    # Create Vertex Agent exporter with content recording
    from tracecraft.contrib.gcp import create_vertex_agent_exporter

    # Use a session ID for multi-turn conversation tracking
    session_id = os.environ.get("TRACECRAFT_GCP_SESSION_ID", "demo-session-001")

    exporter = create_vertex_agent_exporter(
        project_id=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        service_name="tracecraft-gcp-demo",
        session_id=session_id,
        enable_content_recording=True,  # Record prompts/responses
        agent_name="demo-vertex-agent",
        agent_id="agent-001",
        agent_description="A demo agent for GCP Vertex AI Agent Builder integration",
        reasoning_engine_id=os.environ.get("TRACECRAFT_GCP_REASONING_ENGINE_ID"),
    )

    # Initialize with GCP exporter
    runtime = tracecraft.init(
        console=True,
        jsonl=False,  # Disable local JSONL for this demo
        exporters=[exporter],
    )

    # Define traced functions
    @trace_tool(name="vertex_search")
    def vertex_search(query: str) -> str:
        """Simulate Vertex AI Search."""
        time.sleep(0.1)
        return f"Search results for: {query}"

    @trace_tool(name="bigquery_lookup")
    def bigquery_lookup(table: str) -> str:
        """Simulate BigQuery data lookup."""
        time.sleep(0.05)
        return f"BigQuery results from: {table}"

    @trace_llm(name="gemini_pro", model="gemini-1.5-pro", provider="google")
    def gemini_completion(prompt: str) -> str:
        """Simulate Gemini LLM completion."""
        time.sleep(0.2)
        return f"Gemini response to: {prompt[:30]}..."

    @trace_agent(name="vertex_agent")
    def vertex_agent(user_query: str) -> str:
        """Vertex AI agent that uses tools and LLM."""
        # Use tools
        search_results = vertex_search(user_query)
        bq_results = bigquery_lookup("analytics.events")

        # Synthesize with Gemini
        prompt = f"Summarize: {search_results} + {bq_results}"
        response = gemini_completion(prompt)

        return response

    # Create run with session tracking
    run = AgentRun(
        name="vertex_agent_demo",
        start_time=datetime.now(UTC),
        session_id=session_id,  # Links turns in a conversation
        # Set agent metadata (appears in Cloud Trace)
        agent_name="demo-vertex-agent",
        agent_id="agent-001",
    )

    print(f"\nSession ID: {session_id}")
    print("Running traced Vertex AI agent...")

    # Demonstrate Cloud Trace context propagation
    from tracecraft.contrib.gcp import inject_cloudtrace_context

    with run_context(run):
        # Simulate first turn
        result1 = vertex_agent("What is Vertex AI Agent Builder?")

        # Demonstrate injecting Cloud Trace context for downstream calls
        headers: dict[str, str] = {}
        inject_cloudtrace_context(headers, run, session_id=session_id)
        print(f"\nCloud Trace headers for downstream: {headers}")

        # Simulate second turn (same session)
        result2 = vertex_agent("How do I monitor agent performance?")

    runtime.end_run(run)

    # Give exporter time to flush
    print("\nWaiting for traces to export to Cloud Trace...")
    time.sleep(3)

    print("\n" + "=" * 60)
    print(f"Turn 1: {result1}")
    print(f"Turn 2: {result2}")
    print("=" * 60)
    print("\nExample complete!")
    print("\nView traces in GCP Console:")
    print("  1. Go to Cloud Trace > Trace List")
    print("  2. Filter by service name: tracecraft-gcp-demo")
    print("  3. Filter by session ID to see multi-turn correlation")
    print("\nGCP Vertex AI Agent Builder features:")
    print("  - X-Cloud-Trace-Context header propagation")
    print("  - Session ID correlation for multi-turn")
    print("  - gen_ai.agent.* attributes on spans")
    print("  - Content recording (prompts/responses)")
    print("  - Reasoning Engine integration support")


if __name__ == "__main__":
    if not check_prerequisites():
        sys.exit(1)
    main()
