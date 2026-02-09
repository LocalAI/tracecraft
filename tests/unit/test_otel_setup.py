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
from tracecraft.otel.instrumentors import instrument_sdk, instrument_sdks, uninstrument_sdk


class TestParseEndpoint:
    """Tests for parse_endpoint function."""

    def test_default_endpoint(self) -> None:
        """Test default endpoint when none provided."""
        with patch.dict(os.environ, {}, clear=True):
            config = parse_endpoint(None)
            assert config.endpoint_url == "http://localhost:4318/v1/traces"
            assert config.backend_type == "generic"

    def test_empty_endpoint_raises_error(self) -> None:
        """Test empty endpoint raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_endpoint("")

    def test_whitespace_endpoint_raises_error(self) -> None:
        """Test whitespace-only endpoint raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_endpoint("   ")

    def test_missing_scheme_raises_error(self) -> None:
        """Test URL without valid scheme raises ValueError."""
        with pytest.raises(ValueError, match="Must include valid scheme"):
            parse_endpoint("localhost:4318")

    def test_invalid_scheme_raises_error(self) -> None:
        """Test URL with invalid scheme raises ValueError."""
        with pytest.raises(ValueError, match="Must include valid scheme"):
            parse_endpoint("ftp://localhost:4318")

    def test_missing_hostname_raises_error(self) -> None:
        """Test URL without hostname raises ValueError."""
        with pytest.raises(ValueError, match="Must include hostname"):
            parse_endpoint("http://")

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

    def test_aws_scheme(self) -> None:
        """Test aws:// scheme."""
        config = parse_endpoint("aws://xray.us-east-1.amazonaws.com")
        assert config.scheme == "aws"
        assert config.backend_type == "aws"
        assert config.endpoint_url == "https://xray.us-east-1.amazonaws.com:443/v1/traces"

    def test_xray_scheme(self) -> None:
        """Test xray:// scheme alias for AWS."""
        config = parse_endpoint("xray://xray.us-west-2.amazonaws.com")
        assert config.scheme == "xray"
        assert config.backend_type == "aws"
        assert config.endpoint_url == "https://xray.us-west-2.amazonaws.com:443/v1/traces"

    def test_custom_path_preserved(self) -> None:
        """Test custom path in URL is preserved."""
        config = parse_endpoint("http://localhost:4318/custom/traces/endpoint")
        assert config.path == "/custom/traces/endpoint"
        assert config.endpoint_url == "http://localhost:4318/custom/traces/endpoint"

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

    def test_uninstrument_sdk_success(self) -> None:
        """Test uninstrumenting an SDK."""
        with patch("tracecraft.otel.instrumentors.importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_instrumentor = MagicMock()
            mock_module.OpenAIInstrumentor.return_value = mock_instrumentor
            mock_import.return_value = mock_module

            result = uninstrument_sdk("openai")

            assert result is True
            mock_instrumentor.uninstrument.assert_called_once()

    def test_uninstrument_unknown_sdk(self) -> None:
        """Test uninstrumenting unknown SDK returns False."""
        result = uninstrument_sdk("nonexistent-sdk")
        assert result is False

    def test_uninstrument_sdk_import_error(self) -> None:
        """Test uninstrument returns False on ImportError."""
        with patch("tracecraft.otel.instrumentors.importlib.import_module") as mock_import:
            mock_import.side_effect = ImportError("Not found")
            result = uninstrument_sdk("openai")
            assert result is False

    def test_instrument_sdk_already_instrumented(self) -> None:
        """Test instrumenting SDK that is already instrumented."""
        with patch("tracecraft.otel.instrumentors.importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_instrumentor = MagicMock()
            mock_instrumentor.is_instrumented_by_opentelemetry = True
            mock_module.OpenAIInstrumentor.return_value = mock_instrumentor
            mock_import.return_value = mock_module

            result = instrument_sdk("openai")

            assert result is True
            mock_instrumentor.instrument.assert_not_called()

    def test_instrument_sdk_attribute_error(self) -> None:
        """Test warning when SDK has attribute error during instrumentation."""
        with patch("tracecraft.otel.instrumentors.importlib.import_module") as mock_import:
            mock_import.side_effect = AttributeError("No such class")
            with pytest.warns(UserWarning, match="Failed to instrument"):
                result = instrument_sdk("openai")
            assert result is False

    def test_instrument_sdk_runtime_error(self) -> None:
        """Test warning when SDK raises RuntimeError during instrumentation."""
        with patch("tracecraft.otel.instrumentors.importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_instrumentor = MagicMock()
            # Ensure is_instrumented_by_opentelemetry returns False so we proceed to instrument()
            mock_instrumentor.is_instrumented_by_opentelemetry = False
            mock_instrumentor.instrument.side_effect = RuntimeError("Already instrumented")
            mock_module.OpenAIInstrumentor.return_value = mock_instrumentor
            mock_import.return_value = mock_module

            with pytest.warns(UserWarning, match="Failed to instrument"):
                result = instrument_sdk("openai")
            assert result is False

    def test_instrument_sdks_with_unknown_sdk(self) -> None:
        """Test instrument_sdks warns for unknown SDK."""
        with pytest.warns(UserWarning, match="Unknown SDK"):
            result = instrument_sdks(["nonexistent-sdk"])
        assert result == []

    def test_instrument_sdk_callable_is_instrumented(self) -> None:
        """Test handling is_instrumented_by_opentelemetry as callable method."""
        with patch("tracecraft.otel.instrumentors.importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_instrumentor = MagicMock()
            # Make is_instrumented_by_opentelemetry a callable that returns True
            mock_instrumentor.is_instrumented_by_opentelemetry = MagicMock(return_value=True)
            mock_module.OpenAIInstrumentor.return_value = mock_instrumentor
            mock_import.return_value = mock_module

            result = instrument_sdk("openai")

            assert result is True
            mock_instrumentor.instrument.assert_not_called()

    def test_instrument_sdk_success_path(self) -> None:
        """Test successful instrumentation when not already instrumented."""
        with patch("tracecraft.otel.instrumentors.importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_instrumentor = MagicMock()
            # No is_instrumented_by_opentelemetry attribute
            del mock_instrumentor.is_instrumented_by_opentelemetry
            mock_module.OpenAIInstrumentor.return_value = mock_instrumentor
            mock_import.return_value = mock_module

            result = instrument_sdk("openai")

            assert result is True
            mock_instrumentor.instrument.assert_called_once()


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

    def test_setup_exporter_with_tracecraft_backend(self) -> None:
        """Test setup_exporter adds backend attribute for non-generic backends."""
        with (
            patch("tracecraft.otel.setup.trace"),
            patch("tracecraft.otel.setup.Resource") as mock_resource,
            patch("tracecraft.otel.setup.TracerProvider"),
        ):
            setup_exporter(endpoint="tracecraft://localhost:4318", service_name="test")

            # Check that Resource.create was called with backend attribute
            call_args = mock_resource.create.call_args[0][0]
            assert call_args["tracecraft.backend"] == "tracecraft"

    def test_setup_exporter_with_custom_tracer_name(self) -> None:
        """Test setup_exporter uses custom tracer name."""
        with (
            patch("tracecraft.otel.setup.trace") as mock_trace,
            patch("tracecraft.otel.setup.TracerProvider"),
        ):
            setup_exporter(endpoint="http://localhost:4318", tracer_name="custom-tracer")

            mock_trace.get_tracer.assert_called_with("custom-tracer")

    def test_setup_exporter_with_service_version(self) -> None:
        """Test setup_exporter uses custom service version."""
        with (
            patch("tracecraft.otel.setup.trace"),
            patch("tracecraft.otel.setup.Resource") as mock_resource,
            patch("tracecraft.otel.setup.TracerProvider"),
        ):
            setup_exporter(
                endpoint="http://localhost:4318",
                service_name="test",
                service_version="2.0.0",
            )

            call_args = mock_resource.create.call_args[0][0]
            assert call_args["service.version"] == "2.0.0"

    def test_setup_exporter_empty_instrument_list(self) -> None:
        """Test setup_exporter handles empty instrument list."""
        with (
            patch("tracecraft.otel.setup.trace"),
            patch("tracecraft.otel.setup.TracerProvider"),
            patch("tracecraft.otel.setup.instrument_sdks") as mock_instrument,
        ):
            # Empty list should not call instrument_sdks
            setup_exporter(endpoint="http://localhost:4318", instrument=[])

            mock_instrument.assert_not_called()


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

    def test_flush_traces_no_force_flush(self) -> None:
        """Test flush_traces returns True when provider has no force_flush."""
        with patch("tracecraft.otel.setup.trace") as mock_trace:
            mock_provider = MagicMock(spec=[])  # No force_flush attribute
            mock_trace.get_tracer_provider.return_value = mock_provider

            result = flush_traces()

            assert result is True

    def test_shutdown_no_shutdown_method(self) -> None:
        """Test shutdown handles provider without shutdown method."""
        with patch("tracecraft.otel.setup.trace") as mock_trace:
            mock_provider = MagicMock(spec=[])  # No shutdown attribute
            mock_trace.get_tracer_provider.return_value = mock_provider

            # Should not raise
            shutdown()


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
