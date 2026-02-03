"""
Tests for Azure AI Foundry integration.

Tests Foundry exporter, content recording, and LangChain adapter.
"""

from __future__ import annotations

import pytest


class TestFoundryExporter:
    """Tests for Azure AI Foundry exporter configuration."""

    def test_create_foundry_exporter(self) -> None:
        """create_foundry_exporter should return configured exporter."""
        from tracecraft.contrib.azure import create_foundry_exporter

        connection_string = (
            "InstrumentationKey=test-key;"
            "IngestionEndpoint=https://test.applicationinsights.azure.com/"
        )

        exporter = create_foundry_exporter(
            connection_string=connection_string,
            service_name="test-agent",
        )

        assert exporter is not None
        assert exporter.service_name == "test-agent"

    def test_create_foundry_exporter_stores_config(self) -> None:
        """create_foundry_exporter should store FoundryConfig on exporter."""
        from tracecraft.contrib.azure import FoundryConfig, create_foundry_exporter

        connection_string = (
            "InstrumentationKey=test-key;"
            "IngestionEndpoint=https://test.applicationinsights.azure.com/"
        )

        exporter = create_foundry_exporter(
            connection_string=connection_string,
            enable_content_recording=True,
            agent_name="research-agent",
            agent_id="agent-001",
            agent_description="An agent that researches topics",
        )

        config = getattr(exporter, "_foundry_config", None)
        assert config is not None
        assert isinstance(config, FoundryConfig)
        assert config.enable_content_recording is True
        assert config.agent_name == "research-agent"
        assert config.agent_id == "agent-001"
        assert config.agent_description == "An agent that researches topics"

    def test_create_foundry_exporter_content_recording_default(self) -> None:
        """create_foundry_exporter should have content recording disabled by default."""
        from tracecraft.contrib.azure import create_foundry_exporter

        connection_string = (
            "InstrumentationKey=test-key;"
            "IngestionEndpoint=https://test.applicationinsights.azure.com/"
        )

        exporter = create_foundry_exporter(connection_string=connection_string)

        config = getattr(exporter, "_foundry_config", None)
        assert config is not None
        assert config.enable_content_recording is False


class TestConfigureForAIFoundry:
    """Tests for configure_for_ai_foundry."""

    def test_configure_for_ai_foundry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """configure_for_ai_foundry should use environment variables."""
        from tracecraft.contrib.azure import configure_for_ai_foundry

        connection_string = (
            "InstrumentationKey=test-key;"
            "IngestionEndpoint=https://test.applicationinsights.azure.com/"
        )
        monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", connection_string)
        monkeypatch.setenv("TRACECRAFT_AZURE_CONTENT_RECORDING", "true")
        monkeypatch.setenv("TRACECRAFT_AZURE_AGENT_NAME", "env-agent")
        monkeypatch.setenv("TRACECRAFT_AZURE_AGENT_ID", "env-agent-id")

        exporter = configure_for_ai_foundry(service_name="my-agent")

        config = getattr(exporter, "_foundry_config", None)
        assert config is not None
        assert config.enable_content_recording is True
        assert config.agent_name == "env-agent"
        assert config.agent_id == "env-agent-id"

    def test_configure_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """configure_for_ai_foundry should allow overriding env values."""
        from tracecraft.contrib.azure import configure_for_ai_foundry

        connection_string = (
            "InstrumentationKey=test-key;"
            "IngestionEndpoint=https://test.applicationinsights.azure.com/"
        )
        monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", connection_string)
        monkeypatch.setenv("TRACECRAFT_AZURE_CONTENT_RECORDING", "false")
        monkeypatch.setenv("TRACECRAFT_AZURE_AGENT_NAME", "env-agent")

        exporter = configure_for_ai_foundry(
            enable_content_recording=True,
            agent_name="override-agent",
        )

        config = getattr(exporter, "_foundry_config", None)
        assert config is not None
        assert config.enable_content_recording is True
        assert config.agent_name == "override-agent"


class TestFoundryConfig:
    """Tests for FoundryConfig dataclass."""

    def test_foundry_config_defaults(self) -> None:
        """FoundryConfig should have sensible defaults."""
        from tracecraft.contrib.azure import FoundryConfig

        config = FoundryConfig()

        assert config.enable_content_recording is False
        assert config.agent_name is None
        assert config.agent_id is None
        assert config.agent_description is None
        assert config.extra_attributes == {}

    def test_foundry_config_with_values(self) -> None:
        """FoundryConfig should accept custom values."""
        from tracecraft.contrib.azure import FoundryConfig

        config = FoundryConfig(
            enable_content_recording=True,
            agent_name="my-agent",
            agent_id="agent-001",
            agent_description="Test agent",
            extra_attributes={"key": "value"},
        )

        assert config.enable_content_recording is True
        assert config.agent_name == "my-agent"
        assert config.agent_id == "agent-001"
        assert config.agent_description == "Test agent"
        assert config.extra_attributes == {"key": "value"}


