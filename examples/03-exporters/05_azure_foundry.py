#!/usr/bin/env python3
"""Azure AI Foundry - Export traces to Azure Application Insights.

Demonstrates how to export traces to Azure AI Foundry observability
with GenAI semantic conventions and content recording.

Prerequisites:
    - Azure Application Insights resource
    - Connection string from Azure Portal

Environment Variables:
    - APPLICATIONINSIGHTS_CONNECTION_STRING: Required. Get from Azure Portal.
    - TRACECRAFT_AZURE_CONTENT_RECORDING: Enable content recording (true/false)
    - TRACECRAFT_AZURE_AGENT_NAME: Agent name for metadata

Usage:
    # Set connection string
    export APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=...;IngestionEndpoint=..."

    # Run the example
    python examples/03-exporters/05_azure_foundry.py

    # View traces in Azure Portal
    # Navigate to Application Insights > Transaction Search

Expected Output:
    - Traces visible in Azure Portal
    - Agent spans with gen_ai.agent.* attributes
    - LLM spans with gen_ai.* attributes
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
    """Verify Azure connection string is available."""
    connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")

    if not connection_string:
        print("ERROR: APPLICATIONINSIGHTS_CONNECTION_STRING not set")
        print("\nTo set up Azure Application Insights:")
        print("  1. Create Application Insights resource in Azure Portal")
        print("  2. Go to Overview > Connection String")
        print("  3. Set environment variable:")
        print('     export APPLICATIONINSIGHTS_CONNECTION_STRING="..."')
        return False

    print(f"Using Azure connection string: {connection_string[:50]}...")
    return True


def main() -> None:
    """Run the Azure AI Foundry export example."""
    print("=" * 60)
    print("TraceCraft Azure AI Foundry Export")
    print("=" * 60)

    # Create Azure Foundry exporter with content recording
    from tracecraft.contrib.azure import create_foundry_exporter

    exporter = create_foundry_exporter(
        service_name="tracecraft-azure-demo",
        enable_content_recording=True,  # Record prompts/responses
        agent_name="demo-research-agent",
        agent_id="agent-001",
        agent_description="A demo agent for Azure AI Foundry integration",
    )

    # Initialize with Azure exporter
    runtime = tracecraft.init(
        console=True,
        jsonl=False,  # Disable local JSONL for this demo
        exporters=[exporter],
    )

    # Define traced functions
    @trace_tool(name="search_api")
    def search_web(query: str) -> str:
        """Simulate web search."""
        time.sleep(0.1)
        return f"Search results for: {query}"

    @trace_tool(name="knowledge_base")
    def query_kb(topic: str) -> str:
        """Simulate knowledge base query."""
        time.sleep(0.05)
        return f"KB results for: {topic}"

    @trace_llm(name="gpt4_chat", model="gpt-4", provider="openai")
    def chat_completion(prompt: str) -> str:
        """Simulate LLM chat completion."""
        time.sleep(0.2)
        return f"Response to: {prompt[:30]}..."

    @trace_agent(name="research_agent")
    def research_agent(query: str) -> str:
        """Research agent that uses tools and LLM."""
        # Use tools
        search_results = search_web(query)
        kb_results = query_kb(query)

        # Synthesize with LLM
        prompt = f"Summarize: {search_results} + {kb_results}"
        response = chat_completion(prompt)

        return response

    # Create and run the trace
    run = AgentRun(
        name="azure_foundry_demo",
        start_time=datetime.now(UTC),
        # Set agent metadata (appears in Azure traces)
        agent_name="demo-research-agent",
        agent_id="agent-001",
    )

    print("\nRunning traced agent...")

    with run_context(run):
        result = research_agent("Azure AI Foundry observability")

    runtime.end_run(run)

    # Give exporter time to flush
    print("\nWaiting for traces to export to Azure...")
    time.sleep(3)

    print("\n" + "=" * 60)
    print(f"Result: {result}")
    print("=" * 60)
    print("\nExample complete!")
    print("\nView traces in Azure Portal:")
    print("  1. Navigate to Application Insights resource")
    print("  2. Click 'Transaction Search'")
    print("  3. Filter by service name: tracecraft-azure-demo")
    print("\nAzure AI Foundry features:")
    print("  - gen_ai.agent.name attribute on agent spans")
    print("  - gen_ai.agent.id for agent identification")
    print("  - Content recording (prompts/responses in traces)")
    print("  - End-to-end trace correlation")


if __name__ == "__main__":
    if not check_prerequisites():
        sys.exit(1)
    main()
