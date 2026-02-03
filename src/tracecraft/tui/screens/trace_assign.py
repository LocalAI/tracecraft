"""
Trace assignment screen for assigning traces to projects.

Provides a modal dialog for selecting which project to assign a trace to.
NOIR SIGNAL theme styling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

# Import theme constants
from tracecraft.tui.theme import (
    ACCENT_AMBER,
    BACKGROUND,
    BORDER,
    INFO_BLUE,
    SURFACE,
    SURFACE_HIGHLIGHT,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

try:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Vertical
    from textual.screen import ModalScreen
    from textual.widgets import Footer, Label, OptionList, Static
    from textual.widgets.option_list import Option

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    ComposeResult = Any  # type: ignore[misc,assignment]
    ModalScreen = object  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun
    from tracecraft.storage.sqlite import SQLiteTraceStore


class TraceAssignScreen(ModalScreen if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Modal screen for assigning a trace to a project.

    Shows the current trace info and a list of projects to choose from.
    Returns the selected project_id (or None to unassign).
    """

    BINDINGS = (
        [
            Binding("escape", "cancel", "Cancel"),
            Binding("enter", "select", "Assign"),
        ]
        if TEXTUAL_AVAILABLE
        else []
    )

    CSS = f"""
    /* NOIR SIGNAL - Trace Assign */
    TraceAssignScreen {{
        align: center middle;
        background: rgba(11, 14, 17, 0.8);
    }}

    #assign-container {{
        width: 60%;
        height: 60%;
        min-width: 40;
        max-width: 80;
        border: solid {ACCENT_AMBER};
        background: {SURFACE};
    }}

    #assign-header {{
        height: 3;
        background: {SURFACE_HIGHLIGHT};
        padding: 0 1;
        content-align: center middle;
        border-bottom: solid {BORDER};
    }}

    #assign-header Label {{
        text-style: bold;
        color: {ACCENT_AMBER};
    }}

    #trace-info {{
        padding: 1;
        border-bottom: solid {BORDER};
        height: auto;
        background: {SURFACE};
    }}

    #trace-name {{
        text-style: bold;
        color: {TEXT_PRIMARY};
    }}

    #trace-details {{
        color: {TEXT_MUTED};
    }}

    #current-project {{
        color: {INFO_BLUE};
        margin-top: 1;
    }}

    #project-list-container {{
        padding: 1;
        height: 1fr;
    }}

    #project-list-label {{
        margin-bottom: 1;
        color: {TEXT_MUTED};
    }}

    #assign-project-list {{
        height: 1fr;
        border: solid {BORDER};
        background: {BACKGROUND};
    }}

    #assign-project-list:focus {{
        border: solid {ACCENT_AMBER};
    }}
    """

    def __init__(
        self,
        trace: AgentRun,
        store: SQLiteTraceStore,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the trace assign screen.

        Args:
            trace: The trace to assign.
            store: SQLite store for project operations.
        """
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__(*args, **kwargs)
        self._trace = trace
        self._store = store
        self._projects: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        """Compose the assign screen layout."""
        with Vertical(id="assign-container"):
            # Header
            with Vertical(id="assign-header"):
                yield Label("ASSIGN TRACE")

            # Trace info
            with Vertical(id="trace-info"):
                yield Label(f"Trace: {self._trace.name}", id="trace-name")
                duration = f"{self._trace.duration_ms:.0f}ms" if self._trace.duration_ms else "—"
                tokens = self._trace.total_tokens or 0
                yield Static(
                    f"{duration} | {tokens:,} tokens",
                    id="trace-details",
                )
                # Show current project assignment
                yield Static("Currently: Loading...", id="current-project")

            # Project selection
            with Vertical(id="project-list-container"):
                yield Label("SELECT PROJECT", id="project-list-label")
                yield OptionList(id="assign-project-list")

        yield Footer()

    def on_mount(self) -> None:
        """Load projects when mounted."""
        self._load_projects()

    def _load_projects(self) -> None:
        """Load projects from store and populate list."""
        self._projects = self._store.list_projects()

        # Update current project display
        current_project_id = self._get_current_project_id()
        current_label = self.query_one("#current-project", Static)
        if current_project_id:
            # Find project name
            project_name = "Unknown"
            for p in self._projects:
                if p["id"] == current_project_id:
                    project_name = p["name"]
                    break
            current_label.update(f"Currently: {project_name}")
        else:
            current_label.update("Currently: Unassigned")

        option_list = self.query_one("#assign-project-list", OptionList)
        option_list.clear_options()

        # Add unassign option first
        option_list.add_option(Option("Unassign from project", id="__none__"))

        # Add each project
        for project in self._projects:
            name = project["name"]
            option_list.add_option(Option(name, id=project["id"]))

        # Try to highlight the current project if trace is already assigned
        # This requires checking the trace's current project_id
        current_project_id = self._get_current_project_id()
        if current_project_id:
            for i, project in enumerate(self._projects):
                if project["id"] == current_project_id:
                    option_list.highlighted = i + 1  # +1 for "No Project" option
                    break
        else:
            option_list.highlighted = 0  # Highlight "No Project"

    def _get_current_project_id(self) -> str | None:
        """Get the current project_id for this trace."""
        # Try to get it from trace attributes
        if self._trace.attributes and "project_id" in self._trace.attributes:
            return self._trace.attributes["project_id"]

        # Otherwise query the store
        try:
            # The store doesn't have a direct method for this, so we'll just return None
            # The trace would need to have project_id in its data
            return None
        except Exception:
            return None

    def action_cancel(self) -> None:
        """Cancel and close."""
        self.dismiss(None)

    def action_select(self) -> None:
        """Select the highlighted project and assign."""
        option_list = self.query_one("#assign-project-list", OptionList)
        if option_list.highlighted is None:
            self.dismiss(None)
            return

        option = option_list.get_option_at_index(option_list.highlighted)
        project_id = option.id

        if project_id == "__none__":
            # Unassign from project
            self._assign_trace(None)
        else:
            self._assign_trace(project_id)

    def on_option_list_option_selected(self, event: Any) -> None:
        """Handle double-click or Enter on an option."""
        project_id = event.option.id
        if project_id == "__none__":
            self._assign_trace(None)
        else:
            self._assign_trace(project_id)

    def _assign_trace(self, project_id: str | None) -> None:
        """Assign the trace to the project."""
        try:
            trace_id = str(self._trace.id)
            self._store.assign_trace_to_project(trace_id, project_id)

            # Return the project_id (or None for unassign)
            self.dismiss(project_id)

        except Exception as e:
            self.notify(f"Assignment failed: {e}", title="ERROR", severity="error")
