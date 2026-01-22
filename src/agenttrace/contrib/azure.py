"""
Azure Application Insights and AI Foundry configuration helpers.

Provides easy configuration for exporting traces to:
- Azure Monitor Application Insights via OpenTelemetry
- Azure AI Foundry observability with GenAI semantic conventions

See:
- https://learn.microsoft.com/en-us/azure/ai-foundry/observability/concepts/trace-agent-concept
- https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/azure-ai-foundry-advancing-opentelemetry-and-delivering-unified-multi-agent-obse/4456039
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agenttrace.exporters.otlp import OTLPExporter


@dataclass
class FoundryConfig:
    """Configuration for Azure AI Foundry integration.

    Attributes:
        enable_content_recording: Whether to record prompt/response content.
            Disabled by default for privacy.
        agent_name: Optional agent name for gen_ai.agent.name attribute.
        agent_id: Optional agent ID for gen_ai.agent.id attribute.
        agent_description: Optional description for gen_ai.agent.description.
    """

    enable_content_recording: bool = False
    agent_name: str | None = None
    agent_id: str | None = None
    agent_description: str | None = None
    extra_attributes: dict[str, Any] = field(default_factory=dict)


def create_appinsights_exporter(
    connection_string: str | None = None,
    service_name: str = "agenttrace",
) -> OTLPExporter:
    """
    Create an exporter configured for Azure Application Insights.

    Args:
        connection_string: Azure connection string. Defaults to
            APPLICATIONINSIGHTS_CONNECTION_STRING env var.
        service_name: Service name for traces.

    Returns:
        Configured OTLPExporter for Application Insights.

    Raises:
        ValueError: If connection string is not provided or invalid.

    Example:
        ```python
        from agenttrace.contrib.azure import create_appinsights_exporter
        import agenttrace

        exporter = create_appinsights_exporter()
        agenttrace.init(exporters=[exporter])
        ```
    """
    from agenttrace.exporters.otlp import OTLPExporter

    connection_string = connection_string or os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")

    if not connection_string:
        raise ValueError(
            "Azure connection string required. Set APPLICATIONINSIGHTS_CONNECTION_STRING "
            "environment variable or pass connection_string parameter."
        )

    # Parse connection string
    # Format: InstrumentationKey=xxx;IngestionEndpoint=https://xxx.in.applicationinsights.azure.com/
    parts = dict(p.split("=", 1) for p in connection_string.split(";") if "=" in p)
    ingestion_endpoint = parts.get("IngestionEndpoint", "").rstrip("/")
    instrumentation_key = parts.get("InstrumentationKey", "")

    if not ingestion_endpoint:
        raise ValueError("Invalid connection string: missing IngestionEndpoint")

    if not instrumentation_key:
        raise ValueError("Invalid connection string: missing InstrumentationKey")

    # Azure Monitor OTLP endpoint
    # Azure uses the /v2.1/track endpoint for OTLP
    otlp_endpoint = f"{ingestion_endpoint}/v2.1/track"

    return OTLPExporter(
        endpoint=otlp_endpoint,
        service_name=service_name,
        protocol="http",
        headers={"x-ms-instrumentation-key": instrumentation_key},
    )


def configure_for_azure_functions(
    service_name: str = "agenttrace",
) -> OTLPExporter:
    """
    Configure for Azure Functions with Application Insights.

    Uses the APPLICATIONINSIGHTS_CONNECTION_STRING environment variable
    that Azure Functions automatically sets.

    Args:
        service_name: Service name for traces.

    Returns:
        Configured OTLPExporter for Azure Functions.

    Example:
        ```python
        from agenttrace.contrib.azure import configure_for_azure_functions
        import agenttrace

        # In your Azure Function
        exporter = configure_for_azure_functions(service_name="my-function")
        agenttrace.init(exporters=[exporter], console=False, jsonl=False)
        ```
    """
    return create_appinsights_exporter(service_name=service_name)


def configure_for_aks(
    connection_string: str | None = None,
    service_name: str = "agenttrace",
) -> OTLPExporter:
    """
    Configure for Azure Kubernetes Service (AKS) with Application Insights.

    Args:
        connection_string: Azure connection string. Can be injected via
            Kubernetes secret or ConfigMap.
        service_name: Service name for traces.

    Returns:
        Configured OTLPExporter for AKS.

    Example:
        ```python
        from agenttrace.contrib.azure import configure_for_aks
        import agenttrace

        exporter = configure_for_aks(service_name="my-aks-service")
        agenttrace.init(exporters=[exporter])
        ```
    """
    return create_appinsights_exporter(
        connection_string=connection_string,
        service_name=service_name,
    )


def parse_connection_string(connection_string: str) -> dict[str, str]:
    """
    Parse an Azure Application Insights connection string.

    Args:
        connection_string: The connection string to parse.

    Returns:
        Dictionary with parsed components (InstrumentationKey, IngestionEndpoint, etc.)

    Example:
        ```python
        from agenttrace.contrib.azure import parse_connection_string

        parts = parse_connection_string(os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"])
        print(f"Instrumentation Key: {parts['InstrumentationKey']}")
        ```
    """
    return dict(p.split("=", 1) for p in connection_string.split(";") if "=" in p)


# --- Azure AI Foundry Integration ---


def create_foundry_exporter(
    connection_string: str | None = None,
    service_name: str = "agenttrace",
    enable_content_recording: bool = False,
    agent_name: str | None = None,
    agent_id: str | None = None,
    agent_description: str | None = None,
) -> OTLPExporter:
    """
    Create an exporter configured for Azure AI Foundry observability.

    Extends Application Insights export with AI Foundry-specific
    semantic conventions and content recording support.

    Args:
        connection_string: Azure connection string. Defaults to
            APPLICATIONINSIGHTS_CONNECTION_STRING env var.
        service_name: Service name for traces.
        enable_content_recording: Whether to record prompt/completion content.
            Disabled by default for privacy.
        agent_name: Optional agent name for gen_ai.agent.name attribute.
        agent_id: Optional agent ID for gen_ai.agent.id attribute.
        agent_description: Optional description for gen_ai.agent.description.

    Returns:
        Configured OTLPExporter for Azure AI Foundry.

    Example:
        ```python
        from agenttrace.contrib.azure import create_foundry_exporter
        import agenttrace

        exporter = create_foundry_exporter(
            enable_content_recording=True,
            agent_name="research-agent",
            agent_id="agent-001",
        )
        agenttrace.init(exporters=[exporter])
        ```

    Note:
        Content recording captures prompt and response content in traces.
        Only enable in development/debugging scenarios or when your data
        handling policies allow it.
    """
    # Get base App Insights exporter
    exporter = create_appinsights_exporter(
        connection_string=connection_string,
        service_name=service_name,
    )

    # Store Foundry-specific configuration on the exporter
    # This will be used by the export pipeline to add attributes
    exporter._foundry_config = FoundryConfig(  # type: ignore[attr-defined]
        enable_content_recording=enable_content_recording,
        agent_name=agent_name,
        agent_id=agent_id,
        agent_description=agent_description,
    )

    return exporter


def configure_for_ai_foundry(
    service_name: str = "agenttrace",
    enable_content_recording: bool | None = None,
    agent_name: str | None = None,
) -> OTLPExporter:
    """
    Configure for Azure AI Foundry using environment variables.

    Uses environment variables:
    - APPLICATIONINSIGHTS_CONNECTION_STRING: Required
    - AGENTTRACE_AZURE_CONTENT_RECORDING: Enable content recording (true/false)
    - AGENTTRACE_AZURE_AGENT_NAME: Agent name
    - AGENTTRACE_AZURE_AGENT_ID: Agent ID

    Args:
        service_name: Service name for traces.
        enable_content_recording: Override env var for content recording.
        agent_name: Override env var for agent name.

    Returns:
        Configured OTLPExporter for Azure AI Foundry.

    Example:
        ```python
        from agenttrace.contrib.azure import configure_for_ai_foundry
        import agenttrace

        # Uses APPLICATIONINSIGHTS_CONNECTION_STRING env var
        exporter = configure_for_ai_foundry(service_name="my-agent")
        agenttrace.init(exporters=[exporter])
        ```
    """
    # Resolve content recording from env if not provided
    if enable_content_recording is None:
        env_value = os.environ.get("AGENTTRACE_AZURE_CONTENT_RECORDING", "false")
        enable_content_recording = env_value.lower() in ("true", "1", "yes")

    # Resolve agent name from env if not provided
    if agent_name is None:
        agent_name = os.environ.get("AGENTTRACE_AZURE_AGENT_NAME")

    # Get agent ID from env
    agent_id = os.environ.get("AGENTTRACE_AZURE_AGENT_ID")

    return create_foundry_exporter(
        service_name=service_name,
        enable_content_recording=enable_content_recording,
        agent_name=agent_name,
        agent_id=agent_id,
    )


class AzureAITracerAdapter:
    """
    Adapter for Azure AI Foundry's AzureAIOpenTelemetryTracer compatibility.

    Allows using AgentTrace as a drop-in replacement or alongside
    the langchain-azure-ai tracer. Implements the LangChain callback
    handler interface.

    Example:
        ```python
        from agenttrace.contrib.azure import AzureAITracerAdapter

        adapter = AzureAITracerAdapter(
            connection_string="...",
            enable_content_recording=True,
            agent_name="my-agent",
        )

        # Use with LangChain
        chain.invoke({"input": "..."}, config={"callbacks": [adapter]})
        ```

    Note:
        This adapter wraps AgentTraceCallbackHandler and adds Azure AI Foundry
        specific attributes. For full AzureAIOpenTelemetryTracer compatibility,
        install langchain-azure-ai and use their tracer directly.
    """

    def __init__(
        self,
        connection_string: str | None = None,
        enable_content_recording: bool = False,
        agent_name: str | None = None,
        agent_id: str | None = None,
    ) -> None:
        """
        Initialize the Azure AI Tracer adapter.

        Args:
            connection_string: Azure connection string.
            enable_content_recording: Whether to record content.
            agent_name: Agent name for traces.
            agent_id: Agent ID for traces.
        """
        self.connection_string = connection_string
        self.enable_content_recording = enable_content_recording
        self.agent_name = agent_name
        self.agent_id = agent_id

        # Store config for reference
        self._config = FoundryConfig(
            enable_content_recording=enable_content_recording,
            agent_name=agent_name,
            agent_id=agent_id,
        )

        # Lazily initialize the underlying handler
        self._handler: Any = None

    def _get_handler(self) -> Any:
        """Get or create the underlying callback handler."""
        if self._handler is None:
            from agenttrace.adapters.langchain import AgentTraceCallbackHandler

            self._handler = AgentTraceCallbackHandler()

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
