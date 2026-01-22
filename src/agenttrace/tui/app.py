"""
AgentTrace Terminal UI - k9s-style trace explorer.

A real-time, interactive terminal interface for exploring
and debugging LLM/Agent traces.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
    from agenttrace.core.models import AgentRun, Step
    from agenttrace.tui.data.loader import TraceLoader


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
        Binding("tab", "cycle_view", "Cycle View"),
        Binding("question_mark", "help", "Help"),
        Binding("escape", "back", "Back"),
        # j/k navigation is built into Textual's Tree widget
    ]


class AgentTraceApp(App if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Main AgentTrace TUI application.

    Provides a k9s-style interface for exploring traces with:
    - Real-time trace updates
    - Hierarchical tree navigation
    - Input/output inspection
    - Filtering and search
    - Keyboard-driven navigation
    """

    TITLE = "AgentTrace"
    SUB_TITLE = "LLM Observability"

    CSS = """
    /* Main layout */
    #main {
        layout: vertical;
        height: 100%;
    }

    #content {
        layout: horizontal;
        height: 1fr;
    }

    /* Tree panel */
    #tree-panel {
        width: 40%;
        min-width: 30;
        border: solid $primary;
        padding: 0 1;
    }

    #tree-panel .panel-title {
        text-style: bold;
        color: $text;
        padding: 0 0 1 0;
    }

    #run-tree {
        height: 1fr;
    }

    /* Detail panel */
    #detail-panel {
        width: 60%;
        padding: 0 1;
    }

    #metrics {
        height: auto;
        max-height: 15;
        margin-bottom: 1;
    }

    #io-viewer {
        height: 1fr;
        border: solid $primary-darken-2;
        scrollbar-gutter: stable;
    }

    /* Filter bar */
    FilterBar {
        height: 3;
        background: $surface;
        padding: 0 1;
        border-bottom: solid $primary-darken-2;
    }

    FilterBar > Input {
        width: 1fr;
    }

    FilterBar > Static {
        width: auto;
        padding: 0 1;
        content-align: center middle;
    }

    .toggle {
        border: solid $primary-darken-2;
        margin-left: 1;
    }

    /* Status bar */
    #status-bar {
        height: 1;
        dock: bottom;
        background: $surface;
        padding: 0 1;
    }
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
            raise ImportError("textual required for TUI. Install with: pip install agenttrace[tui]")
        super().__init__()
        self.trace_source = trace_source
        self.watch = watch
        self.env = env
        self._loader: TraceLoader | None = None
        self._runs: list[AgentRun] = []  # Cached runs for display
        self._current_run: AgentRun | None = None
        self._current_step: Step | None = None

    def compose(self) -> ComposeResult:
        """Compose the UI layout."""
        from agenttrace.tui.widgets.filter_bar import FilterBar
        from agenttrace.tui.widgets.io_viewer import IOViewer
        from agenttrace.tui.widgets.metrics_panel import MetricsPanel
        from agenttrace.tui.widgets.run_tree import RunTree

        yield Header()

        with Container(id="main"):
            yield FilterBar(id="filter-bar")

            with Horizontal(id="content"):
                # Left panel: Run/Step tree
                with Vertical(id="tree-panel"):
                    yield Static("Traces", classes="panel-title")
                    yield RunTree(id="run-tree")

                # Right panel: Details
                with Vertical(id="detail-panel"):
                    yield MetricsPanel(id="metrics")
                    yield IOViewer(id="io-viewer")

        yield Footer()

    async def on_mount(self) -> None:
        """Called when app is mounted."""
        from agenttrace.tui.data.loader import TraceLoader, get_loader_for_env

        if self.trace_source:
            # Use explicit source
            try:
                self._loader = TraceLoader.from_source(self.trace_source)
            except ValueError as e:
                self.notify(str(e), title="Load Error", severity="error")
                return
        else:
            # Use environment configuration
            self._loader = get_loader_for_env(self.env)

        # Load initial runs
        self._load_runs()
        self._update_tree()

        if self.watch:
            self.set_interval(1.0, self._poll_for_updates)

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
        from agenttrace.tui.widgets.run_tree import RunTree

        tree = self.query_one("#run-tree", RunTree)
        tree.update_runs(self._runs)

    def on_tree_node_selected(self, event: Any) -> None:  # noqa: ARG002
        """Handle tree node selection (Enter key)."""
        self._update_selection()

    def on_tree_node_highlighted(self, event: Any) -> None:  # noqa: ARG002
        """Handle tree node highlight (navigation with j/k or arrows)."""
        self._update_selection()

    def _update_selection(self) -> None:
        """Update detail panels based on current tree selection."""
        from agenttrace.tui.widgets.io_viewer import IOViewer
        from agenttrace.tui.widgets.metrics_panel import MetricsPanel
        from agenttrace.tui.widgets.run_tree import RunTree

        tree = self.query_one("#run-tree", RunTree)
        metrics = self.query_one("#metrics", MetricsPanel)
        io_viewer = self.query_one("#io-viewer", IOViewer)

        # Check what is currently highlighted/selected
        run = tree.get_selected_run()
        step = tree.get_selected_step()

        if step:
            self._current_step = step
            metrics.show_step(step)
            io_viewer.show_step(step)
        elif run:
            self._current_run = run
            self._current_step = None
            metrics.show_run(run)
            io_viewer.show_run(run)

    def on_filter_bar_filter_changed(self, event: Any) -> None:
        """Handle filter changes."""
        from agenttrace.storage.base import TraceQuery
        from agenttrace.tui.widgets.run_tree import RunTree

        if not self._loader:
            return

        # Build query from filter options
        query = TraceQuery(
            name_contains=event.filter_text if event.filter_text else None,
            has_error=True if event.show_errors_only else None,
        )

        # Query filtered runs
        filtered_runs = self._loader.query_traces(query)

        tree = self.query_one("#run-tree", RunTree)
        tree.update_runs(filtered_runs)

    # Actions

    def action_filter(self) -> None:
        """Focus the filter bar."""
        from agenttrace.tui.widgets.filter_bar import FilterBar

        self.query_one("#filter-bar", FilterBar).focus_input()

    def action_refresh(self) -> None:
        """Refresh the trace data."""
        if self._loader:
            self._loader.refresh()
            self._load_runs()
            self._update_tree()
            self.notify("Traces refreshed", title="Refresh", timeout=2)

    def action_show_input(self) -> None:
        """Show input view."""
        from agenttrace.tui.widgets.io_viewer import IOViewer

        self.query_one("#io-viewer", IOViewer).set_mode(IOViewer.MODE_INPUT)

    def action_show_output(self) -> None:
        """Show output view."""
        from agenttrace.tui.widgets.io_viewer import IOViewer

        self.query_one("#io-viewer", IOViewer).set_mode(IOViewer.MODE_OUTPUT)

    def action_show_attributes(self) -> None:
        """Show attributes view."""
        from agenttrace.tui.widgets.io_viewer import IOViewer

        self.query_one("#io-viewer", IOViewer).set_mode(IOViewer.MODE_ATTRIBUTES)

    def action_show_json(self) -> None:
        """Show full JSON view."""
        from agenttrace.tui.widgets.io_viewer import IOViewer

        self.query_one("#io-viewer", IOViewer).set_mode(IOViewer.MODE_JSON)

    def action_show_error(self) -> None:
        """Show error view."""
        from agenttrace.tui.widgets.io_viewer import IOViewer

        self.query_one("#io-viewer", IOViewer).set_mode(IOViewer.MODE_ERROR)

    def action_cycle_view(self) -> None:
        """Cycle through IO viewer modes."""
        from agenttrace.tui.widgets.io_viewer import IOViewer

        self.query_one("#io-viewer", IOViewer).cycle_mode()

    def action_back(self) -> None:
        """Go back / clear selection."""
        from agenttrace.tui.widgets.filter_bar import FilterBar

        filter_bar = self.query_one("#filter-bar", FilterBar)
        if filter_bar.filter_text or filter_bar.show_errors_only:
            filter_bar.clear()
        else:
            self._current_run = None
            self._current_step = None
            self._update_detail_panels()

    def _update_detail_panels(self) -> None:
        """Update detail panels based on current selection."""
        from agenttrace.tui.widgets.io_viewer import IOViewer
        from agenttrace.tui.widgets.metrics_panel import MetricsPanel

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
        from agenttrace.core.models import StepType

        if self._current_step is None:
            self.notify(
                "Select a step first (navigate with j/k, select with Enter)",
                title="No Step Selected",
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
                f"No LLM steps found within '{self._current_step.name}'. "
                f"Navigate to an LLM step to use the playground.",
                title="No LLM Steps",
                severity="warning",
            )
            return

        if len(llm_steps) == 1:
            # Only one LLM step - use it directly
            self._open_playground_for_step(llm_steps[0])
        else:
            # Multiple LLM steps - show picker dialog
            from agenttrace.tui.screens.llm_picker import LLMPickerScreen

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
        from agenttrace.core.models import StepType

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
        from agenttrace.tui.screens.playground import PlaygroundScreen

        self.push_screen(
            PlaygroundScreen(
                step=step,
                original_output=original_output,
                store=store,
                trace_id=trace_id,
            )
        )

    def action_help(self) -> None:
        """Show help dialog."""
        self.notify(
            "Keys: q=quit, r=refresh, /=filter, i=input, o=output, "
            "a=attrs, d=detail, e=error, p=playground, tab=cycle, j/k=navigate, ?=help",
            title="Help",
            timeout=10,
        )
