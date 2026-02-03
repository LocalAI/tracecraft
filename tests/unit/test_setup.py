"""Tests for the setup/initialization module."""

from pathlib import Path

import pytest

from tracecraft.core.init import (
    InitLocation,
    config_exists,
    database_exists,
    find_existing_config,
    find_existing_database,
    get_default_config,
    get_global_dir,
    get_local_dir,
    get_source_for_location,
    initialize,
    needs_setup,
)


class TestInitLocation:
    """Tests for InitLocation enum."""

    def test_location_values(self) -> None:
        """Test location enum values."""
        assert InitLocation.GLOBAL.value == "global"
        assert InitLocation.LOCAL.value == "local"


class TestPathFunctions:
    """Tests for path helper functions."""

    def test_get_global_dir(self) -> None:
        """Test global directory path."""
        global_dir = get_global_dir()
        assert global_dir == Path.home() / ".tracecraft"

    def test_get_local_dir_default(self) -> None:
        """Test local directory with default path."""
        local_dir = get_local_dir()
        assert local_dir == Path.cwd() / ".tracecraft"

    def test_get_local_dir_custom_base(self, tmp_path: Path) -> None:
        """Test local directory with custom base path."""
        local_dir = get_local_dir(tmp_path)
        assert local_dir == tmp_path / ".tracecraft"


