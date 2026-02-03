"""
Evaluation case selector screen for adding traces/steps to eval sets.

Provides a modal dialog for selecting which evaluation set to add
a trace or step to as a test case.
NOIR SIGNAL theme styling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

# Import theme constants
from tracecraft.tui.theme import (
    ACCENT_AMBER,
    BACKGROUND,
    BORDER,
    INFO_BLUE,
    SUCCESS_GREEN,
    SURFACE,
    SURFACE_HIGHLIGHT,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

try:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Vertical
    from textual.screen import ModalScreen
    from textual.widgets import Footer, Label, OptionList, Static
    from textual.widgets.option_list import Option

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    ComposeResult = Any  # type: ignore[misc,assignment]
    ModalScreen = object  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun, Step
    from tracecraft.storage.sqlite import SQLiteTraceStore


class EvalCaseSelectorScreen(ModalScreen if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Modal screen for adding a trace/step to an evaluation set.

    Shows the current trace/step info and a list of evaluation sets to choose from.
    Creates an evaluation case from the trace/step and adds it to the selected set.
    """

    BINDINGS = (
        [
            Binding("escape", "cancel", "Cancel"),
            Binding("enter", "select", "Add to Eval"),
        ]
        if TEXTUAL_AVAILABLE
        else []
    )

    CSS = f"""
    /* NOIR SIGNAL - Eval Case Selector */
    EvalCaseSelectorScreen {{
        align: center middle;
        background: rgba(11, 14, 17, 0.8);
    }}

    #eval-select-container {{
        width: 60%;
        height: 60%;
        min-width: 40;
        max-width: 80;
        border: solid {ACCENT_AMBER};
        background: {SURFACE};
    }}

    #eval-select-header {{
        height: 3;
        background: {SURFACE_HIGHLIGHT};
        padding: 0 1;
        content-align: center middle;
        border-bottom: solid {BORDER};
    }}

    #eval-select-header Label {{
        text-style: bold;
        color: {ACCENT_AMBER};
    }}

    #trace-info {{
        padding: 1;
        border-bottom: solid {BORDER};
        height: auto;
        background: {SURFACE};
    }}

    #item-name {{
        text-style: bold;
        color: {TEXT_PRIMARY};
    }}

    #item-details {{
        color: {TEXT_MUTED};
    }}

    #item-type {{
        color: {INFO_BLUE};
        margin-top: 1;
    }}

    #eval-list-container {{
        padding: 1;
        height: 1fr;
    }}

    #eval-list-label {{
        margin-bottom: 1;
        color: {TEXT_MUTED};
    }}

    #eval-set-list {{
        height: 1fr;
        border: solid {BORDER};
        background: {BACKGROUND};
    }}

    #eval-set-list:focus {{
        border: solid {ACCENT_AMBER};
    }}

    .no-evals {{
        color: {TEXT_MUTED};
        text-align: center;
        padding: 2;
    }}
    """

    def __init__(
        self,
        trace: AgentRun,
        step: Step | None = None,
        store: SQLiteTraceStore = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the eval case selector screen.

        Args:
            trace: The trace to add as a case.
            step: Optional specific step to add (uses trace root if None).
            store: SQLite store for eval set operations.
        """
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__(*args, **kwargs)
        self._trace = trace
        self._step = step
        self._store = store
        self._eval_sets: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        """Compose the selector screen layout."""
        with Vertical(id="eval-select-container"):
            # Header
            with Vertical(id="eval-select-header"):
                yield Label("ADD TO EVALUATION SET")

            # Item info (trace or step)
            with Vertical(id="trace-info"):
                if self._step:
                    yield Label(f"Step: {self._step.name}", id="item-name")
                    duration = f"{self._step.duration_ms:.0f}ms" if self._step.duration_ms else "-"
                    tokens = self._step.token_count or 0
                    yield Static(f"{duration} | {tokens:,} tokens", id="item-details")
                    yield Static(f"Type: {self._step.step_type.value}", id="item-type")
                else:
                    yield Label(f"Trace: {self._trace.name}", id="item-name")
                    duration = (
                        f"{self._trace.duration_ms:.0f}ms" if self._trace.duration_ms else "-"
                    )
                    tokens = self._trace.total_tokens or 0
                    yield Static(f"{duration} | {tokens:,} tokens", id="item-details")
                    yield Static("Type: Full Trace", id="item-type")

            # Eval set selection
            with Vertical(id="eval-list-container"):
                yield Label("SELECT EVALUATION SET", id="eval-list-label")
                yield OptionList(id="eval-set-list")

        yield Footer()

    def on_mount(self) -> None:
        """Load evaluation sets when mounted."""
        self._load_eval_sets()

    def _load_eval_sets(self) -> None:
        """Load evaluation sets from store and populate list."""
        self._eval_sets = self._store.list_evaluation_sets()

        option_list = self.query_one("#eval-set-list", OptionList)
        option_list.clear_options()

        if not self._eval_sets:
            # Show hint when no eval sets exist
            option_list.add_option(
                Option("No evaluation sets. Press E to create one.", id="__none__")
            )
            return

        # Add each eval set
        for eval_set in self._eval_sets:
            name = eval_set["name"]
            # Get case count
            case_count = len(self._store.get_evaluation_cases(eval_set["id"]))
            threshold = eval_set.get("default_threshold", 0.7)
            label = f"{name} ({case_count} cases, threshold: {threshold:.0%})"
            option_list.add_option(Option(label, id=eval_set["id"]))

    def action_cancel(self) -> None:
        """Cancel and close."""
        self.dismiss(None)

    def action_select(self) -> None:
        """Select the highlighted eval set and add the case."""
        option_list = self.query_one("#eval-set-list", OptionList)
        if option_list.highlighted is None:
            self.dismiss(None)
            return

        option = option_list.get_option_at_index(option_list.highlighted)
        eval_set_id = option.id

        if eval_set_id == "__none__":
            self.dismiss(None)
            return

        self._add_case_to_eval_set(eval_set_id)

    def on_option_list_option_selected(self, event: Any) -> None:
        """Handle double-click or Enter on an option."""
        eval_set_id = event.option.id
        if eval_set_id == "__none__":
            self.dismiss(None)
        else:
            self._add_case_to_eval_set(eval_set_id)

    def _add_case_to_eval_set(self, eval_set_id: str) -> None:
        """Add the trace/step as a case to the eval set."""
        try:
            trace_id = str(self._trace.id)
            step_id = str(self._step.id) if self._step else None

            case_id = self._store.create_case_from_trace(
                set_id=eval_set_id,
                trace_id=trace_id,
                step_id=step_id,
            )

            # Find eval set name for notification
            eval_set_name = "Unknown"
            for es in self._eval_sets:
                if es["id"] == eval_set_id:
                    eval_set_name = es["name"]
                    break

            # Return success info
            self.dismiss(
                {
                    "case_id": case_id,
                    "eval_set_id": eval_set_id,
                    "eval_set_name": eval_set_name,
                }
            )

        except Exception as e:
            self.notify(f"Failed to add case: {e}", title="ERROR", severity="error")
