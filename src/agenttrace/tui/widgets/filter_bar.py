"""
Filter bar widget for searching and filtering traces.

Provides text input for filtering runs by name and type.
"""

from __future__ import annotations

from typing import Any

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
        ) -> None:
            """Initialize the message."""
            if TEXTUAL_AVAILABLE:
                super().__init__()
            self.filter_text = filter_text
            self.show_errors_only = show_errors_only

    DEFAULT_CSS = """
    FilterBar {
        height: 3;
        background: $surface;
        padding: 0 1;
    }

    FilterBar > Input {
        width: 1fr;
    }

    FilterBar > Static {
        width: auto;
        padding: 0 1;
    }
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the filter bar."""
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install agenttrace[tui]")
        super().__init__(*args, **kwargs)
        self._filter_text: str = ""
        self._show_errors_only: bool = False

    def compose(self) -> Any:
        """Compose the filter bar layout."""

        yield Static("🔍", classes="filter-icon")
        yield Input(placeholder="Filter traces...", id="filter-input")
        yield Static("Errors [E]", id="error-toggle", classes="toggle")

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
            toggle.update("Errors [E] ✓")
            toggle.styles.background = "red"
        else:
            toggle.update("Errors [E]")
            toggle.styles.background = "transparent"

    def _emit_filter_changed(self) -> None:
        """Emit the filter changed message."""
        self.post_message(
            self.FilterChanged(
                filter_text=self._filter_text,
                show_errors_only=self._show_errors_only,
            )
        )

    def clear(self) -> None:
        """Clear the filter."""
        self._filter_text = ""
        self._show_errors_only = False
        self.query_one("#filter-input", Input).value = ""
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

    def focus_input(self) -> None:
        """Focus the filter input."""
        self.query_one("#filter-input", Input).focus()
