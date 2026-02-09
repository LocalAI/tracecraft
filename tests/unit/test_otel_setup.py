"""Tests for the tracecraft.otel module."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from tracecraft.otel import (
    BackendConfig,
    flush_traces,
    get_available_instrumentors,
    get_service_name,
    get_tracer,
    parse_endpoint,
    setup_exporter,
    shutdown,
)
from tracecraft.otel.instrumentors import instrument_sdk, instrument_sdks


class TestParseEndpoint:
    """Tests for parse_endpoint function."""

    def test_default_endpoint(self) -> None:
        """Test default endpoint when none provided."""
        with patch.dict(os.environ, {}, clear=True):
            config = parse_endpoint(None)
            assert config.endpoint_url == "http://localhost:4318/v1/traces"
            assert config.backend_type == "generic"

    def test_http_endpoint(self) -> None:
        """Test parsing standard HTTP endpoint."""
        config = parse_endpoint("http://localhost:4318")
        assert config.scheme == "http"
        assert config.host == "localhost"
        assert config.port == 4318
        assert config.path == "/v1/traces"
        assert config.endpoint_url == "http://localhost:4318/v1/traces"
        assert config.backend_type == "generic"

    def test_https_endpoint(self) -> None:
        """Test parsing HTTPS endpoint."""
        config = parse_endpoint("https://otel.example.com:443/traces")
        assert config.scheme == "https"
        assert config.host == "otel.example.com"
        assert config.port == 443
        assert config.path == "/traces"
        assert config.endpoint_url == "https://otel.example.com:443/traces"

    def test_tracecraft_scheme(self) -> None:
        """Test tracecraft:// scheme converts to http://."""
        config = parse_endpoint("tracecraft://localhost:4318")
        assert config.scheme == "tracecraft"
        assert config.backend_type == "tracecraft"
        assert config.endpoint_url == "http://localhost:4318/v1/traces"

    def test_datadog_scheme(self) -> None:
        """Test datadog:// scheme converts to https://."""
        config = parse_endpoint("datadog://intake.datadoghq.com")
        assert config.scheme == "datadog"
        assert config.backend_type == "datadog"
        assert config.endpoint_url == "https://intake.datadoghq.com:4318/v1/traces"

    def test_azure_scheme(self) -> None:
        """Test azure:// scheme."""
        config = parse_endpoint("azure://appinsights.azure.com")
        assert config.scheme == "azure"
        assert config.backend_type == "azure"
        assert config.endpoint_url == "https://appinsights.azure.com:443/v1/traces"

    def test_env_var_tracecraft_endpoint(self) -> None:
        """Test TRACECRAFT_ENDPOINT environment variable."""
        with patch.dict(os.environ, {"TRACECRAFT_ENDPOINT": "http://custom:9999"}):
            config = parse_endpoint(None)
            assert config.host == "custom"
            assert config.port == 9999

    def test_env_var_otel_endpoint(self) -> None:
        """Test OTEL_EXPORTER_OTLP_ENDPOINT fallback."""
        with patch.dict(
            os.environ, {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://otel-collector:4318"}, clear=True
        ):
            config = parse_endpoint(None)
            assert config.host == "otel-collector"

    def test_tracecraft_env_takes_precedence(self) -> None:
        """Test TRACECRAFT_ENDPOINT takes precedence over OTEL_EXPORTER_OTLP_ENDPOINT."""
        with patch.dict(
            os.environ,
            {
                "TRACECRAFT_ENDPOINT": "http://tracecraft:4318",
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://otel:4318",
            },
        ):
            config = parse_endpoint(None)
            assert config.host == "tracecraft"


class TestGetServiceName:
    """Tests for get_service_name function."""

    def test_explicit_name(self) -> None:
        """Test explicit service name is used."""
        assert get_service_name("my-service") == "my-service"

    def test_default_name(self) -> None:
        """Test default service name."""
        with patch.dict(os.environ, {}, clear=True):
            assert get_service_name(None) == "tracecraft-agent"

    def test_tracecraft_env_var(self) -> None:
        """Test TRACECRAFT_SERVICE_NAME environment variable."""
        with patch.dict(os.environ, {"TRACECRAFT_SERVICE_NAME": "custom-agent"}):
            assert get_service_name(None) == "custom-agent"

    def test_otel_env_var(self) -> None:
        """Test OTEL_SERVICE_NAME fallback."""
        with patch.dict(os.environ, {"OTEL_SERVICE_NAME": "otel-service"}, clear=True):
            assert get_service_name(None) == "otel-service"


class TestInstrumentors:
    """Tests for instrumentation functions."""

    def test_get_available_instrumentors(self) -> None:
        """Test getting list of available instrumentors."""
        available = get_available_instrumentors()
        assert "openai" in available
        assert "anthropic" in available
        assert "langchain" in available
        assert isinstance(available, list)

    def test_instrument_unknown_sdk(self) -> None:
        """Test instrumenting unknown SDK raises ValueError."""
        with pytest.raises(ValueError, match="Unknown SDK"):
            instrument_sdk("nonexistent-sdk")

    def test_instrument_sdk_missing_package(self) -> None:
        """Test warning when instrumentation package not installed."""
        with patch("tracecraft.otel.instrumentors.importlib.import_module") as mock_import:
            mock_import.side_effect = ImportError("No module named 'opentelemetry.instrumentation'")
            with pytest.warns(UserWarning, match="Instrumentation not installed"):
                result = instrument_sdk("openai")
            assert result is False

    def test_instrument_sdks_partial_success(self) -> None:
        """Test instrumenting multiple SDKs with partial success."""
        with patch("tracecraft.otel.instrumentors.importlib.import_module") as mock_import:
            # First SDK succeeds, second fails
            mock_module = MagicMock()
            mock_instrumentor = MagicMock()
            mock_module.OpenAIInstrumentor.return_value = mock_instrumentor

            def side_effect(name: str) -> MagicMock:
                if "openai" in name:
                    return mock_module
                raise ImportError("Not found")

            mock_import.side_effect = side_effect

            with pytest.warns(UserWarning):
                result = instrument_sdks(["openai", "anthropic"])

            assert "openai" in result
            assert "anthropic" not in result


class TestSetupExporter:
    """Tests for setup_exporter function."""

    def test_setup_exporter_creates_tracer(self) -> None:
        """Test setup_exporter returns a valid tracer."""
        with patch("tracecraft.otel.setup.trace") as mock_trace:
            mock_provider = MagicMock()
            mock_tracer = MagicMock()
            mock_trace.get_tracer.return_value = mock_tracer

            tracer = setup_exporter(
                endpoint="http://localhost:4318",
                service_name="test-service",
            )

            assert tracer == mock_tracer
            mock_trace.set_tracer_provider.assert_called_once()

    def test_setup_exporter_with_batch_processor(self) -> None:
        """Test setup_exporter uses BatchSpanProcessor by default."""
        with (
            patch("tracecraft.otel.setup.trace"),
            patch("tracecraft.otel.setup.BatchSpanProcessor") as mock_batch,
            patch("tracecraft.otel.setup.TracerProvider") as mock_provider,
        ):
            setup_exporter(endpoint="http://localhost:4318", batch_export=True)
            mock_batch.assert_called_once()

    def test_setup_exporter_with_simple_processor(self) -> None:
        """Test setup_exporter can use SimpleSpanProcessor."""
        with (
            patch("tracecraft.otel.setup.trace"),
            patch("tracecraft.otel.setup.SimpleSpanProcessor") as mock_simple,
            patch("tracecraft.otel.setup.TracerProvider"),
        ):
            setup_exporter(endpoint="http://localhost:4318", batch_export=False)
            mock_simple.assert_called_once()

    def test_setup_exporter_with_resource_attributes(self) -> None:
        """Test custom resource attributes are applied."""
        with (
            patch("tracecraft.otel.setup.trace"),
            patch("tracecraft.otel.setup.Resource") as mock_resource,
            patch("tracecraft.otel.setup.TracerProvider"),
        ):
            setup_exporter(
                endpoint="http://localhost:4318",
                service_name="test",
                resource_attributes={"deployment.environment": "test"},
            )

            # Check that Resource.create was called with the right attributes
            call_args = mock_resource.create.call_args[0][0]
            assert call_args["deployment.environment"] == "test"
            assert call_args["service.name"] == "test"

    def test_setup_exporter_with_instrumentation(self) -> None:
        """Test auto-instrumentation is triggered."""
        with (
            patch("tracecraft.otel.setup.trace"),
            patch("tracecraft.otel.setup.TracerProvider"),
            patch("tracecraft.otel.setup.instrument_sdks") as mock_instrument,
        ):
            mock_instrument.return_value = ["openai"]

            setup_exporter(endpoint="http://localhost:4318", instrument=["openai"])

            mock_instrument.assert_called_once_with(["openai"])


class TestTracerUtilities:
    """Tests for tracer utility functions."""

    def test_get_tracer(self) -> None:
        """Test get_tracer returns tracer from provider."""
        with patch("tracecraft.otel.setup.trace") as mock_trace:
            mock_tracer = MagicMock()
            mock_trace.get_tracer.return_value = mock_tracer

            tracer = get_tracer("my-tracer")

            assert tracer == mock_tracer
            mock_trace.get_tracer.assert_called_with("my-tracer")

    def test_flush_traces(self) -> None:
        """Test flush_traces calls force_flush on provider."""
        with patch("tracecraft.otel.setup.trace") as mock_trace:
            mock_provider = MagicMock()
            mock_provider.force_flush.return_value = True
            mock_trace.get_tracer_provider.return_value = mock_provider

            result = flush_traces(timeout_millis=5000)

            assert result is True
            mock_provider.force_flush.assert_called_once_with(5000)

    def test_shutdown(self) -> None:
        """Test shutdown calls provider shutdown."""
        with patch("tracecraft.otel.setup.trace") as mock_trace:
            mock_provider = MagicMock()
            mock_trace.get_tracer_provider.return_value = mock_provider

            shutdown()

            mock_provider.shutdown.assert_called_once()


class TestBackendConfig:
    """Tests for BackendConfig dataclass."""

    def test_backend_config_attributes(self) -> None:
        """Test BackendConfig has all expected attributes."""
        config = BackendConfig(
            scheme="http",
            host="localhost",
            port=4318,
            path="/v1/traces",
            endpoint_url="http://localhost:4318/v1/traces",
            backend_type="generic",
        )
        assert config.scheme == "http"
        assert config.host == "localhost"
        assert config.port == 4318
        assert config.path == "/v1/traces"
        assert config.endpoint_url == "http://localhost:4318/v1/traces"
        assert config.backend_type == "generic"
