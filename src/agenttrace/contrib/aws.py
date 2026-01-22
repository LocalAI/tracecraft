"""
AWS X-Ray and Bedrock AgentCore configuration helpers.

Provides easy configuration for exporting traces to:
- AWS X-Ray via the AWS Distro for OpenTelemetry (ADOT)
- AWS Bedrock AgentCore observability with session tracking

See:
- https://docs.aws.amazon.com/xray/latest/devguide/xray-services-agentcore.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agenttrace.core.models import AgentRun
    from agenttrace.exporters.otlp import OTLPExporter


@dataclass
class AgentCoreConfig:
    """Configuration for AWS Bedrock AgentCore integration.

    Attributes:
        session_id: Session ID for multi-turn conversations.
        use_xray_propagation: Whether to use X-Ray header format.
        extra_attributes: Additional attributes to include in traces.
    """

    session_id: str | None = None
    use_xray_propagation: bool = True
    extra_attributes: dict[str, Any] | None = None


def create_xray_exporter(
    region: str | None = None,
    endpoint: str | None = None,
    service_name: str = "agenttrace",
) -> OTLPExporter:
    """
    Create an OTLP exporter configured for AWS X-Ray.

    Args:
        region: AWS region. Defaults to AWS_REGION env var.
        endpoint: Custom OTLP endpoint. Defaults to local ADOT collector.
        service_name: Service name for traces.

    Returns:
        Configured OTLPExporter for X-Ray.

    Example:
        ```python
        from agenttrace.contrib.aws import create_xray_exporter
        import agenttrace

        exporter = create_xray_exporter(region="us-east-1")
        agenttrace.init(exporters=[exporter])
        ```

    Note:
        Requires ADOT collector running as sidecar or daemon.
        AWS credentials must be configured via env vars, IAM role, or profile.
    """
    from agenttrace.exporters.otlp import OTLPExporter

    region = region or os.environ.get("AWS_REGION", "us-east-1")
    resolved_endpoint = endpoint or os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
    )

    return OTLPExporter(
        endpoint=resolved_endpoint,
        service_name=service_name,
        protocol="grpc",
    )


def configure_for_lambda(service_name: str = "agenttrace") -> OTLPExporter:
    """
    Configure for AWS Lambda with X-Ray extension.

    Uses the Lambda OTLP extension endpoint for trace export.

    Args:
        service_name: Service name for traces.

    Returns:
        Configured OTLPExporter for Lambda.

    Example:
        ```python
        from agenttrace.contrib.aws import configure_for_lambda
        import agenttrace

        # In your Lambda handler
        exporter = configure_for_lambda(service_name="my-lambda")
        agenttrace.init(exporters=[exporter], console=False, jsonl=False)
        ```
    """
    return create_xray_exporter(
        endpoint="http://localhost:4317",
        service_name=service_name,
    )


def configure_for_ecs(
    service_name: str = "agenttrace",
    use_resource_detection: bool = True,  # noqa: ARG001
) -> OTLPExporter:
    """
    Configure for Amazon ECS with X-Ray sidecar.

    Args:
        service_name: Service name for traces.
        use_resource_detection: Whether to detect ECS resource attributes.

    Returns:
        Configured OTLPExporter for ECS.

    Example:
        ```python
        from agenttrace.contrib.aws import configure_for_ecs
        import agenttrace

        exporter = configure_for_ecs(service_name="my-ecs-service")
        agenttrace.init(exporters=[exporter])
        ```
    """
    # ECS typically uses the ADOT sidecar on localhost
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

    return create_xray_exporter(
        endpoint=endpoint,
        service_name=service_name,
    )


def configure_for_eks(
    service_name: str = "agenttrace",
    collector_endpoint: str | None = None,
) -> OTLPExporter:
    """
    Configure for Amazon EKS with ADOT collector.

    Args:
        service_name: Service name for traces.
        collector_endpoint: ADOT collector endpoint. Defaults to the
            typical ClusterIP service endpoint.

    Returns:
        Configured OTLPExporter for EKS.

    Example:
        ```python
        from agenttrace.contrib.aws import configure_for_eks
        import agenttrace

        exporter = configure_for_eks(
            service_name="my-eks-service",
            collector_endpoint="http://adot-collector:4317"
        )
        agenttrace.init(exporters=[exporter])
        ```
    """
    endpoint = collector_endpoint or os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "http://adot-collector:4317"
    )

    return create_xray_exporter(
        endpoint=endpoint,
        service_name=service_name,
    )


# --- AWS Bedrock AgentCore Integration ---


def create_agentcore_exporter(
    endpoint: str | None = None,
    service_name: str = "agenttrace",
    session_id: str | None = None,
    use_xray_propagation: bool = True,
) -> OTLPExporter:
    """
    Create an exporter configured for AWS Bedrock AgentCore.

    Extends X-Ray export with AgentCore-specific telemetry format
    and session tracking for multi-turn conversations.

    Args:
        endpoint: ADOT collector endpoint. Defaults to localhost:4317.
        service_name: Service name for traces.
        session_id: Session ID for multi-turn conversations.
        use_xray_propagation: Whether to use X-Ray header format.

    Returns:
        Configured OTLPExporter for Bedrock AgentCore.

    Example:
        ```python
        from agenttrace.contrib.aws import create_agentcore_exporter
        import agenttrace

        exporter = create_agentcore_exporter(
            service_name="my-agent",
            session_id="session-12345",
        )
        agenttrace.init(exporters=[exporter])
        ```

    Note:
        Requires ADOT collector configured for X-Ray export.
        Session ID enables correlation of multi-turn conversations.
    """
    exporter = create_xray_exporter(
        endpoint=endpoint,
        service_name=service_name,
    )

    # Store AgentCore-specific configuration on the exporter
    exporter._agentcore_config = AgentCoreConfig(  # type: ignore[attr-defined]
        session_id=session_id,
        use_xray_propagation=use_xray_propagation,
    )

    return exporter


def configure_for_agentcore_runtime(
    service_name: str = "agenttrace",
    session_id: str | None = None,
) -> OTLPExporter:
    """
    Configure for AWS Bedrock AgentCore Runtime using environment variables.

    Uses environment variables:
    - OTEL_EXPORTER_OTLP_ENDPOINT: ADOT collector endpoint
    - AGENTTRACE_AWS_SESSION_ID: Session ID for conversation tracking
    - AWS_REGION: AWS region

    Args:
        service_name: Service name for traces.
        session_id: Override env var for session ID.

    Returns:
        Configured OTLPExporter for AgentCore Runtime.

    Example:
        ```python
        from agenttrace.contrib.aws import configure_for_agentcore_runtime
        import agenttrace

        # Uses environment variables
        exporter = configure_for_agentcore_runtime(service_name="my-agent")
        agenttrace.init(exporters=[exporter])
        ```
    """
    # Resolve session ID from env if not provided
    if session_id is None:
        session_id = os.environ.get("AGENTTRACE_AWS_SESSION_ID")

    return create_agentcore_exporter(
        service_name=service_name,
        session_id=session_id,
    )


def inject_xray_context(
    carrier: dict[str, str],
    run: AgentRun,
    session_id: str | None = None,
    sampled: bool = True,
) -> None:
    """
    Inject X-Ray trace context headers for cross-service tracing.

    Adds X-Amzn-Trace-Id header and optionally the AgentCore session header
    for propagating trace context to downstream services.

    Args:
        carrier: Dictionary to inject headers into (e.g., HTTP headers).
        run: The current AgentRun to extract trace context from.
        session_id: Optional session ID for AgentCore session tracking.
        sampled: Whether the trace is sampled.

    Example:
        ```python
        from agenttrace.contrib.aws import inject_xray_context
        from agenttrace import get_current_run
        import requests

        # Inject X-Ray context into outgoing request
        headers = {}
        inject_xray_context(headers, get_current_run(), session_id="session-123")
        response = requests.post(url, headers=headers, json=payload)
        ```
    """
    from agenttrace.propagation.xray import XRayTraceContextPropagator

    propagator = XRayTraceContextPropagator()

    # Use session_id from run if not provided
    if session_id is None:
        session_id = getattr(run, "session_id", None)

    # Temporarily set session_id on run for injection
    original_session_id = getattr(run, "session_id", None)
    if session_id:
        run.session_id = session_id

    propagator.inject(carrier, run, sampled=sampled)

    # Restore original session_id
    if original_session_id != session_id:
        run.session_id = original_session_id


def extract_xray_context(
    carrier: dict[str, str],
) -> tuple[str, str, bool, str | None] | None:
    """
    Extract X-Ray trace context from incoming request headers.

    Parses the X-Amzn-Trace-Id header and optional AgentCore session header.

    Args:
        carrier: Dictionary containing headers (e.g., HTTP request headers).

    Returns:
        Tuple of (trace_id, span_id, sampled, session_id) or None if not found.

    Example:
        ```python
        from agenttrace.contrib.aws import extract_xray_context

        # Extract context from incoming request
        result = extract_xray_context(request.headers)
        if result:
            trace_id, span_id, sampled, session_id = result
            # Use extracted context to continue the trace
        ```
    """
    from agenttrace.propagation.xray import XRayTraceContextPropagator

    propagator = XRayTraceContextPropagator()
    return propagator.extract(carrier)
