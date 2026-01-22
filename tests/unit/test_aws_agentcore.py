"""
Tests for AWS Bedrock AgentCore integration.

Tests AgentCore exporter, X-Ray context injection, and configuration.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from agenttrace.core.models import AgentRun


class TestAgentCoreExporter:
    """Tests for AWS AgentCore exporter configuration."""

    def test_create_agentcore_exporter(self) -> None:
        """create_agentcore_exporter should return configured exporter."""
        from agenttrace.contrib.aws import create_agentcore_exporter

        exporter = create_agentcore_exporter(
            service_name="test-agent",
            session_id="session-123",
        )

        assert exporter is not None
        assert exporter.service_name == "test-agent"

    def test_create_agentcore_exporter_stores_config(self) -> None:
        """create_agentcore_exporter should store AgentCoreConfig on exporter."""
        from agenttrace.contrib.aws import AgentCoreConfig, create_agentcore_exporter

        exporter = create_agentcore_exporter(
            session_id="session-123",
            use_xray_propagation=True,
        )

        config = getattr(exporter, "_agentcore_config", None)
        assert config is not None
        assert isinstance(config, AgentCoreConfig)
        assert config.session_id == "session-123"
        assert config.use_xray_propagation is True

    def test_create_agentcore_exporter_default_endpoint(self) -> None:
        """create_agentcore_exporter should default to localhost:4317."""
        from agenttrace.contrib.aws import create_agentcore_exporter

        exporter = create_agentcore_exporter()

        assert "localhost:4317" in exporter.endpoint

    def test_create_agentcore_exporter_custom_endpoint(self) -> None:
        """create_agentcore_exporter should accept custom endpoint."""
        from agenttrace.contrib.aws import create_agentcore_exporter

        exporter = create_agentcore_exporter(
            endpoint="http://adot-collector:4317",
        )

        assert exporter.endpoint == "http://adot-collector:4317"


class TestConfigureForAgentCoreRuntime:
    """Tests for configure_for_agentcore_runtime."""

    def test_configure_for_agentcore_runtime(self) -> None:
        """configure_for_agentcore_runtime should return configured exporter."""
        from agenttrace.contrib.aws import configure_for_agentcore_runtime

        exporter = configure_for_agentcore_runtime(
            service_name="my-agent",
            session_id="session-456",
        )

        assert exporter is not None
        config = getattr(exporter, "_agentcore_config", None)
        assert config is not None
        assert config.session_id == "session-456"

    def test_configure_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """configure_for_agentcore_runtime should use environment variables."""
        from agenttrace.contrib.aws import configure_for_agentcore_runtime

        monkeypatch.setenv("AGENTTRACE_AWS_SESSION_ID", "env-session-789")

        exporter = configure_for_agentcore_runtime()

        config = getattr(exporter, "_agentcore_config", None)
        assert config is not None
        assert config.session_id == "env-session-789"


class TestInjectXRayContext:
    """Tests for X-Ray context injection helper."""

    def test_inject_xray_context(self, sample_run: AgentRun) -> None:
        """inject_xray_context should add X-Ray header to carrier."""
        from agenttrace.contrib.aws import inject_xray_context

        carrier: dict[str, str] = {}
        inject_xray_context(carrier, sample_run)

        assert "X-Amzn-Trace-Id" in carrier
        header = carrier["X-Amzn-Trace-Id"]
        assert "Root=" in header
        assert "Parent=" in header
        assert "Sampled=" in header

    def test_inject_xray_context_with_session_id(self, sample_run: AgentRun) -> None:
        """inject_xray_context should add session header when provided."""
        from agenttrace.contrib.aws import inject_xray_context

        carrier: dict[str, str] = {}
        inject_xray_context(carrier, sample_run, session_id="my-session")

        assert "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id" in carrier
        assert carrier["X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"] == "my-session"

    def test_inject_xray_context_uses_run_session(self, sample_run_with_session: AgentRun) -> None:
        """inject_xray_context should use session_id from run if not provided."""
        from agenttrace.contrib.aws import inject_xray_context

        carrier: dict[str, str] = {}
        inject_xray_context(carrier, sample_run_with_session)

        assert "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id" in carrier
        assert carrier["X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"] == "session-12345"

    def test_inject_xray_context_sampled_flag(self, sample_run: AgentRun) -> None:
        """inject_xray_context should respect sampled parameter."""
        from agenttrace.contrib.aws import inject_xray_context

        # Test sampled=True
        carrier: dict[str, str] = {}
        inject_xray_context(carrier, sample_run, sampled=True)
        assert "Sampled=1" in carrier["X-Amzn-Trace-Id"]

        # Test sampled=False
        carrier = {}
        inject_xray_context(carrier, sample_run, sampled=False)
        assert "Sampled=0" in carrier["X-Amzn-Trace-Id"]


class TestExtractXRayContext:
    """Tests for X-Ray context extraction helper."""

    def test_extract_xray_context(self) -> None:
        """extract_xray_context should parse valid X-Ray header."""
        from agenttrace.contrib.aws import extract_xray_context

        carrier = {
            "X-Amzn-Trace-Id": "Root=1-5759e988-bd862e3fe1be46a994272793;Parent=53995c3f42cd8ad8;Sampled=1"
        }

        result = extract_xray_context(carrier)

        assert result is not None
        trace_id, span_id, sampled, session_id = result
        assert trace_id == "1-5759e988-bd862e3fe1be46a994272793"
        assert span_id == "53995c3f42cd8ad8"
        assert sampled is True
        assert session_id is None

    def test_extract_xray_context_with_session(self) -> None:
        """extract_xray_context should extract session ID when present."""
        from agenttrace.contrib.aws import extract_xray_context

        carrier = {
            "X-Amzn-Trace-Id": "Root=1-5759e988-bd862e3fe1be46a994272793;Parent=53995c3f42cd8ad8;Sampled=1",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": "my-session",
        }

        result = extract_xray_context(carrier)

        assert result is not None
        _, _, _, session_id = result
        assert session_id == "my-session"

    def test_extract_xray_context_missing_header(self) -> None:
        """extract_xray_context should return None when header missing."""
        from agenttrace.contrib.aws import extract_xray_context

        carrier: dict[str, str] = {}

        result = extract_xray_context(carrier)

        assert result is None


class TestAgentCoreConfig:
    """Tests for AgentCoreConfig dataclass."""

    def test_agentcore_config_defaults(self) -> None:
        """AgentCoreConfig should have sensible defaults."""
        from agenttrace.contrib.aws import AgentCoreConfig

        config = AgentCoreConfig()

        assert config.session_id is None
        assert config.use_xray_propagation is True
        assert config.extra_attributes is None

    def test_agentcore_config_with_values(self) -> None:
        """AgentCoreConfig should accept custom values."""
        from agenttrace.contrib.aws import AgentCoreConfig

        config = AgentCoreConfig(
            session_id="session-123",
            use_xray_propagation=False,
            extra_attributes={"key": "value"},
        )

        assert config.session_id == "session-123"
        assert config.use_xray_propagation is False
        assert config.extra_attributes == {"key": "value"}


class TestAWSAgentCoreConfigEnv:
    """Tests for AWS AgentCore configuration via environment."""

    def test_load_config_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """load_config_from_env should load AWS AgentCore config."""
        from agenttrace.core.config import load_config_from_env

        monkeypatch.setenv("AGENTTRACE_AWS_AGENTCORE_ENABLED", "true")
        monkeypatch.setenv("AGENTTRACE_AWS_XRAY_PROPAGATION", "false")
        monkeypatch.setenv("AGENTTRACE_AWS_SESSION_ID", "env-session")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://custom:4317")

        config = load_config_from_env()

        assert config.aws_agentcore.enabled is True
        assert config.aws_agentcore.use_xray_propagation is False
        assert config.aws_agentcore.session_id == "env-session"
        assert config.aws_agentcore.adot_endpoint == "http://custom:4317"

    def test_aws_config_defaults(self) -> None:
        """AWS AgentCore config should have sensible defaults."""
        from agenttrace.core.config import AWSAgentCoreConfig

        config = AWSAgentCoreConfig()

        assert config.enabled is False
        assert config.use_xray_propagation is True
        assert config.session_id is None
        assert config.adot_endpoint == "http://localhost:4317"


# Fixtures
@pytest.fixture
def sample_run() -> AgentRun:
    """Create a sample run for testing."""
    return AgentRun(
        id=uuid4(),
        name="test_run",
        start_time=datetime.now(UTC),
    )


@pytest.fixture
def sample_run_with_session() -> AgentRun:
    """Create a sample run with session ID for testing."""
    return AgentRun(
        id=uuid4(),
        name="test_run",
        start_time=datetime.now(UTC),
        session_id="session-12345",
    )
