"""
Tests for the configuration system.

Tests environment variable loading and configuration dataclasses.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from agenttrace.core.config import (
    AgentTraceConfig,
    ExporterConfig,
    RedactionConfig,
    SamplingConfig,
    load_config,
    load_config_from_env,
)
from agenttrace.processors.redaction import RedactionMode


class TestAgentTraceConfig:
    """Tests for AgentTraceConfig dataclass."""

    def test_config_default_values(self) -> None:
        """Should have sensible defaults."""
        config = AgentTraceConfig()
        assert config.console_enabled is True
        assert config.jsonl_enabled is True
        assert config.service_name == "agenttrace"

    def test_config_custom_values(self) -> None:
        """Should accept custom values."""
        config = AgentTraceConfig(
            service_name="my-service",
            console_enabled=False,
            jsonl_enabled=True,
            jsonl_path="/tmp/traces.jsonl",
        )
        assert config.service_name == "my-service"
        assert config.console_enabled is False
        assert config.jsonl_path == "/tmp/traces.jsonl"

    def test_config_immutable_defaults(self) -> None:
        """Default instances should not share mutable state."""
        config1 = AgentTraceConfig()
        config2 = AgentTraceConfig()
        config1.tags.append("test")
        assert "test" not in config2.tags

    def test_config_with_nested_configs(self) -> None:
        """Should support nested configuration objects."""
        config = AgentTraceConfig(
            redaction=RedactionConfig(enabled=True),
            sampling=SamplingConfig(rate=0.5),
        )
        assert config.redaction.enabled is True
        assert config.sampling.rate == 0.5


class TestRedactionConfig:
    """Tests for RedactionConfig."""

    def test_redaction_config_defaults(self) -> None:
        """Should have sensible defaults (privacy-first: enabled by default)."""
        config = RedactionConfig()
        assert config.enabled is True  # Privacy-first: enabled by default
        assert config.mode == RedactionMode.MASK

    def test_redaction_config_custom_patterns(self) -> None:
        """Should accept custom patterns."""
        config = RedactionConfig(
            enabled=True,
            custom_patterns=[r"SECRET-\d+"],
        )
        assert config.enabled is True
        assert r"SECRET-\d+" in config.custom_patterns

    def test_redaction_config_allowlist(self) -> None:
        """Should support allowlist configuration."""
        config = RedactionConfig(
            allowlist=["safe@email.com"],
            allowlist_patterns=[r".*@company\.com"],
        )
        assert "safe@email.com" in config.allowlist
        assert r".*@company\.com" in config.allowlist_patterns

    def test_redaction_config_mode(self) -> None:
        """Should support different redaction modes."""
        config = RedactionConfig(mode=RedactionMode.HASH)
        assert config.mode == RedactionMode.HASH


class TestSamplingConfig:
    """Tests for SamplingConfig."""

    def test_sampling_config_defaults(self) -> None:
        """Should have sensible defaults."""
        config = SamplingConfig()
        assert config.rate == 1.0
        assert config.always_keep_errors is True
        assert config.always_keep_slow is False

    def test_sampling_config_custom_rate(self) -> None:
        """Should accept custom sampling rate."""
        config = SamplingConfig(rate=0.1)
        assert config.rate == 0.1

    def test_sampling_config_slow_threshold(self) -> None:
        """Should support slow trace threshold."""
        config = SamplingConfig(
            always_keep_slow=True,
            slow_threshold_ms=3000.0,
        )
        assert config.always_keep_slow is True
        assert config.slow_threshold_ms == 3000.0

    def test_sampling_rate_validation(self) -> None:
        """Rate should be between 0 and 1."""
        # This should work
        config = SamplingConfig(rate=0.0)
        assert config.rate == 0.0

        config = SamplingConfig(rate=1.0)
        assert config.rate == 1.0


class TestExporterConfig:
    """Tests for ExporterConfig."""

    def test_exporter_config_defaults(self) -> None:
        """Should have sensible defaults."""
        config = ExporterConfig()
        assert config.console_enabled is True
        assert config.jsonl_enabled is True
        assert config.otlp_enabled is False

    def test_exporter_config_otlp(self) -> None:
        """Should support OTLP configuration."""
        config = ExporterConfig(
            otlp_enabled=True,
            otlp_endpoint="http://localhost:4317",
        )
        assert config.otlp_enabled is True
        assert config.otlp_endpoint == "http://localhost:4317"


class TestLoadConfigFromEnv:
    """Tests for loading config from environment variables."""

    def test_env_var_service_name(self) -> None:
        """Should load service name from env var."""
        with patch.dict(os.environ, {"AGENTTRACE_SERVICE_NAME": "test-service"}):
            config = load_config_from_env()
            assert config.service_name == "test-service"

    def test_env_var_console_enabled(self) -> None:
        """Should load console enabled from env var."""
        with patch.dict(os.environ, {"AGENTTRACE_CONSOLE_ENABLED": "false"}):
            config = load_config_from_env()
            assert config.console_enabled is False

    def test_env_var_console_enabled_true(self) -> None:
        """Should parse true values correctly."""
        with patch.dict(os.environ, {"AGENTTRACE_CONSOLE_ENABLED": "true"}):
            config = load_config_from_env()
            assert config.console_enabled is True

    def test_env_var_jsonl_path(self) -> None:
        """Should load JSONL path from env var."""
        with patch.dict(os.environ, {"AGENTTRACE_JSONL_PATH": "/custom/path.jsonl"}):
            config = load_config_from_env()
            assert config.jsonl_path == "/custom/path.jsonl"

    def test_env_var_sampling_rate(self) -> None:
        """Should load sampling rate from env var."""
        with patch.dict(os.environ, {"AGENTTRACE_SAMPLING_RATE": "0.5"}):
            config = load_config_from_env()
            assert config.sampling.rate == 0.5

    def test_env_var_otlp_endpoint(self) -> None:
        """Should load OTLP endpoint from env var."""
        with patch.dict(
            os.environ,
            {
                "AGENTTRACE_OTLP_ENABLED": "true",
                "AGENTTRACE_OTLP_ENDPOINT": "http://collector:4317",
            },
        ):
            config = load_config_from_env()
            assert config.exporter.otlp_enabled is True
            assert config.exporter.otlp_endpoint == "http://collector:4317"

    def test_env_var_redaction_enabled(self) -> None:
        """Should load redaction enabled from env var."""
        # Redaction is enabled by default, verify explicit true still works
        with patch.dict(os.environ, {"AGENTTRACE_REDACTION_ENABLED": "true"}):
            config = load_config_from_env()
            assert config.redaction.enabled is True

    def test_env_var_redaction_disabled(self) -> None:
        """Should be able to explicitly disable redaction via env var."""
        with patch.dict(os.environ, {"AGENTTRACE_REDACTION_ENABLED": "false"}):
            config = load_config_from_env()
            assert config.redaction.enabled is False

    def test_env_var_redaction_default_is_enabled(self) -> None:
        """Redaction should be enabled by default (privacy-first)."""
        with patch.dict(os.environ, {}, clear=True):
            env = {k: v for k, v in os.environ.items() if not k.startswith("AGENTTRACE_")}
            with patch.dict(os.environ, env, clear=True):
                config = load_config_from_env()
                assert config.redaction.enabled is True  # Privacy-first default

    def test_env_var_defaults_when_not_set(self) -> None:
        """Should use defaults when env vars not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Clear any AGENTTRACE_ vars
            env = {k: v for k, v in os.environ.items() if not k.startswith("AGENTTRACE_")}
            with patch.dict(os.environ, env, clear=True):
                config = load_config_from_env()
                assert config.service_name == "agenttrace"
                assert config.console_enabled is True


