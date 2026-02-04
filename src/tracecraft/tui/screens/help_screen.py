"""
Help screen modal for displaying keyboard shortcuts.

Shows all keybindings grouped by function with NOIR SIGNAL styling.
"""

from __future__ import annotations

from typing import Any

# Import theme constants
from tracecraft.tui.theme import (
    ACCENT_AMBER,
    BORDER,
    SURFACE,
    SURFACE_HIGHLIGHT,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

try:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Vertical, VerticalScroll
    from textual.screen import ModalScreen
    from textual.widgets import Static

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    ModalScreen = object  # type: ignore[misc,assignment]


class HelpScreen(ModalScreen if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Modal screen showing all keyboard shortcuts.

    Groups keybindings by function: Navigation, Views, Actions, Projects.
    Styled with NOIR SIGNAL theme.
    """

    BINDINGS = (
        [
            Binding("escape", "close", "Close"),
            Binding("question_mark", "close", "Close"),
            Binding("q", "close", "Close"),
        ]
        if TEXTUAL_AVAILABLE
        else []
    )

    CSS = f"""
    HelpScreen {{
        align: center middle;
        background: rgba(11, 14, 17, 0.8);
    }}

    #help-container {{
        width: 70;
        max-width: 90%;
        height: 80%;
        background: {SURFACE};
        border: solid {ACCENT_AMBER};
    }}

    #help-header {{
        height: 3;
        background: {SURFACE_HIGHLIGHT};
        padding: 0 1;
        content-align: center middle;
        border-bottom: solid {BORDER};
    }}

    #help-header Static {{
        text-style: bold;
        color: {ACCENT_AMBER};
    }}

    #help-content {{
        height: 1fr;
        padding: 1 2;
    }}

    #help-footer {{
        height: 3;
        background: {SURFACE_HIGHLIGHT};
        padding: 0 1;
        content-align: center middle;
        border-top: solid {BORDER};
    }}

    #help-footer Static {{
        color: {TEXT_MUTED};
    }}

    .section-title {{
        color: {TEXT_MUTED};
        text-style: bold;
        margin-top: 1;
    }}

    .keybind-row {{
        margin-left: 2;
    }}

    .key {{
        color: {ACCENT_AMBER};
        text-style: bold;
    }}

    .description {{
        color: {TEXT_PRIMARY};
    }}
    """

    def __init__(self, context: str = "Main App", *args: Any, **kwargs: Any) -> None:
        """
        Initialize the help screen.

        Args:
            context: Current context (e.g., "Main App", "Playground", "Project Manager")
        """
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__(*args, **kwargs)
        self._help_context = context  # Renamed to avoid conflict with Textual's _context

    def compose(self) -> ComposeResult:
        """Compose the help screen layout."""
        with Vertical(id="help-container"):
            # Header
            with Vertical(id="help-header"):
                yield Static("KEYBOARD SHORTCUTS")

            # Content - scrollable list of keybindings
            with VerticalScroll(id="help-content"):
                # Navigation
                yield Static("NAVIGATION", classes="section-title")
                yield Static("  j / k        Navigate up/down in tree", classes="keybind-row")
                yield Static("  Enter        Select / expand node", classes="keybind-row")
                yield Static("  Escape       Go back / clear filter", classes="keybind-row")
                yield Static("  /            Focus filter input", classes="keybind-row")

                # Views
                yield Static("VIEWS", classes="section-title")
                yield Static(
                    "  Tab          Cycle through views (Input → Output → Detail)",
                    classes="keybind-row",
                )

                # Actions
                yield Static("ACTIONS", classes="section-title")
                yield Static("  r            Refresh data", classes="keybind-row")
                yield Static("  p            Open Playground for LLM step", classes="keybind-row")
                yield Static("  ?            Show this help", classes="keybind-row")
                yield Static("  q            Quit application", classes="keybind-row")

                # Projects
                yield Static("PROJECTS", classes="section-title")
                yield Static("  P            Open Project Manager (Shift+P)", classes="keybind-row")
                yield Static(
                    "  A            Assign trace to project (Shift+A)", classes="keybind-row"
                )

                # Context-specific sections
                if self._help_context == "Playground":
                    yield Static("PLAYGROUND", classes="section-title")
                    yield Static(
                        "  r            Run replay with modified prompt", classes="keybind-row"
                    )
                    yield Static("  s            Save iteration history", classes="keybind-row")
                    yield Static("  c            Copy output to clipboard", classes="keybind-row")
                    yield Static("  n            Add note / mark as best", classes="keybind-row")
                    yield Static("  d            Toggle diff view", classes="keybind-row")

                if self._help_context == "Project Manager":
                    yield Static("PROJECT MANAGER", classes="section-title")
                    yield Static("  n            Create new project", classes="keybind-row")
                    yield Static("  d            Delete selected project", classes="keybind-row")
                    yield Static("  Enter        Filter by selected project", classes="keybind-row")

            # Footer
            with Vertical(id="help-footer"):
                yield Static(f"Context: {self._help_context}  |  Press ESC or ? to close")

    def action_close(self) -> None:
        """Close the help screen."""
        self.dismiss()
