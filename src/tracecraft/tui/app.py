"""
Trace Craft Terminal UI - k9s-style trace explorer.

A real-time, interactive terminal interface for exploring
and debugging LLM/Agent traces.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import Footer, Header, Static

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    App = object
    Binding = None

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun, Step
    from tracecraft.tui.data.loader import TraceLoader
    from tracecraft.tui.widgets.view_toggle import ViewMode


def _get_bindings() -> list[Any]:
    """Get keybindings for the app (only when textual is available)."""
    if not TEXTUAL_AVAILABLE or Binding is None:
        return []
    return [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("slash", "filter", "Filter"),
        Binding("i", "show_input", "Input"),
        Binding("o", "show_output", "Output"),
        Binding("a", "show_attributes", "Attrs"),
        Binding("d", "show_json", "Detail"),  # Full JSON detail view
        Binding("e", "show_error", "Error"),
        Binding("p", "playground", "Play"),  # Open playground for LLM steps
        Binding("P", "project_manager", "Projects"),  # Shift+P opens project manager
        Binding("A", "assign_project", "Assign"),  # Shift+A assigns trace to project
        Binding("M", "agent_manager", "Agents"),  # Shift+M opens agent manager
        Binding("B", "assign_agent", "Assign Agent"),  # Shift+B assigns trace to agent
        Binding("tab", "cycle_view", "Cycle View"),
        Binding("t", "toggle_format", "Table/JSON"),  # Toggle display format
        Binding("question_mark", "help", "Help"),
        Binding("escape", "back", "Back"),
        # View mode switching
        Binding("1", "view_traces", "Traces", show=False),
        Binding("2", "view_projects", "Projects", show=False),
        Binding("3", "view_agents", "Agents", show=False),
        Binding("4", "view_evals", "Evals", show=False),
        Binding("E", "create_eval_set", "New Eval"),  # Shift+E creates eval set
        Binding("R", "run_eval", "Run Eval"),  # Run evaluation on selected set
        Binding("ctrl+e", "add_to_eval", "Add to Eval"),  # Add trace/step to eval set
        Binding("C", "create_eval_case", "New Case"),  # Shift+C creates manual eval case
        Binding("g", "goto_source", "Goto Source"),  # Jump to source trace from eval case
        Binding("V", "show_trace_evals", "View Evals"),  # Shift+V shows eval associations
        # Eval viewing actions (when eval set selected)
        Binding("c", "view_eval_cases", "Cases"),  # View cases for selected eval
        Binding("H", "view_eval_history", "History"),  # Shift+H shows run history
        Binding("L", "view_latest_run", "Latest"),  # Shift+L shows latest run results
        # j/k navigation is built into Textual's Tree widget
    ]


class TraceCraftApp(App if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Main Trace Craft TUI application.

    Provides a k9s-style interface for exploring traces with:
    - Real-time trace updates
    - Hierarchical tree navigation
    - Input/output inspection
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

    #content {{
        layout: horizontal;
        height: 1fr;
    }}

    /* Tree panel - DRAMATIC: Add top padding, minimal borders */
    #tree-panel {{
        width: 40%;
        min-width: 30;
        background: {SURFACE};
        border: none;
        border-right: solid {BORDER};
        padding: 1 1 0 1;
    }}

    #tree-panel .panel-title {{
        text-style: bold;
        color: {TEXT_MUTED};
        padding: 1 0;
    }}

    #run-tree {{
        height: 1fr;
        background: {SURFACE};
    }}

    /* Detail panel - DRAMATIC: Add top padding */
    #detail-panel {{
        width: 60%;
        padding: 1 1 0 1;
        background: {BACKGROUND};
    }}

    #metrics {{
        height: auto;
        max-height: 15;
        margin-bottom: 1;
        background: {SURFACE};
        border: none;
        border-bottom: solid {BORDER};
    }}

    #io-viewer {{
        height: 1fr;
        background: {SURFACE};
        border: solid {BORDER};
        scrollbar-gutter: stable;
    }}

    /* Filter bar - Clean underline style */
    FilterBar {{
        height: 3;
        background: {SURFACE};
        padding: 0 1;
        border-bottom: solid {BORDER};
    }}

    /* Status bar */
    #status-bar {{
        height: 1;
        dock: bottom;
        background: {SURFACE};
        padding: 0 1;
        color: {TEXT_MUTED};
    }}

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

    /* Tree widget */
    Tree {{
        background: {SURFACE};
        color: {TEXT_PRIMARY};
    }}

    Tree:focus {{
        border: solid {ACCENT_AMBER};
    }}

    Tree > .tree--cursor {{
        background: {SURFACE_HIGHLIGHT};
        color: {ACCENT_AMBER};
    }}

    Tree > .tree--highlight {{
        background: {SURFACE_HIGHLIGHT};
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
        self._runs: list[AgentRun] = []  # Cached runs for display
        self._current_run: AgentRun | None = None
        self._current_step: Step | None = None
        self._current_project: dict[str, Any] | None = None  # Current project filter
        self._current_agent: dict[str, Any] | None = None  # Current agent filter
        self._view_mode: ViewMode | None = None  # Current view mode (imported on demand)

    def compose(self) -> ComposeResult:
        """Compose the UI layout."""
        from tracecraft.tui.widgets.breadcrumb import Breadcrumb
        from tracecraft.tui.widgets.filter_bar import FilterBar
        from tracecraft.tui.widgets.io_viewer import IOViewer, ModeIndicator
        from tracecraft.tui.widgets.metrics_panel import MetricsPanel
        from tracecraft.tui.widgets.run_tree import RunTree
        from tracecraft.tui.widgets.view_toggle import ViewToggle

        yield Header()
        yield Breadcrumb(id="breadcrumb")

        with Container(id="main"):
            yield FilterBar(id="filter-bar")

            with Horizontal(id="content"):
                # Left panel: Run/Step tree
                with Vertical(id="tree-panel"):
                    yield ViewToggle(id="view-toggle")
                    yield RunTree(id="run-tree")

                # Right panel: Details
                with Vertical(id="detail-panel"):
                    yield MetricsPanel(id="metrics")
                    yield ModeIndicator(id="mode-indicator")
                    yield IOViewer(id="io-viewer")

        yield Footer()

    async def on_mount(self) -> None:
        """Called when app is mounted."""
        from tracecraft.tui.data.loader import TraceLoader, get_loader_for_env

        if self.trace_source:
            # Use explicit source
            try:
                self._loader = TraceLoader.from_source(self.trace_source)
            except ValueError as e:
                self.notify(str(e), title="Load Error", severity="error")
                return
        else:
            # Check if setup is needed (no config or database exists)
            from tracecraft.core.init import find_existing_database, needs_setup

            if needs_setup():
                # Show setup wizard for first-time users
                self._show_setup_wizard()
                return
            elif find_existing_database():
                # Use existing database
                db_path = find_existing_database()
                try:
                    self._loader = TraceLoader.from_source(f"sqlite://{db_path}")
                except ValueError as e:
                    self.notify(str(e), title="Load Error", severity="error")
                    return
            else:
                # Use environment configuration as fallback
                self._loader = get_loader_for_env(self.env)

        # Initialize view mode
        from tracecraft.tui.widgets.view_toggle import ViewMode

        self._view_mode = ViewMode.TRACES

        # Initialize breadcrumb
        self._update_breadcrumb()

        # Load initial runs
        self._load_runs()
        self._update_tree()

        if self.watch:
            self.set_interval(1.0, self._poll_for_updates)

    def _show_setup_wizard(self) -> None:
        """Show the setup wizard for first-time users."""
        from tracecraft.tui.screens.setup_wizard import SetupChoice, SetupWizardScreen

        def on_wizard_complete(result: Any) -> None:
            if result is None or result.choice == SetupChoice.CANCEL:
                # User cancelled - exit app
                self.exit()
                return

            if result.choice == SetupChoice.OPEN_FILE:
                # For now, show a notification - file picker is complex
                # In future, could integrate with a file picker dialog
                self.notify(
                    "Use: tracecraft ui <path/to/file.db>",
                    title="Open File",
                    severity="information",
                    timeout=5,
                )
                self.exit()
                return

            # For GLOBAL, LOCAL, and DEMO - use the source from result
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
            self._update_tree()

            if self.watch:
                self.set_interval(1.0, self._poll_for_updates)

        except ValueError as e:
            self.notify(str(e), title="Load Error", severity="error")

    def _load_runs(self) -> None:
        """Load runs from the loader."""
        if self._loader:
            self._runs = self._loader.list_traces(limit=1000)

    async def _poll_for_updates(self) -> None:
        """Poll for new traces."""
        if self._loader:
            # Refresh cache and reload
            self._loader.refresh()
            new_count = self._loader.count()
            if new_count != len(self._runs):
                self._load_runs()
                self._update_tree()

    def _update_tree(self) -> None:
        """Update the run tree with current data."""
        from tracecraft.tui.widgets.view_toggle import ViewMode

        # Use view-aware update if view mode is set
        if self._view_mode is not None:
            self._update_tree_for_view()
        else:
            # Fallback for initial load before view mode is set
            from tracecraft.tui.widgets.filter_bar import FilterBar
            from tracecraft.tui.widgets.run_tree import RunTree

            tree = self.query_one("#run-tree", RunTree)
            tree.show_traces(self._runs)

            # Update result count
            filter_bar = self.query_one("#filter-bar", FilterBar)
            total = self._loader.count() if self._loader else len(self._runs)
            filter_bar.update_result_count(len(self._runs), total)

    def _update_breadcrumb(self, segment: dict[str, Any] | None = None) -> None:
        """Update the breadcrumb navigation.

        If segment is provided, pushes it. Otherwise, resets to current view mode.
        """
        from tracecraft.tui.widgets.breadcrumb import Breadcrumb
        from tracecraft.tui.widgets.view_toggle import ViewMode

        try:
            breadcrumb = self.query_one("#breadcrumb", Breadcrumb)
        except Exception:
            return  # Breadcrumb not mounted yet

        if segment is not None:
            # Push a new segment
            breadcrumb.push(segment["label"], segment.get("data", {}))
        else:
            # Reset breadcrumb to show current view mode
            breadcrumb.clear()
            view_name = "Traces"
            if self._view_mode == ViewMode.PROJECTS:
                view_name = "Projects"
            elif self._view_mode == ViewMode.AGENTS:
                view_name = "Agents"
            elif self._view_mode == ViewMode.EVALS:
                view_name = "Evals"
            breadcrumb.push(view_name, {"type": "view", "mode": self._view_mode})

    def on_tree_node_selected(self, event: Any) -> None:  # noqa: ARG002
        """Handle tree node selection (Enter key)."""
        self._handle_tree_selection(is_activation=True)

    def on_tree_node_highlighted(self, event: Any) -> None:  # noqa: ARG002
        """Handle tree node highlight (navigation with j/k or arrows)."""
        self._handle_tree_selection(is_activation=False)

    def _handle_tree_selection(self, *, is_activation: bool = False) -> None:
        """
        Handle tree selection based on view mode.

        Args:
            is_activation: True if this is an Enter key press (drill-down action).
        """
        from tracecraft.tui.widgets.run_tree import RunTree, TreeViewMode

        tree = self.query_one("#run-tree", RunTree)
        data = tree.get_selected_data()

        if not data:
            return

        node_type = data.get("type")

        # Handle project selection
        if node_type == "project":
            if is_activation:
                # Drill down into project - show its traces
                self._drill_into_project(data)
            else:
                # Just show project info in detail panel
                self._show_project_details(data)
            return

        # Handle agent selection
        if node_type == "agent":
            if is_activation:
                # Drill down into agent - show its traces
                self._drill_into_agent(data)
            else:
                # Just show agent info in detail panel
                self._show_agent_details(data)
            return

        # Handle eval selection
        if node_type == "eval":
            if is_activation:
                # Drill down into eval - show its cases or run it
                self._drill_into_eval(data)
            else:
                # Just show eval info in detail panel
                self._show_eval_details(data)
            return

        # Handle folder selection (in project tree view)
        if node_type == "folder":
            if is_activation:
                # Expand/collapse folder or load more items
                self._handle_folder_activation(data)
            return

        # Handle trace selection (dict from project tree view)
        if node_type == "trace":
            if is_activation:
                # Load full trace and show details
                self._drill_into_trace(data)
            else:
                # Show trace preview in detail panel
                self._show_trace_preview(data)
            return

        # Handle "more" node (load more items)
        if node_type == "more":
            if is_activation:
                self._load_more_items(data)
            return

        # Handle run/step selection (existing behavior)
        self._update_selection()

    def _drill_into_project(self, project_data: dict[str, Any]) -> None:
        """Load and display hierarchical project tree with agents, evals, and traces."""
        from tracecraft.storage.base import TraceQuery
        from tracecraft.tui.widgets.filter_bar import FilterBar
        from tracecraft.tui.widgets.run_tree import RunTree

        if not self._loader or not self._loader.is_sqlite:
            return

        project_id = project_data.get("id")
        project_name = project_data.get("name", "Unknown")

        # Get project structure (agents, evals, trace count)
        structure = self._loader.store.get_project_structure(project_id)

        # Load preview traces for the tree (limit to 10 for performance)
        query = TraceQuery(project_id=project_id, limit=10)
        preview_traces = self._loader.query_traces(query)

        # Convert AgentRun objects to dicts for the tree
        structure["traces"] = [
            {
                "id": str(trace.id),
                "name": trace.name,
                "duration_ms": trace.duration_ms,
                "error": trace.error,
            }
            for trace in preview_traces
        ]

        # Update tree to show hierarchical project structure
        tree = self.query_one("#run-tree", RunTree)
        tree.show_project_tree(structure)

        # Update filter bar to show project filter
        filter_bar = self.query_one("#filter-bar", FilterBar)
        filter_bar.set_project(project_id, project_name)

        # Store current project
        self._current_project = {"id": project_id, "name": project_name}

        # Update breadcrumb
        self._update_breadcrumb(
            {"label": project_name, "data": {"type": "project", "id": project_id}}
        )

        self.notify(f"Viewing project: {project_name}", title="PROJECT", timeout=2)

    def _drill_into_agent(self, agent_data: dict[str, Any]) -> None:
        """Load and display traces for an agent."""
        from tracecraft.tui.widgets.filter_bar import FilterBar
        from tracecraft.tui.widgets.run_tree import RunTree

        if not self._loader or not self._loader.is_sqlite:
            return

        agent_id = agent_data.get("id")
        agent_name = agent_data.get("name", "Unknown")

        # Get traces for this agent - try both FK-based and JSON-based methods
        # First-class agents use the agent_id column
        traces_by_fk = self._loader.store.get_traces_by_agent_id(agent_id)
        # Legacy agents use JSON fields (agent_id or agent_name in trace data)
        traces_by_json = self._loader.store.get_traces_by_agent(agent_id)

        # Combine results, avoiding duplicates by trace ID
        seen_ids = {str(t.id) for t in traces_by_fk}
        traces = list(traces_by_fk)
        for trace in traces_by_json:
            if str(trace.id) not in seen_ids:
                traces.append(trace)
                seen_ids.add(str(trace.id))

        # Update tree to show these traces
        tree = self.query_one("#run-tree", RunTree)
        tree.show_traces(traces)

        # Update filter bar to show agent filter
        filter_bar = self.query_one("#filter-bar", FilterBar)
        filter_bar.update_result_count(len(traces), len(traces))

        # Store current agent
        self._current_agent = {"id": agent_id, "name": agent_name}

        # Update breadcrumb
        self._update_breadcrumb({"label": agent_name, "data": {"type": "agent", "id": agent_id}})

        self.notify(f"Showing traces for agent: {agent_name}", title="AGENT", timeout=2)

    def _show_project_details(self, project_data: dict[str, Any]) -> None:
        """Show project information in the detail panel."""
        from tracecraft.tui.widgets.io_viewer import IOViewer
        from tracecraft.tui.widgets.metrics_panel import MetricsPanel

        if not self._loader or not self._loader.is_sqlite:
            return

        project_id = project_data.get("id")

        # Get project stats
        stats = self._loader.store.get_project_stats(project_id)
        project = self._loader.store.get_project(project_id)

        if project:
            metrics = self.query_one("#metrics", MetricsPanel)
            io_viewer = self.query_one("#io-viewer", IOViewer)

            # Show project in metrics panel
            metrics.show_project(project, stats)

            # Clear IO viewer or show project description
            io_viewer.show_project(project)

    def _show_agent_details(self, agent_data: dict[str, Any]) -> None:
        """Show agent information in the detail panel."""
        from tracecraft.tui.widgets.io_viewer import IOViewer
        from tracecraft.tui.widgets.metrics_panel import MetricsPanel

        if not self._loader or not self._loader.is_sqlite:
            return

        agent_id = agent_data.get("id")

        # Get agent stats
        stats = self._loader.store.get_agent_stats(agent_id)
        agent = agent_data  # We already have the agent data

        metrics = self.query_one("#metrics", MetricsPanel)
        io_viewer = self.query_one("#io-viewer", IOViewer)

        # Show agent in metrics panel
        metrics.show_agent(agent, stats)

        # Clear IO viewer
        io_viewer.show_agent(agent)

    def _drill_into_eval(self, eval_data: dict[str, Any]) -> None:
        """Show evaluation set details and allow running."""
        if not self._loader or not self._loader.is_sqlite:
            return

        eval_id = eval_data.get("id")
        eval_name = eval_data.get("name", "Unknown")

        # Get full eval set with cases
        eval_set = self._loader.store.get_evaluation_set(eval_id)
        if not eval_set:
            return

        # Update breadcrumb
        self._update_breadcrumb({"label": eval_name, "data": {"type": "eval", "id": eval_id}})

        # Show eval details
        self._show_eval_details(eval_data)

        # Offer to run evaluation
        self.notify(
            f"Press R to run evaluation '{eval_name}'",
            title="EVAL SELECTED",
            timeout=3,
        )

    def _show_eval_details(self, eval_data: dict[str, Any]) -> None:
        """Show evaluation set information in the detail panel."""
        from tracecraft.tui.widgets.io_viewer import IOViewer
        from tracecraft.tui.widgets.metrics_panel import MetricsPanel

        if not self._loader or not self._loader.is_sqlite:
            return

        eval_id = eval_data.get("id")

        # Get full eval set with stats
        eval_set = self._loader.store.get_evaluation_set(eval_id)
        if not eval_set:
            return

        stats = self._loader.store.get_evaluation_set_stats(eval_id)
        eval_set.update(stats)

        metrics = self.query_one("#metrics", MetricsPanel)
        io_viewer = self.query_one("#io-viewer", IOViewer)

        # Show eval set in metrics panel
        metrics.show_eval_set(eval_set)

        # Show eval set details in IO viewer
        io_viewer.show_eval_set(eval_set)

    def _handle_folder_activation(self, folder_data: dict[str, Any]) -> None:
        """Handle activation of a folder node (expand/collapse or load items)."""
        # Folders are auto-expanded by Textual tree widget
        # This method is a placeholder for future folder-specific actions
        pass

    def _drill_into_trace(self, trace_data: dict[str, Any]) -> None:
        """Load full trace and display it."""
        from tracecraft.tui.widgets.io_viewer import IOViewer, ModeIndicator
        from tracecraft.tui.widgets.metrics_panel import MetricsPanel
        from tracecraft.tui.widgets.run_tree import RunTree

        if not self._loader:
            return

        trace_id = trace_data.get("id")
        if not trace_id:
            return

        # Load the full trace
        trace = self._loader.get_trace(trace_id)
        if not trace:
            self.notify(f"Trace not found: {trace_id}", title="ERROR", severity="error")
            return

        # Update the tree to show this trace expanded
        tree = self.query_one("#run-tree", RunTree)
        tree.show_traces([trace])

        # Update detail panels
        metrics = self.query_one("#metrics", MetricsPanel)
        io_viewer = self.query_one("#io-viewer", IOViewer)
        mode_indicator = self.query_one("#mode-indicator", ModeIndicator)

        metrics.show_run(trace)
        io_viewer.show_run_io(trace)
        mode_indicator.update_mode("output")

        self._current_run = trace

    def _show_trace_preview(self, trace_data: dict[str, Any]) -> None:
        """Show trace preview in detail panel (without loading full trace)."""
        from tracecraft.tui.widgets.io_viewer import IOViewer
        from tracecraft.tui.widgets.metrics_panel import MetricsPanel

        _ = self.query_one("#metrics", MetricsPanel)
        io_viewer = self.query_one("#io-viewer", IOViewer)

        # Show basic info from the dict
        trace_name = trace_data.get("name", "Unknown")
        trace_id = trace_data.get("id", "")
        duration = trace_data.get("duration_ms")
        has_error = trace_data.get("error")

        # Create a summary view
        summary = {
            "name": trace_name,
            "id": trace_id,
            "duration_ms": duration,
            "has_error": has_error,
            "hint": "Press Enter to view full trace",
        }

        io_viewer.show_dict(summary, title="Trace Preview")

    def _load_more_items(self, data: dict[str, Any]) -> None:
        """Load more items for a folder (e.g., more traces)."""
        folder_type = data.get("folder_type")
        project_id = data.get("project_id")

        if folder_type == "traces" and project_id:
            # For now, just drill into the project to show all traces
            # Future: could implement pagination
            self._drill_into_project({"id": project_id, "name": ""})

    def _update_selection(self) -> None:
        """Update detail panels based on current tree selection."""
        from tracecraft.tui.widgets.io_viewer import IOViewer, ModeIndicator
        from tracecraft.tui.widgets.metrics_panel import MetricsPanel
        from tracecraft.tui.widgets.run_tree import RunTree

        tree = self.query_one("#run-tree", RunTree)
        metrics = self.query_one("#metrics", MetricsPanel)
        io_viewer = self.query_one("#io-viewer", IOViewer)
        mode_indicator = self.query_one("#mode-indicator", ModeIndicator)

        # Check what is currently highlighted/selected
        run = tree.get_selected_run()
        step = tree.get_selected_step()

        if step:
            self._current_step = step
            metrics.show_step(step)
            io_viewer.show_step(step)
            # Update mode indicator - show error mode if step has error
            mode_indicator.set_has_error(bool(step.error))
        elif run:
            self._current_run = run
            self._current_step = None
            metrics.show_run(run)
            io_viewer.show_run(run)
            # Update mode indicator - show error mode if run has error
            mode_indicator.set_has_error(bool(run.error))

    def on_filter_bar_filter_changed(self, event: Any) -> None:
        """Handle filter changes."""
        from tracecraft.storage.base import TraceQuery
        from tracecraft.tui.widgets.filter_bar import FilterBar
        from tracecraft.tui.widgets.run_tree import RunTree

        if not self._loader:
            return

        # Update current project from event
        if hasattr(event, "project_id"):
            if event.project_id:
                self._current_project = {"id": event.project_id, "name": event.project_name}
            else:
                self._current_project = None

        # Build query from filter options
        query = TraceQuery(
            name_contains=event.filter_text if event.filter_text else None,
            has_error=True if event.show_errors_only else None,
            project_id=event.project_id if hasattr(event, "project_id") else None,
        )

        # Query filtered runs
        filtered_runs = self._loader.query_traces(query)

        tree = self.query_one("#run-tree", RunTree)
        # Check if any filter is actually applied
        is_filtered = bool(
            event.filter_text
            or event.show_errors_only
            or (hasattr(event, "project_id") and event.project_id)
        )
        tree.update_runs(filtered_runs, is_filtered=is_filtered)

        # Update result count to show filter effect
        filter_bar = self.query_one("#filter-bar", FilterBar)
        total = self._loader.count()
        filter_bar.update_result_count(len(filtered_runs), total)

    def on_view_toggle_view_changed(self, event: Any) -> None:
        """Handle view mode changes."""
        from tracecraft.tui.widgets.run_tree import RunTree
        from tracecraft.tui.widgets.view_toggle import ViewMode

        self._view_mode = event.mode

        # Clear any current selection
        self._current_run = None
        self._current_step = None
        self._current_project = None
        self._current_agent = None

        # Reset breadcrumb to show current view
        self._update_breadcrumb()

        # Update the tree with the new view
        self._update_tree_for_view()

        # Update detail panels
        self._update_detail_panels()

    def on_breadcrumb_segment_clicked(self, event: Any) -> None:
        """Handle breadcrumb segment click for navigation."""
        from tracecraft.tui.widgets.view_toggle import ViewMode, ViewToggle

        data = event.data
        if not data:
            return

        segment_type = data.get("type")

        if segment_type == "view":
            # Navigate back to a view mode (e.g., Traces, Projects, Evals)
            mode = data.get("mode")
            if mode:
                self._view_mode = mode
                try:
                    view_toggle = self.query_one("#view-toggle", ViewToggle)
                    view_toggle.mode = mode
                except Exception:
                    pass
                self._update_tree_for_view()
                self._update_detail_panels()

        elif segment_type == "project":
            # Navigate back to a project
            project_id = data.get("id")
            if project_id and self._loader and self._loader.is_sqlite:
                project = self._loader.store.get_project(project_id)
                if project:
                    self._current_project = project
                    self._drill_into_project(project)

        elif segment_type == "agent":
            # Navigate back to an agent
            agent_id = data.get("id")
            if agent_id and self._loader and self._loader.is_sqlite:
                agent = self._loader.store.get_agent(agent_id)
                if agent:
                    self._current_agent = agent
                    self._drill_into_agent(agent)

        elif segment_type == "eval":
            # Navigate back to an eval set
            eval_id = data.get("id")
            if eval_id and self._loader and self._loader.is_sqlite:
                eval_set = self._loader.store.get_evaluation_set(eval_id)
                if eval_set:
                    self._drill_into_eval(eval_set)

    def _update_tree_for_view(self) -> None:
        """Update the tree based on the current view mode."""
        from tracecraft.tui.widgets.filter_bar import FilterBar
        from tracecraft.tui.widgets.run_tree import RunTree
        from tracecraft.tui.widgets.view_toggle import ViewMode

        if not self._loader:
            return

        tree = self.query_one("#run-tree", RunTree)
        filter_bar = self.query_one("#filter-bar", FilterBar)

        if self._view_mode == ViewMode.TRACES:
            # Show all traces (default behavior)
            tree.show_traces(self._runs)
            total = self._loader.count() if self._loader else len(self._runs)
            filter_bar.update_result_count(len(self._runs), total)

        elif self._view_mode == ViewMode.PROJECTS:
            # Show projects (if SQLite backend)
            if self._loader.is_sqlite:
                projects = self._loader.store.list_projects()
                tree.show_projects(projects)
                filter_bar.update_result_count(len(projects), len(projects))
            else:
                tree.show_traces([])
                self.notify("Projects require SQLite storage.", severity="warning")

        elif self._view_mode == ViewMode.AGENTS:
            # Show agents (if SQLite backend)
            if self._loader.is_sqlite:
                agents = self._loader.store.list_agents()
                tree.show_agents(agents)
                filter_bar.update_result_count(len(agents), len(agents))
            else:
                tree.show_traces([])
                self.notify("Agents require SQLite storage.", severity="warning")

        elif self._view_mode == ViewMode.EVALS:
            # Show evaluation sets (if SQLite backend)
            if self._loader.is_sqlite:
                evals = self._loader.store.list_evaluation_sets()
                # Add stats to each eval set for display
                for eval_set in evals:
                    stats = self._loader.store.get_evaluation_set_stats(eval_set["id"])
                    eval_set.update(stats)
                tree.show_evals(evals)
                filter_bar.update_result_count(len(evals), len(evals))
            else:
                tree.show_traces([])
                self.notify("Evals require SQLite storage.", severity="warning")

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
            self._update_tree()
            self.notify("Data refreshed.", title="REFRESH", timeout=2)

    def action_show_input(self) -> None:
        """Show input view."""
        from tracecraft.tui.widgets.io_viewer import IOViewer, ModeIndicator

        io_viewer = self.query_one("#io-viewer", IOViewer)
        io_viewer.set_mode(IOViewer.MODE_INPUT)
        self.query_one("#mode-indicator", ModeIndicator).set_mode(IOViewer.MODE_INPUT)

    def action_show_output(self) -> None:
        """Show output view."""
        from tracecraft.tui.widgets.io_viewer import IOViewer, ModeIndicator

        io_viewer = self.query_one("#io-viewer", IOViewer)
        io_viewer.set_mode(IOViewer.MODE_OUTPUT)
        self.query_one("#mode-indicator", ModeIndicator).set_mode(IOViewer.MODE_OUTPUT)

    def action_show_attributes(self) -> None:
        """Show attributes view."""
        from tracecraft.tui.widgets.io_viewer import IOViewer, ModeIndicator

        io_viewer = self.query_one("#io-viewer", IOViewer)
        io_viewer.set_mode(IOViewer.MODE_ATTRIBUTES)
        self.query_one("#mode-indicator", ModeIndicator).set_mode(IOViewer.MODE_ATTRIBUTES)

    def action_show_json(self) -> None:
        """Show full JSON view."""
        from tracecraft.tui.widgets.io_viewer import IOViewer, ModeIndicator

        io_viewer = self.query_one("#io-viewer", IOViewer)
        io_viewer.set_mode(IOViewer.MODE_JSON)
        self.query_one("#mode-indicator", ModeIndicator).set_mode(IOViewer.MODE_JSON)

    def action_show_error(self) -> None:
        """Show error view."""
        from tracecraft.tui.widgets.io_viewer import IOViewer, ModeIndicator

        io_viewer = self.query_one("#io-viewer", IOViewer)
        io_viewer.set_mode(IOViewer.MODE_ERROR)
        self.query_one("#mode-indicator", ModeIndicator).set_mode(IOViewer.MODE_ERROR)

    def action_cycle_view(self) -> None:
        """Cycle through IO viewer modes."""
        from tracecraft.tui.widgets.io_viewer import IOViewer, ModeIndicator

        io_viewer = self.query_one("#io-viewer", IOViewer)
        io_viewer.cycle_mode()
        # Update mode indicator with the new mode
        self.query_one("#mode-indicator", ModeIndicator).set_mode(io_viewer.mode)

    def action_toggle_format(self) -> None:
        """Toggle display format between AUTO, TABLE, and JSON."""
        from tracecraft.tui.widgets.io_viewer import DisplayFormat, IOViewer

        io_viewer = self.query_one("#io-viewer", IOViewer)
        io_viewer.toggle_display_format()

        # Show notification of new format
        format_name = io_viewer.display_format.value.upper()
        self.notify(f"Display format: {format_name}", timeout=2)

    def action_back(self) -> None:
        """Go back / clear selection."""
        from tracecraft.tui.widgets.breadcrumb import Breadcrumb
        from tracecraft.tui.widgets.filter_bar import FilterBar
        from tracecraft.tui.widgets.view_toggle import ViewMode

        filter_bar = self.query_one("#filter-bar", FilterBar)

        # If we're viewing a project's or agent's traces, go back to the list
        if self._current_project and self._view_mode == ViewMode.TRACES:
            # Clear project filter and return to projects view
            self._current_project = None
            filter_bar.clear_project()
            self._view_mode = ViewMode.PROJECTS
            self._update_tree_for_view()
            # Update view toggle to show PROJECTS
            from tracecraft.tui.widgets.view_toggle import ViewToggle

            try:
                view_toggle = self.query_one("#view-toggle", ViewToggle)
                view_toggle.set_mode(ViewMode.PROJECTS)
            except Exception:
                pass
            # Pop breadcrumb
            try:
                breadcrumb = self.query_one("#breadcrumb", Breadcrumb)
                breadcrumb.pop()
            except Exception:
                pass
            return

        if self._current_agent and self._view_mode == ViewMode.TRACES:
            # Clear agent filter and return to agents view
            self._current_agent = None
            self._view_mode = ViewMode.AGENTS
            self._update_tree_for_view()
            # Update view toggle to show AGENTS
            from tracecraft.tui.widgets.view_toggle import ViewToggle

            try:
                view_toggle = self.query_one("#view-toggle", ViewToggle)
                view_toggle.set_mode(ViewMode.AGENTS)
            except Exception:
                pass
            # Pop breadcrumb
            try:
                breadcrumb = self.query_one("#breadcrumb", Breadcrumb)
                breadcrumb.pop()
            except Exception:
                pass
            return

        # Standard back behavior
        if filter_bar.filter_text or filter_bar.show_errors_only:
            filter_bar.clear()
        else:
            self._current_run = None
            self._current_step = None
            self._update_detail_panels()
            # Pop breadcrumb if there are extra segments
            try:
                breadcrumb = self.query_one("#breadcrumb", Breadcrumb)
                if len(breadcrumb) > 1:
                    breadcrumb.pop()
            except Exception:
                pass

    def _update_detail_panels(self) -> None:
        """Update detail panels based on current selection."""
        from tracecraft.tui.widgets.io_viewer import IOViewer
        from tracecraft.tui.widgets.metrics_panel import MetricsPanel

        metrics = self.query_one("#metrics", MetricsPanel)
        io_viewer = self.query_one("#io-viewer", IOViewer)

        if self._current_step:
            metrics.show_step(self._current_step)
            io_viewer.show_step(self._current_step)
        elif self._current_run:
            metrics.show_run(self._current_run)
            io_viewer.show_run(self._current_run)
        else:
            metrics.show_run(None)
            io_viewer.show_run(None)

    def action_playground(self) -> None:
        """Open the playground for the selected LLM step or agent's nested LLM steps."""
        from tracecraft.core.models import StepType

        if self._current_step is None:
            self.notify(
                "No step selected. Navigate with j/k, select with Enter.",
                title="NO SELECTION",
                severity="warning",
            )
            return

        # If it's an LLM step, open playground directly
        if self._current_step.type == StepType.LLM:
            self._open_playground_for_step(self._current_step)
            return

        # For AGENT or other types with children, find nested LLM steps
        llm_steps = self._find_llm_steps_in_children(self._current_step)

        if not llm_steps:
            self.notify(
                f"No LLM steps in '{self._current_step.name}'. Select an LLM step.",
                title="NO LLM STEPS",
                severity="warning",
            )
            return

        if len(llm_steps) == 1:
            # Only one LLM step - use it directly
            self._open_playground_for_step(llm_steps[0])
        else:
            # Multiple LLM steps - show picker dialog
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
        """
        Recursively find all LLM steps within a step's children.

        Args:
            step: The parent step to search within.

        Returns:
            List of LLM steps found in children (depth-first order).
        """
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
        """
        Open the playground screen for a specific LLM step.

        Args:
            step: The LLM step to replay in the playground.
        """
        # Get original output
        original_output = ""
        outputs = step.outputs or {}
        if "result" in outputs:
            original_output = str(outputs["result"])
        elif "content" in outputs:
            original_output = str(outputs["content"])
        elif outputs:
            original_output = str(outputs)

        # Check if using SQLite backend for auto-persistence
        store = None
        trace_id = None
        if self._loader and self._loader.is_sqlite and self._current_run:
            store = self._loader.store
            trace_id = str(self._current_run.id)

        # Open playground screen
        from tracecraft.tui.screens.playground import PlaygroundScreen

        self.push_screen(
            PlaygroundScreen(
                step=step,
                original_output=original_output,
                store=store,
                trace_id=trace_id,
            )
        )

    def action_project_manager(self) -> None:
        """Open the project manager screen."""
        if not self._loader or not self._loader.is_sqlite:
            self.notify(
                "SQLite storage required. Use: tracecraft ui traces.db",
                title="SQLITE REQUIRED",
                severity="warning",
            )
            return

        from tracecraft.tui.screens.project_manager import ProjectManagerScreen
        from tracecraft.tui.widgets.filter_bar import FilterBar

        def on_project_selected(project: dict[str, Any] | None) -> None:
            if project is None:
                return  # Cancelled

            filter_bar = self.query_one("#filter-bar", FilterBar)

            if project.get("id") is None:
                # "All Projects" selected - clear filter
                self._current_project = None
                filter_bar.set_project(None, None)
                self.notify("Filter cleared.", title="ALL PROJECTS")
            else:
                # Specific project selected
                self._current_project = project
                filter_bar.set_project(project["id"], project["name"])
                self.notify(f"Filtering: {project['name']}", title="PROJECT")

        self.push_screen(
            ProjectManagerScreen(store=self._loader.store),
            on_project_selected,
        )

    def action_assign_project(self) -> None:
        """Assign the current trace to a project."""
        if not self._loader or not self._loader.is_sqlite:
            self.notify(
                "SQLite storage required. Use: tracecraft ui traces.db",
                title="SQLITE REQUIRED",
                severity="warning",
            )
            return

        if not self._current_run:
            self.notify(
                "No trace selected. Navigate with j/k, select with Enter.",
                title="NO SELECTION",
                severity="warning",
            )
            return

        from tracecraft.tui.screens.trace_assign import TraceAssignScreen

        def on_project_assigned(project_id: str | None) -> None:
            if project_id is None:
                # User cancelled or unassigned
                if project_id == "":
                    self.notify("Trace unassigned.", title="UNASSIGNED")
                return

            # Find project name for notification
            projects = self._loader.store.list_projects()
            project = next((p for p in projects if p["id"] == project_id), None)
            if project:
                self.notify(f"Assigned to {project['name']}.", title="ASSIGNED")
            else:
                self.notify("Trace assigned.", title="ASSIGNED")

        self.push_screen(
            TraceAssignScreen(trace=self._current_run, store=self._loader.store),
            on_project_assigned,
        )

    def action_agent_manager(self) -> None:
        """Open the agent manager screen."""
        if not self._loader or not self._loader.is_sqlite:
            self.notify(
                "SQLite storage required. Use: tracecraft ui traces.db",
                title="SQLITE REQUIRED",
                severity="warning",
            )
            return

        from tracecraft.tui.screens.agent_manager import AgentManagerScreen

        def on_agent_selected(agent: dict[str, Any] | None) -> None:
            if agent is None:
                return  # Cancelled

            if agent.get("id") is None:
                # "All Agents" selected - go to agents view
                self._current_agent = None
                self.action_view_agents()
            else:
                # Specific agent selected - drill down to show its traces
                self._drill_into_agent(agent)

        self.push_screen(AgentManagerScreen(store=self._loader.store), on_agent_selected)

    def action_assign_agent(self) -> None:
        """Assign the current trace to an agent."""
        if not self._loader or not self._loader.is_sqlite:
            self.notify(
                "SQLite storage required. Use: tracecraft ui traces.db",
                title="SQLITE REQUIRED",
                severity="warning",
            )
            return

        if not self._current_run:
            self.notify(
                "No trace selected. Navigate with j/k, select with Enter.",
                title="NO SELECTION",
                severity="warning",
            )
            return

        from tracecraft.tui.screens.agent_manager import AgentManagerScreen

        def on_agent_assigned(agent: dict[str, Any] | None) -> None:
            if agent is None:
                return  # Cancelled

            agent_id = agent.get("id")
            trace_id = str(self._current_run.id)

            try:
                self._loader.store.assign_trace_to_agent(trace_id, agent_id)
                if agent_id:
                    self.notify(
                        f"Trace assigned to '{agent['name']}'.",
                        title="ASSIGNED",
                    )
                else:
                    self.notify("Trace unassigned from agent.", title="UNASSIGNED")
            except Exception as e:
                self.notify(f"Assignment failed: {e}", title="ERROR", severity="error")

        self.push_screen(AgentManagerScreen(store=self._loader.store), on_agent_assigned)

    def action_help(self) -> None:
        """Show help modal with all keybindings."""
        from tracecraft.tui.screens.help_screen import HelpScreen

        # Don't push another HelpScreen if one is already displayed
        if any(isinstance(screen, HelpScreen) for screen in self.screen_stack):
            return

        self.push_screen(HelpScreen(context="Main App"))

    def action_view_traces(self) -> None:
        """Switch to traces view."""
        from tracecraft.tui.widgets.view_toggle import ViewMode, ViewToggle

        self._view_mode = ViewMode.TRACES
        self._current_project = None
        self._current_agent = None

        # Update the view toggle widget
        try:
            view_toggle = self.query_one("#view-toggle", ViewToggle)
            view_toggle.set_mode(ViewMode.TRACES)
        except Exception:
            pass

        self._load_runs()
        self._update_tree_for_view()

    def action_view_projects(self) -> None:
        """Switch to projects view."""
        from tracecraft.tui.widgets.view_toggle import ViewMode, ViewToggle

        if not self._loader or not self._loader.is_sqlite:
            self.notify("Projects require SQLite storage.", severity="warning")
            return

        self._view_mode = ViewMode.PROJECTS
        self._current_project = None
        self._current_agent = None

        # Update the view toggle widget
        try:
            view_toggle = self.query_one("#view-toggle", ViewToggle)
            view_toggle.set_mode(ViewMode.PROJECTS)
        except Exception:
            pass

        self._update_tree_for_view()

    def action_view_agents(self) -> None:
        """Switch to agents view."""
        from tracecraft.tui.widgets.view_toggle import ViewMode, ViewToggle

        if not self._loader or not self._loader.is_sqlite:
            self.notify("Agents require SQLite storage.", severity="warning")
            return

        self._view_mode = ViewMode.AGENTS
        self._current_project = None
        self._current_agent = None

        # Update the view toggle widget
        try:
            view_toggle = self.query_one("#view-toggle", ViewToggle)
            view_toggle.set_mode(ViewMode.AGENTS)
        except Exception:
            pass

        self._update_tree_for_view()

    def action_view_evals(self) -> None:
        """Switch to evaluations view."""
        from tracecraft.tui.widgets.view_toggle import ViewMode, ViewToggle

        if not self._loader or not self._loader.is_sqlite:
            self.notify("Evals require SQLite storage.", severity="warning")
            return

        self._view_mode = ViewMode.EVALS
        self._current_project = None
        self._current_agent = None

        # Update the view toggle widget
        try:
            view_toggle = self.query_one("#view-toggle", ViewToggle)
            view_toggle.set_mode(ViewMode.EVALS)
        except Exception:
            pass

        self._update_tree_for_view()

    def action_create_eval_set(self) -> None:
        """Create a new evaluation set."""
        if not self._loader or not self._loader.is_sqlite:
            self.notify(
                "SQLite storage required. Use: tracecraft ui traces.db",
                title="SQLITE REQUIRED",
                severity="warning",
            )
            return

        from tracecraft.tui.screens.eval_set_creator import EvalSetCreatorScreen

        def on_eval_created(result: dict[str, Any] | None) -> None:
            if result is None:
                return  # Cancelled

            self.notify(
                f"Created: {result['name']}",
                title="EVAL SET CREATED",
            )

            # Refresh the view if we're in evals mode
            from tracecraft.tui.widgets.view_toggle import ViewMode

            if self._view_mode == ViewMode.EVALS:
                self._update_tree_for_view()

        self.push_screen(
            EvalSetCreatorScreen(store=self._loader.store),
            on_eval_created,
        )

    def action_run_eval(self) -> None:
        """Run the selected evaluation set."""
        if not self._loader or not self._loader.is_sqlite:
            self.notify(
                "SQLite storage required. Use: tracecraft ui traces.db",
                title="SQLITE REQUIRED",
                severity="warning",
            )
            return

        from tracecraft.tui.widgets.run_tree import RunTree

        tree = self.query_one("#run-tree", RunTree)
        eval_set = tree.get_selected_eval()

        if not eval_set:
            self.notify(
                "No evaluation set selected. Switch to EVALS view.",
                title="NO SELECTION",
                severity="warning",
            )
            return

        from tracecraft.tui.screens.eval_runner import EvalRunnerScreen

        def on_run_complete(result: dict[str, Any] | None) -> None:
            if result:
                passed = result.get("passed", False)
                pass_rate = result.get("pass_rate", 0) * 100
                if passed:
                    self.notify(
                        f"Pass rate: {pass_rate:.0f}%",
                        title="EVAL PASSED",
                    )
                else:
                    self.notify(
                        f"Pass rate: {pass_rate:.0f}%",
                        title="EVAL FAILED",
                        severity="warning",
                    )

            # Refresh the view
            from tracecraft.tui.widgets.view_toggle import ViewMode

            if self._view_mode == ViewMode.EVALS:
                self._update_tree_for_view()

        self.push_screen(
            EvalRunnerScreen(eval_set=eval_set, store=self._loader.store),
            on_run_complete,
        )

    def action_add_to_eval(self) -> None:
        """Add the selected trace/step to an evaluation set as a test case."""
        if not self._loader or not self._loader.is_sqlite:
            self.notify(
                "SQLite storage required. Use: tracecraft ui traces.db",
                title="SQLITE REQUIRED",
                severity="warning",
            )
            return

        # Get the current trace and step selection
        if not self._current_run:
            self.notify(
                "Select a trace first.",
                title="NO TRACE SELECTED",
                severity="warning",
            )
            return

        from tracecraft.tui.screens.eval_case_selector import EvalCaseSelectorScreen

        def on_case_added(result: dict[str, Any] | None) -> None:
            if result is None:
                return  # Cancelled

            self.notify(
                f"Added to: {result['eval_set_name']}",
                title="CASE ADDED",
            )

        self.push_screen(
            EvalCaseSelectorScreen(
                trace=self._current_run,
                step=self._current_step,
                store=self._loader.store,
            ),
            on_case_added,
        )

    def action_create_eval_case(self) -> None:
        """Create a manual evaluation test case."""
        if not self._loader or not self._loader.is_sqlite:
            self.notify(
                "SQLite storage required. Use: tracecraft ui traces.db",
                title="SQLITE REQUIRED",
                severity="warning",
            )
            return

        from tracecraft.tui.widgets.run_tree import RunTree

        tree = self.query_one("#run-tree", RunTree)
        eval_set = tree.get_selected_eval()

        if not eval_set:
            self.notify(
                "Select an evaluation set first (view EVALS with key '4').",
                title="NO EVAL SET SELECTED",
                severity="warning",
            )
            return

        from tracecraft.tui.screens.eval_case_creator import EvalCaseCreatorScreen

        def on_case_created(result: dict[str, Any] | None) -> None:
            if result is None:
                return  # Cancelled

            self.notify(
                f"Created case: {result['name']}",
                title="CASE CREATED",
            )

            # Refresh the eval set details
            self._show_eval_details(eval_set)

        self.push_screen(
            EvalCaseCreatorScreen(
                eval_set_id=eval_set["id"],
                store=self._loader.store,
            ),
            on_case_created,
        )

    def action_goto_source(self) -> None:
        """Navigate to source trace from an eval case."""
        if not self._loader or not self._loader.is_sqlite:
            self.notify(
                "SQLite storage required. Use: tracecraft ui traces.db",
                title="SQLITE REQUIRED",
                severity="warning",
            )
            return

        from tracecraft.tui.widgets.run_tree import RunTree

        tree = self.query_one("#run-tree", RunTree)
        selected = tree.cursor_node

        if not selected or not selected.data:
            self.notify(
                "Select an eval case to navigate to its source.",
                title="NO SELECTION",
                severity="warning",
            )
            return

        node_data = selected.data
        node_type = node_data.get("type")

        # Handle eval case node
        if node_type == "eval_case":
            case_data = node_data.get("data", {})
            source_trace_id = case_data.get("source_trace_id")

            if source_trace_id:
                # Switch to traces view and select the source trace
                from tracecraft.tui.widgets.view_toggle import ViewMode, ViewToggle

                self._view_mode = ViewMode.TRACES
                self._update_tree_for_view()

                # Update view toggle
                try:
                    view_toggle = self.query_one("#view-toggle", ViewToggle)
                    view_toggle.set_mode(ViewMode.TRACES)
                except Exception:
                    pass

                # Try to select the trace
                self._select_trace_by_id(source_trace_id)
                self.notify("Jumped to source trace")
            else:
                self.notify(
                    "This case has no source trace.",
                    title="NO SOURCE",
                    severity="warning",
                )
        else:
            self.notify(
                "Select an eval case to navigate to its source.",
                title="INVALID SELECTION",
                severity="warning",
            )

    def _select_trace_by_id(self, trace_id: str) -> None:
        """Select a trace in the tree by its ID."""
        from tracecraft.tui.widgets.run_tree import RunTree

        tree = self.query_one("#run-tree", RunTree)

        # Search through tree nodes to find matching trace
        # Note: Tree may use "trace" or "run" as the type depending on view mode
        for node in tree.root.children:
            if node.data:
                node_type = node.data.get("type")
                node_id = node.data.get("id")
                if node_type in ("trace", "run") and node_id == trace_id:
                    tree.select_node(node)
                    # Also show the trace details
                    trace = self._loader.store.get(trace_id)
                    if trace:
                        self._show_trace_details(trace)
                    return

        # If not found in current tree, load and show it directly
        trace = self._loader.store.get(trace_id)
        if trace:
            self._show_trace_details(trace)
            self.notify(f"Loaded trace: {trace.name}")
        else:
            # Safe slicing for display
            display_id = trace_id[:8] if trace_id else "unknown"
            self.notify(
                f"Trace not found: {display_id}...",
                title="NOT FOUND",
                severity="warning",
            )

    def action_show_trace_evals(self) -> None:
        """Show evaluation associations for the current trace."""
        if not self._loader or not self._loader.is_sqlite:
            self.notify(
                "SQLite storage required for eval associations.",
                title="SQLITE REQUIRED",
                severity="warning",
            )
            return

        if not self._current_run:
            self.notify(
                "Select a trace first.",
                title="NO TRACE SELECTED",
                severity="warning",
            )
            return

        from tracecraft.tui.widgets.io_viewer import IOViewer

        io_viewer = self.query_one("#io-viewer", IOViewer)
        io_viewer.show_trace_eval_associations(
            str(self._current_run.id),
            self._loader.store,
        )

    def action_view_eval_cases(self) -> None:
        """View cases for the selected evaluation set."""
        if not self._loader or not self._loader.is_sqlite:
            self.notify(
                "SQLite storage required. Use: tracecraft ui traces.db",
                title="SQLITE REQUIRED",
                severity="warning",
            )
            return

        from tracecraft.tui.widgets.run_tree import RunTree

        tree = self.query_one("#run-tree", RunTree)
        eval_set = tree.get_selected_eval()

        if not eval_set:
            self.notify(
                "No evaluation set selected. Switch to EVALS view.",
                title="NO SELECTION",
                severity="warning",
            )
            return

        from tracecraft.tui.screens.eval_cases_viewer import EvalCasesViewerScreen

        def on_cases_viewer_dismiss(result: dict | None) -> None:
            """Handle cases viewer dismiss callback."""
            if result and result.get("action") == "goto_trace":
                trace_id = result.get("trace_id")
                if trace_id:
                    # Switch to TRACES view and navigate to the trace
                    from tracecraft.tui.widgets.view_toggle import ViewMode, ViewToggle

                    self._view_mode = ViewMode.TRACES
                    try:
                        view_toggle = self.query_one("#view-toggle", ViewToggle)
                        view_toggle.mode = ViewMode.TRACES
                    except Exception:
                        pass  # View toggle not mounted
                    self._update_tree_for_view()
                    self._update_breadcrumb()
                    self._select_trace_by_id(trace_id)

        self.push_screen(
            EvalCasesViewerScreen(eval_set=eval_set, store=self._loader.store),
            on_cases_viewer_dismiss,
        )

    def action_view_eval_history(self) -> None:
        """View run history for the selected evaluation set."""
        if not self._loader or not self._loader.is_sqlite:
            self.notify(
                "SQLite storage required. Use: tracecraft ui traces.db",
                title="SQLITE REQUIRED",
                severity="warning",
            )
            return

        from tracecraft.tui.widgets.run_tree import RunTree

        tree = self.query_one("#run-tree", RunTree)
        eval_set = tree.get_selected_eval()

        if not eval_set:
            self.notify(
                "No evaluation set selected. Switch to EVALS view.",
                title="NO SELECTION",
                severity="warning",
            )
            return

        from tracecraft.tui.screens.eval_run_history import EvalRunHistoryScreen

        self.push_screen(EvalRunHistoryScreen(eval_set=eval_set, store=self._loader.store))

    def action_view_latest_run(self) -> None:
        """View results of the latest run for the selected evaluation set."""
        if not self._loader or not self._loader.is_sqlite:
            self.notify(
                "SQLite storage required. Use: tracecraft ui traces.db",
                title="SQLITE REQUIRED",
                severity="warning",
            )
            return

        from tracecraft.tui.widgets.run_tree import RunTree

        tree = self.query_one("#run-tree", RunTree)
        eval_set = tree.get_selected_eval()

        if not eval_set:
            self.notify(
                "No evaluation set selected. Switch to EVALS view.",
                title="NO SELECTION",
                severity="warning",
            )
            return

        # Get the latest run for this eval set
        runs = self._loader.store.list_evaluation_runs(set_id=eval_set["id"])
        if not runs:
            self.notify(
                "No runs found for this evaluation set. Run an evaluation first.",
                title="NO RUNS",
                severity="warning",
            )
            return

        # Get the most recent run (first in list, assumed sorted by date desc)
        latest_run = runs[0]

        from tracecraft.tui.screens.eval_results_viewer import EvalResultsViewerScreen

        self.push_screen(
            EvalResultsViewerScreen(
                eval_run=latest_run,
                eval_set=eval_set,
                store=self._loader.store,
            )
        )
