"""Tests for TUI components."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from tracecraft.core.models import AgentRun, Step, StepType


class TestTraceStore:
    """Tests for the TraceStore data management class."""

    @pytest.fixture
    def sample_run(self) -> AgentRun:
        """Create a sample AgentRun for testing."""
        run_id = uuid4()
        step = Step(
            trace_id=run_id,
            type=StepType.LLM,
            name="test_llm",
            start_time=datetime.now(UTC),
            duration_ms=100.0,
            model_name="gpt-4o",
            input_tokens=100,
            output_tokens=50,
        )
        run = AgentRun(
            id=run_id,
            name="test_run",
            start_time=datetime.now(UTC),
            duration_ms=150.0,
            steps=[step],
            total_tokens=150,
            total_cost_usd=0.01,
        )
        return run

    @pytest.fixture
    def sample_jsonl_file(self, sample_run: AgentRun, tmp_path: Path) -> Path:
        """Create a sample JSONL file with traces."""
        file_path = tmp_path / "traces.jsonl"
        with file_path.open("w") as f:
            f.write(sample_run.model_dump_json() + "\n")
        return file_path

    @pytest.mark.asyncio
    async def test_load_from_file(self, sample_jsonl_file: Path) -> None:
        """Test loading traces from a JSONL file."""
        from tracecraft.tui.data.store import TraceStore

        store = TraceStore()
        await store.load_from_source(str(sample_jsonl_file))

        assert store.run_count == 1
        assert store.runs[0].name == "test_run"

    @pytest.mark.asyncio
    async def test_load_from_nonexistent_file(self, tmp_path: Path) -> None:
        """Test loading from a nonexistent file."""
        from tracecraft.tui.data.store import TraceStore

        store = TraceStore()
        await store.load_from_source(str(tmp_path / "nonexistent.jsonl"))

        assert store.run_count == 0

    @pytest.mark.asyncio
    async def test_load_multiple_runs(self, tmp_path: Path) -> None:
        """Test loading multiple runs from a file."""
        from tracecraft.tui.data.store import TraceStore

        file_path = tmp_path / "multi.jsonl"
        with file_path.open("w") as f:
            for i in range(3):
                run = AgentRun(
                    name=f"run_{i}",
                    start_time=datetime.now(UTC),
                )
                f.write(run.model_dump_json() + "\n")

        store = TraceStore()
        await store.load_from_source(str(file_path))

        assert store.run_count == 3

    @pytest.mark.asyncio
    async def test_get_run_by_id(self, sample_run: AgentRun, tmp_path: Path) -> None:
        """Test getting a run by ID."""
        from tracecraft.tui.data.store import TraceStore

        file_path = tmp_path / "traces.jsonl"
        with file_path.open("w") as f:
            f.write(sample_run.model_dump_json() + "\n")

        store = TraceStore()
        await store.load_from_source(str(file_path))

        found = store.get_run(str(sample_run.id))
        assert found is not None
        assert found.name == sample_run.name

    def test_get_run_not_found(self) -> None:
        """Test getting a run that doesn't exist."""
        from tracecraft.tui.data.store import TraceStore

        store = TraceStore()
        assert store.get_run("nonexistent-id") is None

    @pytest.mark.asyncio
    async def test_filter_runs_by_name(self, tmp_path: Path) -> None:
        """Test filtering runs by name."""
        from tracecraft.tui.data.store import TraceStore

        file_path = tmp_path / "traces.jsonl"
        with file_path.open("w") as f:
            for name in ["chat_agent", "search_agent", "chat_bot"]:
                run = AgentRun(name=name, start_time=datetime.now(UTC))
                f.write(run.model_dump_json() + "\n")

        store = TraceStore()
        await store.load_from_source(str(file_path))

        filtered = store.filter_runs(name_filter="chat")
        assert len(filtered) == 2

    @pytest.mark.asyncio
    async def test_filter_runs_by_error(self, tmp_path: Path) -> None:
        """Test filtering runs by error status."""
        from tracecraft.tui.data.store import TraceStore

        file_path = tmp_path / "traces.jsonl"
        with file_path.open("w") as f:
            run1 = AgentRun(name="success", start_time=datetime.now(UTC))
            run2 = AgentRun(name="failure", start_time=datetime.now(UTC), error="Failed")
            f.write(run1.model_dump_json() + "\n")
            f.write(run2.model_dump_json() + "\n")

        store = TraceStore()
        await store.load_from_source(str(file_path))

        # Filter to errors only
        errors_only = store.filter_runs(has_error=True)
        assert len(errors_only) == 1
        assert errors_only[0].name == "failure"

        # Filter to successful only
        success_only = store.filter_runs(has_error=False)
        assert len(success_only) == 1
        assert success_only[0].name == "success"

    def test_get_statistics_empty(self) -> None:
        """Test getting statistics with no runs."""
        from tracecraft.tui.data.store import TraceStore

        store = TraceStore()
        stats = store.get_statistics()

        assert stats["total_runs"] == 0
        assert stats["total_tokens"] == 0

    @pytest.mark.asyncio
    async def test_get_statistics(self, tmp_path: Path) -> None:
        """Test getting statistics with runs."""
        from tracecraft.tui.data.store import TraceStore

        file_path = tmp_path / "traces.jsonl"
        with file_path.open("w") as f:
            for i in range(3):
                run = AgentRun(
                    name=f"run_{i}",
                    start_time=datetime.now(UTC),
                    duration_ms=100.0 * (i + 1),
                    total_tokens=1000 * (i + 1),
                    total_cost_usd=0.01 * (i + 1),
                    error="error" if i == 2 else None,
                )
                f.write(run.model_dump_json() + "\n")

        store = TraceStore()
        await store.load_from_source(str(file_path))

        stats = store.get_statistics()
        assert stats["total_runs"] == 3
        assert stats["total_tokens"] == 6000  # 1000 + 2000 + 3000
        assert stats["error_count"] == 1

    @pytest.mark.asyncio
    async def test_check_for_updates(self, tmp_path: Path) -> None:
        """Test checking for updates to a file."""
        from tracecraft.tui.data.store import TraceStore

        file_path = tmp_path / "traces.jsonl"
        with file_path.open("w") as f:
            run = AgentRun(name="initial", start_time=datetime.now(UTC))
            f.write(run.model_dump_json() + "\n")

        store = TraceStore()
        await store.load_from_source(str(file_path))
        assert store.run_count == 1

        # No update yet
        has_updates = await store.check_for_updates()
        assert has_updates is False

        # Add a new run to the file
        import time

        time.sleep(0.1)  # Ensure mtime changes
        with file_path.open("a") as f:
            run2 = AgentRun(name="new_run", start_time=datetime.now(UTC))
            f.write(run2.model_dump_json() + "\n")

        # Now should have updates
        has_updates = await store.check_for_updates()
        assert has_updates is True
        assert store.run_count == 2

    def test_clear(self) -> None:
        """Test clearing the store."""
        from tracecraft.tui.data.store import TraceStore

        store = TraceStore()
        store._runs = [AgentRun(name="test", start_time=datetime.now(UTC))]
        assert store.run_count == 1

        store.clear()
        assert store.run_count == 0