class TestLoadConfig:
    """Tests for the load_config function."""

    def test_load_config_returns_config(self) -> None:
        """Should return a valid config object."""
        config = load_config()
        assert isinstance(config, AgentTraceConfig)

    def test_load_config_merges_env_and_kwargs(self) -> None:
        """Should merge env vars and keyword arguments."""
        with patch.dict(os.environ, {"AGENTTRACE_SERVICE_NAME": "env-service"}):
            # Kwargs should override env vars
            config = load_config(service_name="kwarg-service")
            assert config.service_name == "kwarg-service"

    def test_load_config_env_fallback(self) -> None:
        """Should fall back to env vars when kwargs not provided."""
        with patch.dict(os.environ, {"AGENTTRACE_SERVICE_NAME": "env-service"}):
            config = load_config()
            assert config.service_name == "env-service"


class TestConfigEdgeCases:
    """Tests for edge cases in configuration."""

    def test_config_with_empty_tags(self) -> None:
        """Should handle empty tags list."""
        config = AgentTraceConfig(tags=[])
        assert config.tags == []

    def test_config_with_tags(self) -> None:
        """Should accept tags list."""
        config = AgentTraceConfig(tags=["prod", "v1"])
        assert config.tags == ["prod", "v1"]

    def test_config_with_path_object(self) -> None:
        """Should accept Path objects for file paths."""
        config = AgentTraceConfig(jsonl_path=Path("/tmp/traces.jsonl"))
        assert config.jsonl_path == Path("/tmp/traces.jsonl")

    def test_env_var_boolean_variations(self) -> None:
        """Should handle various boolean string formats."""
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("0", False),
            ("no", False),
        ]
        for value, expected in test_cases:
            with patch.dict(os.environ, {"AGENTTRACE_CONSOLE_ENABLED": value}):
                config = load_config_from_env()
                assert config.console_enabled is expected, f"Failed for {value}"
