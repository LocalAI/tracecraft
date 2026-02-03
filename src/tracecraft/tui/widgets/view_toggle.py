"""
View toggle widget for switching between Traces, Projects, and Agents views.

Provides a horizontal toggle bar for selecting the main view mode.
NOIR SIGNAL theme styling.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

# Import theme constants for consistent styling
from tracecraft.tui.theme import (
    ACCENT_AMBER,
    BORDER,
    SURFACE,
    TEXT_MUTED,
)

try:
    from textual.containers import Horizontal
    from textual.message import Message
    from textual.widgets import Label

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    Horizontal = object  # type: ignore[misc,assignment]
    Label = object  # type: ignore[misc,assignment]
    Message = object  # type: ignore[misc,assignment]


class ViewMode(str, Enum):
    """The main view modes for the TUI."""

    TRACES = "traces"
    PROJECTS = "projects"
    AGENTS = "agents"
    EVALS = "evals"


class ClickableLabel(Label if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """A Label that can be clicked."""

    class Clicked(Message if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
        """Message sent when the label is clicked."""

        def __init__(self, label: Any) -> None:
            if TEXTUAL_AVAILABLE:
                super().__init__()
            self.label = label

    def on_click(self, _event: Any) -> None:
        """Handle click events."""
        self.post_message(self.Clicked(self))


class ViewToggle(Horizontal if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Toggle bar for switching between view modes.

    Displays three clickable options: TRACES | PROJECTS | AGENTS
    """

    class ViewChanged(Message if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
        """Message sent when the view mode changes."""

        def __init__(self, mode: ViewMode) -> None:
            """Initialize the message."""
            if TEXTUAL_AVAILABLE:
                super().__init__()
            self.mode = mode

    DEFAULT_CSS = f"""
    /* NOIR SIGNAL - View Toggle */
    ViewToggle {{
        height: 1;
        width: 100%;
        background: {SURFACE};
        padding: 0 1;
    }}

    ViewToggle > ClickableLabel {{
        width: auto;
        height: 1;
        padding: 0 1;
        margin: 0;
        color: {TEXT_MUTED};
    }}

    ViewToggle > ClickableLabel:hover {{
        color: {ACCENT_AMBER};
    }}

    ViewToggle > ClickableLabel.view-active {{
        color: {ACCENT_AMBER};
        text-style: bold;
    }}

    ViewToggle > .view-separator {{
        width: 1;
        height: 1;
        padding: 0;
        margin: 0;
        color: {BORDER};
    }}
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the view toggle."""
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__(*args, **kwargs)
        self._mode: ViewMode = ViewMode.TRACES

    def compose(self) -> Any:
        """Compose the view toggle layout."""
        yield ClickableLabel("TRACES", id="view-traces", classes="view-active")
        yield Label("|", classes="view-separator")
        yield ClickableLabel("PROJECTS", id="view-projects")
        yield Label("|", classes="view-separator")
        yield ClickableLabel("AGENTS", id="view-agents")
        yield Label("|", classes="view-separator")
        yield ClickableLabel("EVALS", id="view-evals")

    @property
    def mode(self) -> ViewMode:
        """Get the current view mode."""
        return self._mode

    def set_mode(self, mode: ViewMode) -> None:
        """Set the current view mode without posting message (for external updates)."""
        if mode == self._mode:
            return

        self._mode = mode
        self._update_styles()

    def _select_mode(self, mode: ViewMode) -> None:
        """Select a mode and post the change message."""
        if mode == self._mode:
            return

        self._mode = mode
        self._update_styles()
        self.post_message(self.ViewChanged(mode))

    def _update_styles(self) -> None:
        """Update the toggle styles based on current mode."""
        # Reset all options
        for option_id in ["view-traces", "view-projects", "view-agents", "view-evals"]:
            try:
                option = self.query_one(f"#{option_id}", ClickableLabel)
                option.remove_class("view-active")
            except Exception:
                pass

        # Set active option
        active_id = f"view-{self._mode.value}"
        try:
            active = self.query_one(f"#{active_id}", ClickableLabel)
            active.add_class("view-active")
        except Exception:
            pass

    def on_clickable_label_clicked(self, event: ClickableLabel.Clicked) -> None:
        """Handle label clicks."""
        label_id = event.label.id
        if label_id == "view-traces":
            self._select_mode(ViewMode.TRACES)
        elif label_id == "view-projects":
            self._select_mode(ViewMode.PROJECTS)
        elif label_id == "view-agents":
            self._select_mode(ViewMode.AGENTS)
        elif label_id == "view-evals":
            self._select_mode(ViewMode.EVALS)