class TestTUIWidgetsImport:
    """Test that TUI widgets handle missing textual gracefully."""

    def test_run_tree_requires_textual(self) -> None:
        """Test RunTree raises ImportError without textual."""
        # This test verifies the import error handling
        # The actual behavior depends on whether textual is installed
        try:
            from tracecraft.tui.widgets.run_tree import TEXTUAL_AVAILABLE, RunTree

            if not TEXTUAL_AVAILABLE:
                with pytest.raises(ImportError):
                    RunTree()
        except ImportError:
            pass  # Expected if textual not installed

    def test_metrics_panel_requires_textual(self) -> None:
        """Test MetricsPanel raises ImportError without textual."""
        try:
            from tracecraft.tui.widgets.metrics_panel import TEXTUAL_AVAILABLE, MetricsPanel

            if not TEXTUAL_AVAILABLE:
                with pytest.raises(ImportError):
                    MetricsPanel()
        except ImportError:
            pass

    def test_io_viewer_requires_textual(self) -> None:
        """Test IOViewer raises ImportError without textual."""
        try:
            from tracecraft.tui.widgets.io_viewer import TEXTUAL_AVAILABLE, IOViewer

            if not TEXTUAL_AVAILABLE:
                with pytest.raises(ImportError):
                    IOViewer()
        except ImportError:
            pass

    def test_filter_bar_requires_textual(self) -> None:
        """Test FilterBar raises ImportError without textual."""
        try:
            from tracecraft.tui.widgets.filter_bar import TEXTUAL_AVAILABLE, FilterBar

            if not TEXTUAL_AVAILABLE:
                with pytest.raises(ImportError):
                    FilterBar()
        except ImportError:
            pass


