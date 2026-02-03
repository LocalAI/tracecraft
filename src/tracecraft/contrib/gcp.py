"""
Google Cloud Trace and Vertex AI Agent Builder configuration helpers.

Provides easy configuration for exporting traces to:
- GCP Cloud Trace via the native OTLP endpoint
- Vertex AI Agent Builder with session tracking and OTel GenAI conventions

See:
- https://cloud.google.com/trace/docs/setup
- https://cloud.google.com/vertex-ai/generative-ai/docs/agent-builder/overview
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun
    from tracecraft.exporters.otlp import OTLPExporter


@dataclass
class VertexAgentConfig:
    """Configuration for Vertex AI Agent Builder integration.

    Attributes:
        session_id: Session ID for multi-turn conversations.
        agent_name: Agent name for gen_ai.agent.name attribute.
        agent_id: Agent ID for gen_ai.agent.id attribute.
        agent_description: Agent description for gen_ai.agent.description.
        enable_content_recording: Whether to record prompt/response content.
        reasoning_engine_id: For Reasoning Engine integration.
        extra_attributes: Additional attributes to include in traces.
    """

    session_id: str | None = None
    agent_name: str | None = None
    agent_id: str | None = None
    agent_description: str | None = None
    enable_content_recording: bool = False
    reasoning_engine_id: str | None = None
    extra_attributes: dict[str, Any] = field(default_factory=dict)


def create_cloudtrace_exporter(
    project_id: str | None = None,
    service_name: str = "tracecraft",
    credentials: Any | None = None,
) -> OTLPExporter:
    """
    Create an exporter configured for GCP Cloud Trace.

    Args:
        project_id: GCP project ID. Defaults to GOOGLE_CLOUD_PROJECT env var.
        service_name: Service name for traces.
        credentials: Optional google.auth Credentials object. If not provided,
            uses Application Default Credentials.

    Returns:
        Configured OTLPExporter for Cloud Trace.

    Raises:
        ValueError: If project_id is not provided.
        ImportError: If google-auth package is not installed.

    Example:
        ```python
        from tracecraft.contrib.gcp import create_cloudtrace_exporter
        import tracecraft

        exporter = create_cloudtrace_exporter(project_id="my-project")
        tracecraft.init(exporters=[exporter])
        ```

    Note:
        Requires google-auth package: pip install tracecraft[gcp]
        Credentials can be configured via:
        - GOOGLE_APPLICATION_CREDENTIALS env var
        - Application Default Credentials
        - Service account on GCE/GKE/Cloud Run
    """
    from tracecraft.exporters.otlp import OTLPExporter

    project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")

    if not project_id:
        raise ValueError(
            "GCP project ID required. Set GOOGLE_CLOUD_PROJECT "
            "environment variable or pass project_id parameter."
        )

    # Get access token for authentication
    access_token = _get_access_token(credentials)

    # GCP Cloud Trace OTLP endpoint (publicly available since 2023)
    endpoint = "https://cloudtrace.googleapis.com:443"

    return OTLPExporter(
        endpoint=endpoint,
        service_name=service_name,
        protocol="grpc",
        headers={
            "authorization": f"Bearer {access_token}",
            "x-goog-user-project": project_id,
        },
    )


def _get_access_token(credentials: Any | None = None) -> str:
    """
    Get an access token for GCP authentication.

    Args:
        credentials: Optional credentials object.

    Returns:
        Access token string.

    Raises:
        ImportError: If google-auth is not installed.
    """
    try:
        from google.auth import default
        from google.auth.transport.requests import Request
    except ImportError as e:
        raise ImportError(
            "google-auth required for GCP. Install with: pip install tracecraft[gcp]"
        ) from e

    if credentials is None:
        credentials, _ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])

    # Refresh credentials if needed
    if not credentials.valid:
        credentials.refresh(Request())

    return str(credentials.token)


def configure_for_cloud_run(
    service_name: str | None = None,
) -> OTLPExporter:
    """
    Configure for Google Cloud Run.

    Uses the K_SERVICE environment variable for service name if not provided.
    Cloud Run automatically provides credentials via metadata server.

    Args:
        service_name: Service name for traces. Defaults to K_SERVICE env var.

    Returns:
        Configured OTLPExporter for Cloud Run.

    Example:
        ```python
        from tracecraft.contrib.gcp import configure_for_cloud_run
        import tracecraft

        # In your Cloud Run service
        exporter = configure_for_cloud_run()
        tracecraft.init(exporters=[exporter], console=False, jsonl=False)
        ```
    """
    # Cloud Run sets K_SERVICE for the service name
    svc_name = service_name if service_name else os.environ.get("K_SERVICE", "tracecraft")

    return create_cloudtrace_exporter(service_name=svc_name)


def configure_for_cloud_functions(
    service_name: str | None = None,
) -> OTLPExporter:
    """
    Configure for Google Cloud Functions.

    Uses the FUNCTION_NAME environment variable for service name if not provided.

    Args:
        service_name: Service name for traces. Defaults to FUNCTION_NAME env var.

    Returns:
        Configured OTLPExporter for Cloud Functions.

    Example:
        ```python
        from tracecraft.contrib.gcp import configure_for_cloud_functions
        import tracecraft

        # In your Cloud Function
        exporter = configure_for_cloud_functions()
        tracecraft.init(exporters=[exporter], console=False, jsonl=False)
        ```
    """
    # Cloud Functions sets FUNCTION_NAME
    svc_name = service_name if service_name else os.environ.get("FUNCTION_NAME", "tracecraft")

    return create_cloudtrace_exporter(service_name=svc_name)


def configure_for_gke(
    service_name: str = "tracecraft",
    collector_endpoint: str | None = None,
) -> OTLPExporter:
    """
    Configure for Google Kubernetes Engine (GKE).

    Can use either direct Cloud Trace export or via an OTEL Collector.

    Args:
        service_name: Service name for traces.
        collector_endpoint: Optional OTEL Collector endpoint. If provided,
            sends to collector instead of directly to Cloud Trace.

    Returns:
        Configured OTLPExporter for GKE.

    Example:
        ```python
        from tracecraft.contrib.gcp import configure_for_gke
        import tracecraft

        # Direct to Cloud Trace
        exporter = configure_for_gke(service_name="my-gke-service")

        # Via OTEL Collector
        exporter = configure_for_gke(
            service_name="my-gke-service",
            collector_endpoint="http://otel-collector:4317"
        )
        tracecraft.init(exporters=[exporter])
        ```
    """
    if collector_endpoint:
        # Use local collector
        from tracecraft.exporters.otlp import OTLPExporter

        return OTLPExporter(
            endpoint=collector_endpoint,
            service_name=service_name,
            protocol="grpc",
        )

    # Direct to Cloud Trace
    return create_cloudtrace_exporter(service_name=service_name)


def configure_for_vertex_ai(
    service_name: str = "tracecraft",
) -> OTLPExporter:
    """
    Configure for Vertex AI (custom training, prediction, or pipelines).

    Vertex AI workloads have access to GCP credentials automatically.

    Args:
        service_name: Service name for traces.

    Returns:
        Configured OTLPExporter for Vertex AI.

    Example:
        ```python
        from tracecraft.contrib.gcp import configure_for_vertex_ai
        import tracecraft

        # In your Vertex AI custom training job
        exporter = configure_for_vertex_ai(service_name="my-training-job")
        tracecraft.init(exporters=[exporter])
        ```
    """
    return create_cloudtrace_exporter(service_name=service_name)


# --- Vertex AI Agent Builder Integration ---


def create_vertex_agent_exporter(
    project_id: str | None = None,
    service_name: str = "tracecraft",
    session_id: str | None = None,
    agent_name: str | None = None,
    agent_id: str | None = None,
    agent_description: str | None = None,
    enable_content_recording: bool = False,
    reasoning_engine_id: str | None = None,
) -> OTLPExporter:
    """
    Create an exporter configured for Vertex AI Agent Builder.

    Extends Cloud Trace export with Vertex AI-specific telemetry format
    and session tracking for multi-turn conversations.

    Args:
        project_id: GCP project ID. Defaults to GOOGLE_CLOUD_PROJECT env var.
        service_name: Service name for traces.
        session_id: Session ID for multi-turn conversations.
        agent_name: Agent name for gen_ai.agent.name attribute.
        agent_id: Agent ID for gen_ai.agent.id attribute.
        agent_description: Agent description for gen_ai.agent.description.
        enable_content_recording: Whether to record prompt/response content.
        reasoning_engine_id: For Reasoning Engine integration.

    Returns:
        Configured OTLPExporter for Vertex AI Agent Builder.

    Example:
        ```python
        from tracecraft.contrib.gcp import create_vertex_agent_exporter
        import tracecraft

        exporter = create_vertex_agent_exporter(
            service_name="my-agent",
            session_id="session-12345",
            agent_name="research-agent",
            agent_id="agent-001",
        )
        tracecraft.init(exporters=[exporter])
        ```

    Note:
        Requires GCP credentials configured via ADC or service account.
        Session ID enables correlation of multi-turn conversations.
    """
    exporter = create_cloudtrace_exporter(
        project_id=project_id,
        service_name=service_name,
    )

    # Store Vertex AI-specific configuration on the exporter
    exporter._vertex_config = VertexAgentConfig(  # type: ignore[attr-defined]
        session_id=session_id,
        agent_name=agent_name,
        agent_id=agent_id,
        agent_description=agent_description,
        enable_content_recording=enable_content_recording,
        reasoning_engine_id=reasoning_engine_id,
    )

    return exporter


def configure_for_vertex_agent_builder(
    service_name: str = "tracecraft",
    session_id: str | None = None,
    agent_name: str | None = None,
    enable_content_recording: bool | None = None,
) -> OTLPExporter:
    """
    Configure for Vertex AI Agent Builder using environment variables.

    Uses environment variables:
    - GOOGLE_CLOUD_PROJECT: GCP project ID (required)
    - TRACECRAFT_GCP_SESSION_ID: Session ID for conversation tracking
    - TRACECRAFT_GCP_AGENT_NAME: Agent name
    - TRACECRAFT_GCP_AGENT_ID: Agent ID
    - TRACECRAFT_GCP_CONTENT_RECORDING: Enable content recording (true/false)
    - TRACECRAFT_GCP_REASONING_ENGINE_ID: Reasoning Engine ID

    Args:
        service_name: Service name for traces.
        session_id: Override env var for session ID.
        agent_name: Override env var for agent name.
        enable_content_recording: Override env var for content recording.

    Returns:
        Configured OTLPExporter for Vertex AI Agent Builder.

    Example:
        ```python
        from tracecraft.contrib.gcp import configure_for_vertex_agent_builder
        import tracecraft

        # Uses environment variables
        exporter = configure_for_vertex_agent_builder(service_name="my-agent")
        tracecraft.init(exporters=[exporter])
        ```
    """
    # Resolve session ID from env if not provided
    if session_id is None:
        session_id = os.environ.get("TRACECRAFT_GCP_SESSION_ID")

    # Resolve agent name from env if not provided
    if agent_name is None:
        agent_name = os.environ.get("TRACECRAFT_GCP_AGENT_NAME")

    # Get agent ID from env
    agent_id = os.environ.get("TRACECRAFT_GCP_AGENT_ID")

    # Resolve content recording from env if not provided
    if enable_content_recording is None:
        env_value = os.environ.get("TRACECRAFT_GCP_CONTENT_RECORDING", "false")
        enable_content_recording = env_value.lower() in ("true", "1", "yes")

    # Get reasoning engine ID from env
    reasoning_engine_id = os.environ.get("TRACECRAFT_GCP_REASONING_ENGINE_ID")

    return create_vertex_agent_exporter(
        service_name=service_name,
        session_id=session_id,
        agent_name=agent_name,
        agent_id=agent_id,
        enable_content_recording=enable_content_recording,
        reasoning_engine_id=reasoning_engine_id,
    )


def inject_cloudtrace_context(
    carrier: dict[str, str],
    run: AgentRun,
    session_id: str | None = None,
    sampled: bool = True,
    use_legacy_format: bool = False,
) -> None:
    """
    Inject Cloud Trace context headers for cross-service tracing.

    Adds both W3C traceparent and X-Cloud-Trace-Context headers, plus
    optional session header for Vertex AI Agent Builder.

    Args:
        carrier: Dictionary to inject headers into (e.g., HTTP headers).
        run: The current AgentRun to extract trace context from.
        session_id: Optional session ID for agent session tracking.
        sampled: Whether the trace is sampled.
        use_legacy_format: If True, use legacy X-Cloud-Trace-Context only.

    Example:
        ```python
        from tracecraft.contrib.gcp import inject_cloudtrace_context
        from tracecraft import get_current_run
        import requests

        # Inject Cloud Trace context into outgoing request
        headers = {}
        inject_cloudtrace_context(headers, get_current_run(), session_id="session-123")
        response = requests.post(url, headers=headers, json=payload)
        ```
    """
    from tracecraft.propagation.cloudtrace import CloudTraceContextPropagator

    propagator = CloudTraceContextPropagator(use_legacy_format=use_legacy_format)

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


def extract_cloudtrace_context(
    carrier: dict[str, str],
) -> tuple[str, str, bool, str | None] | None:
    """
    Extract Cloud Trace context from incoming request headers.

    Parses both W3C traceparent and legacy X-Cloud-Trace-Context headers,
    plus optional session header for Vertex AI Agent Builder.

    Args:
        carrier: Dictionary containing headers (e.g., HTTP request headers).

    Returns:
        Tuple of (trace_id, span_id, sampled, session_id) or None if not found.

    Example:
        ```python
        from tracecraft.contrib.gcp import extract_cloudtrace_context

        # Extract context from incoming request
        result = extract_cloudtrace_context(request.headers)
        if result:
            trace_id, span_id, sampled, session_id = result
            # Use extracted context to continue the trace
        ```
    """
    from tracecraft.propagation.cloudtrace import CloudTraceContextPropagator

    propagator = CloudTraceContextPropagator()
    return propagator.extract(carrier)


class VertexAITracerAdapter:
    """
    Adapter for Vertex AI Agent Builder tracing.

    Wraps TraceCraftCallbackHandler and adds Vertex AI-specific
    attributes for gen_ai semantic conventions. Implements the LangChain
    callback handler interface for use with LangChain agents.

    Example:
        ```python
        from tracecraft.contrib.gcp import VertexAITracerAdapter

        adapter = VertexAITracerAdapter(
            project_id="my-project",
            enable_content_recording=True,
            agent_name="my-agent",
        )

        # Use with LangChain
        chain.invoke({"input": "..."}, config={"callbacks": [adapter]})
        ```

    Note:
        This adapter wraps TraceCraftCallbackHandler and adds Vertex AI
        specific attributes. For Reasoning Engine integration, pass
        the reasoning_engine_id parameter.
    """

    def __init__(
        self,
        project_id: str | None = None,
        enable_content_recording: bool = False,
        agent_name: str | None = None,
        agent_id: str | None = None,
        reasoning_engine_id: str | None = None,
    ) -> None:
        """
        Initialize the Vertex AI Tracer adapter.

        Args:
            project_id: GCP project ID.
            enable_content_recording: Whether to record content.
            agent_name: Agent name for traces.
            agent_id: Agent ID for traces.
            reasoning_engine_id: Reasoning Engine ID for integration.
        """
        self.project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
        self.enable_content_recording = enable_content_recording
        self.agent_name = agent_name
        self.agent_id = agent_id
        self.reasoning_engine_id = reasoning_engine_id

        # Store config for reference
        self._config = VertexAgentConfig(
            agent_name=agent_name,
            agent_id=agent_id,
            enable_content_recording=enable_content_recording,
            reasoning_engine_id=reasoning_engine_id,
        )

        # Lazily initialize the underlying handler
        self._handler: Any = None

    def _get_handler(self) -> Any:
        """Get or create the underlying callback handler."""
        if self._handler is None:
            from tracecraft.adapters.langchain import TraceCraftCallbackHandler

            self._handler = TraceCraftCallbackHandler()

        return self._handler

    # --- LangChain Callback Handler Interface ---
    # Delegate all callback methods to the underlying handler

    def on_chain_start(self, *args: Any, **kwargs: Any) -> Any:
        """Handle chain start event."""
        return self._get_handler().on_chain_start(*args, **kwargs)

    def on_chain_end(self, *args: Any, **kwargs: Any) -> Any:
        """Handle chain end event."""
        return self._get_handler().on_chain_end(*args, **kwargs)

    def on_chain_error(self, *args: Any, **kwargs: Any) -> Any:
        """Handle chain error event."""
        return self._get_handler().on_chain_error(*args, **kwargs)

    def on_llm_start(self, *args: Any, **kwargs: Any) -> Any:
        """Handle LLM start event."""
        return self._get_handler().on_llm_start(*args, **kwargs)

    def on_llm_end(self, *args: Any, **kwargs: Any) -> Any:
        """Handle LLM end event."""
        return self._get_handler().on_llm_end(*args, **kwargs)

    def on_llm_error(self, *args: Any, **kwargs: Any) -> Any:
        """Handle LLM error event."""
        return self._get_handler().on_llm_error(*args, **kwargs)

    def on_llm_new_token(self, *args: Any, **kwargs: Any) -> Any:
        """Handle new token event (streaming)."""
        return self._get_handler().on_llm_new_token(*args, **kwargs)

    def on_tool_start(self, *args: Any, **kwargs: Any) -> Any:
        """Handle tool start event."""
        return self._get_handler().on_tool_start(*args, **kwargs)

    def on_tool_end(self, *args: Any, **kwargs: Any) -> Any:
        """Handle tool end event."""
        return self._get_handler().on_tool_end(*args, **kwargs)

    def on_tool_error(self, *args: Any, **kwargs: Any) -> Any:
        """Handle tool error event."""
        return self._get_handler().on_tool_error(*args, **kwargs)

    def on_retriever_start(self, *args: Any, **kwargs: Any) -> Any:
        """Handle retriever start event."""
        return self._get_handler().on_retriever_start(*args, **kwargs)

    def on_retriever_end(self, *args: Any, **kwargs: Any) -> Any:
        """Handle retriever end event."""
        return self._get_handler().on_retriever_end(*args, **kwargs)

    def on_retriever_error(self, *args: Any, **kwargs: Any) -> Any:
        """Handle retriever error event."""
        return self._get_handler().on_retriever_error(*args, **kwargs)

    def clear(self) -> None:
        """Clear the handler state."""
        if self._handler is not None:
            self._handler.clear()
