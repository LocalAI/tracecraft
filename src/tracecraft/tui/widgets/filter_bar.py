"""
Filter bar widget for searching and filtering traces.

Provides text input for filtering runs by name and type,
plus a project dropdown for filtering by project.
NOIR SIGNAL theme styling.
"""

from __future__ import annotations

from typing import Any

# Import theme constants for consistent styling
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
    from textual.containers import Horizontal
    from textual.message import Message
    from textual.widgets import Input, Select, Static

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    Horizontal = object  # type: ignore[misc,assignment]
    Input = object  # type: ignore[misc,assignment]
    Select = object  # type: ignore[misc,assignment]
    Static = object  # type: ignore[misc,assignment]
    Message = object  # type: ignore[misc,assignment]


class FilterBar(Horizontal if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Filter bar for searching and filtering traces.

    Provides a text input for filtering runs by name,
    a project dropdown for filtering by project,
    and an errors-only toggle.
    """

    class FilterChanged(Message if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
        """Message sent when the filter changes."""

        def __init__(
            self,
            filter_text: str,
            show_errors_only: bool = False,
            project_id: str | None = None,
            session_id: str | None = None,
        ) -> None:
            """Initialize the message."""
            if TEXTUAL_AVAILABLE:
                super().__init__()
            self.filter_text = filter_text
            self.show_errors_only = show_errors_only
            self.project_id = project_id
            self.session_id = session_id

    class ProjectChanged(Message if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
        """Message sent when the project selection changes (to reload sessions)."""

        def __init__(self, project_id: str | None) -> None:
            """Initialize the message."""
            if TEXTUAL_AVAILABLE:
                super().__init__()
            self.project_id = project_id

    DEFAULT_CSS = f"""
    /* NOIR SIGNAL - Filter Bar - Bordered input design */
    FilterBar {{
        height: 3;
        background: {SURFACE};
        padding: 0 1;
        margin-bottom: 1;
        align: left top;
    }}

    /* Project dropdown - no border to avoid misalignment with Input */
    FilterBar > #project-select {{
        width: 22;
        height: 3;
        margin-right: 1;
        background: {SURFACE};
        border: none;
        color: {TEXT_PRIMARY};
    }}

    FilterBar > #project-select:focus {{
        border: none;
    }}

    FilterBar > #project-select.-has-focus > SelectCurrent {{
        border: round {ACCENT_AMBER};
    }}

    FilterBar > #project-select > SelectCurrent {{
        background: {BACKGROUND};
        color: {TEXT_PRIMARY};
        padding: 0 1;
        height: 3;
        border: round {BORDER};
    }}

    FilterBar > #project-select > SelectOverlay {{
        background: {SURFACE};
        border: solid {BORDER};
    }}

    FilterBar > #project-select > SelectOverlay:focus {{
        border: solid {ACCENT_AMBER};
    }}

    FilterBar > #project-select > SelectOverlay > .option-list--option {{
        color: {TEXT_PRIMARY};
        padding: 0 1;
    }}

    FilterBar > #project-select > SelectOverlay > .option-list--option-highlighted {{
        background: {SURFACE_HIGHLIGHT};
        color: {ACCENT_AMBER};
    }}

    /* Session dropdown - same styling as project dropdown */
    FilterBar > #session-select {{
        width: 22;
        height: 3;
        margin-right: 1;
        background: {SURFACE};
        border: none;
        color: {TEXT_PRIMARY};
    }}

    FilterBar > #session-select:focus {{
        border: none;
    }}

    FilterBar > #session-select.-has-focus > SelectCurrent {{
        border: round {ACCENT_AMBER};
    }}

    FilterBar > #session-select > SelectCurrent {{
        background: {BACKGROUND};
        color: {TEXT_PRIMARY};
        padding: 0 1;
        height: 3;
        border: round {BORDER};
    }}

    FilterBar > #session-select > SelectOverlay {{
        background: {SURFACE};
        border: solid {BORDER};
    }}

    FilterBar > #session-select > SelectOverlay:focus {{
        border: solid {ACCENT_AMBER};
    }}

    FilterBar > #session-select > SelectOverlay > .option-list--option {{
        color: {TEXT_PRIMARY};
        padding: 0 1;
    }}

    FilterBar > #session-select > SelectOverlay > .option-list--option-highlighted {{
        background: {SURFACE_HIGHLIGHT};
        color: {ACCENT_AMBER};
    }}

    /* Input - bordered style matching Select */
    FilterBar > Input {{
        width: 1fr;
        height: 3;
        background: {BACKGROUND};
        border: round {BORDER};
        color: {TEXT_PRIMARY};
        margin-right: 1;
    }}

    FilterBar > Input:focus {{
        border: round {ACCENT_AMBER};
    }}

    FilterBar > Input > .input--placeholder {{
        color: {TEXT_MUTED};
    }}

    /* Static labels - vertically centered */
    FilterBar > Static {{
        width: auto;
        height: 3;
        padding: 0 1;
        color: {TEXT_MUTED};
        content-align: left middle;
    }}

    FilterBar > .toggle {{
        margin-left: 1;
        height: 3;
        padding: 0 1;
        background: transparent;
        color: {TEXT_MUTED};
        content-align: left middle;
    }}

    FilterBar > .toggle:hover {{
        color: {ACCENT_AMBER};
    }}

    FilterBar > .toggle-active {{
        color: {ACCENT_AMBER};
        text-style: bold;
    }}

    FilterBar > .result-count {{
        margin-left: 1;
        height: 3;
        color: {TEXT_MUTED};
        content-align: left middle;
    }}
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the filter bar."""
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__(*args, **kwargs)
        self._filter_text: str = ""
        self._show_errors_only: bool = False
        self._project_id: str | None = None
        self._session_id: str | None = None
        self._has_projects: bool = False
        self._has_sessions: bool = False

    def compose(self) -> Any:
        """Compose the filter bar layout."""
        # Project dropdown - starts with just "All Projects"
        yield Select[str | None](
            options=[("All Projects", None)],
            value=None,
            id="project-select",
            allow_blank=False,
            prompt="Project",
        )
        # Session dropdown - starts with just "All Sessions"
        yield Select[str | None](
            options=[("All Sessions", None)],
            value=None,
            id="session-select",
            allow_blank=False,
            prompt="Session",
        )
        yield Input(placeholder="filter traces...", id="filter-input")
        yield Static("0 traces", id="result-count", classes="result-count")
        yield Static("ERRORS", id="error-toggle", classes="toggle")

    def on_input_changed(self, event: Any) -> None:
        """Handle input changes."""
        self._filter_text = event.value
        self._emit_filter_changed()

    def on_select_changed(self, event: Any) -> None:
        """Handle project or session selection changes."""
        if event.select.id == "project-select":
            self._project_id = event.value
            # Reset session when project changes
            self._session_id = None
            self.query_one("#session-select", Select).value = None
            # Emit ProjectChanged so app can reload sessions for this project
            self.post_message(self.ProjectChanged(self._project_id))
            self._emit_filter_changed()
        elif event.select.id == "session-select":
            self._session_id = event.value
            self._emit_filter_changed()

    def toggle_errors_only(self) -> None:
        """Toggle the errors-only filter."""
        self._show_errors_only = not self._show_errors_only
        self._update_toggle_style()
        self._emit_filter_changed()

    def _update_toggle_style(self) -> None:
        """Update the toggle button style."""
        toggle = self.query_one("#error-toggle", Static)
        if self._show_errors_only:
            toggle.update("ERRORS +")
            toggle.remove_class("toggle")
            toggle.add_class("toggle-active")
        else:
            toggle.update("ERRORS")
            toggle.remove_class("toggle-active")
            toggle.add_class("toggle")

    def _emit_filter_changed(self) -> None:
        """Emit the filter changed message."""
        self.post_message(
            self.FilterChanged(
                filter_text=self._filter_text,
                show_errors_only=self._show_errors_only,
                project_id=self._project_id,
                session_id=self._session_id,
            )
        )

    def clear(self) -> None:
        """Clear the filter."""
        self._filter_text = ""
        self._show_errors_only = False
        self._project_id = None
        self._session_id = None
        self.query_one("#filter-input", Input).value = ""
        self.query_one("#project-select", Select).value = None
        self.query_one("#session-select", Select).value = None
        self._update_toggle_style()
        self._emit_filter_changed()

    @property
    def filter_text(self) -> str:
        """Get the current filter text."""
        return self._filter_text

    @property
    def show_errors_only(self) -> bool:
        """Get whether to show errors only."""
        return self._show_errors_only

    @property
    def project_id(self) -> str | None:
        """Get the currently selected project ID."""
        return self._project_id

    @property
    def session_id(self) -> str | None:
        """Get the currently selected session ID."""
        return self._session_id

    def focus_input(self) -> None:
        """Focus the filter input."""
        self.query_one("#filter-input", Input).focus()

    def update_result_count(self, shown: int, total: int) -> None:
        """
        Update the result count display.

        Args:
            shown: Number of traces currently shown after filtering.
            total: Total number of traces before filtering.
        """
        label = self.query_one("#result-count", Static)
        if shown == total:
            label.update(f"{total} traces")
        elif shown == 0:
            label.update("No matches")
        else:
            label.update(f"{shown} of {total}")

    def set_projects(self, projects: list[tuple[str, str]]) -> None:
        """
        Set the available projects for the dropdown.

        Args:
            projects: List of (project_id, project_name) tuples.
        """
        if not projects:
            return

        # Build options list: "All Projects" first, then sorted projects
        options: list[tuple[str, str | None]] = [("All Projects", None)]
        for project_id, project_name in sorted(projects, key=lambda p: p[1].lower()):
            options.append((project_name, project_id))

        self._has_projects = True

        # Update the Select widget
        select = self.query_one("#project-select", Select)
        select.set_options(options)

        # Reset to "All Projects" if current selection is no longer valid
        if self._project_id is not None:
            project_ids = [p[1] for p in options]
            if self._project_id not in project_ids:
                self._project_id = None
                select.value = None

    def set_sessions(self, sessions: list[tuple[str, str]]) -> None:
        """
        Set the available sessions for the dropdown.

        Args:
            sessions: List of (session_id, session_name) tuples.
        """
        # Build options list: "All Sessions" first, then sorted sessions
        options: list[tuple[str, str | None]] = [("All Sessions", None)]
        for session_id, session_name in sorted(sessions, key=lambda s: s[1].lower()):
            options.append((session_name, session_id))

        self._has_sessions = len(sessions) > 0

        # Update the Select widget
        select = self.query_one("#session-select", Select)
        select.set_options(options)

        # Reset to "All Sessions" if current selection is no longer valid
        if self._session_id is not None:
            session_ids = [s[1] for s in options]
            if self._session_id not in session_ids:
                self._session_id = None
                select.value = None
