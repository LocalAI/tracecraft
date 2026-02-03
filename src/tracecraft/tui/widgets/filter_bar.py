"""
Filter bar widget for searching and filtering traces.

Provides text input for filtering runs by name and type.
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
    truncate_with_ellipsis,
)

try:
    from textual.containers import Horizontal
    from textual.message import Message
    from textual.widgets import Input, Static

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    Horizontal = object  # type: ignore[misc,assignment]
    Input = object  # type: ignore[misc,assignment]
    Static = object  # type: ignore[misc,assignment]
    Message = object  # type: ignore[misc,assignment]

# Max length for project name truncation (increased from 12)
MAX_PROJECT_NAME_LENGTH = 20


class FilterBar(Horizontal if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Filter bar for searching and filtering traces.

    Provides a text input for filtering runs by name,
    with additional filter options.
    """

    class FilterChanged(Message if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
        """Message sent when the filter changes."""

        def __init__(
            self,
            filter_text: str,
            show_errors_only: bool = False,
            project_id: str | None = None,
            project_name: str | None = None,
        ) -> None:
            """Initialize the message."""
            if TEXTUAL_AVAILABLE:
                super().__init__()
            self.filter_text = filter_text
            self.show_errors_only = show_errors_only
            self.project_id = project_id
            self.project_name = project_name

    DEFAULT_CSS = f"""
    /* NOIR SIGNAL - Filter Bar - Clean, minimal design */
    FilterBar {{
        height: 3;
        background: {SURFACE};
        padding: 0 1;
        border-bottom: solid {ACCENT_AMBER};
    }}

    FilterBar > .filter-label {{
        width: auto;
        padding: 0 1 0 0;
        color: {TEXT_MUTED};
    }}

    FilterBar > Input {{
        width: 1fr;
        background: {BACKGROUND};
        border: none;
        border-bottom: solid {INFO_BLUE};
        color: {TEXT_PRIMARY};
    }}

    FilterBar > Input:focus {{
        border-bottom: solid {ACCENT_AMBER};
    }}

    FilterBar > Input > .input--placeholder {{
        color: {TEXT_MUTED};
    }}

    FilterBar > Static {{
        width: auto;
        padding: 0 1;
        color: {TEXT_MUTED};
    }}

    FilterBar > .toggle {{
        margin-left: 1;
        padding: 0 1;
        background: transparent;
        color: {TEXT_MUTED};
    }}

    FilterBar > .toggle:hover {{
        color: {ACCENT_AMBER};
    }}

    FilterBar > .toggle-active {{
        color: {ACCENT_AMBER};
        text-style: bold;
    }}

    FilterBar > .project-active {{
        color: {INFO_BLUE};
        text-style: bold;
    }}

    FilterBar > .result-count {{
        margin-left: 1;
        color: {TEXT_MUTED};
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
        self._project_name: str | None = None

    def compose(self) -> Any:
        """Compose the filter bar layout."""
        yield Static("/", classes="filter-label")
        yield Input(placeholder="filter traces", id="filter-input")
        yield Static("0 traces", id="result-count", classes="result-count")
        yield Static("ALL", id="project-indicator", classes="toggle")
        yield Static("ERRORS", id="error-toggle", classes="toggle")

    def on_input_changed(self, event: Any) -> None:
        """Handle input changes."""
        self._filter_text = event.value
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
                project_name=self._project_name,
            )
        )

    def clear(self) -> None:
        """Clear the filter."""
        self._filter_text = ""
        self._show_errors_only = False
        self._project_id = None
        self._project_name = None
        self.query_one("#filter-input", Input).value = ""
        self._update_toggle_style()
        self._update_project_indicator()
        self._emit_filter_changed()

    @property
    def filter_text(self) -> str:
        """Get the current filter text."""
        return self._filter_text

    @property
    def show_errors_only(self) -> bool:
        """Get whether to show errors only."""
        return self._show_errors_only

    def focus_input(self) -> None:
        """Focus the filter input."""
        self.query_one("#filter-input", Input).focus()

    def set_project(self, project_id: str | None, project_name: str | None = None) -> None:
        """Set the project filter."""
        self._project_id = project_id
        self._project_name = project_name
        self._update_project_indicator()
        self._emit_filter_changed()

    def clear_project(self) -> None:
        """Clear the project filter."""
        self.set_project(None, None)

    def _update_project_indicator(self) -> None:
        """Update the project indicator display."""
        indicator = self.query_one("#project-indicator", Static)
        if self._project_name and self._project_id:
            # Truncate long names with ellipsis (increased from 12 to 20 chars)
            name = truncate_with_ellipsis(self._project_name.upper(), MAX_PROJECT_NAME_LENGTH)
            indicator.update(name)
            indicator.remove_class("toggle")
            indicator.add_class("project-active")
        else:
            indicator.update("ALL")
            indicator.remove_class("project-active")
            indicator.add_class("toggle")

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

    @property
    def project_id(self) -> str | None:
        """Get the current project ID filter."""
        return self._project_id

    @property
    def project_name(self) -> str | None:
        """Get the current project name filter."""
        return self._project_name
