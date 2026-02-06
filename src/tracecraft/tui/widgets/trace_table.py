"""
Trace table widget for displaying traces in a sortable list.

LangSmith-style table showing all traces at the highest level.
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
    SUCCESS_GREEN,
    SURFACE,
    SURFACE_HIGHLIGHT,
    TEXT_MUTED,
    TEXT_PRIMARY,
    format_duration,
    format_tokens,
    truncate_with_ellipsis,
)

try:
    from textual.binding import Binding
    from textual.message import Message
    from textual.widgets import DataTable

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    Binding = Any  # type: ignore[misc,assignment]
    Message = object  # type: ignore[misc,assignment]
    DataTable = object  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from textual.widgets.data_table import RowKey

    from tracecraft.core.models import AgentRun


class TraceTable(DataTable if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Table widget for displaying agent traces.

    Provides a LangSmith-style table view of all traces with
    sortable columns and row selection.
    """

    class TraceHighlighted(Message if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
        """Message sent when cursor moves to a new trace."""

        def __init__(self, trace: AgentRun | None) -> None:
            """Initialize the message."""
            if TEXTUAL_AVAILABLE:
                super().__init__()
            self.trace = trace

    class TraceSelected(Message if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
        """Message sent when Enter is pressed on a trace."""

        def __init__(self, trace: AgentRun) -> None:
            """Initialize the message."""
            if TEXTUAL_AVAILABLE:
                super().__init__()
            self.trace = trace

    # Column widths
    COL_STATUS = 3
    COL_NAME = 30
    COL_TIME = 10
    COL_DURATION = 10
    COL_TOKENS = 10
    COL_COST = 10
    COL_STEPS = 6

    # Keybindings for vim-style navigation
    BINDINGS: ClassVar[list[Any]] = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("enter", "select_cursor", "Select", show=False),
    ]

    DEFAULT_CSS = f"""
    /* NOIR SIGNAL - Trace Table */
    TraceTable {{
        background: {SURFACE};
        color: {TEXT_PRIMARY};
        border: solid {BORDER};
        height: 1fr;
    }}

    TraceTable:focus {{
        border: solid {ACCENT_AMBER};
    }}

    TraceTable > .datatable--header {{
        background: {SURFACE};
        color: {TEXT_MUTED};
        text-style: bold;
    }}

    TraceTable > .datatable--cursor {{
        background: {SURFACE_HIGHLIGHT};
        color: {ACCENT_AMBER};
    }}

    TraceTable > .datatable--hover {{
        background: {SURFACE_HIGHLIGHT};
    }}

    TraceTable > .datatable--even-row {{
        background: {SURFACE};
    }}

    TraceTable > .datatable--odd-row {{
        background: {SURFACE};
    }}
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the trace table."""
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__(*args, **kwargs)
        self._traces: list[AgentRun] = []
        self._row_key_to_trace: dict[RowKey, AgentRun] = {}
        self._trace_id_to_row_key: dict[str, RowKey] = {}
        self._setup_columns()

    def _setup_columns(self) -> None:
        """Set up the table columns."""
        self.add_column("", width=self.COL_STATUS, key="status")
        self.add_column("NAME", width=self.COL_NAME, key="name")
        self.add_column("TIME", width=self.COL_TIME, key="time")
        self.add_column("DURATION", width=self.COL_DURATION, key="duration")
        self.add_column("TOKENS", width=self.COL_TOKENS, key="tokens")
        self.add_column("COST", width=self.COL_COST, key="cost")
        self.add_column("STEPS", width=self.COL_STEPS, key="steps")
        self.cursor_type = "row"
        self.zebra_stripes = False

    def show_traces(self, traces: list[AgentRun], *, is_filtered: bool = False) -> None:
        """
        Populate the table with traces.

        Args:
            traces: List of AgentRun objects to display.
            is_filtered: Whether the traces are a filtered subset.
        """
        self._traces = traces
        self._row_key_to_trace.clear()
        self._trace_id_to_row_key.clear()
        self.clear()

        if not traces:
            # Show empty state
            if is_filtered:
                empty_text = Text("No matches. Try broadening your filter.", style=TEXT_MUTED)
            else:
                empty_text = Text(
                    "No traces found. Run your agent to capture traces.", style=TEXT_MUTED
                )
            row_key = self.add_row(
                "",
                empty_text,
                "",
                "",
                "",
                "",
                "",
                key="empty",
            )
            return

        # Add traces (most recent first)
        for trace in reversed(traces):
            row_key = self._add_trace_row(trace)
            self._row_key_to_trace[row_key] = trace
            self._trace_id_to_row_key[str(trace.id)] = row_key

    def _add_trace_row(self, trace: AgentRun) -> RowKey:
        """Add a single trace row to the table."""
        # Status column - colored indicator
        if trace.error or trace.error_count > 0:
            status = Text("✕", style=f"{DANGER_RED} bold")
        else:
            status = Text("✓", style=SUCCESS_GREEN)

        # Name column - truncated
        name = truncate_with_ellipsis(trace.name, self.COL_NAME - 2)
        name_text = Text(name, style=TEXT_PRIMARY)

        # Time column
        time_str = trace.start_time.strftime("%H:%M:%S")
        time_text = Text(time_str, style=TEXT_MUTED)

        # Duration column
        if trace.duration_ms:
            duration_str = format_duration(trace.duration_ms)
            duration_text = Text(duration_str, style=ACCENT_AMBER)
        else:
            duration_text = Text("-", style=TEXT_MUTED)

        # Tokens column
        if trace.total_tokens > 0:
            tokens_str = format_tokens(trace.total_tokens)
            tokens_text = Text(tokens_str, style=TEXT_MUTED)
        else:
            tokens_text = Text("-", style=TEXT_MUTED)

        # Cost column
        if trace.total_cost_usd > 0:
            cost_str = f"${trace.total_cost_usd:.4f}"
            cost_text = Text(cost_str, style=TEXT_MUTED)
        else:
            cost_text = Text("-", style=TEXT_MUTED)

        # Steps column - count total steps
        step_count = self._count_steps(trace.steps)
        steps_text = Text(str(step_count), style=TEXT_MUTED)

        return self.add_row(
            status,
            name_text,
            time_text,
            duration_text,
            tokens_text,
            cost_text,
            steps_text,
            key=str(trace.id),
        )

    def _count_steps(self, steps: list[Any]) -> int:
        """Recursively count all steps."""
        count = len(steps)
        for step in steps:
            if step.children:
                count += self._count_steps(step.children)
        return count

    def get_selected_trace(self) -> AgentRun | None:
        """Get the currently selected trace."""
        if self.cursor_row is not None and self.row_count > 0:
            try:
                row_key = self.get_row_at(self.cursor_row)
                return self._row_key_to_trace.get(row_key)
            except Exception:
                return None
        return None

    def select_trace_by_id(self, trace_id: str) -> bool:
        """
        Select a trace by its ID.

        Args:
            trace_id: The trace ID to select.

        Returns:
            True if the trace was found and selected, False otherwise.
        """
        row_key = self._trace_id_to_row_key.get(trace_id)
        if row_key:
            # Find the row index for this key
            for idx in range(self.row_count):
                if self.get_row_at(idx) == row_key:
                    self.cursor_row = idx
                    return True
        return False

    def on_data_table_row_highlighted(self, event: Any) -> None:
        """Handle row highlight (cursor movement)."""
        trace = self._row_key_to_trace.get(event.row_key)
        self.post_message(self.TraceHighlighted(trace))

    def on_data_table_row_selected(self, event: Any) -> None:
        """Handle row selection (Enter pressed or click)."""
        trace = self._row_key_to_trace.get(event.row_key)
        if trace:
            # Also post highlighted to ensure waterfall updates on click
            self.post_message(self.TraceHighlighted(trace))
            self.post_message(self.TraceSelected(trace))

    @property
    def trace_count(self) -> int:
        """Get the number of traces in the table."""
        return len(self._traces)