class TestAzureAITracerAdapter:
    """Tests for AzureAITracerAdapter."""

    def test_adapter_init(self) -> None:
        """AzureAITracerAdapter should initialize correctly."""
        from tracecraft.contrib.azure import AzureAITracerAdapter

        adapter = AzureAITracerAdapter(
            enable_content_recording=True,
            agent_name="test-agent",
            agent_id="agent-001",
        )

        assert adapter.enable_content_recording is True
        assert adapter.agent_name == "test-agent"
        assert adapter.agent_id == "agent-001"

    def test_adapter_stores_config(self) -> None:
        """AzureAITracerAdapter should store FoundryConfig."""
        from tracecraft.contrib.azure import AzureAITracerAdapter, FoundryConfig

        adapter = AzureAITracerAdapter(
            enable_content_recording=True,
            agent_name="test-agent",
        )

        assert isinstance(adapter._config, FoundryConfig)
        assert adapter._config.enable_content_recording is True
        assert adapter._config.agent_name == "test-agent"

    def test_adapter_lazy_handler_init(self) -> None:
        """AzureAITracerAdapter should lazily initialize handler."""
        from tracecraft.contrib.azure import AzureAITracerAdapter

        adapter = AzureAITracerAdapter()

        # Handler should not be initialized yet
        assert adapter._handler is None

    def test_adapter_clear(self) -> None:
        """AzureAITracerAdapter clear should handle uninitialized handler."""
        from tracecraft.contrib.azure import AzureAITracerAdapter

        adapter = AzureAITracerAdapter()

        # Should not raise even if handler not initialized
        adapter.clear()


class TestAzureFoundryConfigEnv:
    """Tests for Azure Foundry configuration via environment."""

    def test_load_config_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """load_config_from_env should load Azure Foundry config."""
        from tracecraft.core.config import load_config_from_env

        connection_string = (
            "InstrumentationKey=test-key;"
            "IngestionEndpoint=https://test.applicationinsights.azure.com/"
        )
        monkeypatch.setenv("TRACECRAFT_AZURE_FOUNDRY_ENABLED", "true")
        monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", connection_string)
        monkeypatch.setenv("TRACECRAFT_AZURE_CONTENT_RECORDING", "true")
        monkeypatch.setenv("TRACECRAFT_AZURE_AGENT_NAME", "env-agent")
        monkeypatch.setenv("TRACECRAFT_AZURE_AGENT_ID", "env-agent-id")

        config = load_config_from_env()

        assert config.azure_foundry.enabled is True
        assert config.azure_foundry.connection_string == connection_string
        assert config.azure_foundry.enable_content_recording is True
        assert config.azure_foundry.agent_name == "env-agent"
        assert config.azure_foundry.agent_id == "env-agent-id"

    def test_azure_config_defaults(self) -> None:
        """Azure Foundry config should have sensible defaults."""
        from tracecraft.core.config import AzureFoundryConfig

        config = AzureFoundryConfig()

        assert config.enabled is False
        assert config.connection_string is None
        assert config.enable_content_recording is False
        assert config.agent_name is None
        assert config.agent_id is None
        assert config.agent_description is None


class TestAppInsightsConnectionString:
    """Tests for Azure connection string parsing."""

    def test_parse_connection_string(self) -> None:
        """parse_connection_string should extract components."""
        from tracecraft.contrib.azure import parse_connection_string

        connection_string = (
            "InstrumentationKey=abc123;"
            "IngestionEndpoint=https://test.in.applicationinsights.azure.com/;"
            "LiveEndpoint=https://test.livediagnostics.monitor.azure.com/"
        )

        parts = parse_connection_string(connection_string)

        assert parts["InstrumentationKey"] == "abc123"
        assert parts["IngestionEndpoint"] == "https://test.in.applicationinsights.azure.com/"
        assert parts["LiveEndpoint"] == "https://test.livediagnostics.monitor.azure.com/"

    def test_create_appinsights_exporter_missing_connection(self) -> None:
        """create_appinsights_exporter should raise if no connection string."""
        from tracecraft.contrib.azure import create_appinsights_exporter

        with pytest.raises(ValueError, match="connection string required"):
            create_appinsights_exporter()

    def test_create_appinsights_exporter_missing_endpoint(self) -> None:
        """create_appinsights_exporter should raise if missing IngestionEndpoint."""
        from tracecraft.contrib.azure import create_appinsights_exporter

        with pytest.raises(ValueError, match="missing IngestionEndpoint"):
            create_appinsights_exporter(connection_string="InstrumentationKey=test")

    def test_create_appinsights_exporter_missing_key(self) -> None:
        """create_appinsights_exporter should raise if missing InstrumentationKey."""
        from tracecraft.contrib.azure import create_appinsights_exporter

        with pytest.raises(ValueError, match="missing InstrumentationKey"):
            create_appinsights_exporter(
                connection_string="IngestionEndpoint=https://test.azure.com/"
            )
