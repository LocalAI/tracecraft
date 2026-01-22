"""
Tests for GCP Vertex AI Agent Builder integration.

Tests Vertex Agent exporter, content recording, and LangChain adapter.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

import pytest

from agenttrace.core.models import AgentRun


class TestVertexAgentExporter:
    """Tests for Vertex AI Agent Builder exporter configuration."""

    def test_create_vertex_agent_exporter(self) -> None:
        """create_vertex_agent_exporter should return configured exporter."""
        with patch("agenttrace.contrib.gcp._get_access_token", return_value="mock-token"):
            from agenttrace.contrib.gcp import create_vertex_agent_exporter

            exporter = create_vertex_agent_exporter(
                project_id="test-project",
                service_name="test-agent",
                session_id="session-123",
            )

            assert exporter is not None
            assert exporter.service_name == "test-agent"

    def test_create_vertex_agent_exporter_stores_config(self) -> None:
        """create_vertex_agent_exporter should store VertexAgentConfig on exporter."""
        with patch("agenttrace.contrib.gcp._get_access_token", return_value="mock-token"):
            from agenttrace.contrib.gcp import (
                VertexAgentConfig,
                create_vertex_agent_exporter,
            )

            exporter = create_vertex_agent_exporter(
                project_id="test-project",
                session_id="session-123",
                agent_name="research-agent",
                agent_id="agent-001",
                agent_description="A research agent",
                enable_content_recording=True,
                reasoning_engine_id="re-001",
            )

            config = getattr(exporter, "_vertex_config", None)
            assert config is not None
            assert isinstance(config, VertexAgentConfig)
            assert config.session_id == "session-123"
            assert config.agent_name == "research-agent"
            assert config.agent_id == "agent-001"
            assert config.agent_description == "A research agent"
            assert config.enable_content_recording is True
            assert config.reasoning_engine_id == "re-001"

    def test_create_vertex_agent_exporter_content_recording_default(self) -> None:
        """create_vertex_agent_exporter should have content recording disabled by default."""
        with patch("agenttrace.contrib.gcp._get_access_token", return_value="mock-token"):
            from agenttrace.contrib.gcp import create_vertex_agent_exporter

            exporter = create_vertex_agent_exporter(project_id="test-project")

            config = getattr(exporter, "_vertex_config", None)
            assert config is not None
            assert config.enable_content_recording is False


class TestConfigureForVertexAgentBuilder:
    """Tests for configure_for_vertex_agent_builder."""

    def test_configure_for_vertex_agent_builder(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """configure_for_vertex_agent_builder should use environment variables."""
        with patch("agenttrace.contrib.gcp._get_access_token", return_value="mock-token"):
            from agenttrace.contrib.gcp import configure_for_vertex_agent_builder

            monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
            monkeypatch.setenv("AGENTTRACE_GCP_SESSION_ID", "env-session")
            monkeypatch.setenv("AGENTTRACE_GCP_AGENT_NAME", "env-agent")
            monkeypatch.setenv("AGENTTRACE_GCP_AGENT_ID", "env-agent-id")
            monkeypatch.setenv("AGENTTRACE_GCP_CONTENT_RECORDING", "true")
            monkeypatch.setenv("AGENTTRACE_GCP_REASONING_ENGINE_ID", "re-001")

            exporter = configure_for_vertex_agent_builder(service_name="my-agent")

            config = getattr(exporter, "_vertex_config", None)
            assert config is not None
            assert config.session_id == "env-session"
            assert config.agent_name == "env-agent"
            assert config.agent_id == "env-agent-id"
            assert config.enable_content_recording is True
            assert config.reasoning_engine_id == "re-001"

    def test_configure_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """configure_for_vertex_agent_builder should allow overriding env values."""
        with patch("agenttrace.contrib.gcp._get_access_token", return_value="mock-token"):
            from agenttrace.contrib.gcp import configure_for_vertex_agent_builder

            monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
            monkeypatch.setenv("AGENTTRACE_GCP_SESSION_ID", "env-session")
            monkeypatch.setenv("AGENTTRACE_GCP_AGENT_NAME", "env-agent")
            monkeypatch.setenv("AGENTTRACE_GCP_CONTENT_RECORDING", "false")

            exporter = configure_for_vertex_agent_builder(
                session_id="override-session",
                agent_name="override-agent",
                enable_content_recording=True,
            )

            config = getattr(exporter, "_vertex_config", None)
            assert config is not None
            assert config.session_id == "override-session"
            assert config.agent_name == "override-agent"
            assert config.enable_content_recording is True


class TestVertexAgentConfig:
    """Tests for VertexAgentConfig dataclass."""

    def test_vertex_agent_config_defaults(self) -> None:
        """VertexAgentConfig should have sensible defaults."""
        from agenttrace.contrib.gcp import VertexAgentConfig

        config = VertexAgentConfig()

        assert config.session_id is None
        assert config.agent_name is None
        assert config.agent_id is None
        assert config.agent_description is None
        assert config.enable_content_recording is False
        assert config.reasoning_engine_id is None
        assert config.extra_attributes == {}

    def test_vertex_agent_config_with_values(self) -> None:
        """VertexAgentConfig should accept custom values."""
        from agenttrace.contrib.gcp import VertexAgentConfig

        config = VertexAgentConfig(
            session_id="session-123",
            agent_name="my-agent",
            agent_id="agent-001",
            agent_description="Test agent",
            enable_content_recording=True,
            reasoning_engine_id="re-001",
            extra_attributes={"key": "value"},
        )

        assert config.session_id == "session-123"
        assert config.agent_name == "my-agent"
        assert config.agent_id == "agent-001"
        assert config.agent_description == "Test agent"
        assert config.enable_content_recording is True
        assert config.reasoning_engine_id == "re-001"
        assert config.extra_attributes == {"key": "value"}


class TestInjectCloudTraceContext:
    """Tests for Cloud Trace context injection helper."""

    def test_inject_cloudtrace_context(self, sample_run: AgentRun) -> None:
        """inject_cloudtrace_context should add Cloud Trace headers to carrier."""
        from agenttrace.contrib.gcp import inject_cloudtrace_context

        carrier: dict[str, str] = {}
        inject_cloudtrace_context(carrier, sample_run)

        # Should have W3C traceparent
        assert "traceparent" in carrier
        # Should have Cloud Trace header
        assert "X-Cloud-Trace-Context" in carrier

    def test_inject_cloudtrace_context_with_session_id(self, sample_run: AgentRun) -> None:
        """inject_cloudtrace_context should add session header when provided."""
        from agenttrace.contrib.gcp import inject_cloudtrace_context

        carrier: dict[str, str] = {}
        inject_cloudtrace_context(carrier, sample_run, session_id="my-session")

        assert "X-Cloud-Trace-Session-Id" in carrier
        assert carrier["X-Cloud-Trace-Session-Id"] == "my-session"

    def test_inject_cloudtrace_context_uses_run_session(
        self, sample_run_with_session: AgentRun
    ) -> None:
        """inject_cloudtrace_context should use session_id from run if not provided."""
        from agenttrace.contrib.gcp import inject_cloudtrace_context

        carrier: dict[str, str] = {}
        inject_cloudtrace_context(carrier, sample_run_with_session)

        assert "X-Cloud-Trace-Session-Id" in carrier
        assert carrier["X-Cloud-Trace-Session-Id"] == "session-12345"

    def test_inject_cloudtrace_context_sampled_flag(self, sample_run: AgentRun) -> None:
        """inject_cloudtrace_context should respect sampled parameter."""
        from agenttrace.contrib.gcp import inject_cloudtrace_context

        # Test sampled=True
        carrier: dict[str, str] = {}
        inject_cloudtrace_context(carrier, sample_run, sampled=True)
        assert ";o=1" in carrier["X-Cloud-Trace-Context"]

        # Test sampled=False
        carrier = {}
        inject_cloudtrace_context(carrier, sample_run, sampled=False)
        assert ";o=0" in carrier["X-Cloud-Trace-Context"]

    def test_inject_cloudtrace_context_legacy_format(self, sample_run: AgentRun) -> None:
        """inject_cloudtrace_context should support legacy format only."""
        from agenttrace.contrib.gcp import inject_cloudtrace_context

        carrier: dict[str, str] = {}
        inject_cloudtrace_context(carrier, sample_run, use_legacy_format=True)

        assert "X-Cloud-Trace-Context" in carrier
        # With legacy_format=True, we still add Cloud Trace header
        assert "/" in carrier["X-Cloud-Trace-Context"]


class TestExtractCloudTraceContext:
    """Tests for Cloud Trace context extraction helper."""

    def test_extract_cloudtrace_context(self) -> None:
        """extract_cloudtrace_context should parse valid Cloud Trace header."""
        from agenttrace.contrib.gcp import extract_cloudtrace_context

        carrier = {"X-Cloud-Trace-Context": "105445aa7843bc8bf206b12000100000/123;o=1"}

        result = extract_cloudtrace_context(carrier)

        assert result is not None
        trace_id, span_id, sampled, session_id = result
        assert trace_id == "105445aa7843bc8bf206b12000100000"
        assert len(span_id) == 16
        assert sampled is True
        assert session_id is None

    def test_extract_cloudtrace_context_with_session(self) -> None:
        """extract_cloudtrace_context should extract session ID when present."""
        from agenttrace.contrib.gcp import extract_cloudtrace_context

        carrier = {
            "X-Cloud-Trace-Context": "105445aa7843bc8bf206b12000100000/123;o=1",
            "X-Cloud-Trace-Session-Id": "my-session",
        }

        result = extract_cloudtrace_context(carrier)

        assert result is not None
        _, _, _, session_id = result
        assert session_id == "my-session"

    def test_extract_cloudtrace_context_missing_header(self) -> None:
        """extract_cloudtrace_context should return None when header missing."""
        from agenttrace.contrib.gcp import extract_cloudtrace_context

        carrier: dict[str, str] = {}

        result = extract_cloudtrace_context(carrier)

        assert result is None

    def test_extract_cloudtrace_context_w3c_format(self) -> None:
        """extract_cloudtrace_context should also parse W3C format."""
        from agenttrace.contrib.gcp import extract_cloudtrace_context

        carrier = {"traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"}

        result = extract_cloudtrace_context(carrier)

        assert result is not None
        trace_id, span_id, sampled, _ = result
        assert trace_id == "0af7651916cd43dd8448eb211c80319c"
        assert span_id == "b7ad6b7169203331"
        assert sampled is True


class TestVertexAITracerAdapter:
    """Tests for VertexAITracerAdapter."""

    def test_adapter_init(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """VertexAITracerAdapter should initialize correctly."""
        from agenttrace.contrib.gcp import VertexAITracerAdapter

        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")

        adapter = VertexAITracerAdapter(
            enable_content_recording=True,
            agent_name="test-agent",
            agent_id="agent-001",
            reasoning_engine_id="re-001",
        )

        assert adapter.project_id == "test-project"
        assert adapter.enable_content_recording is True
        assert adapter.agent_name == "test-agent"
        assert adapter.agent_id == "agent-001"
        assert adapter.reasoning_engine_id == "re-001"

    def test_adapter_stores_config(self) -> None:
        """VertexAITracerAdapter should store VertexAgentConfig."""
        from agenttrace.contrib.gcp import VertexAgentConfig, VertexAITracerAdapter

        adapter = VertexAITracerAdapter(
            project_id="test-project",
            enable_content_recording=True,
            agent_name="test-agent",
        )

        assert isinstance(adapter._config, VertexAgentConfig)
        assert adapter._config.enable_content_recording is True
        assert adapter._config.agent_name == "test-agent"

    def test_adapter_lazy_handler_init(self) -> None:
        """VertexAITracerAdapter should lazily initialize handler."""
        from agenttrace.contrib.gcp import VertexAITracerAdapter

        adapter = VertexAITracerAdapter(project_id="test-project")

        # Handler should not be initialized yet
        assert adapter._handler is None

    def test_adapter_clear(self) -> None:
        """VertexAITracerAdapter clear should handle uninitialized handler."""
        from agenttrace.contrib.gcp import VertexAITracerAdapter

        adapter = VertexAITracerAdapter(project_id="test-project")

        # Should not raise even if handler not initialized
        adapter.clear()


class TestGCPVertexAgentConfigEnv:
    """Tests for GCP Vertex Agent configuration via environment."""

    def test_load_config_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """load_config_from_env should load GCP Vertex Agent config."""
        from agenttrace.core.config import load_config_from_env

        monkeypatch.setenv("AGENTTRACE_GCP_VERTEX_ENABLED", "true")
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
        monkeypatch.setenv("AGENTTRACE_GCP_SESSION_ID", "env-session")
        monkeypatch.setenv("AGENTTRACE_GCP_AGENT_NAME", "env-agent")
        monkeypatch.setenv("AGENTTRACE_GCP_AGENT_ID", "env-agent-id")
        monkeypatch.setenv("AGENTTRACE_GCP_CONTENT_RECORDING", "true")
        monkeypatch.setenv("AGENTTRACE_GCP_REASONING_ENGINE_ID", "re-001")

        config = load_config_from_env()

        assert config.gcp_vertex_agent.enabled is True
        assert config.gcp_vertex_agent.project_id == "test-project"
        assert config.gcp_vertex_agent.session_id == "env-session"
        assert config.gcp_vertex_agent.agent_name == "env-agent"
        assert config.gcp_vertex_agent.agent_id == "env-agent-id"
        assert config.gcp_vertex_agent.enable_content_recording is True
        assert config.gcp_vertex_agent.reasoning_engine_id == "re-001"

    def test_gcp_config_defaults(self) -> None:
        """GCP Vertex Agent config should have sensible defaults."""
        from agenttrace.core.config import GCPVertexAgentConfig

        config = GCPVertexAgentConfig()

        assert config.enabled is False
        assert config.project_id is None
        assert config.session_id is None
        assert config.agent_name is None
        assert config.agent_id is None
        assert config.enable_content_recording is False
        assert config.reasoning_engine_id is None


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
