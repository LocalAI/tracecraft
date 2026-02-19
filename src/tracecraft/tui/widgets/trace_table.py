"""
Trace table widget for displaying traces in a sortable list.

LangSmith-style table showing all traces at the highest level.
NOIR SIGNAL theme styling with sortable columns and column reordering.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar
from uuid import UUID

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


@dataclass
class ColumnDef:
    """Definition for a table column."""

    key: str
    label: str
    width: int
    sortable: bool = True
    sort_key: Callable[[Any, dict[str, str], dict[str, str]], Any] | None = None


class TraceTable(DataTable if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Table widget for displaying agent traces.

    Provides a LangSmith-style table view of all traces with
    sortable columns, column reordering, and row selection.

    Keybindings:
        s: Cycle sort column forward
        S: Cycle sort column backward
        r: Reverse sort direction
        <: Move current column left
        >: Move current column right
        1-9: Sort by column number
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

    class SortChanged(Message if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
        """Message sent when sort column or direction changes."""

        def __init__(self, column: str, ascending: bool) -> None:
            """Initialize the message."""
            if TEXTUAL_AVAILABLE:
                super().__init__()
            self.column = column
            self.ascending = ascending

    class ColumnsReordered(Message if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
        """Message sent when columns are reordered."""

        def __init__(self, column_order: list[str]) -> None:
            """Initialize the message."""
            if TEXTUAL_AVAILABLE:
                super().__init__()
            self.column_order = column_order

    # Default column definitions
    DEFAULT_COLUMNS: ClassVar[list[ColumnDef]] = [
        ColumnDef(
            key="status",
            label="",
            width=3,
            sortable=True,
            sort_key=lambda t, _p, _s: (0 if (t.error or t.error_count > 0) else 1),
        ),
        ColumnDef(
            key="name",
            label="NAME",
            width=25,
            sortable=True,
            sort_key=lambda t, _p, _s: t.name.lower(),
        ),
        ColumnDef(
            key="project",
            label="PROJECT",
            width=15,
            sortable=True,
            sort_key=lambda t, p, _s: p.get(
                t.attributes.get("project_id", "") if t.attributes else "", ""
            ).lower(),
        ),
        ColumnDef(
            key="session",
            label="SESSION",
            width=15,
            sortable=True,
            sort_key=lambda t, _p, s: s.get(t.session_id or "", "").lower(),
        ),
        ColumnDef(
            key="time",
            label="TIME",
            width=10,
            sortable=True,
            sort_key=lambda t, _p, _s: t.start_time,
        ),
        ColumnDef(
            key="duration",
            label="DURATION",
            width=10,
            sortable=True,
            sort_key=lambda t, _p, _s: t.duration_ms or 0,
        ),
        ColumnDef(
            key="tokens",
            label="TOKENS",
            width=10,
            sortable=True,
            sort_key=lambda t, _p, _s: t.total_tokens,
        ),
        ColumnDef(
            key="cost",
            label="COST",
            width=10,
            sortable=True,
            sort_key=lambda t, _p, _s: t.total_cost_usd,
        ),
        ColumnDef(
            key="steps",
            label="STEPS",
            width=6,
            sortable=True,
            sort_key=None,  # Will use _count_steps
        ),
    ]

    # Keybindings for vim-style navigation and sorting
    BINDINGS: ClassVar[list[Any]] = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("enter", "select_cursor", "Select", show=False),
        # Sorting
        Binding("s", "cycle_sort_forward", "Sort", show=True),
        Binding("S", "cycle_sort_backward", "Sort←", show=False),
        Binding("r", "reverse_sort", "Reverse", show=True),
        # Column reordering
        Binding("<", "move_column_left", "Col←", show=False),
        Binding(">", "move_column_right", "Col→", show=False),
        Binding("comma", "move_column_left", "Col←", show=False),
        Binding("period", "move_column_right", "Col→", show=False),
        # Direct column sort (1-9)
        Binding("1", "sort_column_1", "Sort 1", show=False),
        Binding("2", "sort_column_2", "Sort 2", show=False),
        Binding("3", "sort_column_3", "Sort 3", show=False),
        Binding("4", "sort_column_4", "Sort 4", show=False),
        Binding("5", "sort_column_5", "Sort 5", show=False),
        Binding("6", "sort_column_6", "Sort 6", show=False),
        Binding("7", "sort_column_7", "Sort 7", show=False),
        Binding("8", "sort_column_8", "Sort 8", show=False),
        Binding("9", "sort_column_9", "Sort 9", show=False),
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
        # Name mappings for project/session display
        self._project_names: dict[str, str] = {}
        self._session_names: dict[str, str] = {}
        # Column management
        self._column_order: list[str] = [col.key for col in self.DEFAULT_COLUMNS]
        self._column_defs: dict[str, ColumnDef] = {col.key: col for col in self.DEFAULT_COLUMNS}
        # Sorting state
        self._sort_column: str = "time"
        self._sort_ascending: bool = False  # Default: most recent first
        # Track current column for reordering
        self._current_column_index: int = 0
        # Track if we need to refresh
        self._is_filtered: bool = False
        # Track marked trace for comparison
        self._marked_trace_id: UUID | None = None
        self._setup_columns()

    def _setup_columns(self) -> None:
        """Set up the table columns based on current order."""
        for col_key in self._column_order:
            col_def = self._column_defs[col_key]
            label = self._get_column_label(col_key)
            self.add_column(label, width=col_def.width, key=col_key)

        self.cursor_type = "row"
        self.zebra_stripes = False

    def _get_column_label(self, col_key: str) -> str | Text:
        """Get column label with sort indicator if applicable."""
        col_def = self._column_defs[col_key]
        base_label = col_def.label

        if col_key == self._sort_column and col_def.sortable:
            indicator = "▲" if self._sort_ascending else "▼"
            if base_label:
                return Text(f"{base_label} {indicator}", style=INFO_BLUE)
            return Text(indicator, style=INFO_BLUE)
        return base_label

    def _rebuild_columns(self) -> None:
        """Rebuild columns after reordering or sort change."""
        # Store current selection
        selected_trace = self.get_selected_trace()

        # Clear rows AND columns using proper DataTable API
        # This clears _column_locations, _row_locations, columns, and rows
        self.clear(columns=True)
        self._row_key_to_trace.clear()
        self._trace_id_to_row_key.clear()

        # Setup columns with new order
        for col_key in self._column_order:
            col_def = self._column_defs[col_key]
            label = self._get_column_label(col_key)
            self.add_column(label, width=col_def.width, key=col_key)

        # Re-add traces
        self._populate_table()

        # Restore selection
        if selected_trace:
            self.select_trace_by_id(str(selected_trace.id))

    def _update_column_headers(self) -> None:
        """Update column headers to reflect current sort state."""
        # Unfortunately Textual's DataTable doesn't support updating column labels
        # So we need to rebuild the table
        self._rebuild_columns()

    def set_name_mappings(
        self,
        project_names: dict[str, str] | None = None,
        session_names: dict[str, str] | None = None,
    ) -> None:
        """
        Set the name mappings for projects and sessions.

        Args:
            project_names: Dict mapping project_id to project_name.
            session_names: Dict mapping session_id to session_name.
        """
        if project_names is not None:
            self._project_names = project_names
        if session_names is not None:
            self._session_names = session_names

    def show_traces(self, traces: list[AgentRun], *, is_filtered: bool = False) -> None:
        """
        Populate the table with traces.

        Args:
            traces: List of AgentRun objects to display.
            is_filtered: Whether the traces are a filtered subset.
        """
        self._traces = traces
        self._is_filtered = is_filtered
        self._row_key_to_trace.clear()
        self._trace_id_to_row_key.clear()
        self.clear()
        self._populate_table()

    def _populate_table(self) -> None:
        """Populate the table with sorted traces."""
        if not self._traces:
            # Show empty state
            if self._is_filtered:
                empty_text = Text("No matches. Try broadening your filter.", style=TEXT_MUTED)
            else:
                empty_text = Text(
                    "No traces found. Run your agent to capture traces.", style=TEXT_MUTED
                )
            # Add empty row with correct number of columns
            empty_row = ["", empty_text] + [""] * (len(self._column_order) - 2)
            self.add_row(*empty_row, key="empty")
            return

        # Sort traces
        sorted_traces = self._sort_traces(self._traces)

        # Add traces in sorted order
        for trace in sorted_traces:
            row_key = self._add_trace_row(trace)
            self._row_key_to_trace[row_key] = trace
            self._trace_id_to_row_key[str(trace.id)] = row_key

    def _sort_traces(self, traces: list[AgentRun]) -> list[AgentRun]:
        """Sort traces by current sort column and direction."""
        col_def = self._column_defs.get(self._sort_column)
        if not col_def or not col_def.sortable:
            # Default: most recent first
            return list(reversed(traces))

        # Get sort key function
        def _sort_by_steps(t: AgentRun, _p: dict[str, str], _s: dict[str, str]) -> int:
            return self._count_steps(t.steps)

        def _sort_by_time(t: AgentRun, _p: dict[str, str], _s: dict[str, str]) -> datetime:
            return t.start_time

        if col_def.sort_key:
            sort_fn = col_def.sort_key
        elif self._sort_column == "steps":
            # Special case for steps - count them
            sort_fn = _sort_by_steps
        else:
            # Fallback to time
            sort_fn = _sort_by_time

        try:
            sorted_traces = sorted(
                traces,
                key=lambda t: sort_fn(t, self._project_names, self._session_names),
                reverse=not self._sort_ascending,
            )
        except Exception:
            # If sorting fails, fall back to default order
            sorted_traces = list(reversed(traces))

        return sorted_traces

    def _add_trace_row(self, trace: AgentRun) -> RowKey:
        """Add a single trace row to the table."""
        # Build cell values for each column in current order
        cells: list[Any] = []

        for col_key in self._column_order:
            cell = self._get_cell_value(trace, col_key)
            cells.append(cell)

        return self.add_row(*cells, key=str(trace.id))

    def _get_cell_value(self, trace: AgentRun, col_key: str) -> Text | str:
        """Get the display value for a cell."""
        col_def = self._column_defs[col_key]

        if col_key == "status":
            # Blue diamond for marked trace (takes precedence)
            is_marked = self._marked_trace_id and trace.id == self._marked_trace_id
            if is_marked:
                return Text("◆", style=f"{INFO_BLUE} bold")
            # Error/success status
            if trace.error or trace.error_count > 0:
                return Text("✕", style=f"{DANGER_RED} bold")
            return Text("✓", style=SUCCESS_GREEN)

        if col_key == "name":
            name = truncate_with_ellipsis(trace.name, col_def.width - 2)
            return Text(name, style=TEXT_PRIMARY)

        if col_key == "project":
            project_id = trace.attributes.get("project_id") if trace.attributes else None
            if project_id:
                project_name = self._project_names.get(project_id, "-")
                project_display = truncate_with_ellipsis(project_name, col_def.width - 2)
            else:
                project_display = "-"
            return Text(project_display, style=TEXT_MUTED)

        if col_key == "session":
            if trace.session_id:
                session_name = self._session_names.get(trace.session_id, "-")
                session_display = truncate_with_ellipsis(session_name, col_def.width - 2)
            else:
                session_display = "-"
            return Text(session_display, style=TEXT_MUTED)

        if col_key == "time":
            time_str = trace.start_time.strftime("%H:%M:%S")
            return Text(time_str, style=TEXT_MUTED)

        if col_key == "duration":
            if trace.duration_ms:
                duration_str = format_duration(trace.duration_ms)
                return Text(duration_str, style=ACCENT_AMBER)
            return Text("-", style=TEXT_MUTED)

        if col_key == "tokens":
            if trace.total_tokens > 0:
                tokens_str = format_tokens(trace.total_tokens)
                return Text(tokens_str, style=TEXT_MUTED)
            return Text("-", style=TEXT_MUTED)

        if col_key == "cost":
            if trace.total_cost_usd > 0:
                cost_str = f"${trace.total_cost_usd:.5f}"
                return Text(cost_str, style=TEXT_MUTED)
            return Text("-", style=TEXT_MUTED)

        if col_key == "steps":
            step_count = self._count_steps(trace.steps)
            return Text(str(step_count), style=TEXT_MUTED)

        return ""

    def _count_steps(self, steps: list[Any]) -> int:
        """Recursively count all steps."""
        count = len(steps)
        for step in steps:
            if step.children:
                count += self._count_steps(step.children)
        return count

    # === Sorting Actions ===

    def action_cycle_sort_forward(self) -> None:
        """Cycle to the next sortable column."""
        sortable_columns = [k for k in self._column_order if self._column_defs[k].sortable]
        if not sortable_columns:
            return

        try:
            current_idx = sortable_columns.index(self._sort_column)
            next_idx = (current_idx + 1) % len(sortable_columns)
        except ValueError:
            next_idx = 0

        self._sort_column = sortable_columns[next_idx]
        self._sort_ascending = False  # Reset to descending when changing column
        self._update_column_headers()
        self.post_message(self.SortChanged(self._sort_column, self._sort_ascending))

    def action_cycle_sort_backward(self) -> None:
        """Cycle to the previous sortable column."""
        sortable_columns = [k for k in self._column_order if self._column_defs[k].sortable]
        if not sortable_columns:
            return

        try:
            current_idx = sortable_columns.index(self._sort_column)
            prev_idx = (current_idx - 1) % len(sortable_columns)
        except ValueError:
            prev_idx = len(sortable_columns) - 1

        self._sort_column = sortable_columns[prev_idx]
        self._sort_ascending = False  # Reset to descending when changing column
        self._update_column_headers()
        self.post_message(self.SortChanged(self._sort_column, self._sort_ascending))

    def action_reverse_sort(self) -> None:
        """Reverse the current sort direction."""
        self._sort_ascending = not self._sort_ascending
        self._update_column_headers()
        self.post_message(self.SortChanged(self._sort_column, self._sort_ascending))

    def _sort_by_column_index(self, index: int) -> None:
        """Sort by column at the given index (0-based)."""
        if 0 <= index < len(self._column_order):
            col_key = self._column_order[index]
            if self._column_defs[col_key].sortable:
                if self._sort_column == col_key:
                    # Toggle direction if same column
                    self._sort_ascending = not self._sort_ascending
                else:
                    self._sort_column = col_key
                    self._sort_ascending = False
                self._update_column_headers()
                self.post_message(self.SortChanged(self._sort_column, self._sort_ascending))

    def action_sort_column_1(self) -> None:
        """Sort by column 1."""
        self._sort_by_column_index(0)

    def action_sort_column_2(self) -> None:
        """Sort by column 2."""
        self._sort_by_column_index(1)

    def action_sort_column_3(self) -> None:
        """Sort by column 3."""
        self._sort_by_column_index(2)

    def action_sort_column_4(self) -> None:
        """Sort by column 4."""
        self._sort_by_column_index(3)

    def action_sort_column_5(self) -> None:
        """Sort by column 5."""
        self._sort_by_column_index(4)

    def action_sort_column_6(self) -> None:
        """Sort by column 6."""
        self._sort_by_column_index(5)

    def action_sort_column_7(self) -> None:
        """Sort by column 7."""
        self._sort_by_column_index(6)

    def action_sort_column_8(self) -> None:
        """Sort by column 8."""
        self._sort_by_column_index(7)

    def action_sort_column_9(self) -> None:
        """Sort by column 9."""
        self._sort_by_column_index(8)

    # === Column Reordering Actions ===

    def action_move_column_left(self) -> None:
        """Move the current column left."""
        if self._current_column_index <= 0:
            return

        # Swap columns
        idx = self._current_column_index
        self._column_order[idx], self._column_order[idx - 1] = (
            self._column_order[idx - 1],
            self._column_order[idx],
        )
        self._current_column_index -= 1

        self._rebuild_columns()
        self.post_message(self.ColumnsReordered(self._column_order.copy()))

    def action_move_column_right(self) -> None:
        """Move the current column right."""
        if self._current_column_index >= len(self._column_order) - 1:
            return

        # Swap columns
        idx = self._current_column_index
        self._column_order[idx], self._column_order[idx + 1] = (
            self._column_order[idx + 1],
            self._column_order[idx],
        )
        self._current_column_index += 1

        self._rebuild_columns()
        self.post_message(self.ColumnsReordered(self._column_order.copy()))

    def set_current_column(self, column_key: str) -> None:
        """Set the current column for reordering operations."""
        with contextlib.suppress(ValueError):
            self._current_column_index = self._column_order.index(column_key)

    def get_column_order(self) -> list[str]:
        """Get the current column order."""
        return self._column_order.copy()

    def set_column_order(self, order: list[str]) -> None:
        """
        Set the column order.

        Args:
            order: List of column keys in desired order.
        """
        # Validate all keys are valid
        valid_keys = set(self._column_defs.keys())
        if set(order) != valid_keys:
            return  # Invalid order, ignore

        self._column_order = order.copy()
        self._rebuild_columns()

    def get_sort_state(self) -> tuple[str, bool]:
        """Get current sort state (column, ascending)."""
        return self._sort_column, self._sort_ascending

    def set_sort_state(self, column: str, ascending: bool) -> None:
        """
        Set the sort state.

        Args:
            column: Column key to sort by.
            ascending: True for ascending, False for descending.
        """
        if column in self._column_defs and self._column_defs[column].sortable:
            self._sort_column = column
            self._sort_ascending = ascending
            if self._traces:
                self._update_column_headers()

    # === Selection Methods ===

    def get_selected_trace(self) -> AgentRun | None:
        """Get the currently selected trace."""
        if self.cursor_row is not None and self.row_count > 0:
            try:
                # Use coordinate_to_cell_key to get the row key from cursor position
                row_key, _ = self.coordinate_to_cell_key(self.cursor_coordinate)
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
            try:
                # Use get_row_index to find row index from key
                idx = self.get_row_index(row_key)
                self.cursor_row = idx
                return True
            except Exception:
                return False
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

    def on_data_table_header_selected(self, event: Any) -> None:
        """Handle column header click for sorting."""
        col_key = str(event.column_key)
        if col_key in self._column_defs and self._column_defs[col_key].sortable:
            # Also set as current column for reordering
            self._current_column_index = self._column_order.index(col_key)

            if self._sort_column == col_key:
                # Toggle direction
                self._sort_ascending = not self._sort_ascending
            else:
                self._sort_column = col_key
                self._sort_ascending = False

            self._update_column_headers()
            self.post_message(self.SortChanged(self._sort_column, self._sort_ascending))

    @property
    def trace_count(self) -> int:
        """Get the number of traces in the table."""
        return len(self._traces)

    @property
    def sort_column(self) -> str:
        """Get the current sort column key."""
        return self._sort_column

    @property
    def sort_ascending(self) -> bool:
        """Get whether sort is ascending."""
        return self._sort_ascending

    @property
    def selected_trace(self) -> AgentRun | None:
        """Get the currently selected trace."""
        return self.get_selected_trace()

    @property
    def marked_trace_id(self) -> UUID | None:
        """Get the ID of the marked trace."""
        return self._marked_trace_id

    def set_marked_trace(self, trace_id: UUID | None) -> None:
        """
        Set the marked trace for comparison.

        Args:
            trace_id: The trace ID to mark, or None to clear.
        """
        old_marked = self._marked_trace_id
        self._marked_trace_id = trace_id

        # Refresh affected rows to update mark indicator
        if old_marked:
            old_row_key = self._trace_id_to_row_key.get(str(old_marked))
            if old_row_key and old_row_key in self._row_key_to_trace:
                trace = self._row_key_to_trace[old_row_key]
                self._update_row(old_row_key, trace)

        if trace_id:
            new_row_key = self._trace_id_to_row_key.get(str(trace_id))
            if new_row_key and new_row_key in self._row_key_to_trace:
                trace = self._row_key_to_trace[new_row_key]
                self._update_row(new_row_key, trace)

    def _update_row(self, row_key: Any, trace: AgentRun) -> None:
        """Update a single row in the table."""
        # Use update_cell with row_key and column_key directly
        for col_key in self._column_order:
            cell = self._get_cell_value(trace, col_key)
            self.update_cell(row_key, col_key, cell)
