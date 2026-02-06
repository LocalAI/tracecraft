"""
Waterfall view widget for displaying trace step timing.

LangSmith-style waterfall visualization showing step timing and hierarchy.
NOIR SIGNAL theme styling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from rich.text import Text

# Import theme constants for consistent styling
from tracecraft.tui.theme import (
    ACCENT_AMBER,
    BORDER,
    DANGER_RED,
    INFO_BLUE,
    SUCCESS_GREEN,
    SURFACE,
    SURFACE_HIGHLIGHT,
    TEXT_MUTED,
    TEXT_PRIMARY,
    format_duration,
)

try:
    from textual.binding import Binding
    from textual.containers import ScrollableContainer
    from textual.events import Click
    from textual.message import Message
    from textual.widgets import Static

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    Binding = Any  # type: ignore[misc,assignment]
    ScrollableContainer = object  # type: ignore[misc,assignment]
    Click = Any  # type: ignore[misc,assignment]
    Message = object  # type: ignore[misc,assignment]
    Static = object  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun, Step


# Additional step type color (purple for retrieval)
RETRIEVAL_PURPLE = "#9B7EDE"


class WaterfallView(ScrollableContainer if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Waterfall visualization for trace step timing.

    Displays steps as horizontal bars showing relative timing
    and hierarchy, similar to LangSmith's waterfall view.
    """

    class StepHighlighted(Message if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
        """Message sent when cursor moves to a new step."""

        def __init__(self, step: Step | None) -> None:
            """Initialize the message."""
            if TEXTUAL_AVAILABLE:
                super().__init__()
            self.step = step

    class StepSelected(Message if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
        """Message sent when Enter is pressed on a step."""

        def __init__(self, step: Step) -> None:
            """Initialize the message."""
            if TEXTUAL_AVAILABLE:
                super().__init__()
            self.step = step

    # Step type icons (same as RunTree for consistency)
    STEP_TYPE_ICONS: ClassVar[dict[str, str]] = {
        "agent": "◆",
        "llm": "◉",
        "tool": "▶",
        "retrieval": "◀",
        "memory": "▬",
        "guardrail": "◇",
        "evaluation": "◈",
        "workflow": "▷",
        "error": "✕",
    }

    # Step type colors
    STEP_TYPE_COLORS: ClassVar[dict[str, str]] = {
        "agent": ACCENT_AMBER,
        "llm": INFO_BLUE,
        "tool": SUCCESS_GREEN,
        "retrieval": RETRIEVAL_PURPLE,
        "memory": TEXT_MUTED,
        "guardrail": ACCENT_AMBER,
        "evaluation": INFO_BLUE,
        "workflow": TEXT_MUTED,
        "error": DANGER_RED,
    }

    # Bar characters
    BAR_FULL = "█"
    BAR_HALF = "▓"
    BAR_LIGHT = "░"

    # Layout constants
    LABEL_WIDTH = 35  # Width for step type and name label
    BAR_WIDTH = 40  # Width for the timing bar

    # Keybindings for vim-style navigation
    BINDINGS: ClassVar[list[Any]] = [
        Binding("j", "move_down", "Down", show=False),
        Binding("k", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("up", "move_up", "Up", show=False),
        Binding("enter", "select_step", "Select", show=False),
    ]

    DEFAULT_CSS = f"""
    /* NOIR SIGNAL - Waterfall View */
    WaterfallView {{
        background: {SURFACE};
        color: {TEXT_PRIMARY};
        border: solid {BORDER};
        height: auto;
        max-height: 15;
        padding: 0 1;
    }}

    WaterfallView:focus {{
        border: solid {ACCENT_AMBER};
    }}

    WaterfallView > .waterfall-header {{
        color: {TEXT_MUTED};
        text-style: bold;
        padding: 0;
        height: 1;
    }}

    WaterfallView > .waterfall-row {{
        height: 1;
        padding: 0;
    }}

    WaterfallView > .waterfall-row:hover {{
        background: {SURFACE_HIGHLIGHT};
    }}

    WaterfallView > .waterfall-row-selected {{
        background: {SURFACE_HIGHLIGHT};
    }}
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the waterfall view."""
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__(*args, **kwargs)
        self._trace: AgentRun | None = None
        self._steps: list[tuple[Step, int]] = []  # (step, depth) pairs
        self._cursor_index: int = 0
        self._trace_duration_ms: float = 1.0  # Avoid division by zero
        self._trace_start_ms: float = 0.0
        self._row_widgets: list[Static] = []

    def show_trace(self, trace: AgentRun) -> None:
        """
        Display the waterfall for a trace.

        Args:
            trace: The AgentRun to visualize.
        """
        # Skip if already showing this trace
        if self._trace is not None and self._trace.id == trace.id:
            return

        self._trace = trace
        self._steps = []
        self._cursor_index = 0
        self._row_widgets = []

        # Calculate trace timing bounds
        if trace.duration_ms:
            self._trace_duration_ms = trace.duration_ms
        else:
            self._trace_duration_ms = 1.0

        self._trace_start_ms = trace.start_time.timestamp() * 1000

        # Flatten the step hierarchy with depth info
        self._flatten_steps(trace.steps, depth=0)

        # Rebuild the widget
        self._rebuild()

        # Emit initial highlight
        if self._steps:
            self.post_message(self.StepHighlighted(self._steps[0][0]))

    def _flatten_steps(self, steps: list[Step], depth: int) -> None:
        """Flatten step hierarchy into a list with depth info."""
        for step in steps:
            self._steps.append((step, depth))
            if step.children:
                self._flatten_steps(step.children, depth + 1)

    def _rebuild(self) -> None:
        """Rebuild the widget contents."""
        # Remove existing children
        self.remove_children()

        if not self._steps:
            empty = Static(
                Text("No steps to display.", style=TEXT_MUTED),
                classes="waterfall-header",
            )
            self.mount(empty)
            return

        # Add header with timeline
        header = self._create_header()
        self.mount(header)

        # Add step rows
        for idx, (step, depth) in enumerate(self._steps):
            row = self._create_row(step, depth, idx)
            self._row_widgets.append(row)
            self.mount(row)

        # Highlight initial row
        self._update_selection()

    def _create_header(self) -> Static:
        """Create the timeline header."""
        text = Text()

        # Label column
        text.append(" " * self.LABEL_WIDTH, style=TEXT_MUTED)

        # Timeline markers
        text.append("0ms", style=TEXT_MUTED)
        quarter = self._trace_duration_ms / 4
        mid = self._trace_duration_ms / 2
        three_quarter = 3 * self._trace_duration_ms / 4

        # Calculate spacing
        marker_width = self.BAR_WIDTH // 4
        text.append(" " * (marker_width - 3))
        text.append(format_duration(quarter), style=TEXT_MUTED)
        text.append(" " * (marker_width - len(format_duration(quarter))))
        text.append(format_duration(mid), style=TEXT_MUTED)
        text.append(" " * (marker_width - len(format_duration(mid))))
        text.append(format_duration(three_quarter), style=TEXT_MUTED)

        return Static(text, classes="waterfall-header")

    def _create_row(self, step: Step, depth: int, index: int) -> Static:
        """Create a row widget for a step."""
        text = Text()

        # Indentation
        indent = "  " * depth

        # Icon and type
        icon = self.STEP_TYPE_ICONS.get(step.type.value, "?")
        color = self.STEP_TYPE_COLORS.get(step.type.value, TEXT_MUTED)
        if step.error:
            color = DANGER_RED

        text.append(indent)
        text.append(f"{icon} ", style=color)
        text.append(f"{step.type.value}: ", style=f"{color} dim")

        # Step name (truncated)
        max_name_len = self.LABEL_WIDTH - len(indent) - len(step.type.value) - 5
        name = step.name[:max_name_len] + "..." if len(step.name) > max_name_len else step.name
        text.append(name, style=TEXT_PRIMARY if not step.error else DANGER_RED)

        # Pad to label width
        current_len = len(text.plain)
        if current_len < self.LABEL_WIDTH:
            text.append(" " * (self.LABEL_WIDTH - current_len))

        # Calculate bar position and width
        bar = self._create_timing_bar(step, color)
        text.append(bar)

        # Duration at end
        if step.duration_ms:
            text.append(f" {format_duration(step.duration_ms)}", style=f"{ACCENT_AMBER} dim")

        # Use trace ID in widget ID to ensure uniqueness across trace changes
        trace_id = str(self._trace.id)[:8] if self._trace else "none"
        widget = Static(text, classes="waterfall-row", id=f"step-{trace_id}-{index}")
        # Store step reference for click handling
        widget._step_data = (step, index)  # type: ignore[attr-defined]
        return widget

    def _create_timing_bar(self, step: Step, color: str) -> Text:
        """Create the timing bar for a step."""
        text = Text()

        # Calculate step position relative to trace
        step_start_ms = step.start_time.timestamp() * 1000 - self._trace_start_ms
        step_duration_ms = step.duration_ms or 1.0

        # Ensure non-negative start
        step_start_ms = max(0, step_start_ms)

        # Calculate positions as fractions of bar width
        start_pos = int((step_start_ms / self._trace_duration_ms) * self.BAR_WIDTH)
        bar_len = max(1, int((step_duration_ms / self._trace_duration_ms) * self.BAR_WIDTH))

        # Clamp values
        start_pos = min(start_pos, self.BAR_WIDTH - 1)
        bar_len = min(bar_len, self.BAR_WIDTH - start_pos)

        # Build the bar
        text.append(self.BAR_LIGHT * start_pos, style=TEXT_MUTED)
        text.append(self.BAR_FULL * bar_len, style=color)
        remaining = self.BAR_WIDTH - start_pos - bar_len
        if remaining > 0:
            text.append(self.BAR_LIGHT * remaining, style=TEXT_MUTED)

        return text

    def _update_selection(self) -> None:
        """Update the visual selection state."""
        for idx, widget in enumerate(self._row_widgets):
            if idx == self._cursor_index:
                widget.add_class("waterfall-row-selected")
            else:
                widget.remove_class("waterfall-row-selected")

    def action_move_down(self) -> None:
        """Move cursor down."""
        if self._steps and self._cursor_index < len(self._steps) - 1:
            self._cursor_index += 1
            self._update_selection()
            self._scroll_to_cursor()
            self.post_message(self.StepHighlighted(self._steps[self._cursor_index][0]))

    def action_move_up(self) -> None:
        """Move cursor up."""
        if self._steps and self._cursor_index > 0:
            self._cursor_index -= 1
            self._update_selection()
            self._scroll_to_cursor()
            self.post_message(self.StepHighlighted(self._steps[self._cursor_index][0]))

    def action_select_step(self) -> None:
        """Select the current step."""
        if self._steps and 0 <= self._cursor_index < len(self._steps):
            step = self._steps[self._cursor_index][0]
            self.post_message(self.StepSelected(step))

    def _scroll_to_cursor(self) -> None:
        """Scroll to keep cursor visible."""
        if self._row_widgets and 0 <= self._cursor_index < len(self._row_widgets):
            self._row_widgets[self._cursor_index].scroll_visible()

    def get_selected_step(self) -> Step | None:
        """Get the currently selected step."""
        if self._steps and 0 <= self._cursor_index < len(self._steps):
            return self._steps[self._cursor_index][0]
        return None

    def clear(self) -> None:
        """Clear the waterfall view."""
        self._trace = None
        self._steps = []
        self._cursor_index = 0
        self._row_widgets = []
        self.remove_children()

    def on_click(self, event: Click) -> None:
        """Handle clicks on waterfall rows."""
        if not self._steps:
            return

        # Get the widget at click location
        widget = self.screen.get_widget_at(event.screen_x, event.screen_y)[0]

        # Check if the clicked widget has step data
        if widget and hasattr(widget, "_step_data"):
            step, index = widget._step_data
            self._cursor_index = index
            self._update_selection()
            self.post_message(self.StepSelected(step))
            # Focus the waterfall view
            self.focus()
            event.stop()

    @property
    def step_count(self) -> int:
        """Get the number of steps displayed."""
        return len(self._steps)

    @property
    def current_trace(self) -> AgentRun | None:
        """Get the currently displayed trace."""
        return self._trace
