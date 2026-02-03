"""
Project manager screen for browsing and managing projects.

Provides a modal dialog for viewing projects, creating new ones,
deleting existing ones, and selecting a project to filter traces.
NOIR SIGNAL theme styling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

# Import theme constants
from tracecraft.tui.theme import (
    ACCENT_AMBER,
    BACKGROUND,
    BORDER,
    SURFACE,
    SURFACE_HIGHLIGHT,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

try:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.screen import ModalScreen
    from textual.widgets import Footer, Label, OptionList, Static
    from textual.widgets.option_list import Option

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    ComposeResult = Any  # type: ignore[misc,assignment]
    ModalScreen = object  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from tracecraft.storage.sqlite import SQLiteTraceStore


class ProjectManagerScreen(ModalScreen if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Modal screen for browsing and managing projects.

    Features:
    - List all projects with stats
    - Create new projects (n key)
    - Delete projects (d key)
    - Select project to filter traces (Enter)

    Returns the selected project dict when dismissed, or None if cancelled.
    Special return value {"id": None, "name": "All Projects"} clears filter.
    """

    BINDINGS = (
        [
            Binding("escape", "cancel", "Back"),
            Binding("enter", "select", "Select"),
            Binding("n", "new_project", "New"),
            Binding("d", "delete_project", "Delete"),
        ]
        if TEXTUAL_AVAILABLE
        else []
    )

    CSS = f"""
    /* NOIR SIGNAL - Project Manager */
    ProjectManagerScreen {{
        align: center middle;
        background: rgba(11, 14, 17, 0.8);
    }}

    #project-container {{
        width: 80%;
        height: 70%;
        min-width: 60;
        max-width: 120;
        border: solid {ACCENT_AMBER};
        background: {SURFACE};
    }}

    #project-header {{
        height: 3;
        background: {SURFACE_HIGHLIGHT};
        padding: 0 1;
        content-align: center middle;
        border-bottom: solid {BORDER};
    }}

    #project-header Label {{
        text-style: bold;
        color: {ACCENT_AMBER};
    }}

    #project-content {{
        height: 1fr;
    }}

    #project-list-panel {{
        width: 50%;
        padding: 1;
        border-right: solid {BORDER};
    }}

    #project-list {{
        height: 1fr;
        border: solid {BORDER};
        background: {BACKGROUND};
    }}

    #project-list:focus {{
        border: solid {ACCENT_AMBER};
    }}

    #project-stats-panel {{
        width: 50%;
        padding: 1;
        background: {SURFACE};
    }}

    #project-stats {{
        height: 1fr;
        color: {TEXT_PRIMARY};
    }}

    .stats-title {{
        text-style: bold;
        margin-bottom: 1;
        color: {TEXT_MUTED};
    }}

    .stat-row {{
        margin-bottom: 0;
    }}
    """

    def __init__(
        self,
        store: SQLiteTraceStore,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the project manager screen.

        Args:
            store: SQLite store for project operations.
        """
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__(*args, **kwargs)
        self._store = store
        self._projects: list[dict[str, Any]] = []
        self._selected_index: int = 0

    def compose(self) -> ComposeResult:
        """Compose the project manager layout."""
        with Vertical(id="project-container"):
            # Header
            with Horizontal(id="project-header"):
                yield Label("PROJECTS")

            # Content area
            with Horizontal(id="project-content"):
                # Left panel: Project list
                with Vertical(id="project-list-panel"):
                    yield OptionList(id="project-list")

                # Right panel: Stats
                with Vertical(id="project-stats-panel"):
                    yield Label("DETAILS", classes="stats-title")
                    yield Static("Select a project to view details.", id="project-stats")

        yield Footer()

    def on_mount(self) -> None:
        """Load projects when mounted."""
        self._load_projects()

    def _load_projects(self) -> None:
        """Load projects from store and populate list."""
        self._projects = self._store.list_projects()

        option_list = self.query_one("#project-list", OptionList)
        option_list.clear_options()

        # Add "All Projects" option first
        option_list.add_option(Option("All Projects", id="__all__"))

        # Add each project
        for project in self._projects:
            name = project["name"]
            option_list.add_option(Option(name, id=project["id"]))

        # Select first item
        if option_list.option_count > 0:
            option_list.highlighted = 0

    def on_option_list_option_highlighted(self, event: Any) -> None:
        """Update stats when a project is highlighted."""
        self._update_stats(event.option.id)

    def _update_stats(self, project_id: str) -> None:
        """Update the stats panel for the selected project."""
        stats_widget = self.query_one("#project-stats", Static)

        if project_id == "__all__":
            # Show summary for all projects
            total_projects = len(self._projects)
            stats_widget.update(
                f"TOTAL PROJECTS: {total_projects}\n\n"
                f"Select project to filter traces.\n"
                f"Press [n] to create new project."
            )
            return

        # Find the project
        project = next((p for p in self._projects if p["id"] == project_id), None)
        if not project:
            stats_widget.update("Project not found.")
            return

        # Get stats for this project
        try:
            stats = self._store.get_project_stats(project_id)
            stats_text = (
                f"NAME: {project['name']}\n"
                f"DESC: {project.get('description') or '—'}\n\n"
                f"TRACES: {stats.get('trace_count', 0)}\n"
                f"TOKENS: {stats.get('total_tokens', 0):,}\n"
                f"COST: ${stats.get('total_cost_usd', 0):.4f}\n"
                f"ERRORS: {stats.get('error_count', 0)}\n\n"
                f"CREATED: {project.get('created_at', 'N/A')[:10]}"
            )
        except Exception:
            stats_text = (
                f"NAME: {project['name']}\n"
                f"DESC: {project.get('description') or '—'}\n\n"
                f"Stats unavailable."
            )

        stats_widget.update(stats_text)

    def action_cancel(self) -> None:
        """Cancel and close the manager."""
        self.dismiss(None)

    def action_select(self) -> None:
        """Select the highlighted project and close."""
        option_list = self.query_one("#project-list", OptionList)
        if option_list.highlighted is None:
            self.dismiss(None)
            return

        option = option_list.get_option_at_index(option_list.highlighted)
        project_id = option.id

        if project_id == "__all__":
            # Return special "All Projects" value to clear filter
            self.dismiss({"id": None, "name": "All Projects"})
        else:
            # Return the selected project
            project = next((p for p in self._projects if p["id"] == project_id), None)
            self.dismiss(project)

    def on_option_list_option_selected(self, event: Any) -> None:
        """Handle double-click or Enter on an option."""
        project_id = event.option.id

        if project_id == "__all__":
            self.dismiss({"id": None, "name": "All Projects"})
        else:
            project = next((p for p in self._projects if p["id"] == project_id), None)
            self.dismiss(project)

    def action_new_project(self) -> None:
        """Open the create project dialog."""
        from tracecraft.tui.screens.project_create import ProjectCreateScreen

        def on_project_created(project: dict[str, Any] | None) -> None:
            if project:
                self._load_projects()
                self.notify(f"Project created: {project['name']}", title="CREATED")

        self.app.push_screen(ProjectCreateScreen(store=self._store), on_project_created)

    def action_delete_project(self) -> None:
        """Delete the selected project."""
        option_list = self.query_one("#project-list", OptionList)
        if option_list.highlighted is None:
            return

        option = option_list.get_option_at_index(option_list.highlighted)
        project_id = option.id

        if project_id == "__all__":
            self.notify("Cannot delete all projects.", title="WARNING", severity="warning")
            return

        project = next((p for p in self._projects if p["id"] == project_id), None)
        if not project:
            return

        # Confirm deletion
        def confirm_delete(confirmed: bool) -> None:
            if confirmed:
                try:
                    self._store.delete_project(project_id)
                    self._load_projects()
                    self.notify(f"Project deleted: {project['name']}", title="DELETED")
                except Exception as e:
                    self.notify(f"Delete failed: {e}", title="ERROR", severity="error")

        # Show confirmation
        self.app.push_screen(
            ConfirmScreen(
                message=f"Delete project '{project['name']}'?\n\nTraces will be unlinked, not deleted.",
                title="CONFIRM DELETE",
            ),
            confirm_delete,
        )


class ConfirmScreen(ModalScreen if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """Simple confirmation dialog."""

    BINDINGS = (
        [
            Binding("y", "confirm", "Yes"),
            Binding("n", "cancel", "No"),
            Binding("escape", "cancel", "No"),
        ]
        if TEXTUAL_AVAILABLE
        else []
    )

    CSS = f"""
    /* NOIR SIGNAL - Confirm Dialog */
    ConfirmScreen {{
        align: center middle;
        background: rgba(11, 14, 17, 0.8);
    }}

    #confirm-container {{
        width: 50%;
        height: auto;
        max-height: 50%;
        border: solid {ACCENT_AMBER};
        background: {SURFACE};
        padding: 2;
    }}

    #confirm-title {{
        text-style: bold;
        margin-bottom: 1;
        color: {ACCENT_AMBER};
    }}

    #confirm-message {{
        margin-bottom: 1;
        color: {TEXT_PRIMARY};
    }}

    #confirm-hint {{
        color: {TEXT_MUTED};
    }}
    """

    def __init__(
        self,
        message: str,
        title: str = "Confirm",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI")
        super().__init__(*args, **kwargs)
        self._message = message
        self._title = title

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-container"):
            yield Label(self._title, id="confirm-title")
            yield Static(self._message, id="confirm-message")
            yield Static("[y] Yes  [n] No", id="confirm-hint")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
