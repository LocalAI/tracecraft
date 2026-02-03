"""
Evaluation run history screen for TraceCraft TUI.

Shows past evaluation runs for an eval set in a simplified 4-column table.
NOIR SIGNAL theme styling.
"""

from __future__ import annotations

from datetime import UTC, datetime, timezone
from typing import TYPE_CHECKING, Any

from tracecraft.tui.theme import (
    ACCENT_AMBER,
    BACKGROUND,
    BORDER,
    SURFACE,
    SURFACE_HIGHLIGHT,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

try:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Horizontal
    from textual.screen import ModalScreen
    from textual.widgets import DataTable, Label, Static

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    ModalScreen = object  # type: ignore[misc,assignment]
    ComposeResult = Any  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from tracecraft.storage.sqlite import SQLiteTraceStore


def _format_duration(ms: float | None) -> str:
    """Format duration in milliseconds to human readable string."""
    if ms is None:
        return "-"
    if ms < 1000:
        return f"{ms:.0f}ms"
    return f"{ms / 1000:.1f}s"


def _format_datetime_friendly(dt_str: str | None) -> str:
    """Format ISO datetime string to friendly format like 'Jan 15, 2:30pm'."""
    if not dt_str:
        return "-"
    try:
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        dt = datetime.fromisoformat(dt_str)

        # Make naive datetime aware (assume UTC)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)

        # Format as "Jan 15, 2:30pm"
        return (
            dt.strftime("%b %d, %I:%M%p")
            .replace(" 0", " ")
            .lower()
            .replace("am", "am")
            .replace("pm", "pm")
        )
    except (ValueError, AttributeError):
        return str(dt_str)[:16]


class EvalRunHistoryScreen(ModalScreen if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Modal screen for viewing evaluation run history.

    Shows a simplified 4-column table:
    - Date
    - Pass Rate
    - Cases (total)
    - Duration
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("enter", "view_results", "View Results"),
        Binding("d", "delete_run", "Delete"),
        Binding("r", "refresh", "Refresh"),
    ]

    CSS = f"""
    EvalRunHistoryScreen {{
        align: center middle;
        background: rgba(11, 14, 17, 0.8);
    }}

    #history-viewer-container {{
        width: 80%;
        max-width: 80;
        height: 70%;
        background: {SURFACE};
        border: solid {ACCENT_AMBER};
    }}

    #history-viewer-header {{
        height: 3;
        background: {SURFACE_HIGHLIGHT};
        padding: 0 2;
        content-align: left middle;
        border-bottom: solid {BORDER};
    }}

    #history-viewer-header Label {{
        text-style: bold;
        color: {TEXT_PRIMARY};
    }}

    #runs-table {{
        height: 1fr;
        background: {BACKGROUND};
        border: none;
    }}

    #runs-table > .datatable--header {{
        background: {SURFACE_HIGHLIGHT};
        color: {TEXT_MUTED};
        text-style: bold;
    }}

    #runs-table > .datatable--cursor {{
        background: {ACCENT_AMBER};
        color: {BACKGROUND};
    }}

    #footer {{
        height: 2;
        background: {SURFACE};
        border-top: solid {BORDER};
        padding: 0 1;
        align: center middle;
    }}

    #footer .key-hint {{
        color: {TEXT_MUTED};
    }}
    """

    def __init__(
        self,
        eval_set: dict[str, Any],
        store: SQLiteTraceStore,
    ) -> None:
        """
        Initialize the run history screen.

        Args:
            eval_set: The evaluation set to view history for.
            store: SQLite store for data access.
        """
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__()
        self.eval_set = eval_set
        self.store = store
        self._runs: list[dict[str, Any]] = []
        self._selected_run: dict[str, Any] | None = None

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        with Container(id="history-viewer-container"):
            with Horizontal(id="history-viewer-header"):
                yield Label(f"History: {self.eval_set.get('name', 'Evaluation Set')}")

            yield DataTable(id="runs-table", cursor_type="row")

            with Horizontal(id="footer"):
                yield Static(
                    "[Enter] View Results  [d] Delete  [r] Refresh  [Esc] Close", classes="key-hint"
                )

    def on_mount(self) -> None:
        """Load runs when mounted."""
        self._load_runs()
        table = self.query_one("#runs-table", DataTable)
        table.focus()

    def _load_runs(self) -> None:
        """Load evaluation runs from storage."""
        try:
            self._runs = self.store.list_evaluation_runs(set_id=self.eval_set["id"])
        except Exception:
            self._runs = []

        self._populate_table()

    def _populate_table(self) -> None:
        """Populate the runs table with 4 columns."""
        table = self.query_one("#runs-table", DataTable)
        table.clear(columns=True)

        # Simple 4-column layout
        table.add_column("Date", width=20, key="date")
        table.add_column("Pass Rate", width=15, key="pass_rate")
        table.add_column("Cases", width=12, key="cases")
        table.add_column("Duration", width=12, key="duration")

        for run in self._runs:
            date = _format_datetime_friendly(run.get("started_at"))

            # Format pass rate with status indicator
            pass_rate = run.get("overall_pass_rate")
            passed = run.get("passed")
            if pass_rate is not None:
                rate_pct = int(pass_rate * 100)
                status_icon = "+" if passed else "x"
                pass_rate_str = f"{status_icon} {rate_pct}%"
            else:
                pass_rate_str = "-"

            total_cases = run.get("total_cases", 0)

            table.add_row(
                date,
                pass_rate_str,
                str(total_cases),
                _format_duration(run.get("duration_ms")),
                key=run.get("id"),
            )

        # Update header with run count
        header_label = self.query_one("#history-viewer-header Label", Label)
        header_label.update(
            f"History: {self.eval_set.get('name', 'Evaluation Set')} ({len(self._runs)} runs)"
        )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle row highlight to track selected run."""
        if event.row_key is None:
            return

        run_id = str(event.row_key.value)
        self._selected_run = next((r for r in self._runs if r.get("id") == run_id), None)

    def action_close(self) -> None:
        """Close the screen."""
        self.dismiss(None)

    def action_view_results(self) -> None:
        """View results for the selected run."""
        if not self._selected_run:
            self.notify("No run selected", severity="warning")
            return

        from tracecraft.tui.screens.eval_results_viewer import EvalResultsViewerScreen

        self.app.push_screen(
            EvalResultsViewerScreen(
                eval_run=self._selected_run,
                eval_set=self.eval_set,
                store=self.store,
            )
        )

    def action_delete_run(self) -> None:
        """Delete the selected run."""
        if not self._selected_run:
            self.notify("No run selected", severity="warning")
            return

        run_id = self._selected_run["id"]

        # Confirm deletion
        from tracecraft.tui.screens.project_manager import ConfirmScreen

        def on_confirm(confirmed: bool) -> None:
            if confirmed:
                try:
                    self.store.delete_evaluation_run(run_id)
                    self.notify("Run deleted", severity="information")
                    self._load_runs()
                    self._selected_run = None
                except Exception as e:
                    self.notify(f"Error deleting run: {e}", severity="error")

        self.app.push_screen(
            ConfirmScreen(
                title="Delete Run",
                message=f"Delete run {run_id[:8]}...?\n\nThis will also delete all results.\nThis cannot be undone.",
            ),
            on_confirm,
        )

    def action_refresh(self) -> None:
        """Refresh the run list."""
        self._load_runs()
        self.notify("Run list refreshed", severity="information")