class TestConfigExists:
    """Tests for config_exists function."""

    def test_no_config_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test when no config exists."""
        # Mock home and cwd to temp paths
        monkeypatch.setattr("tracecraft.core.init.get_global_dir", lambda: tmp_path / "global")
        monkeypatch.setattr("tracecraft.core.init.get_local_dir", lambda b=None: tmp_path / "local")

        assert config_exists() is False
        assert config_exists(InitLocation.GLOBAL) is False
        assert config_exists(InitLocation.LOCAL) is False

    def test_global_config_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test when global config exists."""
        global_dir = tmp_path / "global"
        global_dir.mkdir(parents=True)
        (global_dir / "config.yaml").write_text("env: development")

        monkeypatch.setattr("tracecraft.core.init.get_global_dir", lambda: global_dir)
        monkeypatch.setattr("tracecraft.core.init.get_local_dir", lambda b=None: tmp_path / "local")

        assert config_exists() is True
        assert config_exists(InitLocation.GLOBAL) is True
        assert config_exists(InitLocation.LOCAL) is False

    def test_local_config_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test when local config exists."""
        local_dir = tmp_path / "local"
        local_dir.mkdir(parents=True)
        (local_dir / "config.yaml").write_text("env: development")

        monkeypatch.setattr("tracecraft.core.init.get_global_dir", lambda: tmp_path / "global")
        monkeypatch.setattr("tracecraft.core.init.get_local_dir", lambda b=None: local_dir)

        assert config_exists() is True
        assert config_exists(InitLocation.GLOBAL) is False
        assert config_exists(InitLocation.LOCAL) is True


class TestDatabaseExists:
    """Tests for database_exists function."""

    def test_no_database_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test when no database exists."""
        monkeypatch.setattr("tracecraft.core.init.get_global_dir", lambda: tmp_path / "global")
        monkeypatch.setattr("tracecraft.core.init.get_local_dir", lambda b=None: tmp_path / "local")

        assert database_exists() is False

    def test_global_database_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test when global database exists."""
        global_dir = tmp_path / "global"
        global_dir.mkdir(parents=True)
        (global_dir / "traces.db").write_text("")  # Empty file for test

        monkeypatch.setattr("tracecraft.core.init.get_global_dir", lambda: global_dir)
        monkeypatch.setattr("tracecraft.core.init.get_local_dir", lambda b=None: tmp_path / "local")

        assert database_exists() is True
        assert database_exists(InitLocation.GLOBAL) is True
        assert database_exists(InitLocation.LOCAL) is False


class TestFindExisting:
    """Tests for find_existing_config and find_existing_database."""

    def test_find_existing_config_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test finding config when none exists."""
        monkeypatch.setattr("tracecraft.core.init.get_global_dir", lambda: tmp_path / "global")
        monkeypatch.setattr("tracecraft.core.init.get_local_dir", lambda b=None: tmp_path / "local")

        assert find_existing_config() is None

    def test_find_existing_config_local_priority(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that local config takes priority over global."""
        global_dir = tmp_path / "global"
        local_dir = tmp_path / "local"
        global_dir.mkdir(parents=True)
        local_dir.mkdir(parents=True)
        (global_dir / "config.yaml").write_text("env: global")
        (local_dir / "config.yaml").write_text("env: local")

        monkeypatch.setattr("tracecraft.core.init.get_global_dir", lambda: global_dir)
        monkeypatch.setattr("tracecraft.core.init.get_local_dir", lambda b=None: local_dir)

        result = find_existing_config()
        assert result == local_dir / "config.yaml"

    def test_find_existing_database_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test finding database when none exists."""
        monkeypatch.setattr("tracecraft.core.init.get_global_dir", lambda: tmp_path / "global")
        monkeypatch.setattr("tracecraft.core.init.get_local_dir", lambda b=None: tmp_path / "local")

        assert find_existing_database() is None


class TestGetDefaultConfig:
    """Tests for get_default_config function."""

    def test_default_config_structure(self, tmp_path: Path) -> None:
        """Test default config has expected structure."""
        db_path = tmp_path / "traces.db"
        config = get_default_config(InitLocation.GLOBAL, db_path)

        assert "env" in config
        assert config["env"] == "development"
        assert "default" in config
        assert "storage" in config["default"]
        assert config["default"]["storage"]["type"] == "sqlite"
        assert "environments" in config

    def test_default_config_local_relative_path(self, tmp_path: Path) -> None:
        """Test local config uses relative database path."""
        db_path = tmp_path / "traces.db"
        config = get_default_config(InitLocation.LOCAL, db_path)

        # Local should just use the filename
        assert config["default"]["storage"]["sqlite_path"] == "traces.db"

    def test_default_config_global_absolute_path(self, tmp_path: Path) -> None:
        """Test global config uses absolute database path."""
        db_path = tmp_path / "traces.db"
        config = get_default_config(InitLocation.GLOBAL, db_path)

        # Global should use full path
        assert config["default"]["storage"]["sqlite_path"] == str(db_path)


class TestInitialize:
    """Tests for the initialize function."""

    def test_initialize_local(self, tmp_path: Path) -> None:
        """Test initializing local database and config."""
        result = initialize(InitLocation.LOCAL, base_path=tmp_path, create_sample_project=False)

        assert result.success is True
        assert result.location == InitLocation.LOCAL
        assert result.config_path.exists()
        assert result.database_path.exists()
        assert result.error is None

        # Check directory structure
        tracecraft_dir = tmp_path / ".tracecraft"
        assert tracecraft_dir.exists()
        assert (tracecraft_dir / "config.yaml").exists()
        assert (tracecraft_dir / "traces.db").exists()
        assert (tracecraft_dir / ".gitignore").exists()

    def test_initialize_with_sample_project(self, tmp_path: Path) -> None:
        """Test initialization creates sample project."""
        result = initialize(InitLocation.LOCAL, base_path=tmp_path, create_sample_project=True)

        assert result.success is True

        # Check project was created
        from tracecraft.storage.sqlite import SQLiteTraceStore

        store = SQLiteTraceStore(result.database_path)
        projects = store.list_projects()
        store.close()

        assert len(projects) >= 1
        assert any(p["name"] == "Example Project" for p in projects)

    def test_initialize_idempotent(self, tmp_path: Path) -> None:
        """Test initialization can be run multiple times."""
        result1 = initialize(InitLocation.LOCAL, base_path=tmp_path, create_sample_project=False)
        result2 = initialize(InitLocation.LOCAL, base_path=tmp_path, create_sample_project=False)

        assert result1.success is True
        assert result2.success is True


class TestNeedsSetup:
    """Tests for needs_setup function."""

    def test_needs_setup_true(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test needs_setup returns True when nothing exists."""
        monkeypatch.setattr("tracecraft.core.init.get_global_dir", lambda: tmp_path / "global")
        monkeypatch.setattr("tracecraft.core.init.get_local_dir", lambda b=None: tmp_path / "local")

        assert needs_setup() is True

    def test_needs_setup_false_with_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test needs_setup returns False when config exists."""
        local_dir = tmp_path / "local"
        local_dir.mkdir(parents=True)
        (local_dir / "config.yaml").write_text("env: development")

        monkeypatch.setattr("tracecraft.core.init.get_global_dir", lambda: tmp_path / "global")
        monkeypatch.setattr("tracecraft.core.init.get_local_dir", lambda b=None: local_dir)

        assert needs_setup() is False

    def test_needs_setup_false_with_database(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test needs_setup returns False when database exists."""
        local_dir = tmp_path / "local"
        local_dir.mkdir(parents=True)
        (local_dir / "traces.db").write_text("")

        monkeypatch.setattr("tracecraft.core.init.get_global_dir", lambda: tmp_path / "global")
        monkeypatch.setattr("tracecraft.core.init.get_local_dir", lambda b=None: local_dir)

        assert needs_setup() is False


class TestGetSourceForLocation:
    """Tests for get_source_for_location function."""

    def test_source_for_global(self) -> None:
        """Test source string for global location."""
        source = get_source_for_location(InitLocation.GLOBAL)
        expected_path = get_global_dir() / "traces.db"
        assert source == f"sqlite://{expected_path}"

    def test_source_for_local(self, tmp_path: Path) -> None:
        """Test source string for local location."""
        source = get_source_for_location(InitLocation.LOCAL, tmp_path)
        expected_path = tmp_path / ".tracecraft" / "traces.db"
        assert source == f"sqlite://{expected_path}"


class TestSetupWizardScreen:
    """Tests for SetupWizardScreen TUI component."""

    def test_setup_wizard_requires_textual(self) -> None:
        """Test SetupWizardScreen raises ImportError without textual."""
        try:
            from tracecraft.tui.screens.setup_wizard import (
                TEXTUAL_AVAILABLE,
                SetupWizardScreen,
            )

            if not TEXTUAL_AVAILABLE:
                with pytest.raises(ImportError):
                    SetupWizardScreen()
        except ImportError:
            pass  # Expected if textual not installed

    def test_setup_choice_enum_values(self) -> None:
        """Test SetupChoice enum has expected values."""
        from tracecraft.tui.screens.setup_wizard import SetupChoice

        assert SetupChoice.GLOBAL.value == "global"
        assert SetupChoice.LOCAL.value == "local"
        assert SetupChoice.OPEN_FILE.value == "open_file"
        assert SetupChoice.DEMO.value == "demo"
        assert SetupChoice.CANCEL.value == "cancel"

    def test_setup_result_dataclass(self) -> None:
        """Test SetupResult dataclass."""
        from tracecraft.tui.screens.setup_wizard import SetupChoice, SetupResult

        result = SetupResult(choice=SetupChoice.GLOBAL, source="sqlite:///test.db")
        assert result.choice == SetupChoice.GLOBAL
        assert result.source == "sqlite:///test.db"
        assert result.error is None

    def test_screens_init_exports_setup_wizard(self) -> None:
        """Test screens __init__ exports SetupWizardScreen."""
        from tracecraft.tui import screens

        # May be None if textual not installed, but should be importable
        assert "SetupWizardScreen" in dir(screens)
