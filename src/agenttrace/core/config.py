"""
Configuration management for AgentTrace.

Provides dataclasses for configuration and functions for loading
configuration from environment variables.
"""

from __future__ import annotations

import contextlib
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from agenttrace.processors.redaction import RedactionMode


class ProcessorOrder(str, Enum):
    """Processor pipeline ordering strategy.

    SAFETY: Enrich → Redact → Sample (default)
        - Ensures redaction happens before any data leaves
        - Better for compliance-sensitive environments
        - Slightly more processing overhead (processes all traces before sampling)

    EFFICIENCY: Sample → Redact → Enrich
        - Samples first to reduce processing overhead
        - Better for high-throughput, cost-sensitive environments
        - Only processes traces that pass sampling
    """

    SAFETY = "safety"
    EFFICIENCY = "efficiency"


def _parse_bool(value: str) -> bool:
    """Parse a string to boolean."""
    return value.lower() in ("true", "1", "yes")


@dataclass
class RedactionConfig:
    """Configuration for PII redaction.

    Note: Redaction is enabled by default for privacy-first behavior.
    To disable redaction (e.g., for debugging), set enabled=False explicitly.
    """

    enabled: bool = True  # Privacy-first: enabled by default
    mode: RedactionMode = RedactionMode.MASK
    custom_patterns: list[str] = field(default_factory=list)
    allowlist: list[str] = field(default_factory=list)
    allowlist_patterns: list[str] = field(default_factory=list)


@dataclass
class SamplingConfig:
    """Configuration for trace sampling."""

    rate: float = 1.0
    always_keep_errors: bool = True
    always_keep_slow: bool = False
    slow_threshold_ms: float = 5000.0

    def __post_init__(self) -> None:
        """Validate sampling rate bounds."""
        if not 0.0 <= self.rate <= 1.0:
            raise ValueError(f"Sampling rate must be between 0.0 and 1.0, got {self.rate}")


@dataclass
class ExporterConfig:
    """Configuration for exporters."""

    console_enabled: bool = True
    console_verbose: bool = False
    jsonl_enabled: bool = True
    jsonl_path: str | Path | None = None
    otlp_enabled: bool = False
    otlp_endpoint: str | None = None
    otlp_headers: dict[str, str] = field(default_factory=dict)


@dataclass
class AzureFoundryConfig:
    """Configuration for Azure AI Foundry integration.

    Attributes:
        enabled: Whether Azure Foundry export is enabled.
        connection_string: Application Insights connection string.
        enable_content_recording: Whether to record prompt/response content.
        agent_name: Agent name for gen_ai.agent.name attribute.
        agent_id: Agent ID for gen_ai.agent.id attribute.
        agent_description: Agent description for gen_ai.agent.description.
    """

    enabled: bool = False
    connection_string: str | None = None
    enable_content_recording: bool = False
    agent_name: str | None = None
    agent_id: str | None = None
    agent_description: str | None = None


@dataclass
class AWSAgentCoreConfig:
    """Configuration for AWS Bedrock AgentCore integration.

    Attributes:
        enabled: Whether AgentCore export is enabled.
        use_xray_propagation: Whether to use X-Ray header format.
        session_id: Session ID for multi-turn conversations.
        adot_endpoint: ADOT collector endpoint.
    """

    enabled: bool = False
    use_xray_propagation: bool = True
    session_id: str | None = None
    adot_endpoint: str = "http://localhost:4317"


@dataclass
class GCPVertexAgentConfig:
    """Configuration for GCP Vertex AI Agent Builder integration.

    Attributes:
        enabled: Whether Vertex Agent export is enabled.
        project_id: GCP project ID.
        session_id: Session ID for multi-turn conversations.
        agent_name: Agent name for gen_ai.agent.name attribute.
        agent_id: Agent ID for gen_ai.agent.id attribute.
        agent_description: Agent description for gen_ai.agent.description.
        enable_content_recording: Whether to record prompt/response content.
        reasoning_engine_id: For Reasoning Engine integration.
    """

    enabled: bool = False
    project_id: str | None = None
    session_id: str | None = None
    agent_name: str | None = None
    agent_id: str | None = None
    agent_description: str | None = None
    enable_content_recording: bool = False
    reasoning_engine_id: str | None = None


