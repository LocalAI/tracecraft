"""
Project creation screen.

Provides a simple modal dialog for creating new projects.
NOIR SIGNAL theme styling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

# Import theme constants
from tracecraft.tui.theme import (
    ACCENT_AMBER,
    BACKGROUND,
    BORDER,
    DANGER_RED,
    SURFACE,
    TEXT_MUTED,
)

try:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Vertical
    from textual.screen import ModalScreen
    from textual.widgets import Footer, Input, Label, Static

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    ComposeResult = Any  # type: ignore[misc,assignment]
    ModalScreen = object  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from tracecraft.storage.sqlite import SQLiteTraceStore


class ProjectCreateScreen(ModalScreen if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Modal screen for creating a new project.

    Returns the created project dict when dismissed, or None if cancelled.
    """

    BINDINGS = (
        [
            Binding("escape", "cancel", "Cancel"),
            Binding("ctrl+s", "submit", "Save"),
        ]
        if TEXTUAL_AVAILABLE
        else []
    )

    CSS = f"""
    /* NOIR SIGNAL - Project Create */
    ProjectCreateScreen {{
        align: center middle;
        background: rgba(11, 14, 17, 0.8);
    }}

    #create-container {{
        width: 60%;
        height: auto;
        max-height: 60%;
        border: solid {ACCENT_AMBER};
        background: {SURFACE};
        padding: 2;
    }}

    #create-title {{
        text-style: bold;
        margin-bottom: 1;
        color: {ACCENT_AMBER};
    }}

    .field-label {{
        margin-top: 1;
        margin-bottom: 0;
        color: {TEXT_MUTED};
    }}

    #name-input {{
        margin-bottom: 1;
        background: {BACKGROUND};
        border: solid {BORDER};
    }}

    #name-input:focus {{
        border: solid {ACCENT_AMBER};
    }}

    #description-input {{
        margin-bottom: 1;
        background: {BACKGROUND};
        border: solid {BORDER};
    }}

    #description-input:focus {{
        border: solid {ACCENT_AMBER};
    }}

    #create-hint {{
        color: {TEXT_MUTED};
        margin-top: 1;
    }}

    #error-message {{
        color: {DANGER_RED};
        margin-top: 1;
    }}
    """

    def __init__(
        self,
        store: SQLiteTraceStore,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the create project screen.

        Args:
            store: SQLite store for creating the project.
        """
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__(*args, **kwargs)
        self._store = store

    def compose(self) -> ComposeResult:
        """Compose the create project layout."""
        with Vertical(id="create-container"):
            yield Label("NEW PROJECT", id="create-title")

            yield Label("NAME", classes="field-label")
            yield Input(placeholder="project name", id="name-input")

            yield Label("DESCRIPTION", classes="field-label")
            yield Input(placeholder="optional", id="description-input")

            yield Static("", id="error-message")
            yield Static("[Enter] create  [Escape] cancel", id="create-hint")

        yield Footer()

    def on_mount(self) -> None:
        """Focus the name input on mount."""
        self.query_one("#name-input", Input).focus()

    def on_input_submitted(self, event: Any) -> None:
        """Handle Enter key in input fields."""
        # Move to next field or submit
        if event.input.id == "name-input":
            self.query_one("#description-input", Input).focus()
        else:
            self._create_project()

    def action_cancel(self) -> None:
        """Cancel and close."""
        self.dismiss(None)

    def action_submit(self) -> None:
        """Submit and create the project."""
        self._create_project()

    def _create_project(self) -> None:
        """Attempt to create the project."""
        name_input = self.query_one("#name-input", Input)
        desc_input = self.query_one("#description-input", Input)
        error_label = self.query_one("#error-message", Static)

        name = name_input.value.strip()
        description = desc_input.value.strip()

        if not name:
            error_label.update("Name required.")
            name_input.focus()
            return

        try:
            project_id = self._store.create_project(
                name=name,
                description=description if description else "",
            )

            # Fetch the created project
            project = self._store.get_project(project_id)
            self.dismiss(project)

        except Exception as e:
            error_msg = str(e)
            if "UNIQUE constraint" in error_msg:
                error_label.update(f"Project '{name}' already exists.")
            else:
                error_label.update(f"Failed: {error_msg}")
            name_input.focus()
