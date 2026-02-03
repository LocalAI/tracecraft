#!/usr/bin/env python3
"""AWS Bedrock AgentCore - Export traces to AWS X-Ray via ADOT.

Demonstrates how to export traces to AWS X-Ray using the AWS Distro
for OpenTelemetry (ADOT) collector, with Bedrock AgentCore session support.

Prerequisites:
    - ADOT collector running (local or as sidecar)
    - AWS credentials configured

Environment Variables:
    - AWS_REGION: AWS region (default: us-east-1)
    - OTEL_EXPORTER_OTLP_ENDPOINT: ADOT endpoint (default: http://localhost:4317)
    - TRACECRAFT_AWS_SESSION_ID: Optional session ID for multi-turn tracking

Usage:
    # Start ADOT collector locally (using Docker)
    docker run -d --name adot \
        -p 4317:4317 \
        -e AWS_REGION=us-east-1 \
        -e AWS_ACCESS_KEY_ID=your-key \
        -e AWS_SECRET_ACCESS_KEY=your-secret \
        public.ecr.aws/aws-observability/aws-otel-collector:latest

    # Run the example
    python examples/03-exporters/06_aws_agentcore.py

    # View traces in AWS Console
    # CloudWatch > X-Ray > Transaction Search

Expected Output:
    - Traces visible in AWS X-Ray
    - X-Amzn-Trace-Id headers for propagation
    - Session correlation for multi-turn conversations
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
    """Verify ADOT endpoint is configured."""
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    region = os.environ.get("AWS_REGION", "us-east-1")

    print(f"Using ADOT endpoint: {endpoint}")
    print(f"AWS Region: {region}")
    print("\nTo set up ADOT collector locally:")
    print("  docker run -d --name adot \\")
    print("    -p 4317:4317 \\")
    print("    -e AWS_REGION=us-east-1 \\")
    print("    -e AWS_ACCESS_KEY_ID=your-key \\")
    print("    -e AWS_SECRET_ACCESS_KEY=your-secret \\")
    print("    public.ecr.aws/aws-observability/aws-otel-collector:latest")
    print("\nView traces at: AWS Console > CloudWatch > X-Ray > Traces")
    return True


def main() -> None:
    """Run the AWS AgentCore export example."""
    print("=" * 60)
    print("TraceCraft AWS Bedrock AgentCore Export")
    print("=" * 60)

    # Create AgentCore exporter with session tracking
    from tracecraft.contrib.aws import create_agentcore_exporter

    # Use a session ID for multi-turn conversation tracking
    session_id = os.environ.get("TRACECRAFT_AWS_SESSION_ID", "demo-session-001")

    exporter = create_agentcore_exporter(
        service_name="tracecraft-aws-demo",
        session_id=session_id,
        use_xray_propagation=True,
    )

    # Initialize with AWS exporter
    runtime = tracecraft.init(
        console=True,
        jsonl=False,  # Disable local JSONL for this demo
        exporters=[exporter],
    )

    # Define traced functions
    @trace_tool(name="bedrock_agent_tool")
    def invoke_bedrock_tool(input_text: str) -> str:
        """Simulate Bedrock agent tool invocation."""
        time.sleep(0.1)
        return f"Tool result for: {input_text}"

    @trace_tool(name="lambda_function")
    def invoke_lambda(payload: str) -> str:
        """Simulate Lambda function invocation."""
        time.sleep(0.05)
        return f"Lambda result: {payload}"

    @trace_llm(name="claude_sonnet", model="claude-3-sonnet", provider="anthropic")
    def invoke_bedrock_llm(prompt: str) -> str:
        """Simulate Bedrock LLM invocation."""
        time.sleep(0.2)
        return f"Claude response to: {prompt[:30]}..."

    @trace_agent(name="bedrock_agent")
    def bedrock_agent(user_input: str) -> str:
        """Bedrock agent that orchestrates tools and LLM."""
        # Use tools
        tool_result = invoke_bedrock_tool(user_input)
        lambda_result = invoke_lambda(user_input)

        # Generate response with LLM
        prompt = f"Based on {tool_result} and {lambda_result}, respond to: {user_input}"
        response = invoke_bedrock_llm(prompt)

        return response

    # Create run with session tracking
    run = AgentRun(
        name="agentcore_demo",
        start_time=datetime.now(UTC),
        session_id=session_id,  # Links turns in a conversation
    )

    print(f"\nSession ID: {session_id}")
    print("Running traced Bedrock agent...")

    # Demonstrate X-Ray context propagation
    from tracecraft.contrib.aws import inject_xray_context

    with run_context(run):
        # Simulate first turn
        result1 = bedrock_agent("What is AWS Bedrock AgentCore?")

        # Demonstrate injecting X-Ray context for downstream calls
        headers: dict[str, str] = {}
        inject_xray_context(headers, run, session_id=session_id)
        print(f"\nX-Ray headers for downstream: {headers}")

        # Simulate second turn (same session)
        result2 = bedrock_agent("Tell me more about observability features")

    runtime.end_run(run)

    # Give exporter time to flush
    print("\nWaiting for traces to export to X-Ray...")
    time.sleep(3)

    print("\n" + "=" * 60)
    print(f"Turn 1: {result1}")
    print(f"Turn 2: {result2}")
    print("=" * 60)
    print("\nExample complete!")
    print("\nView traces in AWS Console:")
    print("  1. Go to CloudWatch > X-Ray > Traces")
    print("  2. Search for service: tracecraft-aws-demo")
    print("  3. Filter by session ID to see multi-turn correlation")
    print("\nAWS AgentCore features:")
    print("  - X-Amzn-Trace-Id header propagation")
    print("  - Session ID correlation for multi-turn")
    print("  - Bedrock AgentCore runtime integration")
    print("  - CloudWatch Transaction Search visibility")


if __name__ == "__main__":
    if not check_prerequisites():
        sys.exit(1)
    main()
