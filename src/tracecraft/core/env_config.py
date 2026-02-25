"""
Environment-aware configuration for TraceCraft.

Supports different storage backends, exporters, and settings
per environment (development, staging, production, etc.).
"""

from __future__ import annotations

import os
import re
import warnings
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, Field

# Known environment names that won't trigger warnings
KNOWN_ENVIRONMENTS = frozenset(
    {
        "development",
        "staging",
        "production",
        "test",
        "local",
        "ci",
        "qa",
        "integration",
        "canary",
        "preview",
        "sandbox",
    }
)


def _validate_environment(v: str) -> str:
    """Validate and normalize environment name.

    Args:
        v: Environment name string.

    Returns:
        Normalized (lowercase) environment name.

    Warns:
        UserWarning if environment name is not in KNOWN_ENVIRONMENTS.
    """
    normalized = v.lower()
    if normalized not in KNOWN_ENVIRONMENTS:
        warnings.warn(
            f"Unknown environment '{v}'. Known environments: {sorted(KNOWN_ENVIRONMENTS)}. "
            "Custom environments are allowed but may not have optimized defaults.",
            UserWarning,
            stacklevel=4,
        )
    return normalized


EnvironmentName = Annotated[str, BeforeValidator(_validate_environment)]


def detect_environment() -> str:
    """
    Auto-detect the current environment from environment variables and context.

    Detection order (first match wins):
    1. TRACECRAFT_ENVIRONMENT / TRACECRAFT_ENV (explicit override)
    2. Production indicators (AWS Lambda, Kubernetes, Cloud Run, etc.)
    3. CI/test indicators (CI=true, GITHUB_ACTIONS, etc.)
    4. Default to "development"

    Returns:
        Detected environment name (lowercase).
    """
    # 1. Explicit environment override
    explicit = os.environ.get("TRACECRAFT_ENVIRONMENT") or os.environ.get("TRACECRAFT_ENV")
    if explicit:
        return explicit.lower()

    # 2. Production environment indicators
    production_indicators = [
        "AWS_LAMBDA_FUNCTION_NAME",  # AWS Lambda
        "KUBERNETES_SERVICE_HOST",  # Kubernetes
        "K_SERVICE",  # Cloud Run
        "WEBSITE_SITE_NAME",  # Azure App Service
        "DYNO",  # Heroku
        "FLY_APP_NAME",  # Fly.io
        "RENDER_SERVICE_NAME",  # Render
        "RAILWAY_ENVIRONMENT",  # Railway
        "VERCEL_ENV",  # Vercel
    ]
    for indicator in production_indicators:
        if os.environ.get(indicator):
            # Special case for Vercel which sets VERCEL_ENV explicitly
            if indicator == "VERCEL_ENV":
                vercel_env = os.environ.get("VERCEL_ENV", "").lower()
                if vercel_env in ("production", "preview"):
                    return "production"
                return vercel_env
            return "production"

    # 3. CI/test environment indicators
    ci_indicators = [
        "CI",  # Generic CI
        "GITHUB_ACTIONS",  # GitHub Actions
        "GITLAB_CI",  # GitLab CI
        "CIRCLECI",  # CircleCI
        "TRAVIS",  # Travis CI
        "JENKINS_URL",  # Jenkins
        "BUILDKITE",  # Buildkite
        "CODEBUILD_BUILD_ID",  # AWS CodeBuild
        "TF_BUILD",  # Azure Pipelines
    ]
    for indicator in ci_indicators:
        if os.environ.get(indicator):
            return "ci"

    # 4. Staging indicators (less common but useful)
    staging_indicators = [
        "STAGING",
        "IS_STAGING",
    ]
    for indicator in staging_indicators:
        val = os.environ.get(indicator, "").lower()
        if val in ("true", "1", "yes"):
            return "staging"

    # 5. Default to development
    return "development"