@dataclass
class AgentTraceConfig:
    """Main configuration for AgentTrace."""

    service_name: str = "agenttrace"
    console_enabled: bool = True
    jsonl_enabled: bool = True
    jsonl_path: str | Path | None = None
    tags: list[str] = field(default_factory=list)

    # Processor configuration
    processor_order: ProcessorOrder = ProcessorOrder.SAFETY

    # Step hierarchy configuration
    max_step_depth: int | None = 100  # None means unlimited

    # Nested configurations
    redaction: RedactionConfig = field(default_factory=RedactionConfig)
    sampling: SamplingConfig = field(default_factory=SamplingConfig)
    exporter: ExporterConfig = field(default_factory=ExporterConfig)

    # Cloud platform configurations
    azure_foundry: AzureFoundryConfig = field(default_factory=AzureFoundryConfig)
    aws_agentcore: AWSAgentCoreConfig = field(default_factory=AWSAgentCoreConfig)
    gcp_vertex_agent: GCPVertexAgentConfig = field(default_factory=GCPVertexAgentConfig)


def load_config_from_env() -> AgentTraceConfig:
    """
    Load configuration from environment variables.

    Environment variables:
        AGENTTRACE_SERVICE_NAME: Service name
        AGENTTRACE_CONSOLE_ENABLED: Enable console exporter (true/false)
        AGENTTRACE_JSONL_ENABLED: Enable JSONL exporter (true/false)
        AGENTTRACE_JSONL_PATH: Path for JSONL file
        AGENTTRACE_SAMPLING_RATE: Sampling rate (0.0-1.0)
        AGENTTRACE_OTLP_ENABLED: Enable OTLP exporter (true/false)
        AGENTTRACE_OTLP_ENDPOINT: OTLP collector endpoint
        AGENTTRACE_REDACTION_ENABLED: Enable PII redaction (true/false, default: true)
        AGENTTRACE_AZURE_FOUNDRY_ENABLED: Enable Azure AI Foundry (true/false)
        AGENTTRACE_AZURE_CONTENT_RECORDING: Enable content recording (true/false)
        AGENTTRACE_AZURE_AGENT_NAME: Agent name for Azure Foundry
        AGENTTRACE_AZURE_AGENT_ID: Agent ID for Azure Foundry
        AGENTTRACE_AWS_AGENTCORE_ENABLED: Enable AWS AgentCore (true/false)
        AGENTTRACE_AWS_XRAY_PROPAGATION: Use X-Ray propagation (true/false)
        AGENTTRACE_AWS_SESSION_ID: Session ID for AgentCore
        AGENTTRACE_GCP_VERTEX_ENABLED: Enable GCP Vertex Agent (true/false)
        AGENTTRACE_GCP_SESSION_ID: Session ID for Vertex Agent
        AGENTTRACE_GCP_AGENT_NAME: Agent name for Vertex Agent
        AGENTTRACE_GCP_AGENT_ID: Agent ID for Vertex Agent
        AGENTTRACE_GCP_CONTENT_RECORDING: Enable content recording (true/false)
        AGENTTRACE_GCP_REASONING_ENGINE_ID: Reasoning Engine ID

    Returns:
        AgentTraceConfig instance.
    """
    # Main config
    service_name = os.environ.get("AGENTTRACE_SERVICE_NAME", "agenttrace")

    console_enabled_str = os.environ.get("AGENTTRACE_CONSOLE_ENABLED")
    console_enabled = _parse_bool(console_enabled_str) if console_enabled_str else True

    jsonl_enabled_str = os.environ.get("AGENTTRACE_JSONL_ENABLED")
    jsonl_enabled = _parse_bool(jsonl_enabled_str) if jsonl_enabled_str else True

    jsonl_path = os.environ.get("AGENTTRACE_JSONL_PATH")

    # Sampling config
    sampling_rate_str = os.environ.get("AGENTTRACE_SAMPLING_RATE")
    sampling_rate = 1.0
    if sampling_rate_str:
        with contextlib.suppress(ValueError):
            sampling_rate = float(sampling_rate_str)

    always_keep_errors_str = os.environ.get("AGENTTRACE_SAMPLING_KEEP_ERRORS")
    always_keep_errors = _parse_bool(always_keep_errors_str) if always_keep_errors_str else True

    sampling_config = SamplingConfig(
        rate=sampling_rate,
        always_keep_errors=always_keep_errors,
    )

    # Exporter config
    otlp_enabled_str = os.environ.get("AGENTTRACE_OTLP_ENABLED")
    otlp_enabled = _parse_bool(otlp_enabled_str) if otlp_enabled_str else False

    otlp_endpoint = os.environ.get("AGENTTRACE_OTLP_ENDPOINT")

    exporter_config = ExporterConfig(
        console_enabled=console_enabled,
        jsonl_enabled=jsonl_enabled,
        jsonl_path=jsonl_path,
        otlp_enabled=otlp_enabled,
        otlp_endpoint=otlp_endpoint,
    )

    # Redaction config (enabled by default for privacy-first behavior)
    redaction_enabled_str = os.environ.get("AGENTTRACE_REDACTION_ENABLED")
    redaction_enabled = _parse_bool(redaction_enabled_str) if redaction_enabled_str else True

    redaction_config = RedactionConfig(enabled=redaction_enabled)

    # Azure Foundry config
    azure_enabled_str = os.environ.get("AGENTTRACE_AZURE_FOUNDRY_ENABLED")
    azure_enabled = _parse_bool(azure_enabled_str) if azure_enabled_str else False

    azure_content_recording_str = os.environ.get("AGENTTRACE_AZURE_CONTENT_RECORDING")
    azure_content_recording = (
        _parse_bool(azure_content_recording_str) if azure_content_recording_str else False
    )

    azure_foundry_config = AzureFoundryConfig(
        enabled=azure_enabled,
        connection_string=os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"),
        enable_content_recording=azure_content_recording,
        agent_name=os.environ.get("AGENTTRACE_AZURE_AGENT_NAME"),
        agent_id=os.environ.get("AGENTTRACE_AZURE_AGENT_ID"),
    )

    # AWS AgentCore config
    aws_enabled_str = os.environ.get("AGENTTRACE_AWS_AGENTCORE_ENABLED")
    aws_enabled = _parse_bool(aws_enabled_str) if aws_enabled_str else False

    aws_xray_str = os.environ.get("AGENTTRACE_AWS_XRAY_PROPAGATION")
    aws_xray = _parse_bool(aws_xray_str) if aws_xray_str else True

    aws_agentcore_config = AWSAgentCoreConfig(
        enabled=aws_enabled,
        use_xray_propagation=aws_xray,
        session_id=os.environ.get("AGENTTRACE_AWS_SESSION_ID"),
        adot_endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
    )

    # GCP Vertex Agent config
    gcp_enabled_str = os.environ.get("AGENTTRACE_GCP_VERTEX_ENABLED")
    gcp_enabled = _parse_bool(gcp_enabled_str) if gcp_enabled_str else False

    gcp_content_recording_str = os.environ.get("AGENTTRACE_GCP_CONTENT_RECORDING")
    gcp_content_recording = (
        _parse_bool(gcp_content_recording_str) if gcp_content_recording_str else False
    )

    gcp_vertex_agent_config = GCPVertexAgentConfig(
        enabled=gcp_enabled,
        project_id=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        session_id=os.environ.get("AGENTTRACE_GCP_SESSION_ID"),
        agent_name=os.environ.get("AGENTTRACE_GCP_AGENT_NAME"),
        agent_id=os.environ.get("AGENTTRACE_GCP_AGENT_ID"),
        enable_content_recording=gcp_content_recording,
        reasoning_engine_id=os.environ.get("AGENTTRACE_GCP_REASONING_ENGINE_ID"),
    )

    return AgentTraceConfig(
        service_name=service_name,
        console_enabled=console_enabled,
        jsonl_enabled=jsonl_enabled,
        jsonl_path=jsonl_path,
        redaction=redaction_config,
        sampling=sampling_config,
        exporter=exporter_config,
        azure_foundry=azure_foundry_config,
        aws_agentcore=aws_agentcore_config,
        gcp_vertex_agent=gcp_vertex_agent_config,
    )


def load_config(**kwargs: Any) -> AgentTraceConfig:
    """
    Load configuration from environment variables and keyword arguments.

    Keyword arguments override environment variables.

    Args:
        **kwargs: Configuration values to override.

    Returns:
        AgentTraceConfig instance.
    """
    # Start with env config
    config = load_config_from_env()

    # Override with kwargs
    for key, value in kwargs.items():
        if value is not None and hasattr(config, key):
            setattr(config, key, value)

    return config
