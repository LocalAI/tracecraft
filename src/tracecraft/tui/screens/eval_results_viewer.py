"""
Evaluation results viewer screen for TraceCraft TUI.

Shows results of a completed evaluation run with a table and detail panel.
NOIR SIGNAL theme styling.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from tracecraft.tui.theme import (
    ACCENT_AMBER,
    BACKGROUND,
    BORDER,
    DANGER_RED,
    SUCCESS_GREEN,
    SURFACE,
    SURFACE_HIGHLIGHT,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

try:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Horizontal, Vertical
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


def _truncate(text: str, max_len: int = 80) -> str:
    """Truncate text with ellipsis if too long."""
    if not text:
        return "-"
    text = str(text).replace("\n", " ")
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


def _format_json(data: Any, max_len: int = 80) -> str:
    """Format data as JSON string, truncated."""
    if data is None:
        return "-"
    try:
        text = json.dumps(data)
        return _truncate(text, max_len)
    except (TypeError, ValueError):
        return _truncate(str(data), max_len)


class EvalResultsViewerScreen(ModalScreen if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Modal screen for viewing evaluation results.

    Shows:
    - Compact header with pass rate summary
    - Table: Case Name | Status | Reason
    - Detail panel: Input, Output, Expected for selected case
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("f", "filter_failed", "Filter Failed"),
        Binding("a", "show_all", "Show All"),
    ]

    CSS = f"""
    EvalResultsViewerScreen {{
        align: center middle;
        background: rgba(11, 14, 17, 0.8);
    }}

    #results-viewer-container {{
        width: 95%;
        max-width: 140;
        height: 90%;
        background: {SURFACE};
        border: solid {ACCENT_AMBER};
    }}

    #results-viewer-header {{
        height: 3;
        background: {SURFACE_HIGHLIGHT};
        padding: 0 2;
        content-align: left middle;
        border-bottom: solid {BORDER};
    }}

    #results-viewer-header Label {{
        text-style: bold;
        color: {TEXT_PRIMARY};
    }}

    .header-passed {{
        color: {SUCCESS_GREEN};
    }}

    .header-failed {{
        color: {DANGER_RED};
    }}

    #results-table {{
        height: 1fr;
        background: {BACKGROUND};
        border: none;
    }}

    #results-table > .datatable--header {{
        background: {SURFACE_HIGHLIGHT};
        color: {TEXT_MUTED};
        text-style: bold;
    }}

    #results-table > .datatable--cursor {{
        background: {ACCENT_AMBER};
        color: {BACKGROUND};
    }}

    #detail-panel {{
        height: 12;
        background: {SURFACE_HIGHLIGHT};
        border-top: solid {BORDER};
        padding: 1 2;
    }}

    .detail-title {{
        color: {ACCENT_AMBER};
        text-style: bold;
        height: 1;
    }}

    .detail-row {{
        height: 2;
    }}

    .detail-label {{
        width: 12;
        color: {TEXT_MUTED};
    }}

    .detail-value {{
        width: 1fr;
        color: {TEXT_PRIMARY};
    }}

    .detail-pass {{
        color: {SUCCESS_GREEN};
    }}

    .detail-fail {{
        color: {DANGER_RED};
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
        eval_run: dict[str, Any],
        eval_set: dict[str, Any],
        store: SQLiteTraceStore,
    ) -> None:
        """
        Initialize the results viewer screen.

        Args:
            eval_run: The evaluation run to view results for.
            eval_set: The evaluation set (for context).
            store: SQLite store for data access.
        """
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__()
        self.eval_run = eval_run
        self.eval_set = eval_set
        self.store = store
        self._results: list[dict[str, Any]] = []
        self._filtered_results: list[dict[str, Any]] = []
        self._selected_result: dict[str, Any] | None = None
        self._show_failed_only = False

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        # Build compact header summary
        passed = self.eval_run.get("passed")
        pass_rate_raw = self.eval_run.get("overall_pass_rate")
        pass_rate = int((pass_rate_raw if pass_rate_raw is not None else 0) * 100)
        passed_cases = self.eval_run.get("passed_cases", 0)
        total_cases = self.eval_run.get("total_cases", 0)
        duration = _format_duration(self.eval_run.get("duration_ms"))

        status_class = "header-passed" if passed else "header-failed"
        header_text = f"{pass_rate}% passed ({passed_cases}/{total_cases}) in {duration}"

        with Container(id="results-viewer-container"):
            with Horizontal(id="results-viewer-header"):
                yield Label(header_text, classes=status_class)

            yield DataTable(id="results-table", cursor_type="row")

            with Vertical(id="detail-panel"):
                yield Static(
                    "Select a case to view details", id="detail-title", classes="detail-title"
                )
                with Horizontal(classes="detail-row"):
                    yield Label("Input:", classes="detail-label")
                    yield Static("-", id="detail-input", classes="detail-value")
                with Horizontal(classes="detail-row"):
                    yield Label("Output:", classes="detail-label")
                    yield Static("-", id="detail-output", classes="detail-value")
                with Horizontal(classes="detail-row"):
                    yield Label("Expected:", classes="detail-label")
                    yield Static("-", id="detail-expected", classes="detail-value")
                with Horizontal(classes="detail-row"):
                    yield Label("Result:", classes="detail-label")
                    yield Static("-", id="detail-result", classes="detail-value")

            with Horizontal(id="footer"):
                yield Static("[f] Filter Failed  [a] Show All  [Esc] Close", classes="key-hint")

    def on_mount(self) -> None:
        """Load results when mounted."""
        self._load_results()
        table = self.query_one("#results-table", DataTable)
        table.focus()

    def _load_results(self) -> None:
        """Load evaluation results from storage."""
        try:
            self._results = self.store.get_evaluation_results(self.eval_run["id"])
        except Exception:
            self._results = []

        self._apply_filter()

    def _apply_filter(self) -> None:
        """Apply current filter and update table."""
        if self._show_failed_only:
            self._filtered_results = [r for r in self._results if not r.get("passed")]
        else:
            self._filtered_results = self._results

        self._populate_table()

    def _get_failure_reason(self, result: dict[str, Any]) -> str:
        """Get the failure reason - only show the first failed metric."""
        if result.get("passed"):
            return ""

        # Check for error first
        error = result.get("error")
        if error:
            error_str = str(error)
            if len(error_str) > 40:
                error_str = error_str[:37] + "..."
            return f"Error: {error_str}"

        # Find failed metric
        scores = result.get("scores", [])
        for s in scores:
            if not s.get("passed", True):
                name = s.get("metric_name", "?")
                val = s.get("score", 0)
                threshold = s.get("threshold", 0.7)
                return f"{name}: {val:.2f} < {threshold:.2f}"

        return "Failed"

    def _populate_table(self) -> None:
        """Populate the results table."""
        table = self.query_one("#results-table", DataTable)
        table.clear(columns=True)

        # Table columns
        table.add_column("Case Name", width=30, key="case")
        table.add_column("Status", width=10, key="status")
        table.add_column("Reason", width=50, key="reason")

        for result in self._filtered_results:
            passed = result.get("passed", False)
            status = "+ PASS" if passed else "x FAIL"
            reason = self._get_failure_reason(result)

            table.add_row(
                result.get("case_name", "Unknown"),
                status,
                reason,
                key=result.get("id", result.get("case_id")),
            )

        # Update header with filter status
        self._update_header()

    def _update_header(self) -> None:
        """Update header to show filter status."""
        passed = self.eval_run.get("passed")
        pass_rate_raw = self.eval_run.get("overall_pass_rate")
        pass_rate = int((pass_rate_raw if pass_rate_raw is not None else 0) * 100)
        passed_cases = self.eval_run.get("passed_cases", 0)
        total_cases = self.eval_run.get("total_cases", 0)
        duration = _format_duration(self.eval_run.get("duration_ms"))

        filter_text = " [failed only]" if self._show_failed_only else ""
        header_text = (
            f"{pass_rate}% passed ({passed_cases}/{total_cases}) in {duration}{filter_text}"
        )

        header_label = self.query_one("#results-viewer-header Label", Label)
        status_class = "header-passed" if passed else "header-failed"
        header_label.update(header_text)
        header_label.remove_class("header-passed", "header-failed")
        header_label.add_class(status_class)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle row highlight to update detail panel."""
        if event.row_key is None:
            return

        # Find the highlighted result
        result_id = str(event.row_key.value)
        self._selected_result = next(
            (
                r
                for r in self._filtered_results
                if r.get("id") == result_id or r.get("case_id") == result_id
            ),
            None,
        )

        if self._selected_result:
            self._update_detail_panel(self._selected_result)

    def _update_detail_panel(self, result: dict[str, Any]) -> None:
        """Update the detail panel with result information."""
        # Title
        title = self.query_one("#detail-title", Static)
        passed = result.get("passed", False)
        status = "PASS" if passed else "FAIL"
        title.update(f"Case: {result.get('case_name', 'Unknown')} - {status}")

        # Input
        input_data = result.get("input")
        self.query_one("#detail-input", Static).update(_format_json(input_data, 100))

        # Actual output
        actual = result.get("actual_output")
        self.query_one("#detail-output", Static).update(_format_json(actual, 100))

        # Expected output
        expected = result.get("expected_output")
        self.query_one("#detail-expected", Static).update(_format_json(expected, 100))

        # Result - show metric scores
        scores = result.get("scores", [])
        if scores:
            result_parts = []
            for s in scores:
                name = s.get("metric_name", "?")
                val = s.get("score", 0)
                threshold = s.get("threshold", 0.7)
                metric_passed = s.get("passed", False)
                icon = "+" if metric_passed else "x"
                result_parts.append(f"{icon} {name}: {val:.2f} (threshold: {threshold:.2f})")
            self.query_one("#detail-result", Static).update(" | ".join(result_parts))
        else:
            error = result.get("error")
            if error:
                self.query_one("#detail-result", Static).update(
                    f"Error: {_truncate(str(error), 80)}"
                )
            else:
                self.query_one("#detail-result", Static).update("-")

    def action_close(self) -> None:
        """Close the screen."""
        self.dismiss(None)

    def action_filter_failed(self) -> None:
        """Filter to show only failed results."""
        self._show_failed_only = True
        self._apply_filter()
        self.notify("Showing failed results only", severity="information")

    def action_show_all(self) -> None:
        """Show all results (remove filter)."""
        self._show_failed_only = False
        self._apply_filter()
        self.notify("Showing all results", severity="information")