def get_environment_defaults(env: str) -> dict[str, bool]:
    """
    Get default exporter settings for an environment.

    Args:
        env: Environment name.

    Returns:
        Dict with 'console' and 'jsonl' boolean defaults.
    """
    env = env.lower()

    # Production: Disable verbose local exporters by default
    if env in ("production", "prod"):
        return {"console": False, "jsonl": False}

    # CI: Disable console (noisy in logs), keep JSONL for artifacts
    if env == "ci":
        return {"console": False, "jsonl": True}

    # Staging/preview: Like production but may want some visibility
    if env in ("staging", "preview", "canary"):
        return {"console": False, "jsonl": True}

    # Development, local, test, or unknown: Enable both
    return {"console": True, "jsonl": True}


class StorageConfig(BaseModel):
    """Storage backend configuration."""

    type: Literal[
        "jsonl",
        "sqlite",
        "mlflow",
        "none",
        "xray",
        "cloudtrace",
        "azuremonitor",
        "datadog",
    ] = "jsonl"

    # JSONL settings
    jsonl_path: str | None = None

    # SQLite settings
    sqlite_path: str | None = None
    sqlite_wal_mode: bool = True  # Better concurrency

    # MLflow settings
    mlflow_tracking_uri: str | None = None
    mlflow_experiment_name: str | None = None

    # X-Ray (AWS / Bedrock AgentCore)
    # Auth: boto3 credential chain (env vars, ~/.aws/credentials, instance profile)
    xray_region: str = "us-east-1"
    xray_service_name: str | None = None  # None = all services
    xray_lookback_hours: int = 1
    xray_cache_ttl_seconds: int = 60

    # Cloud Trace (GCP / Vertex AI Agent Builder)
    # Auth: google.auth.default() ADC chain
    cloudtrace_project_id: str | None = None  # falls back to GOOGLE_CLOUD_PROJECT
    cloudtrace_service_name: str | None = None
    cloudtrace_lookback_hours: int = 1
    cloudtrace_cache_ttl_seconds: int = 60

    # Azure Monitor (AI Foundry / Application Insights)
    # Auth: DefaultAzureCredential (managed identity → CLI → env vars)
    # Secrets: AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID — never in config
    azuremonitor_workspace_id: str | None = None  # falls back to AZURE_MONITOR_WORKSPACE_ID
    azuremonitor_service_name: str | None = None
    azuremonitor_lookback_hours: int = 1
    azuremonitor_cache_ttl_seconds: int = 60

    # DataDog
    # Secrets: DD_API_KEY + DD_APP_KEY env vars only — never stored in config
    datadog_site: str = "us1"  # us1, us3, us5, eu1, ap1
    datadog_service: str | None = None
    datadog_lookback_hours: int = 1
    datadog_cache_ttl_seconds: int = 60


class ExporterConfig(BaseModel):
    """Exporter configuration."""

    console: bool = True
    jsonl: bool = True  # Enabled by default for backward compatibility
    otlp: bool = False
    mlflow: bool = False

    # JSONL settings
    jsonl_path: str | None = None

    # OTLP settings
    otlp_endpoint: str | None = None
    otlp_headers: dict[str, str] = Field(default_factory=dict)

    # MLflow settings
    mlflow_tracking_uri: str | None = None
    mlflow_experiment_name: str = "tracecraft"

    # TraceCraft TUI receiver settings
    receiver: bool = False
    receiver_endpoint: str = "http://localhost:4318"


class ProcessorConfig(BaseModel):
    """Processor configuration."""

    redaction_enabled: bool = False
    redaction_mode: Literal["mask", "hash", "remove"] = "mask"

    sampling_enabled: bool = False
    sampling_rate: float = 1.0

    enrichment_enabled: bool = True


class InstrumentationConfig(BaseModel):
    """Auto-instrumentation configuration.

    Controls which LLM SDKs and frameworks are automatically patched
    to capture traces without manual decorators.

    Example config.yaml usage::

        default:
          instrumentation:
            auto_instrument: true          # instrument everything
            # or selectively:
            # auto_instrument:
            #   - openai
            #   - langchain
    """

    auto_instrument: bool | list[str] = False


class EnvironmentSettings(BaseModel):
    """Settings for a specific environment."""

    service_name: str | None = None
    storage: StorageConfig = Field(default_factory=StorageConfig)
    exporters: ExporterConfig = Field(default_factory=ExporterConfig)
    processors: ProcessorConfig = Field(default_factory=ProcessorConfig)
    instrumentation: InstrumentationConfig = Field(default_factory=InstrumentationConfig)


