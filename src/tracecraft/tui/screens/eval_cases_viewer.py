"""
Evaluation cases viewer screen for TraceCraft TUI.

Shows all evaluation cases in a set as a simplified 3-column table.
NOIR SIGNAL theme styling.
"""

from __future__ import annotations

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


class EvalCasesViewerScreen(ModalScreen if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Modal screen for viewing evaluation cases in a simplified table format.

    Shows a 3-column table:
    - Name
    - Source (trace or manual)
    - Status (from latest run if available)
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("c", "create_case", "Create Case"),
        Binding("d", "delete_case", "Delete"),
        Binding("g", "goto_source", "Goto Source"),
    ]

    CSS = f"""
    EvalCasesViewerScreen {{
        align: center middle;
        background: rgba(11, 14, 17, 0.8);
    }}

    #cases-viewer-container {{
        width: 80%;
        max-width: 80;
        height: 70%;
        background: {SURFACE};
        border: solid {ACCENT_AMBER};
    }}

    #cases-viewer-header {{
        height: 3;
        background: {SURFACE_HIGHLIGHT};
        padding: 0 2;
        content-align: left middle;
        border-bottom: solid {BORDER};
    }}

    #cases-viewer-header Label {{
        text-style: bold;
        color: {TEXT_PRIMARY};
    }}

    #cases-table {{
        height: 1fr;
        background: {BACKGROUND};
        border: none;
    }}

    #cases-table > .datatable--header {{
        background: {SURFACE_HIGHLIGHT};
        color: {TEXT_MUTED};
        text-style: bold;
    }}

    #cases-table > .datatable--cursor {{
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
        Initialize the cases viewer screen.

        Args:
            eval_set: The evaluation set to view cases for.
            store: SQLite store for data access.
        """
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__()
        self.eval_set = eval_set
        self.store = store
        self._cases: list[dict[str, Any]] = []
        self._case_statuses: dict[str, str] = {}  # case_id -> status
        self._selected_case: dict[str, Any] | None = None

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        with Container(id="cases-viewer-container"):
            with Horizontal(id="cases-viewer-header"):
                yield Label(f"Cases: {self.eval_set.get('name', 'Evaluation Set')}")

            yield DataTable(id="cases-table", cursor_type="row")

            with Horizontal(id="footer"):
                yield Static(
                    "[c] Create  [d] Delete  [g] Goto Source  [Esc] Close", classes="key-hint"
                )

    def on_mount(self) -> None:
        """Load cases when mounted."""
        self._load_cases()
        table = self.query_one("#cases-table", DataTable)
        table.focus()

    def _load_case_statuses(self) -> None:
        """Load latest result status for each case."""
        self._case_statuses = {}
        for case in self._cases:
            try:
                result = self.store.get_latest_eval_result_for_case(case["id"])
                if result:
                    passed = result.get("passed")
                    if passed is True or passed == 1:
                        self._case_statuses[case["id"]] = "+ PASS"
                    elif passed is False or passed == 0:
                        self._case_statuses[case["id"]] = "x FAIL"
                    else:
                        self._case_statuses[case["id"]] = "-"
                else:
                    self._case_statuses[case["id"]] = "-"
            except Exception:
                self._case_statuses[case["id"]] = "-"

    def _load_cases(self) -> None:
        """Load evaluation cases from storage."""
        try:
            self._cases = self.store.get_evaluation_cases(self.eval_set["id"])
        except Exception:
            self._cases = []

        # Load statuses from latest run
        self._load_case_statuses()

        # Set up table columns
        table = self.query_one("#cases-table", DataTable)
        table.clear(columns=True)

        # Simple 3-column layout
        table.add_column("Name", width=35, key="name")
        table.add_column("Source", width=15, key="source")
        table.add_column("Status", width=12, key="status")

        # Add rows
        for case in self._cases:
            source = "trace" if case.get("source_trace_id") else "manual"
            status = self._case_statuses.get(case["id"], "-")

            table.add_row(
                case.get("name", "Unnamed"),
                source,
                status,
                key=case["id"],
            )

        # Update header with count
        header_label = self.query_one("#cases-viewer-header Label", Label)
        header_label.update(
            f"Cases: {self.eval_set.get('name', 'Evaluation Set')} ({len(self._cases)} cases)"
        )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle row highlight to track selected case."""
        if event.row_key is None:
            return

        case_id = str(event.row_key.value)
        self._selected_case = next((c for c in self._cases if c["id"] == case_id), None)

    def action_close(self) -> None:
        """Close the screen."""
        self.dismiss(None)

    def action_create_case(self) -> None:
        """Open case creator screen."""
        from tracecraft.tui.screens.eval_case_creator import EvalCaseCreatorScreen

        def on_case_created(result: dict[str, Any] | None) -> None:
            if result:
                self._load_cases()

        self.app.push_screen(
            EvalCaseCreatorScreen(self.eval_set, self.store),
            on_case_created,
        )

    def action_delete_case(self) -> None:
        """Delete the selected case."""
        if not self._selected_case:
            self.notify("No case selected", severity="warning")
            return

        case_id = self._selected_case["id"]
        case_name = self._selected_case.get("name", "Unnamed")

        # Confirm deletion
        from tracecraft.tui.screens.project_manager import ConfirmScreen

        def on_confirm(confirmed: bool) -> None:
            if confirmed:
                try:
                    self.store.delete_evaluation_case(case_id)
                    self.notify(f"Deleted case: {case_name}", severity="information")
                    self._load_cases()
                    self._selected_case = None
                except Exception as e:
                    self.notify(f"Error deleting case: {e}", severity="error")

        self.app.push_screen(
            ConfirmScreen(
                title="Delete Case",
                message=f"Delete case '{case_name}'?\n\nThis cannot be undone.",
            ),
            on_confirm,
        )

    def action_goto_source(self) -> None:
        """Navigate to the source trace of the selected case."""
        if not self._selected_case:
            self.notify("No case selected", severity="warning")
            return

        source_trace_id = self._selected_case.get("source_trace_id")
        if not source_trace_id:
            self.notify("Case has no source trace (manual entry)", severity="information")
            return

        # Dismiss and return the source trace ID for navigation
        self.dismiss({"action": "goto_trace", "trace_id": source_trace_id})
