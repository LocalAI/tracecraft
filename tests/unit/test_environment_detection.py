"""
Tests for environment detection and environment-aware defaults.
"""

from agenttrace.core.env_config import (
    detect_environment,
    get_environment_defaults,
)


class TestEnvironmentDetection:
    """Tests for detect_environment function."""

    def test_explicit_agenttrace_env(self, monkeypatch):
        """Should use AGENTTRACE_ENV when set."""
        monkeypatch.setenv("AGENTTRACE_ENV", "staging")
        assert detect_environment() == "staging"

    def test_explicit_agenttrace_environment(self, monkeypatch):
        """Should use AGENTTRACE_ENVIRONMENT when set."""
        monkeypatch.setenv("AGENTTRACE_ENVIRONMENT", "production")
        assert detect_environment() == "production"

    def test_aws_lambda_detection(self, monkeypatch):
        """Should detect AWS Lambda as production."""
        monkeypatch.delenv("AGENTTRACE_ENV", raising=False)
        monkeypatch.delenv("AGENTTRACE_ENVIRONMENT", raising=False)
        monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "my-function")
        assert detect_environment() == "production"

    def test_kubernetes_detection(self, monkeypatch):
        """Should detect Kubernetes as production."""
        monkeypatch.delenv("AGENTTRACE_ENV", raising=False)
        monkeypatch.delenv("AGENTTRACE_ENVIRONMENT", raising=False)
        monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.0.0.1")
        assert detect_environment() == "production"

    def test_cloud_run_detection(self, monkeypatch):
        """Should detect Cloud Run as production."""
        monkeypatch.delenv("AGENTTRACE_ENV", raising=False)
        monkeypatch.delenv("AGENTTRACE_ENVIRONMENT", raising=False)
        monkeypatch.setenv("K_SERVICE", "my-service")
        assert detect_environment() == "production"

    def test_github_actions_detection(self, monkeypatch):
        """Should detect GitHub Actions as CI."""
        monkeypatch.delenv("AGENTTRACE_ENV", raising=False)
        monkeypatch.delenv("AGENTTRACE_ENVIRONMENT", raising=False)
        # Clear production indicators
        monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
        monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        assert detect_environment() == "ci"

    def test_generic_ci_detection(self, monkeypatch):
        """Should detect generic CI variable."""
        monkeypatch.delenv("AGENTTRACE_ENV", raising=False)
        monkeypatch.delenv("AGENTTRACE_ENVIRONMENT", raising=False)
        monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
        monkeypatch.setenv("CI", "true")
        assert detect_environment() == "ci"

    def test_vercel_production(self, monkeypatch):
        """Should detect Vercel production environment."""
        monkeypatch.delenv("AGENTTRACE_ENV", raising=False)
        monkeypatch.delenv("AGENTTRACE_ENVIRONMENT", raising=False)
        monkeypatch.setenv("VERCEL_ENV", "production")
        assert detect_environment() == "production"

    def test_vercel_preview(self, monkeypatch):
        """Should detect Vercel preview as production."""
        monkeypatch.delenv("AGENTTRACE_ENV", raising=False)
        monkeypatch.delenv("AGENTTRACE_ENVIRONMENT", raising=False)
        monkeypatch.setenv("VERCEL_ENV", "preview")
        assert detect_environment() == "production"

    def test_default_to_development(self, monkeypatch):
        """Should default to development when no indicators."""
        # Clear all possible env vars
        monkeypatch.delenv("AGENTTRACE_ENV", raising=False)
        monkeypatch.delenv("AGENTTRACE_ENVIRONMENT", raising=False)
        monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
        monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
        monkeypatch.delenv("K_SERVICE", raising=False)
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        monkeypatch.delenv("VERCEL_ENV", raising=False)
        assert detect_environment() == "development"


class TestEnvironmentAwareDefaults:
    """Tests for get_environment_defaults function."""

    def test_development_defaults(self):
        """Development should enable console and jsonl."""
        defaults = get_environment_defaults("development")
        assert defaults["console"] is True
        assert defaults["jsonl"] is True

    def test_production_defaults(self):
        """Production should disable console and jsonl."""
        defaults = get_environment_defaults("production")
        assert defaults["console"] is False
        assert defaults["jsonl"] is False

    def test_prod_alias(self):
        """'prod' should work as alias for production."""
        defaults = get_environment_defaults("prod")
        assert defaults["console"] is False
        assert defaults["jsonl"] is False

    def test_ci_defaults(self):
        """CI should disable console but keep jsonl."""
        defaults = get_environment_defaults("ci")
        assert defaults["console"] is False
        assert defaults["jsonl"] is True

    def test_staging_defaults(self):
        """Staging should disable console but keep jsonl."""
        defaults = get_environment_defaults("staging")
        assert defaults["console"] is False
        assert defaults["jsonl"] is True

    def test_local_defaults(self):
        """Local should enable both."""
        defaults = get_environment_defaults("local")
        assert defaults["console"] is True
        assert defaults["jsonl"] is True

    def test_test_defaults(self):
        """Test environment should enable both."""
        defaults = get_environment_defaults("test")
        assert defaults["console"] is True
        assert defaults["jsonl"] is True

    def test_unknown_environment_defaults(self):
        """Unknown environments should default to development behavior."""
        defaults = get_environment_defaults("custom-env")
        assert defaults["console"] is True
        assert defaults["jsonl"] is True

    def test_case_insensitive(self):
        """Should be case-insensitive."""
        defaults = get_environment_defaults("PRODUCTION")
        assert defaults["console"] is False
        assert defaults["jsonl"] is False


class TestProcessorOrder:
    """Tests for ProcessorOrder enum."""

    def test_processor_order_enum_values(self):
        """ProcessorOrder should have expected values."""
        from agenttrace.core.config import ProcessorOrder

        assert ProcessorOrder.SAFETY.value == "safety"
        assert ProcessorOrder.EFFICIENCY.value == "efficiency"

    def test_processor_order_default_in_config(self):
        """AgentTraceConfig should default to SAFETY order."""
        from agenttrace.core.config import AgentTraceConfig, ProcessorOrder

        config = AgentTraceConfig()
        assert config.processor_order == ProcessorOrder.SAFETY

    def test_processor_order_can_be_set(self):
        """ProcessorOrder can be explicitly set."""
        from agenttrace.core.config import AgentTraceConfig, ProcessorOrder

        config = AgentTraceConfig(processor_order=ProcessorOrder.EFFICIENCY)
        assert config.processor_order == ProcessorOrder.EFFICIENCY
