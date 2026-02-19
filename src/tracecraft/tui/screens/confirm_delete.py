"""
Delete confirmation modal.

NOIR SIGNAL theme styling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tracecraft.tui.theme import (
    ACCENT_AMBER,
    BORDER,
    DANGER_RED,
    SURFACE,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

try:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.screen import ModalScreen
    from textual.widgets import Button, Footer, Label

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    ComposeResult = Any  # type: ignore[misc,assignment]
    ModalScreen = object  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun


class ConfirmDeleteModal(ModalScreen if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Modal dialog to confirm trace deletion.

    Returns True if confirmed, False if cancelled.
    """

    BINDINGS = (
        [
            Binding("escape", "cancel", "Cancel"),
            Binding("enter", "confirm", "Delete"),
            Binding("y", "confirm", "Yes", show=False),
            Binding("n", "cancel", "No", show=False),
        ]
        if TEXTUAL_AVAILABLE
        else []
    )

    CSS = f"""
    /* NOIR SIGNAL - Confirm Delete Modal */
    ConfirmDeleteModal {{
        align: center middle;
        background: rgba(11, 14, 17, 0.85);
    }}

    #confirm-container {{
        width: 50;
        height: auto;
        border: solid {DANGER_RED};
        background: {SURFACE};
        padding: 1 2;
    }}

    #confirm-title {{
        text-style: bold;
        text-align: center;
        margin-bottom: 1;
        color: {DANGER_RED};
    }}

    #confirm-message {{
        margin-bottom: 1;
        color: {TEXT_PRIMARY};
    }}

    #trace-name {{
        color: {ACCENT_AMBER};
        text-style: bold;
        margin-bottom: 1;
    }}

    #confirm-warning {{
        color: {TEXT_MUTED};
        margin-bottom: 1;
    }}

    #button-row {{
        margin-top: 1;
        height: auto;
        align: center middle;
    }}

    #delete-btn {{
        margin-right: 2;
    }}

    Button {{
        min-width: 12;
    }}
    """

    def __init__(self, trace: AgentRun, *args: Any, **kwargs: Any) -> None:
        """Initialize the confirmation modal.

        Args:
            trace: The trace to be deleted.
        """
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__(*args, **kwargs)
        self._trace = trace

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Vertical(id="confirm-container"):
            yield Label("⚠ DELETE TRACE", id="confirm-title")
            yield Label("Are you sure you want to delete this trace?", id="confirm-message")
            yield Label(self._trace.name, id="trace-name")
            yield Label("This action cannot be undone.", id="confirm-warning")

            with Horizontal(id="button-row"):
                yield Button("Delete", variant="error", id="delete-btn")
                yield Button("Cancel", id="cancel-btn")

        yield Footer()

    def on_button_pressed(self, event: Any) -> None:
        """Handle button press events."""
        if event.button.id == "delete-btn":
            self.dismiss(True)
        elif event.button.id == "cancel-btn":
            self.dismiss(False)

    def action_cancel(self) -> None:
        """Cancel and close the modal."""
        self.dismiss(False)

    def action_confirm(self) -> None:
        """Confirm deletion and close."""
        self.dismiss(True)
