"""
Tests for environment configuration system.
"""

import pytest

from agenttrace.core.env_config import (
    AgentTraceEnvConfig,
    EnvironmentSettings,
    ExporterConfig,
    ProcessorConfig,
    StorageConfig,
    _expand_env_vars,
    get_config,
    load_config,
    reset_config,
    set_config,
)


class TestStorageConfig:
    """Tests for StorageConfig model."""

    def test_defaults(self):
        """Test default values."""
        config = StorageConfig()
        assert config.type == "jsonl"
        assert config.jsonl_path is None
        assert config.sqlite_path is None
        assert config.sqlite_wal_mode is True

    def test_sqlite_config(self):
        """Test SQLite configuration."""
        config = StorageConfig(
            type="sqlite",
            sqlite_path="traces.db",
            sqlite_wal_mode=False,
        )
        assert config.type == "sqlite"
        assert config.sqlite_path == "traces.db"
        assert config.sqlite_wal_mode is False


class TestExporterConfig:
    """Tests for ExporterConfig model."""

    def test_defaults(self):
        """Test default values."""
        config = ExporterConfig()
        assert config.console is True
        assert config.jsonl is True
        assert config.otlp is False
        assert config.mlflow is False

    def test_otlp_config(self):
        """Test OTLP configuration."""
        config = ExporterConfig(
            otlp=True,
            otlp_endpoint="http://localhost:4317",
            otlp_headers={"Authorization": "Bearer token"},
        )
        assert config.otlp is True
        assert config.otlp_endpoint == "http://localhost:4317"
        assert config.otlp_headers["Authorization"] == "Bearer token"


class TestProcessorConfig:
    """Tests for ProcessorConfig model."""

    def test_defaults(self):
        """Test default values."""
        config = ProcessorConfig()
        assert config.redaction_enabled is False
        assert config.redaction_mode == "mask"
        assert config.sampling_enabled is False
        assert config.sampling_rate == 1.0
        assert config.enrichment_enabled is True


class TestEnvironmentSettings:
    """Tests for EnvironmentSettings model."""

    def test_defaults(self):
        """Test default values."""
        settings = EnvironmentSettings()
        assert settings.storage.type == "jsonl"
        assert settings.exporters.console is True
        assert settings.processors.enrichment_enabled is True


class TestEnvironmentValidation:
    """Tests for environment name validation."""

    def test_known_environments_no_warning(self):
        """Known environments should not trigger warnings."""
        import warnings

        from agenttrace.core.env_config import KNOWN_ENVIRONMENTS

        for env in KNOWN_ENVIRONMENTS:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                config = AgentTraceEnvConfig(env=env)
                # Should not have any warnings
                user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
                assert len(user_warnings) == 0, f"Unexpected warning for known env: {env}"
                assert config.env == env

    def test_unknown_environment_triggers_warning(self):
        """Unknown environments should trigger a warning but still work."""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            config = AgentTraceEnvConfig(env="my_custom_env")
            # Should have exactly one UserWarning
            user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
            assert len(user_warnings) == 1
            assert "Unknown environment" in str(user_warnings[0].message)
            # Config should still be created with the custom env
            assert config.env == "my_custom_env"

    def test_environment_names_are_normalized(self):
        """Environment names should be normalized to lowercase."""
        import warnings

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            # Known environments in different cases should normalize
            config = AgentTraceEnvConfig(env="PRODUCTION")
            assert config.env == "production"

            config = AgentTraceEnvConfig(env="Development")
            assert config.env == "development"

    def test_arbitrary_environment_string_works(self):
        """Arbitrary environment strings should work after warning."""
        import warnings

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            config = AgentTraceEnvConfig(env="canary")  # Known env
            assert config.env == "canary"

            config = AgentTraceEnvConfig(env="blue-green-deploy")  # Unknown
            assert config.env == "blue-green-deploy"


class TestAgentTraceEnvConfig:
    """Tests for AgentTraceEnvConfig model."""

    def test_defaults(self):
        """Test default values."""
        config = AgentTraceEnvConfig()
        assert config.env == "development"
        assert config.default is not None
        assert config.environments == {}

    def test_get_settings_default(self):
        """Test get_settings returns default when no env override."""
        config = AgentTraceEnvConfig()
        settings = config.get_settings()
        assert settings.storage.type == "jsonl"

    def test_get_settings_with_override(self):
        """Test get_settings merges environment overrides."""
        config = AgentTraceEnvConfig(
            env="production",
            default=EnvironmentSettings(
                storage=StorageConfig(type="jsonl"),
                exporters=ExporterConfig(console=True),
            ),
            environments={
                "production": EnvironmentSettings(
                    storage=StorageConfig(type="sqlite", sqlite_path="prod.db"),
                    exporters=ExporterConfig(console=False, otlp=True),
                )
            },
        )
        settings = config.get_settings()

        # Overridden values
        assert settings.storage.type == "sqlite"
        assert settings.storage.sqlite_path == "prod.db"
        assert settings.exporters.console is False
        assert settings.exporters.otlp is True

    def test_get_settings_missing_env(self):
        """Test get_settings returns default for missing environment."""
        config = AgentTraceEnvConfig(env="staging")
        settings = config.get_settings()
        assert settings.storage.type == "jsonl"


