"""
Notes editor modal for trace annotations.

NOIR SIGNAL theme styling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tracecraft.tui.theme import (
    ACCENT_AMBER,
    BACKGROUND,
    BORDER,
    INFO_BLUE,
    SUCCESS_GREEN,
    SURFACE,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

try:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.screen import ModalScreen
    from textual.widgets import Button, Footer, Label, TextArea

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    ComposeResult = Any  # type: ignore[misc,assignment]
    ModalScreen = object  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun


class NotesEditorModal(ModalScreen if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Modal for editing trace notes.

    Returns the notes text if saved, or None if cancelled.
    """

    BINDINGS = (
        [
            Binding("escape", "cancel", "Cancel"),
            Binding("ctrl+s", "save", "Save"),
        ]
        if TEXTUAL_AVAILABLE
        else []
    )

    CSS = f"""
    /* NOIR SIGNAL - Notes Editor Modal */
    NotesEditorModal {{
        align: center middle;
        background: rgba(11, 14, 17, 0.85);
    }}

    #notes-container {{
        width: 80;
        height: auto;
        max-height: 80%;
        border: solid {ACCENT_AMBER};
        background: {SURFACE};
        padding: 1 2;
    }}

    #notes-title {{
        text-style: bold;
        text-align: center;
        margin-bottom: 1;
        color: {ACCENT_AMBER};
    }}

    #trace-name {{
        color: {INFO_BLUE};
        margin-bottom: 1;
    }}

    #notes-input {{
        height: 10;
        background: {BACKGROUND};
        border: solid {BORDER};
        color: {TEXT_PRIMARY};
    }}

    #notes-input:focus {{
        border: solid {ACCENT_AMBER};
    }}

    #hint-text {{
        color: {TEXT_MUTED};
        margin-top: 1;
    }}

    #button-row {{
        margin-top: 1;
        height: auto;
        align: center middle;
    }}

    #save-btn {{
        margin-right: 2;
    }}

    Button {{
        min-width: 12;
    }}
    """

    def __init__(
        self,
        trace: AgentRun,
        current_notes: str | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize the notes editor.

        Args:
            trace: The trace being annotated.
            current_notes: Existing notes to edit (if any).
        """
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__(*args, **kwargs)
        self._trace = trace
        self._current_notes = current_notes or ""

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Vertical(id="notes-container"):
            yield Label("📝 EDIT NOTES", id="notes-title")
            yield Label(f"Trace: {self._trace.name}", id="trace-name")
            yield TextArea(self._current_notes, id="notes-input")
            yield Label("Ctrl+S to save, Escape to cancel", id="hint-text")

            with Horizontal(id="button-row"):
                yield Button("Save", variant="primary", id="save-btn")
                yield Button("Cancel", id="cancel-btn")

        yield Footer()

    def on_mount(self) -> None:
        """Focus the text area on mount."""
        self.query_one("#notes-input", TextArea).focus()

    def on_button_pressed(self, event: Any) -> None:
        """Handle button press events."""
        if event.button.id == "save-btn":
            self._do_save()
        elif event.button.id == "cancel-btn":
            self.dismiss(None)

    def action_cancel(self) -> None:
        """Cancel and close the modal."""
        self.dismiss(None)

    def action_save(self) -> None:
        """Save notes and close."""
        self._do_save()

    def _do_save(self) -> None:
        """Perform the save action."""
        text_area = self.query_one("#notes-input", TextArea)
        self.dismiss(text_area.text)
