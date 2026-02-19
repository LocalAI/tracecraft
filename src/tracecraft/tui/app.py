"""
Trace Craft Terminal UI - LangSmith-style trace explorer.

A real-time, interactive terminal interface for exploring
and debugging LLM/Agent traces with table and waterfall views.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from uuid import UUID

# Import theme for consistent styling
from tracecraft.tui.theme import (
    ACCENT_AMBER,
    BACKGROUND,
    BORDER,
    DANGER_RED,
    INFO_BLUE,
    SURFACE,
    SURFACE_HIGHLIGHT,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Vertical
    from textual.widgets import Footer, Header

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    App = object
    Binding = None

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun, Step
    from tracecraft.tui.data.loader import TraceLoader


def _get_bindings() -> list[Any]:
    """Get keybindings for the app (only when textual is available)."""
    if not TEXTUAL_AVAILABLE or Binding is None:
        return []
    # Note: priority=True ensures app-level bindings work regardless of focused widget
    return [
        Binding("q", "quit", "Quit", priority=True),
        Binding("r", "refresh", "Refresh", priority=True),
        Binding("slash", "filter", "Filter", priority=True),
        Binding("tab", "cycle_view", "Cycle View", priority=True),
        Binding("i", "show_input", "Input", priority=True),
        Binding("o", "show_output", "Output", priority=True),
        Binding("a", "show_detail", "Detail", priority=True),
        Binding("p", "playground", "Play", priority=True),
        Binding("question_mark", "help", "Help", priority=True),
        Binding("escape", "back", "Back", priority=True),
        Binding("plus", "grow_panel", "+Panel", show=False, priority=True),
        Binding("equal", "grow_panel", "+Panel", show=False, priority=True),
        Binding("minus", "shrink_panel", "-Panel", show=False, priority=True),
        Binding("bracketleft", "shrink_left_panel", "←Div", show=False, priority=True),
        Binding("bracketright", "grow_left_panel", "Div→", show=False, priority=True),
        Binding("H", "shrink_left_panel", "←Div", show=True, priority=True),
        Binding("L", "grow_left_panel", "Div→", show=True, priority=True),
        Binding("m", "mark_trace", "Mark", priority=True),
        Binding("C", "compare_traces", "Compare", priority=True),
        Binding("V", "view_comparison", "View Result", priority=True),
        Binding("D", "delete_trace", "Delete", priority=True),
        Binding("N", "edit_notes", "Notes", priority=True),
        Binding("A", "toggle_archive", "Archive", priority=True),
    ]


class TraceCraftApp(App if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Main Trace Craft TUI application.

    Provides a LangSmith-style interface for exploring traces with:
    - Table view showing all traces on the left
    - Waterfall view showing step timing on the right (when expanded)
    - Input/output inspection in detail panels below waterfall
    - Filtering and search
    - Keyboard-driven navigation
    """

    TITLE = "TRACECRAFT"
    SUB_TITLE = "Trace Craft"

    CSS = f"""
    /* ============================================
       NOIR SIGNAL Theme - Main Application
       ============================================ */

    /* Base screen */
    Screen {{
        background: {BACKGROUND};
    }}

    /* Main layout */
    #main {{
        layout: vertical;
        height: 100%;
        background: {BACKGROUND};
    }}

    /* Content area - horizontal split */
    #content {{
        layout: horizontal;
        height: 1fr;
    }}

    /* Left panel - trace table (full height) */
    #left-panel {{
        width: 45%;
        min-width: 35;
        background: {SURFACE};
        border: none;
        border-right: solid {BORDER};
        padding: 0;
    }}

    #trace-table {{
        height: 1fr;
        background: {SURFACE};
    }}

    /* Right panel - waterfall + detail panels */
    #right-panel {{
        width: 55%;
        padding: 0;
        background: {BACKGROUND};
    }}

    /* Waterfall view - hidden by default, shown on right when expanded */
    #waterfall-view {{
        display: none;
        height: auto;
        min-height: 8;
        max-height: 18;
        background: {SURFACE};
        border: solid {BORDER};
        margin: 1;
    }}

    #waterfall-view.expanded {{
        display: block;
    }}

    /* Detail panels container - fills remaining space */
    #detail-panels {{
        height: 1fr;
        padding: 0 1 0 1;
    }}

    /* Metrics panel - compact, auto height */
    #metrics {{
        height: auto;
        min-height: 5;
        max-height: 10;
        background: {SURFACE};
        border: solid {BORDER};
        margin-bottom: 1;
    }}

    /* IO Viewer - takes remaining space */
    #io-viewer {{
        height: 1fr;
        min-height: 10;
        background: {SURFACE};
        border: solid {BORDER};
        scrollbar-gutter: stable;
    }}

    /* Filter bar styling is defined in filter_bar.py DEFAULT_CSS */

    /* Header styling - DRAMATIC: Amber accent with breathing room */
    Header {{
        dock: top;
        width: 100%;
        height: 3;
        background: {BACKGROUND};
        color: {ACCENT_AMBER};
        text-style: bold;
        border-bottom: solid {ACCENT_AMBER};
    }}

    /* Footer styling */
    Footer {{
        background: {SURFACE};
    }}

    Footer > .footer--key {{
        background: {BACKGROUND};
        color: {ACCENT_AMBER};
    }}

    Footer > .footer--description {{
        color: {TEXT_MUTED};
    }}

    /* DataTable styling */
    DataTable {{
        background: {SURFACE};
        color: {TEXT_PRIMARY};
    }}

    DataTable:focus {{
        border: solid {ACCENT_AMBER};
    }}

    DataTable > .datatable--cursor {{
        background: {SURFACE_HIGHLIGHT};
        color: {ACCENT_AMBER};
    }}

    DataTable > .datatable--header {{
        background: {SURFACE};
        color: {TEXT_MUTED};
        text-style: bold;
    }}

    /* Button styling */
    Button {{
        background: {SURFACE};
        color: {TEXT_PRIMARY};
        border: solid {BORDER};
        text-style: bold;
    }}

    Button:hover {{
        background: {SURFACE_HIGHLIGHT};
        border: solid {ACCENT_AMBER};
    }}

    Button:focus {{
        background: {SURFACE_HIGHLIGHT};
        border: solid {ACCENT_AMBER};
        color: {ACCENT_AMBER};
    }}

    /* Input styling */
    Input {{
        background: {BACKGROUND};
        color: {TEXT_PRIMARY};
        border: solid {BORDER};
    }}

    Input:focus {{
        border: solid {ACCENT_AMBER};
    }}

    Input > .input--placeholder {{
        color: {TEXT_MUTED};
    }}

    /* OptionList styling */
    OptionList {{
        background: {SURFACE};
        border: solid {BORDER};
    }}

    OptionList:focus {{
        border: solid {ACCENT_AMBER};
    }}

    OptionList > .option-list--option {{
        color: {TEXT_PRIMARY};
    }}

    OptionList > .option-list--option-highlighted {{
        background: {SURFACE_HIGHLIGHT};
        color: {ACCENT_AMBER};
    }}

    /* Scrollbar styling */
    Scrollbar {{
        background: {BACKGROUND};
    }}

    Scrollbar > .scrollbar--bar {{
        background: {BORDER};
    }}

    Scrollbar > .scrollbar--bar:hover {{
        background: {TEXT_MUTED};
    }}

    /* Toast notifications */
    Toast {{
        background: {SURFACE};
        border: solid {BORDER};
        color: {TEXT_PRIMARY};
    }}

    Toast.-information {{
        border: solid {INFO_BLUE};
    }}

    Toast.-warning {{
        border: solid {ACCENT_AMBER};
    }}

    Toast.-error {{
        border: solid {DANGER_RED};
    }}
    """

    BINDINGS = _get_bindings()

    def __init__(
        self,
        trace_source: str | None = None,
        watch: bool = False,
        env: str | None = None,
    ) -> None:
        """
        Initialize the TUI.

        Args:
            trace_source: Multi-source string (JSONL, SQLite, MLflow).
                Supports: file.jsonl, file.db, sqlite:///path, mlflow://host/exp
            watch: If True, watch for new traces in real-time.
            env: Environment name to use for configuration (development, staging, etc.)
        """
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__()
        self.trace_source = trace_source
        self.watch = watch
        self.env = env
        self._loader: TraceLoader | None = None
        self._runs: list[AgentRun] = []
        self._current_run: AgentRun | None = None
        self._current_step: Step | None = None
        self._waterfall_expanded: bool = False
        self._waterfall_height: int = 18  # Default max-height
        self._left_panel_width: int = 45  # Default width percentage
        # Comparison state
        self._marked_trace_id: UUID | None = None
        # Dict mapping trace_id -> list of ComparisonResults involving that trace
        self._comparisons: dict[UUID, list[Any]] = {}

    def compose(self) -> ComposeResult:
        """Compose the UI layout."""
        from tracecraft.tui.widgets.filter_bar import FilterBar
        from tracecraft.tui.widgets.io_viewer import IOViewer, ModeIndicator
        from tracecraft.tui.widgets.metrics_panel import MetricsPanel
        from tracecraft.tui.widgets.trace_table import TraceTable
        from tracecraft.tui.widgets.waterfall_view import WaterfallView

        yield Header()

        with Container(id="main"):
            yield FilterBar(id="filter-bar")

            with Container(id="content"):
                # Left panel: Trace table only
                with Vertical(id="left-panel"):
                    yield TraceTable(id="trace-table")

                # Right panel: Waterfall (top) + Detail panels (bottom)
                with Vertical(id="right-panel"):
                    yield WaterfallView(id="waterfall-view")
                    with Vertical(id="detail-panels"):
                        yield MetricsPanel(id="metrics")
                        yield ModeIndicator(id="mode-indicator")
                        yield IOViewer(id="io-viewer")

        yield Footer()

    async def on_mount(self) -> None:
        """Called when app is mounted."""
        from tracecraft.tui.data.loader import TraceLoader, get_loader_for_env

        if self.trace_source:
            try:
                self._loader = TraceLoader.from_source(self.trace_source)
            except ValueError as e:
                self.notify(str(e), title="Load Error", severity="error")
                return
        else:
            from tracecraft.core.init import find_existing_database, needs_setup

            if needs_setup():
                self._show_setup_wizard()
                return
            elif find_existing_database():
                db_path = find_existing_database()
                try:
                    self._loader = TraceLoader.from_source(f"sqlite://{db_path}")
                except ValueError as e:
                    self.notify(str(e), title="Load Error", severity="error")
                    return
            else:
                self._loader = get_loader_for_env(self.env)

        self._load_runs()
        self._update_table()
        self._load_projects()
        self._load_sessions()

        if self.watch:
            self.set_interval(1.0, self._poll_for_updates)

    def _show_setup_wizard(self) -> None:
        """Show the setup wizard for first-time users."""
        from tracecraft.tui.screens.setup_wizard import SetupChoice, SetupWizardScreen

        def on_wizard_complete(result: Any) -> None:
            if result is None or result.choice == SetupChoice.CANCEL:
                self.exit()
                return

            if result.choice == SetupChoice.OPEN_FILE:
                self.notify(
                    "Use: tracecraft ui <path/to/file.db>",
                    title="Open File",
                    severity="information",
                    timeout=5,
                )
                self.exit()
                return

            if result.source:
                self._load_source_and_start(result.source)
            else:
                self.exit()

        self.push_screen(SetupWizardScreen(), on_wizard_complete)

    def _load_source_and_start(self, source: str) -> None:
        """Load a source and start the normal TUI flow."""
        from tracecraft.tui.data.loader import TraceLoader

        try:
            self._loader = TraceLoader.from_source(source)
            self._load_runs()
            self._update_table()
            self._load_projects()
            self._load_sessions()

            if self.watch:
                self.set_interval(1.0, self._poll_for_updates)

        except ValueError as e:
            self.notify(str(e), title="Load Error", severity="error")

    def _load_runs(self) -> None:
        """Load runs from the loader."""
        if self._loader:
            self._runs = self._loader.list_traces(limit=1000)

    def _load_projects(self) -> None:
        """Load projects and update the FilterBar dropdown."""
        from tracecraft.tui.widgets.filter_bar import FilterBar

        if not self._loader or not self._loader.is_sqlite:
            return

        try:
            projects_data = self._loader.store.list_projects()
            if projects_data:
                # Convert to (project_id, project_name) tuples
                projects = [(p["id"], p.get("name", p["id"])) for p in projects_data]
                filter_bar = self.query_one("#filter-bar", FilterBar)
                filter_bar.set_projects(projects)
        except Exception:  # noqa: BLE001
            # Projects feature may not be supported by all stores
            pass  # nosec B110

    def _load_sessions(self, project_id: str | None = None) -> None:
        """Load sessions and update the FilterBar dropdown."""
        from tracecraft.tui.widgets.filter_bar import FilterBar

        if not self._loader or not self._loader.is_sqlite:
            return

        try:
            sessions_data = self._loader.store.list_sessions(project_id=project_id)
            # Convert to (session_id, session_name) tuples
            sessions = [(s["id"], s.get("name", s["id"])) for s in sessions_data]
            filter_bar = self.query_one("#filter-bar", FilterBar)
            filter_bar.set_sessions(sessions)
        except Exception:  # noqa: BLE001
            # Sessions feature may not be supported by all stores
            pass  # nosec B110

    def on_filter_bar_project_changed(self, event: Any) -> None:
        """Handle project selection change - reload sessions for that project."""
        self._load_sessions(project_id=event.project_id)

    async def _poll_for_updates(self) -> None:
        """Poll for new traces."""
        if self._loader:
            self._loader.refresh()
            new_count = self._loader.count()
            if new_count != len(self._runs):
                self._load_runs()
                self._update_table()

    def _build_name_mappings(self) -> tuple[dict[str, str], dict[str, str]]:
        """
        Build project_id -> name and session_id -> name mappings.

        Returns:
            Tuple of (project_names, session_names) dicts.
        """
        project_names: dict[str, str] = {}
        session_names: dict[str, str] = {}

        if self._loader and self._loader.is_sqlite:
            try:
                for p in self._loader.store.list_projects():
                    project_names[p["id"]] = p.get("name", p["id"])
                for s in self._loader.store.list_sessions():
                    session_names[s["id"]] = s.get("name", s["id"])
            except Exception:  # noqa: BLE001
                pass  # nosec B110

        return project_names, session_names

    def _update_table(self) -> None:
        """Update the trace table with current data."""
        from tracecraft.tui.widgets.filter_bar import FilterBar
        from tracecraft.tui.widgets.trace_table import TraceTable

        table = self.query_one("#trace-table", TraceTable)

        # Set name mappings for project/session columns
        project_names, session_names = self._build_name_mappings()
        table.set_name_mappings(project_names, session_names)

        table.show_traces(self._runs)

        filter_bar = self.query_one("#filter-bar", FilterBar)
        total = self._loader.count() if self._loader else len(self._runs)
        filter_bar.update_result_count(len(self._runs), total)

    # Event handlers for TraceTable

    def on_trace_table_trace_highlighted(self, event: Any) -> None:
        """Handle trace highlight in table (cursor movement)."""
        if event.trace:
            self._current_run = event.trace
            self._current_step = None
            # Auto-show waterfall for highlighted trace (without changing focus)
            self._show_waterfall_for_trace(event.trace)
            self._update_detail_panels()

    def on_trace_table_trace_selected(self, event: Any) -> None:
        """Handle trace selection in table (Enter pressed or click)."""
        if event.trace:
            self._current_run = event.trace
            # Waterfall auto-shows on highlight, so just focus it
            if self._waterfall_expanded:
                from tracecraft.tui.widgets.waterfall_view import WaterfallView

                waterfall = self.query_one("#waterfall-view", WaterfallView)
                waterfall.focus()

    # Event handlers for WaterfallView

    def on_waterfall_view_step_highlighted(self, event: Any) -> None:
        """Handle step highlight in waterfall (cursor movement)."""
        if event.step:
            self._current_step = event.step
            self._update_detail_panels()

    def on_waterfall_view_step_selected(self, event: Any) -> None:
        """Handle step selection in waterfall (Enter pressed)."""
        if event.step:
            self._current_step = event.step
            self._update_detail_panels()

    # Waterfall expansion

    def _show_waterfall_for_trace(self, trace: AgentRun) -> None:
        """Show waterfall for a trace without changing focus."""
        from tracecraft.tui.widgets.waterfall_view import WaterfallView

        waterfall = self.query_one("#waterfall-view", WaterfallView)
        waterfall.show_trace(trace)
        waterfall.add_class("expanded")
        self._waterfall_expanded = True

    def _expand_waterfall(self, trace: AgentRun) -> None:
        """Expand the waterfall view for a trace and focus it."""
        from tracecraft.tui.widgets.waterfall_view import WaterfallView

        waterfall = self.query_one("#waterfall-view", WaterfallView)
        waterfall.show_trace(trace)
        waterfall.add_class("expanded")
        waterfall.focus()
        self._waterfall_expanded = True

    def _collapse_waterfall(self) -> None:
        """Collapse the waterfall view."""
        from tracecraft.tui.widgets.trace_table import TraceTable
        from tracecraft.tui.widgets.waterfall_view import WaterfallView

        waterfall = self.query_one("#waterfall-view", WaterfallView)
        waterfall.remove_class("expanded")
        waterfall.clear()
        self._waterfall_expanded = False
        self._current_step = None

        # Focus back on table
        table = self.query_one("#trace-table", TraceTable)
        table.focus()

        # Update panels to show run-level info
        self._update_detail_panels()

    def _update_detail_panels(self) -> None:
        """Update detail panels based on current selection."""
        from tracecraft.tui.widgets.io_viewer import IOViewer, ModeIndicator
        from tracecraft.tui.widgets.metrics_panel import MetricsPanel

        metrics = self.query_one("#metrics", MetricsPanel)
        io_viewer = self.query_one("#io-viewer", IOViewer)
        mode_indicator = self.query_one("#mode-indicator", ModeIndicator)

        if self._current_step:
            metrics.show_step(self._current_step)
            io_viewer.show_step(self._current_step)
            mode_indicator.set_has_error(bool(self._current_step.error))
        elif self._current_run:
            metrics.show_run(self._current_run)
            io_viewer.show_run(self._current_run)
            mode_indicator.set_has_error(bool(self._current_run.error))
        else:
            metrics.show_run(None)
            io_viewer.show_run(None)
            mode_indicator.set_has_error(False)

    def on_filter_bar_filter_changed(self, event: Any) -> None:
        """Handle filter changes."""
        from tracecraft.storage.base import TraceQuery
        from tracecraft.tui.widgets.filter_bar import FilterBar
        from tracecraft.tui.widgets.trace_table import TraceTable

        if not self._loader:
            return

        # Build query from filter options
        query = TraceQuery(
            name_contains=event.filter_text if event.filter_text else None,
            has_error=True if event.show_errors_only else None,
            project_id=event.project_id if event.project_id else None,
            session_id=event.session_id if event.session_id else None,
        )

        filtered_runs = self._loader.query_traces(query)

        table = self.query_one("#trace-table", TraceTable)
        is_filtered = bool(
            event.filter_text or event.show_errors_only or event.project_id or event.session_id
        )
        table.show_traces(filtered_runs, is_filtered=is_filtered)

        filter_bar = self.query_one("#filter-bar", FilterBar)
        total = self._loader.count()
        filter_bar.update_result_count(len(filtered_runs), total)

    # Actions

    def action_filter(self) -> None:
        """Focus the filter bar."""
        from tracecraft.tui.widgets.filter_bar import FilterBar

        self.query_one("#filter-bar", FilterBar).focus_input()

    def action_refresh(self) -> None:
        """Refresh the trace data."""
        if self._loader:
            self._loader.refresh()
            self._load_runs()
            self._update_table()
            self.notify("Data refreshed.", title="REFRESH", timeout=2)

    def action_cycle_view(self) -> None:
        """Cycle through IO viewer modes."""
        from tracecraft.tui.widgets.io_viewer import IOViewer, ModeIndicator

        io_viewer = self.query_one("#io-viewer", IOViewer)
        io_viewer.cycle_mode()
        self.query_one("#mode-indicator", ModeIndicator).set_mode(io_viewer.mode)

    def action_show_input(self) -> None:
        """Switch to input view mode (i key)."""
        from tracecraft.tui.widgets.io_viewer import IOViewer, ModeIndicator

        io_viewer = self.query_one("#io-viewer", IOViewer)
        io_viewer.set_mode(IOViewer.MODE_INPUT)
        self.query_one("#mode-indicator", ModeIndicator).set_mode(io_viewer.mode)

    def action_show_output(self) -> None:
        """Switch to output view mode (o key)."""
        from tracecraft.tui.widgets.io_viewer import IOViewer, ModeIndicator

        io_viewer = self.query_one("#io-viewer", IOViewer)
        io_viewer.set_mode(IOViewer.MODE_OUTPUT)
        self.query_one("#mode-indicator", ModeIndicator).set_mode(io_viewer.mode)

    def action_show_detail(self) -> None:
        """Switch to detail/attributes view mode (a key)."""
        from tracecraft.tui.widgets.io_viewer import IOViewer, ModeIndicator

        io_viewer = self.query_one("#io-viewer", IOViewer)
        io_viewer.set_mode(IOViewer.MODE_DETAIL)
        self.query_one("#mode-indicator", ModeIndicator).set_mode(io_viewer.mode)

    def action_back(self) -> None:
        """Go back - collapse waterfall OR clear filter."""
        from tracecraft.tui.widgets.filter_bar import FilterBar

        # If waterfall is expanded, collapse it first
        if self._waterfall_expanded:
            self._collapse_waterfall()
            return

        # Otherwise clear filter
        filter_bar = self.query_one("#filter-bar", FilterBar)
        if filter_bar.filter_text or filter_bar.show_errors_only:
            filter_bar.clear()
        else:
            self._current_run = None
            self._current_step = None
            self._update_detail_panels()

    def action_playground(self) -> None:
        """Open the playground for the selected LLM step."""
        from tracecraft.core.models import StepType

        if self._current_step is None:
            self.notify(
                "No step selected. Expand a trace and select a step.",
                title="NO SELECTION",
                severity="warning",
            )
            return

        if self._current_step.type == StepType.LLM:
            self._open_playground_for_step(self._current_step)
            return

        llm_steps = self._find_llm_steps_in_children(self._current_step)

        if not llm_steps:
            self.notify(
                f"No LLM steps in '{self._current_step.name}'. Select an LLM step.",
                title="NO LLM STEPS",
                severity="warning",
            )
            return

        if len(llm_steps) == 1:
            self._open_playground_for_step(llm_steps[0])
        else:
            from tracecraft.tui.screens.llm_picker import LLMPickerScreen

            def on_picker_result(step: Step | None) -> None:
                if step:
                    self._open_playground_for_step(step)

            self.push_screen(
                LLMPickerScreen(
                    llm_steps=llm_steps,
                    parent_name=self._current_step.name,
                ),
                on_picker_result,
            )

    def _find_llm_steps_in_children(self, step: Step) -> list[Step]:
        """Recursively find all LLM steps within a step's children."""
        from tracecraft.core.models import StepType

        llm_steps: list[Step] = []

        def search(children: list[Step]) -> None:
            for child in children:
                if child.type == StepType.LLM:
                    llm_steps.append(child)
                if child.children:
                    search(child.children)

        search(step.children)
        return llm_steps

    def _open_playground_for_step(self, step: Step) -> None:
        """Open the playground screen for a specific LLM step."""
        original_output = ""
        outputs = step.outputs or {}
        if "result" in outputs:
            original_output = str(outputs["result"])
        elif "content" in outputs:
            original_output = str(outputs["content"])
        elif outputs:
            original_output = str(outputs)

        store = None
        trace_id = None
        if self._loader and self._loader.is_sqlite and self._current_run:
            store = self._loader.store
            trace_id = str(self._current_run.id)

        from tracecraft.tui.screens.playground import PlaygroundScreen

        self.push_screen(
            PlaygroundScreen(
                step=step,
                original_output=original_output,
                store=store,
                trace_id=trace_id,
            )
        )

    def action_grow_panel(self) -> None:
        """Increase panel size (+/= key)."""
        if self._waterfall_expanded:
            # Increase waterfall height
            self._waterfall_height = min(35, self._waterfall_height + 3)
            waterfall = self.query_one("#waterfall-view")
            waterfall.styles.max_height = self._waterfall_height
            self.notify(f"Waterfall: {self._waterfall_height} lines", timeout=1)
        else:
            # Increase left panel width
            self._left_panel_width = min(70, self._left_panel_width + 5)
            left_panel = self.query_one("#left-panel")
            left_panel.styles.width = f"{self._left_panel_width}%"
            right_panel = self.query_one("#right-panel")
            right_panel.styles.width = f"{100 - self._left_panel_width}%"
            self.notify(
                f"Left: {self._left_panel_width}% | Right: {100 - self._left_panel_width}%",
                timeout=1,
            )

    def action_shrink_panel(self) -> None:
        """Decrease panel size (- key)."""
        if self._waterfall_expanded:
            # Decrease waterfall height
            self._waterfall_height = max(8, self._waterfall_height - 3)
            waterfall = self.query_one("#waterfall-view")
            waterfall.styles.max_height = self._waterfall_height
            self.notify(f"Waterfall: {self._waterfall_height} lines", timeout=1)
        else:
            # Decrease left panel width
            self._left_panel_width = max(25, self._left_panel_width - 5)
            left_panel = self.query_one("#left-panel")
            left_panel.styles.width = f"{self._left_panel_width}%"
            right_panel = self.query_one("#right-panel")
            right_panel.styles.width = f"{100 - self._left_panel_width}%"
            self.notify(
                f"Left: {self._left_panel_width}% | Right: {100 - self._left_panel_width}%",
                timeout=1,
            )

    def action_shrink_left_panel(self) -> None:
        """Shrink the left panel (move divider left)."""
        self._left_panel_width = max(25, self._left_panel_width - 5)
        left_panel = self.query_one("#left-panel")
        left_panel.styles.width = f"{self._left_panel_width}%"
        right_panel = self.query_one("#right-panel")
        right_panel.styles.width = f"{100 - self._left_panel_width}%"
        self.notify(
            f"Left: {self._left_panel_width}% | Right: {100 - self._left_panel_width}%",
            timeout=1,
        )

    def action_grow_left_panel(self) -> None:
        """Grow the left panel (move divider right)."""
        self._left_panel_width = min(70, self._left_panel_width + 5)
        left_panel = self.query_one("#left-panel")
        left_panel.styles.width = f"{self._left_panel_width}%"
        right_panel = self.query_one("#right-panel")
        right_panel.styles.width = f"{100 - self._left_panel_width}%"
        self.notify(
            f"Left: {self._left_panel_width}% | Right: {100 - self._left_panel_width}%",
            timeout=1,
        )

    def action_help(self) -> None:
        """Show help modal with all keybindings."""
        from tracecraft.tui.screens.help_screen import HelpScreen

        if any(isinstance(screen, HelpScreen) for screen in self.screen_stack):
            return

        self.push_screen(HelpScreen(context="Main App"))

    # Key handlers for app-level actions
    # This is a workaround for Textual binding resolution issues where
    # app-level bindings show as disabled even though the actions exist.

    async def on_key(self, event: Any) -> None:
        """Handle key events directly for app-level actions."""
        # Skip if we're in an input field (let the input handle the key)
        from textual.widgets import Input

        if isinstance(self.focused, Input):
            return

        key = event.key

        # Core app actions (some inherited actions are async)
        if key == "q":
            await self.action_quit()
            event.stop()
        elif key == "r":
            self.action_refresh()
            event.stop()
        elif key == "slash":
            self.action_filter()
            event.stop()
        elif key == "tab":
            self.action_cycle_view()
            event.stop()
        elif key == "i":
            self.action_show_input()
            event.stop()
        elif key == "o":
            self.action_show_output()
            event.stop()
        elif key == "a":
            self.action_show_detail()
            event.stop()
        elif key == "p":
            self.action_playground()
            event.stop()
        elif key == "question_mark":
            self.action_help()
            event.stop()
        elif key == "escape":
            self.action_back()
            event.stop()
        # Panel resizing
        elif key in ("plus", "equal"):
            self.action_grow_panel()
            event.stop()
        elif key == "minus":
            self.action_shrink_panel()
            event.stop()
        elif key == "bracketleft":
            self.action_shrink_left_panel()
            event.stop()
        elif key == "bracketright":
            self.action_grow_left_panel()
            event.stop()
        elif key == "H":
            self.action_shrink_left_panel()
            event.stop()
        elif key == "L":
            self.action_grow_left_panel()
            event.stop()
        # Comparison and trace management
        elif key == "m":
            self.action_mark_trace()
            event.stop()
        elif key == "C":
            self.action_compare_traces()
            event.stop()
        elif key == "V":
            self.action_view_comparison()
            event.stop()
        elif key == "D":
            self.action_delete_trace()
            event.stop()
        elif key == "N":
            self.action_edit_notes()
            event.stop()
        elif key == "A":
            self.action_toggle_archive()
            event.stop()

    # Comparison actions

    def action_mark_trace(self) -> None:
        """Mark the current trace for comparison."""
        from tracecraft.tui.widgets.trace_table import TraceTable

        # Use _current_run which is set by trace highlight events
        if not self._current_run:
            self.notify("No trace selected", severity="warning")
            return

        self._marked_trace_id = self._current_run.id
        table = self.query_one("#trace-table", TraceTable)
        table.set_marked_trace(self._current_run.id)
        self.notify(f"Marked: {self._current_run.name}", timeout=2)

    def action_compare_traces(self) -> None:
        """Compare the marked trace with the current trace."""
        from tracecraft.tui.screens.comparison_prompt_picker import ComparisonPromptPicker

        if not self._marked_trace_id:
            self.notify(
                "No trace marked. Press 'm' to mark a trace first.",
                severity="warning",
            )
            return

        # Use _current_run which is set by trace highlight events
        if not self._current_run:
            self.notify("No trace selected", severity="warning")
            return

        if self._current_run.id == self._marked_trace_id:
            self.notify("Cannot compare trace with itself", severity="warning")
            return

        def on_config_selected(result: tuple[str, str, str] | None) -> None:
            if result is None:
                return
            self._run_comparison(result)

        self.push_screen(ComparisonPromptPicker(), on_config_selected)

    def _run_comparison(self, config: tuple[str, str, str]) -> None:
        """Run the comparison with the selected configuration."""
        from tracecraft.comparison.models import ComparisonRequest

        prompt_id, model, provider = config

        # Use _current_run which is set by trace highlight events
        if not self._current_run or not self._marked_trace_id:
            return

        request = ComparisonRequest(
            trace_a_id=self._marked_trace_id,
            trace_b_id=self._current_run.id,
            prompt_id=prompt_id,
            model=model,
            provider=provider,
        )

        self.notify("Running comparison...", timeout=3)
        asyncio.create_task(self._execute_comparison(request))

    async def _execute_comparison(self, request: Any) -> None:
        """Execute the comparison in the background."""
        from tracecraft.comparison.runner import ComparisonRunner

        if not self._loader:
            self.notify("No data source available", severity="error")
            return

        runner = ComparisonRunner(self._loader.store)

        try:
            result = await runner.run_comparison(request)

            # Store result for both traces involved
            trace_a_id = request.trace_a_id
            trace_b_id = request.trace_b_id

            if trace_a_id not in self._comparisons:
                self._comparisons[trace_a_id] = []
            self._comparisons[trace_a_id].append(result)

            if trace_b_id not in self._comparisons:
                self._comparisons[trace_b_id] = []
            self._comparisons[trace_b_id].append(result)

            # Refresh bindings so "V View Result" becomes visible
            self.refresh_bindings()

            self.notify(
                "Comparison complete! Press V to view.",
                severity="information",
                timeout=5,
            )
        except Exception as e:
            self.notify(f"Comparison failed: {e}", severity="error")

    def action_view_comparison(self) -> None:
        """View comparison results for the current trace."""
        from tracecraft.tui.screens.comparison_result_viewer import ComparisonResultViewer

        if not self._current_run:
            self.notify("No trace selected", severity="warning")
            return

        trace_id = self._current_run.id
        comparisons = self._comparisons.get(trace_id, [])

        if not comparisons:
            self.notify(
                "No comparisons for this trace. Mark with 'm', then 'C' to compare.",
                severity="warning",
            )
            return

        def on_delete(result: Any) -> None:
            """Handle deletion of a comparison result."""
            self._delete_comparison(result)

        self.push_screen(ComparisonResultViewer(comparisons, on_delete=on_delete))

    def _delete_comparison(self, result: Any) -> None:
        """Delete a comparison result from all traces it's associated with."""
        trace_a_id = result.request.trace_a_id
        trace_b_id = result.request.trace_b_id

        # Remove from trace_a's list
        if trace_a_id in self._comparisons:
            self._comparisons[trace_a_id] = [
                c for c in self._comparisons[trace_a_id] if c.id != result.id
            ]
            if not self._comparisons[trace_a_id]:
                del self._comparisons[trace_a_id]

        # Remove from trace_b's list
        if trace_b_id in self._comparisons:
            self._comparisons[trace_b_id] = [
                c for c in self._comparisons[trace_b_id] if c.id != result.id
            ]
            if not self._comparisons[trace_b_id]:
                del self._comparisons[trace_b_id]

        # Refresh bindings to update "V View Result" visibility
        self.refresh_bindings()

    def has_comparisons_for_trace(self, trace_id: UUID) -> bool:
        """Check if a trace has any comparison results."""
        return trace_id in self._comparisons and len(self._comparisons[trace_id]) > 0

    def check_action(self, action: str, _parameters: tuple[object, ...]) -> bool | None:
        """Check if an action should be enabled.

        Used to conditionally enable/disable keybindings in the footer.
        """
        if action == "view_comparison":
            # Only enable "View Result" if current trace has comparison results
            if not self._current_run:
                return False
            return self.has_comparisons_for_trace(self._current_run.id)
        return None  # Default behavior for other actions

    # =========================================================================
    # Trace Management Actions (Delete, Notes, Archive)
    # =========================================================================

    def action_delete_trace(self) -> None:
        """Delete the current trace after confirmation."""
        from tracecraft.tui.screens.confirm_delete import ConfirmDeleteModal

        if not self._current_run:
            self.notify("No trace selected", severity="warning")
            return

        if not self._loader or not self._loader.store:
            self.notify("No data store available", severity="error")
            return

        trace = self._current_run
        store = self._loader.store  # Capture for closure

        def on_confirm(confirmed: bool) -> None:
            if not confirmed:
                return

            try:
                deleted = store.delete(str(trace.id))
                if deleted:
                    self.notify(f"Deleted: {trace.name}", timeout=2)
                    # Remove from local list and refresh table
                    self._runs = [r for r in self._runs if r.id != trace.id]
                    self._current_run = None
                    self._refresh_trace_table()
                else:
                    self.notify("Trace not found", severity="warning")
            except Exception as e:
                self.notify(f"Delete failed: {e}", severity="error")

        self.push_screen(ConfirmDeleteModal(trace), callback=on_confirm)

    def action_edit_notes(self) -> None:
        """Edit notes for the current trace."""
        from tracecraft.tui.screens.notes_editor import NotesEditorModal

        if not self._current_run:
            self.notify("No trace selected", severity="warning")
            return

        if not self._loader or not self._loader.store:
            self.notify("No data store available", severity="error")
            return

        trace = self._current_run
        store = self._loader.store  # Capture for closure

        # Get current notes
        try:
            current_notes = store.get_notes(str(trace.id))
        except NotImplementedError:
            self.notify("Notes not supported by this backend", severity="warning")
            return

        def on_save(notes: str | None) -> None:
            if notes is None:
                return  # Cancelled

            try:
                updated = store.set_notes(str(trace.id), notes)
                if updated:
                    self.notify("Notes saved", timeout=2)
                else:
                    self.notify("Trace not found", severity="warning")
            except NotImplementedError:
                self.notify("Notes not supported by this backend", severity="warning")
            except Exception as e:
                self.notify(f"Failed to save notes: {e}", severity="error")

        self.push_screen(NotesEditorModal(trace, current_notes), callback=on_save)

    def action_toggle_archive(self) -> None:
        """Toggle archive status of the current trace."""
        if not self._current_run:
            self.notify("No trace selected", severity="warning")
            return

        if not self._loader or not self._loader.store:
            self.notify("No data store available", severity="error")
            return

        trace = self._current_run

        try:
            is_archived = self._loader.store.is_archived(str(trace.id))
            if is_archived:
                success = self._loader.store.unarchive(str(trace.id))
                if success:
                    self.notify(f"Unarchived: {trace.name}", timeout=2)
                else:
                    self.notify("Trace not found", severity="warning")
            else:
                success = self._loader.store.archive(str(trace.id))
                if success:
                    self.notify(f"Archived: {trace.name}", timeout=2)
                    # Remove from current view if hiding archived
                    self._runs = [r for r in self._runs if r.id != trace.id]
                    self._current_run = None
                    self._refresh_trace_table()
                else:
                    self.notify("Trace not found", severity="warning")
        except NotImplementedError:
            self.notify("Archive not supported by this backend", severity="warning")
        except Exception as e:
            self.notify(f"Archive operation failed: {e}", severity="error")

    def _refresh_trace_table(self) -> None:
        """Refresh the trace table with current runs."""
        from tracecraft.tui.widgets.trace_table import TraceTable

        try:
            table = self.query_one("#trace-table", TraceTable)
            table.clear()
            for run in self._runs:
                table.add_trace(run)
        except Exception:  # nosec B110
            pass  # Table might not be mounted yet