class TraceCraftEnvConfig(BaseModel):
    """
    Root configuration with environment-specific overrides.

    Configuration is loaded from (in order of precedence):
    1. Environment variables (TRACECRAFT_*)
    2. .tracecraft/config.yaml in current directory
    3. ~/.tracecraft/config.yaml
    4. Default values

    Example config.yaml:
        default:
          storage:
            type: jsonl
            jsonl_path: traces/tracecraft.jsonl

        environments:
          development:
            storage:
              type: sqlite
              sqlite_path: traces/dev.db
            exporters:
              console: true
              otlp: false

          production:
            storage:
              type: none  # Don't store locally
            exporters:
              console: false
              otlp: true
              otlp_endpoint: ${OTEL_EXPORTER_OTLP_ENDPOINT}
            processors:
              redaction_enabled: true
    """

    # Current environment
    env: EnvironmentName = "development"

    # Default settings (used when no environment-specific override)
    default: EnvironmentSettings = Field(default_factory=EnvironmentSettings)

    # Environment-specific overrides
    environments: dict[str, EnvironmentSettings] = Field(default_factory=dict)

    def get_settings(self) -> EnvironmentSettings:
        """Get merged settings for current environment."""
        base = self.default.model_copy(deep=True)

        if self.env in self.environments:
            env_settings = self.environments[self.env]
            # Deep merge environment settings over defaults
            return self._merge_settings(base, env_settings)

        return base

    def _merge_settings(
        self,
        base: EnvironmentSettings,
        override: EnvironmentSettings,
    ) -> EnvironmentSettings:
        """Deep merge override settings into base."""
        base_dict = base.model_dump()
        override_dict = override.model_dump(exclude_unset=True)

        def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
            result = base.copy()
            for key, value in override.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result

        merged = deep_merge(base_dict, override_dict)
        return EnvironmentSettings.model_validate(merged)


def load_config(
    config_path: str | Path | None = None,
    env: str | None = None,
) -> TraceCraftEnvConfig:
    """
    Load configuration from file and environment.

    Args:
        config_path: Explicit config file path. If None, searches standard locations.
        env: Override environment. If None, uses TRACECRAFT_ENV or defaults to "development".

    Returns:
        Loaded configuration.
    """
    # Determine config file location
    if config_path is None:
        search_paths = [
            Path.cwd() / ".tracecraft" / "config.yaml",
            Path.cwd() / ".tracecraft" / "config.yml",
            Path.home() / ".tracecraft" / "config.yaml",
            Path.home() / ".tracecraft" / "config.yml",
        ]
        for path in search_paths:
            if path.exists():
                config_path = path
                break

    # Load from file if found
    config_data: dict[str, Any] = {}
    if config_path and Path(config_path).exists():
        try:
            import yaml

            with open(config_path) as f:
                config_data = yaml.safe_load(f) or {}
        except ImportError:
            # YAML not installed, try JSON fallback
            import json

            json_path = Path(config_path).with_suffix(".json")
            if json_path.exists():
                with open(json_path) as f:
                    config_data = json.load(f)

    # Override environment if specified
    if env:
        config_data["env"] = env
    elif "TRACECRAFT_ENV" in os.environ:
        config_data["env"] = os.environ["TRACECRAFT_ENV"]

    # Expand environment variables in string values
    config_data = _expand_env_vars(config_data)

    return TraceCraftEnvConfig.model_validate(config_data)


def _expand_env_vars(data: Any) -> Any:
    """Recursively expand ${VAR} patterns in config values."""
    if isinstance(data, str):
        # Expand ${VAR} patterns
        pattern = r"\$\{([^}]+)\}"

        def replacer(match: re.Match[str]) -> str:
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))

        return re.sub(pattern, replacer, data)
    elif isinstance(data, dict):
        return {k: _expand_env_vars(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_expand_env_vars(item) for item in data]
    return data


# Global config instance
_config: TraceCraftEnvConfig | None = None


def get_config() -> TraceCraftEnvConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def set_config(config: TraceCraftEnvConfig) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config


def reset_config() -> None:
    """Reset the global configuration instance."""
    global _config
    _config = None
