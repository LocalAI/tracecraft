"""
Input/Output viewer widget.

Displays inputs, outputs, and attributes as formatted JSON or tables.
NOIR SIGNAL theme styling.
"""

from __future__ import annotations

import json
from contextlib import suppress
from datetime import UTC
from typing import TYPE_CHECKING, Any

from rich.box import SIMPLE
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

# Import theme constants for consistent styling
from tracecraft.tui.theme import (
    ACCENT_AMBER,
    BORDER,
    DANGER_RED,
    INFO_BLUE,
    PANEL_BACKGROUND,
    PANEL_BORDER_DANGER,
    PANEL_BORDER_DEFAULT,
    PANEL_BORDER_INFO,
    SUCCESS_GREEN,
    SURFACE,
    SURFACE_HIGHLIGHT,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

try:
    from textual.containers import Horizontal
    from textual.widgets import RichLog, Static

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    RichLog = object  # type: ignore[misc,assignment]
    Horizontal = object  # type: ignore[misc,assignment]
    Static = object  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun, Step


class ModeIndicator(Horizontal if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Mode indicator bar showing [I] [O] [D] with current mode highlighted.

    Displays above the IOViewer to show current viewing mode.
    Press Tab to cycle through modes.
    """

    # Simplified mode labels: Input, Output, Detail (+ Error when present)
    MODES = [
        ("I", "input", "Input"),
        ("O", "output", "Output"),
        ("D", "detail", "Detail"),
        ("E", "error", "Error"),
    ]

    DEFAULT_CSS = f"""
    ModeIndicator {{
        height: 1;
        background: {SURFACE};
        padding: 0 1;
    }}

    ModeIndicator > Static {{
        width: auto;
        padding: 0 1;
        color: {TEXT_MUTED};
    }}

    ModeIndicator > .mode-active {{
        color: {ACCENT_AMBER};
        text-style: bold;
        background: {SURFACE_HIGHLIGHT};
    }}

    ModeIndicator > .mode-label {{
        color: {TEXT_MUTED};
        padding: 0 0 0 1;
    }}
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the mode indicator."""
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__(*args, **kwargs)
        self._current_mode: str = "output"
        self._has_error: bool = False

    def compose(self) -> Any:
        """Compose the mode indicator layout."""
        yield Static("View:", classes="mode-label")
        for key, mode_id, _name in self.MODES:
            classes = "mode-item"
            if mode_id == self._current_mode:
                classes = "mode-item mode-active"
            yield Static(f"[{key}]", id=f"mode-{mode_id}", classes=classes)

    def set_mode(self, mode: str) -> None:
        """
        Update the indicator to show the current mode.

        Args:
            mode: The current viewing mode.
        """
        self._current_mode = mode
        self._update_display()

    def set_has_error(self, has_error: bool) -> None:
        """
        Set whether error mode should be visible.

        Args:
            has_error: True if current item has an error.
        """
        self._has_error = has_error
        self._update_display()

    def _update_display(self) -> None:
        """Update the visual state of mode indicators."""
        for _key, mode_id, _name in self.MODES:
            with suppress(Exception):  # Widget may not yet be mounted
                indicator = self.query_one(f"#mode-{mode_id}", Static)

                # Update classes
                indicator.remove_class("mode-active")
                if mode_id == self._current_mode:
                    indicator.add_class("mode-active")

                # Show/hide error mode based on whether item has error
                if mode_id == "error":
                    indicator.display = self._has_error


class IOViewer(RichLog if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Widget for viewing inputs, outputs, and attributes.

    Provides syntax-highlighted, scrollable JSON viewing with tabs for
    different data sections. Uses RichLog for built-in scrolling support.
    """

    # View modes
    # Simplified view modes: INPUT, OUTPUT, DETAIL (+ ERROR when applicable)
    MODE_INPUT = "input"
    MODE_OUTPUT = "output"
    MODE_DETAIL = "detail"  # Combines attributes + full JSON
    MODE_ERROR = "error"

    DEFAULT_CSS = f"""
    /* NOIR SIGNAL - IO Viewer */
    IOViewer {{
        background: {SURFACE};
        border: solid {BORDER};
        padding: 0;
    }}

    IOViewer:focus {{
        border: solid {ACCENT_AMBER};
    }}
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the IO viewer."""
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        # RichLog configuration: enable highlighting and markup for rich content
        super().__init__(*args, highlight=True, markup=True, **kwargs)
        self._current_run: AgentRun | None = None
        self._current_step: Step | None = None
        self._mode: str = self.MODE_OUTPUT

    def show_run(self, run: AgentRun | None) -> None:
        """
        Display data for a run.

        Args:
            run: The AgentRun to display, or None to clear.
        """
        self._current_run = run
        self._current_step = None
        self._update_display()

    def show_step(self, step: Step | None) -> None:
        """
        Display data for a step.

        Args:
            step: The Step to display, or None to clear.
        """
        self._current_step = step
        self._update_display()

    def set_mode(self, mode: str) -> None:
        """
        Set the viewing mode.

        Args:
            mode: One of MODE_INPUT, MODE_OUTPUT, MODE_DETAIL, MODE_ERROR.
        """
        self._mode = mode
        self._update_display()

    def cycle_mode(self) -> None:
        """Cycle through viewing modes: INPUT → OUTPUT → DETAIL (→ ERROR if present)."""
        modes = [
            self.MODE_INPUT,
            self.MODE_OUTPUT,
            self.MODE_DETAIL,
        ]

        # Add error mode if there's an error
        if (self._current_step and self._current_step.error) or (
            self._current_run and self._current_run.error
        ):
            modes.append(self.MODE_ERROR)

        try:
            current_idx = modes.index(self._mode)
            next_idx = (current_idx + 1) % len(modes)
            self._mode = modes[next_idx]
        except ValueError:
            self._mode = self.MODE_OUTPUT

        self._update_display()

    def _update_display(self) -> None:
        """Update the viewer content."""
        # Clear existing content for RichLog
        self.clear()

        if self._current_step:
            content = self._render_step_content(self._current_step)
        elif self._current_run:
            content = self._render_run_content(self._current_run)
        else:
            content = self._render_empty()

        # Write content to RichLog (supports scrolling)
        self.write(content)

    def _render_run_content(self, run: AgentRun) -> Panel:
        """Render content for a run."""
        title = f"Run: {run.name} [{self._mode.upper()}]"

        if self._mode == self.MODE_INPUT:
            data = run.input
        elif self._mode == self.MODE_OUTPUT:
            data = run.output
        elif self._mode == self.MODE_ERROR:
            if run.error:
                error_type = run.error_type or "Error"
                return Panel(
                    Text(f"{error_type}: {run.error}", style=DANGER_RED),
                    title=title,
                    title_align="left",
                    border_style=PANEL_BORDER_DANGER,
                    style=PANEL_BACKGROUND,
                )
            data = None
        else:  # DETAIL mode - full JSON representation
            data = run.model_dump(mode="json", exclude={"steps"})

        return self._render_data_panel(data, title)

    def _render_step_content(self, step: Step) -> Panel:
        """Render content for a step."""
        title = f"Step: {step.name} [{self._mode.upper()}]"

        if self._mode == self.MODE_INPUT:
            data = step.inputs
        elif self._mode == self.MODE_OUTPUT:
            data = step.outputs
        elif self._mode == self.MODE_ERROR:
            if step.error:
                error_type = step.error_type or "Error"
                return Panel(
                    Text(f"{error_type}: {step.error}", style=DANGER_RED),
                    title=title,
                    title_align="left",
                    border_style=PANEL_BORDER_DANGER,
                    style=PANEL_BACKGROUND,
                )
            data = None
        else:  # DETAIL mode - full JSON representation
            data = step.model_dump(mode="json", exclude={"children"})

        return self._render_data_panel(data, title)

    def _format_relative_time(self, timestamp: str | None) -> str:
        """Format a timestamp as relative time (e.g., '2 hours ago')."""
        if not timestamp:
            return "-"
        try:
            from datetime import datetime, timezone

            # Parse ISO format timestamp
            if timestamp.endswith("Z"):
                timestamp = timestamp[:-1] + "+00:00"
            dt = datetime.fromisoformat(timestamp)

            # Make naive datetime aware (assume UTC)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)

            now = datetime.now(UTC)
            diff = now - dt

            seconds = diff.total_seconds()
            if seconds < 60:
                return "just now"
            elif seconds < 3600:
                mins = int(seconds / 60)
                return f"{mins} min{'s' if mins != 1 else ''} ago"
            elif seconds < 86400:
                hours = int(seconds / 3600)
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
            elif seconds < 604800:
                days = int(seconds / 86400)
                return f"{days} day{'s' if days != 1 else ''} ago"
            else:
                return dt.strftime("%b %d, %Y")
        except (ValueError, TypeError):
            return str(timestamp)[:16] if timestamp else "-"

    def _format_duration_ms(self, ms: float | None) -> str:
        """Format duration in milliseconds to human readable string."""
        if ms is None:
            return "-"
        if ms < 1000:
            return f"{ms:.0f}ms"
        return f"{ms / 1000:.1f}s"

    def _render_json_panel(self, data: Any, title: str) -> Panel:
        """Render data as a JSON panel with syntax highlighting."""
        if data is None:
            content = Text("No data.", style=TEXT_MUTED)
            return Panel(
                content,
                title=title,
                title_align="left",
                border_style=PANEL_BORDER_DEFAULT,
                style=PANEL_BACKGROUND,
            )

        try:
            json_str = json.dumps(data, indent=2, default=str)
            # No truncation needed - RichLog handles scrolling
            content = Syntax(json_str, "json", theme="monokai", line_numbers=True)
        except (TypeError, ValueError):
            content = Text(str(data), style=TEXT_PRIMARY)

        return Panel(
            content,
            title=title,
            title_align="left",
            border_style=PANEL_BORDER_INFO,
            style=PANEL_BACKGROUND,
        )

    def _render_empty(self) -> Panel:
        """Render empty state."""
        text = Text("Select a trace or step to view data.", style=TEXT_MUTED)
        return Panel(
            text,
            title="DATA",
            title_align="left",
            border_style=PANEL_BORDER_DEFAULT,
            style=PANEL_BACKGROUND,
        )

    @property
    def mode(self) -> str:
        """Get the current viewing mode."""
        return self._mode

    def _should_use_table(self, data: Any) -> bool:
        """Determine if data should be displayed as a table.

        Returns True for:
        - Flat dicts with 3+ keys (worth showing as table)
        - Lists of flat dicts (tabular data like eval results)

        Returns False for:
        - Nested structures with complex values
        - Small dicts (1-2 keys - not worth a table)
        - Primitives or empty data
        """
        # Check for list of dicts (tabular data)
        if isinstance(data, list) and len(data) >= 2:
            # Check if all items are flat dicts with same keys
            if all(isinstance(item, dict) for item in data):
                first_keys = set(data[0].keys()) if data[0] else set()
                if first_keys and all(set(item.keys()) == first_keys for item in data):
                    # Check if values are flat
                    for item in data:
                        for value in item.values():
                            if isinstance(value, (dict, list)) and value:
                                return False
                    return True
            return False

        if not isinstance(data, dict):
            return False

        if not data:
            return False

        # Require at least 3 keys to make a table worthwhile
        if len(data) < 3:
            return False

        # Check if all values are "flat" (not dicts or lists)
        for value in data.values():
            if isinstance(value, (dict, list)):
                # Allow empty lists/dicts
                if value:
                    return False
        return True

    def _render_table_panel(self, data: dict[str, Any], title: str) -> Panel:
        """Render data as a key-value table."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Key", style=TEXT_MUTED, width=20)
        table.add_column("Value", style=TEXT_PRIMARY)

        for key, value in data.items():
            # Format the key (uppercase for consistency)
            key_display = str(key).upper()

            # Format the value
            if value is None:
                value_display = Text("-", style=TEXT_MUTED)
            elif isinstance(value, bool):
                value_display = Text(
                    "yes" if value else "no", style=INFO_BLUE if value else TEXT_MUTED
                )
            elif isinstance(value, (int, float)):
                if isinstance(value, float):
                    value_display = f"{value:.4f}"
                else:
                    value_display = f"{value:,}"
            elif isinstance(value, (list, dict)):
                # Empty containers
                value_display = Text("(empty)", style=TEXT_MUTED)
            else:
                # Truncate long strings
                str_val = str(value)
                if len(str_val) > 60:
                    str_val = str_val[:57] + "..."
                value_display = str_val

            table.add_row(key_display, value_display)

        return Panel(
            table,
            title=f"{title} [TABLE]",
            title_align="left",
            border_style=PANEL_BORDER_INFO,
            style=PANEL_BACKGROUND,
        )

    def _render_list_table_panel(self, data: list[dict[str, Any]], title: str) -> Panel:
        """Render a list of dicts as a multi-row table with headers."""
        if not data:
            return self._render_table_panel({}, title)

        # Get column names from first item
        columns = list(data[0].keys())

        table = Table(show_header=True, box=SIMPLE, padding=(0, 1))
        for col in columns:
            # Format column header
            col_display = str(col).replace("_", " ").title()
            table.add_column(col_display, style=TEXT_PRIMARY)

        # Add rows
        for item in data:
            row_values = []
            for col in columns:
                value = item.get(col)
                if value is None:
                    row_values.append(Text("-", style=TEXT_MUTED))
                elif isinstance(value, bool):
                    row_values.append(
                        Text("yes" if value else "no", style=INFO_BLUE if value else TEXT_MUTED)
                    )
                elif isinstance(value, float):
                    row_values.append(f"{value:.4f}")
                elif isinstance(value, int):
                    row_values.append(f"{value:,}")
                else:
                    str_val = str(value)
                    if len(str_val) > 40:
                        str_val = str_val[:37] + "..."
                    row_values.append(str_val)
            table.add_row(*row_values)

        return Panel(
            table,
            title=f"{title} [TABLE: {len(data)} rows]",
            title_align="left",
            border_style=PANEL_BORDER_INFO,
            style=PANEL_BACKGROUND,
        )

    def _render_data_panel(self, data: Any, title: str) -> Panel:
        """Render data as either table or JSON based on display format."""
        if data is None:
            content = Text("No data.", style=TEXT_MUTED)
            return Panel(
                content,
                title=title,
                title_align="left",
                border_style=PANEL_BORDER_DEFAULT,
                style=PANEL_BACKGROUND,
            )

        # Always use AUTO format - smart detection of best display
        use_table = self._should_use_table(data)

        if use_table:
            # List of dicts - render as multi-row table
            if isinstance(data, list) and data and isinstance(data[0], dict):
                return self._render_list_table_panel(data, title)
            # Single dict - render as key-value table
            elif isinstance(data, dict):
                return self._render_table_panel(data, title)

        # JSON rendering
        try:
            json_str = json.dumps(data, indent=2, default=str)
            content = Syntax(json_str, "json", theme="monokai", line_numbers=True)
        except (TypeError, ValueError):
            content = Text(str(data), style=TEXT_PRIMARY)

        return Panel(
            content,
            title=title,
            title_align="left",
            border_style=PANEL_BORDER_INFO,
            style=PANEL_BACKGROUND,
        )

    def show_project(self, project: dict[str, Any]) -> None:
        """
        Display data for a project as a compact panel.

        Args:
            project: The project dict to display.
        """
        self._current_run = None
        self._current_step = None
        self.clear()

        name = project.get("name", "Unknown")
        description = project.get("description", "")
        trace_count = project.get("trace_count", 0)
        created_at = project.get("created_at", "")

        # Format created date
        created_str = self._format_relative_time(created_at)

        # Build compact text display
        content = Text()
        content.append(f"{name}\n", style=f"{TEXT_PRIMARY} bold")
        if description:
            content.append(f"{description}\n", style=TEXT_MUTED)
        content.append("\n")
        content.append(f"Traces: {trace_count}", style=TEXT_MUTED)
        content.append("    ", style=TEXT_MUTED)
        content.append(f"Created: {created_str}", style=TEXT_MUTED)

        panel = Panel(
            content,
            title="Project",
            title_align="left",
            border_style=PANEL_BORDER_DEFAULT,
            style=PANEL_BACKGROUND,
        )
        self.write(panel)

    def show_run_io(self, run: AgentRun) -> None:
        """
        Display input/output data for a run.

        Alias for show_run for compatibility.

        Args:
            run: The AgentRun to display.
        """
        self.show_run(run)