class TestTUIApp:
    """Tests for the main TUI application."""

    def test_app_requires_textual(self) -> None:
        """Test TraceCraftApp raises ImportError without textual."""
        try:
            from tracecraft.tui.app import TEXTUAL_AVAILABLE, TraceCraftApp

            if not TEXTUAL_AVAILABLE:
                with pytest.raises(ImportError):
                    TraceCraftApp()
        except ImportError:
            pass

    def test_run_tui_function_exists(self) -> None:
        """Test run_tui function is importable."""
        from tracecraft.tui import run_tui

        assert callable(run_tui)


class TestTUIScreensImport:
    """Test that TUI screens handle missing textual gracefully."""

    def test_project_manager_requires_textual(self) -> None:
        """Test ProjectManagerScreen raises ImportError without textual."""
        try:
            from tracecraft.tui.screens.project_manager import (
                TEXTUAL_AVAILABLE,
                ProjectManagerScreen,
            )

            if not TEXTUAL_AVAILABLE:
                with pytest.raises(ImportError):
                    ProjectManagerScreen(store=None)
        except ImportError:
            pass  # Expected if textual not installed

    def test_confirm_screen_requires_textual(self) -> None:
        """Test ConfirmScreen raises ImportError without textual."""
        try:
            from tracecraft.tui.screens.project_manager import (
                TEXTUAL_AVAILABLE,
                ConfirmScreen,
            )

            if not TEXTUAL_AVAILABLE:
                with pytest.raises(ImportError):
                    ConfirmScreen(message="Test")
        except ImportError:
            pass

    def test_project_create_requires_textual(self) -> None:
        """Test ProjectCreateScreen raises ImportError without textual."""
        try:
            from tracecraft.tui.screens.project_create import (
                TEXTUAL_AVAILABLE,
                ProjectCreateScreen,
            )

            if not TEXTUAL_AVAILABLE:
                with pytest.raises(ImportError):
                    ProjectCreateScreen(store=None)
        except ImportError:
            pass

    def test_trace_assign_requires_textual(self) -> None:
        """Test TraceAssignScreen raises ImportError without textual."""
        try:
            from tracecraft.tui.screens.trace_assign import (
                TEXTUAL_AVAILABLE,
                TraceAssignScreen,
            )

            if not TEXTUAL_AVAILABLE:
                with pytest.raises(ImportError):
                    TraceAssignScreen(trace=None, store=None)
        except ImportError:
            pass

    def test_screens_init_exports(self) -> None:
        """Test screens __init__ exports all new screens."""
        from tracecraft.tui import screens

        # These may be None if textual not installed, but should be importable
        assert "LLMPickerScreen" in dir(screens)
        assert "PlaygroundScreen" in dir(screens)
        assert "ProjectManagerScreen" in dir(screens)
        assert "ProjectCreateScreen" in dir(screens)
        assert "TraceAssignScreen" in dir(screens)
        assert "ConfirmScreen" in dir(screens)


class TestFilterBarProject:
    """Tests for FilterBar project functionality."""

    def test_filter_changed_message_has_project_fields(self) -> None:
        """Test FilterChanged message includes project fields."""
        try:
            from tracecraft.tui.widgets.filter_bar import TEXTUAL_AVAILABLE, FilterBar

            if TEXTUAL_AVAILABLE:
                msg = FilterBar.FilterChanged(
                    filter_text="test",
                    show_errors_only=False,
                    project_id="proj-123",
                    project_name="Test Project",
                )
                assert msg.filter_text == "test"
                assert msg.show_errors_only is False
                assert msg.project_id == "proj-123"
                assert msg.project_name == "Test Project"
        except ImportError:
            pass

    def test_filter_changed_message_defaults(self) -> None:
        """Test FilterChanged message has correct defaults."""
        try:
            from tracecraft.tui.widgets.filter_bar import TEXTUAL_AVAILABLE, FilterBar

            if TEXTUAL_AVAILABLE:
                msg = FilterBar.FilterChanged(filter_text="test")
                assert msg.filter_text == "test"
                assert msg.show_errors_only is False
                assert msg.project_id is None
                assert msg.project_name is None
        except ImportError:
            pass


class TestCLIUICommand:
    """Tests for the CLI UI command."""

    def test_ui_command_exists(self) -> None:
        """Test UI command is registered."""
        from tracecraft.cli.main import ui

        # Verify the ui function exists and is callable
        assert callable(ui)

    def test_ui_command_in_app(self) -> None:
        """Test UI command is in the app."""
        from tracecraft.cli.main import app

        # Get command info from the typer app
        # The commands are stored in registered_commands with callback attributes
        command_callbacks = [
            cmd.callback.__name__ for cmd in app.registered_commands if cmd.callback
        ]
        assert "ui" in command_callbacks