class TestExpandEnvVars:
    """Tests for environment variable expansion."""

    def test_expand_simple(self, monkeypatch):
        """Test expanding simple env var."""
        monkeypatch.setenv("TEST_VAR", "test_value")
        result = _expand_env_vars("${TEST_VAR}")
        assert result == "test_value"

    def test_expand_in_string(self, monkeypatch):
        """Test expanding env var in string."""
        monkeypatch.setenv("HOST", "localhost")
        result = _expand_env_vars("http://${HOST}:8080")
        assert result == "http://localhost:8080"

    def test_expand_missing_var(self):
        """Test missing env var is left as-is."""
        result = _expand_env_vars("${NONEXISTENT_VAR}")
        assert result == "${NONEXISTENT_VAR}"

    def test_expand_in_dict(self, monkeypatch):
        """Test expanding in nested dict."""
        monkeypatch.setenv("DB_PATH", "/data/traces.db")
        data = {
            "storage": {
                "path": "${DB_PATH}",
            }
        }
        result = _expand_env_vars(data)
        assert result["storage"]["path"] == "/data/traces.db"

    def test_expand_in_list(self, monkeypatch):
        """Test expanding in list."""
        monkeypatch.setenv("TAG", "prod")
        data = ["${TAG}", "other"]
        result = _expand_env_vars(data)
        assert result == ["prod", "other"]


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_defaults(self):
        """Test loading with no config file."""
        config = load_config()
        assert config.env == "development"

    def test_load_with_env_override(self):
        """Test loading with env parameter."""
        config = load_config(env="production")
        assert config.env == "production"

    def test_load_from_env_var(self, monkeypatch):
        """Test loading env from AGENTTRACE_ENV."""
        monkeypatch.setenv("AGENTTRACE_ENV", "staging")
        config = load_config()
        assert config.env == "staging"

    def test_load_from_yaml_file(self, tmp_path, monkeypatch):
        """Test loading from YAML config file."""
        pytest.importorskip("yaml")

        config_dir = tmp_path / ".agenttrace"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"

        config_file.write_text(
            """
env: test
default:
  storage:
    type: sqlite
    sqlite_path: test.db
"""
        )

        # Change to temp directory
        monkeypatch.chdir(tmp_path)

        config = load_config()
        assert config.env == "test"
        assert config.default.storage.type == "sqlite"
        assert config.default.storage.sqlite_path == "test.db"

    def test_load_explicit_path(self, tmp_path):
        """Test loading from explicit config path."""
        pytest.importorskip("yaml")

        config_file = tmp_path / "custom_config.yaml"
        config_file.write_text(
            """
env: test
"""
        )

        config = load_config(config_path=config_file)
        assert config.env == "test"

    def test_env_param_overrides_file(self, tmp_path, monkeypatch):
        """Test that env parameter overrides file value."""
        pytest.importorskip("yaml")

        config_dir = tmp_path / ".agenttrace"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"

        config_file.write_text(
            """
env: development
"""
        )

        monkeypatch.chdir(tmp_path)

        config = load_config(env="production")
        assert config.env == "production"


class TestGlobalConfig:
    """Tests for global config management."""

    def setup_method(self):
        """Reset global config before each test."""
        reset_config()

    def teardown_method(self):
        """Reset global config after each test."""
        reset_config()

    def test_get_config_lazy_loads(self):
        """Test get_config loads config lazily."""
        config = get_config()
        assert config is not None
        assert config.env == "development"

    def test_get_config_returns_same_instance(self):
        """Test get_config returns same instance."""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_set_config(self):
        """Test set_config sets global config."""
        custom_config = AgentTraceEnvConfig(env="staging")
        set_config(custom_config)

        config = get_config()
        assert config.env == "staging"

    def test_reset_config(self):
        """Test reset_config clears global config."""
        config1 = get_config()
        reset_config()
        config2 = get_config()

        # Should be different instances
        assert config1 is not config2
