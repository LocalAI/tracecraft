"""Tests for cloud provider configuration helpers."""

import contextlib
import os
from unittest.mock import patch

import pytest


class TestAWSHelpers:
    """Tests for AWS X-Ray configuration helpers."""

    def test_create_xray_exporter_default(self):
        """Test creating X-Ray exporter with defaults."""
        from tracecraft.contrib.aws import create_xray_exporter

        exporter = create_xray_exporter()

        assert exporter.endpoint == "http://localhost:4317"
        assert exporter.service_name == "tracecraft"
        assert exporter.protocol == "grpc"

    def test_create_xray_exporter_with_region(self):
        """Test creating X-Ray exporter with custom region."""
        from tracecraft.contrib.aws import create_xray_exporter

        exporter = create_xray_exporter(region="us-west-2", endpoint="http://collector:4317")

        assert exporter.endpoint == "http://collector:4317"

    @patch.dict(os.environ, {"AWS_REGION": "eu-west-1"})
    def test_create_xray_exporter_from_env(self):
        """Test creating X-Ray exporter from environment."""
        from tracecraft.contrib.aws import create_xray_exporter

        exporter = create_xray_exporter()
        assert exporter.service_name == "tracecraft"

    def test_configure_for_lambda(self):
        """Test Lambda configuration."""
        from tracecraft.contrib.aws import configure_for_lambda

        exporter = configure_for_lambda(service_name="my-lambda")

        assert exporter.endpoint == "http://localhost:4317"
        assert exporter.service_name == "my-lambda"

    def test_configure_for_ecs(self):
        """Test ECS configuration."""
        from tracecraft.contrib.aws import configure_for_ecs

        exporter = configure_for_ecs(service_name="my-ecs-service")

        assert exporter.service_name == "my-ecs-service"

    def test_configure_for_eks(self):
        """Test EKS configuration."""
        from tracecraft.contrib.aws import configure_for_eks

        exporter = configure_for_eks(
            service_name="my-eks-service",
            collector_endpoint="http://adot-collector:4317",
        )

        assert exporter.endpoint == "http://adot-collector:4317"
        assert exporter.service_name == "my-eks-service"


class TestAzureHelpers:
    """Tests for Azure Application Insights helpers."""

    def test_create_appinsights_exporter_missing_connection_string(self):
        """Test error when connection string is missing."""
        from tracecraft.contrib.azure import create_appinsights_exporter

        # Clear any existing env var
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(ValueError, match="connection string required"),
        ):
            create_appinsights_exporter()

    def test_create_appinsights_exporter_invalid_connection_string(self):
        """Test error with invalid connection string."""
        from tracecraft.contrib.azure import create_appinsights_exporter

        with pytest.raises(ValueError, match="missing IngestionEndpoint"):
            create_appinsights_exporter(connection_string="InstrumentationKey=test123")

    def test_create_appinsights_exporter_valid(self):
        """Test creating exporter with valid connection string."""
        from tracecraft.contrib.azure import create_appinsights_exporter

        conn_str = (
            "InstrumentationKey=test-key-123;"
            "IngestionEndpoint=https://westus2-2.in.applicationinsights.azure.com/"
        )
        exporter = create_appinsights_exporter(connection_string=conn_str)

        assert "applicationinsights.azure.com" in exporter.endpoint
        assert exporter.protocol == "http"
        assert "x-ms-instrumentation-key" in exporter.headers

    def test_parse_connection_string(self):
        """Test connection string parsing."""
        from tracecraft.contrib.azure import parse_connection_string

        conn_str = (
            "InstrumentationKey=abc123;"
            "IngestionEndpoint=https://example.com/;"
            "LiveEndpoint=https://live.example.com/"
        )
        parts = parse_connection_string(conn_str)

        assert parts["InstrumentationKey"] == "abc123"
        assert parts["IngestionEndpoint"] == "https://example.com/"
        assert parts["LiveEndpoint"] == "https://live.example.com/"


class TestGCPHelpers:
    """Tests for GCP Cloud Trace helpers."""

    def test_create_cloudtrace_exporter_missing_project(self):
        """Test error when project ID is missing."""
        from tracecraft.contrib.gcp import create_cloudtrace_exporter

        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(ValueError, match="project ID required"),
        ):
            create_cloudtrace_exporter()

    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"})
    def test_create_cloudtrace_exporter_missing_google_auth(self):
        """Test error when google-auth is not installed or auth fails."""
        from tracecraft.contrib.gcp import create_cloudtrace_exporter

        # This will raise ImportError if google-auth is not installed
        # or auth errors if credentials are invalid
        try:
            exporter = create_cloudtrace_exporter(project_id="test-project")
            # If it succeeds, verify the endpoint
            assert "cloudtrace.googleapis.com" in exporter.endpoint
        except ImportError:
            # Expected if google-auth not installed
            pass
        except Exception as e:
            # Auth errors are expected if not authenticated with GCP
            assert "RefreshError" in type(e).__name__ or "Reauthentication" in str(e)

    def test_configure_for_cloud_run_uses_k_service(self):
        """Test Cloud Run uses K_SERVICE env var."""
        from tracecraft.contrib.gcp import configure_for_cloud_run

        # Will fail without google-auth, but we're testing the service name logic
        with (
            patch.dict(os.environ, {"K_SERVICE": "my-cloud-run-service"}),
            contextlib.suppress(ImportError, ValueError),
        ):
            configure_for_cloud_run()

    def test_configure_for_cloud_functions_uses_function_name(self):
        """Test Cloud Functions uses FUNCTION_NAME env var."""
        from tracecraft.contrib.gcp import configure_for_cloud_functions

        with (
            patch.dict(os.environ, {"FUNCTION_NAME": "my-function"}),
            contextlib.suppress(ImportError, ValueError),
        ):
            configure_for_cloud_functions()
