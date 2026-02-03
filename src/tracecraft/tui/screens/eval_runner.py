"""
Evaluation runner screen for TraceCraft TUI.

Shows progress while running evaluations and displays results.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from tracecraft.tui.theme import (
    ACCENT_AMBER,
    BACKGROUND,
    BORDER,
    DANGER_RED,
    SUCCESS_GREEN,
    SURFACE,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

try:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Horizontal, Vertical
    from textual.screen import ModalScreen
    from textual.widgets import Button, Label, ProgressBar, Static

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    ModalScreen = object  # type: ignore[misc,assignment]
    ComposeResult = Any  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from tracecraft.storage.sqlite import SQLiteTraceStore


class EvalRunnerScreen(ModalScreen if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Modal screen for running evaluations with progress display.

    Shows:
    - Progress bar for completion
    - Current case being evaluated
    - Running pass/fail counts
    - Final results summary
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "close", "Close", show=False),
    ]

    CSS = f"""
    EvalRunnerScreen {{
        align: center middle;
    }}

    EvalRunnerScreen > Container {{
        width: 70;
        height: auto;
        max-height: 25;
        background: {SURFACE};
        border: solid {ACCENT_AMBER};
        padding: 1 2;
    }}

    EvalRunnerScreen .title {{
        width: 100%;
        text-align: center;
        text-style: bold;
        color: {ACCENT_AMBER};
        padding: 0 0 1 0;
    }}

    EvalRunnerScreen .status {{
        width: 100%;
        text-align: center;
        color: {TEXT_MUTED};
        padding: 1 0;
    }}

    EvalRunnerScreen .progress-container {{
        width: 100%;
        height: 3;
        padding: 0 2;
    }}

    EvalRunnerScreen ProgressBar {{
        width: 100%;
    }}

    EvalRunnerScreen .stats {{
        width: 100%;
        height: auto;
        padding: 1 0;
    }}

    EvalRunnerScreen .stat-row {{
        width: 100%;
        height: 1;
    }}

    EvalRunnerScreen .stat-label {{
        width: 15;
        color: {TEXT_MUTED};
    }}

    EvalRunnerScreen .stat-value {{
        width: 1fr;
        color: {TEXT_PRIMARY};
    }}

    EvalRunnerScreen .passed {{
        color: {SUCCESS_GREEN};
    }}

    EvalRunnerScreen .failed {{
        color: {DANGER_RED};
    }}

    EvalRunnerScreen .result {{
        width: 100%;
        text-align: center;
        text-style: bold;
        padding: 1 0;
    }}

    EvalRunnerScreen .buttons {{
        width: 100%;
        height: 3;
        margin-top: 1;
        align: center middle;
    }}
    """

    def __init__(
        self,
        eval_set: dict[str, Any],
        store: SQLiteTraceStore,
    ) -> None:
        """
        Initialize the runner screen.

        Args:
            eval_set: The evaluation set to run.
            store: SQLite store for persistence.
        """
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__()
        self.eval_set = eval_set
        self.store = store
        self._running = False
        self._cancelled = False
        self._result: dict[str, Any] | None = None

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        with Container():
            yield Static(f"Running: {self.eval_set.get('name', 'Evaluation')}", classes="title")

            yield Static("Initializing...", id="status", classes="status")

            with Container(classes="progress-container"):
                yield ProgressBar(total=100, id="progress")

            with Vertical(classes="stats"):
                with Horizontal(classes="stat-row"):
                    yield Label("Cases:", classes="stat-label")
                    yield Static("0 / 0", id="case-count", classes="stat-value")

                with Horizontal(classes="stat-row"):
                    yield Label("Passed:", classes="stat-label")
                    yield Static("0", id="passed-count", classes="stat-value passed")

                with Horizontal(classes="stat-row"):
                    yield Label("Failed:", classes="stat-label")
                    yield Static("0", id="failed-count", classes="stat-value failed")

                with Horizontal(classes="stat-row"):
                    yield Label("Pass Rate:", classes="stat-label")
                    yield Static("-", id="pass-rate", classes="stat-value")

            yield Static("", id="result", classes="result")

            with Horizontal(classes="buttons"):
                yield Button("Cancel", variant="default", id="cancel-btn")
                yield Button(
                    "View Results", variant="success", id="view-results-btn", disabled=True
                )
                yield Button("Close", variant="primary", id="close-btn", disabled=True)

    async def on_mount(self) -> None:
        """Start the evaluation when mounted."""
        self._running = True
        # Run evaluation in background
        asyncio.create_task(self._run_evaluation())

    async def _run_evaluation(self) -> None:
        """Run the evaluation asynchronously."""
        from tracecraft.evaluation import EvaluationRunner, EvaluationSet, ProgressInfo

        try:
            # Get cases for the eval set
            cases = self.store.get_evaluation_cases(self.eval_set["id"])

            if not cases:
                self._update_status("No cases to evaluate")
                self._show_error("Add cases to this evaluation set first")
                return

            # Build eval set model
            eval_set_data = {
                "id": self.eval_set["id"],
                "name": self.eval_set["name"],
                "metrics": self.eval_set.get("metrics", []),
                "default_threshold": self.eval_set.get("default_threshold", 0.7),
                "pass_rate_threshold": self.eval_set.get("pass_rate_threshold", 0.8),
                "cases": [
                    {
                        "id": c["id"],
                        "name": c["name"],
                        "input": c["input"],
                        "expected_output": c.get("expected_output"),
                        "retrieval_context": c.get("retrieval_context", []),
                    }
                    for c in cases
                ],
            }

            eval_set_model = EvaluationSet.model_validate(eval_set_data)

            # Progress callback
            def on_progress(info: ProgressInfo) -> None:
                if self._cancelled:
                    return
                self.call_from_thread(self._update_progress, info)

            # Run evaluation
            runner = EvaluationRunner(store=self.store)
            result = await runner.run(
                eval_set_model,
                on_progress=on_progress,
            )

            if self._cancelled:
                return

            # Store result and show completion
            self._result = {
                "run_id": str(result.run_id),
                "passed": result.overall_passed,
                "pass_rate": result.pass_rate,
                "passed_cases": result.passed_cases,
                "failed_cases": result.failed_cases,
            }

            self.call_from_thread(self._show_completion, result)

        except Exception as e:
            self.call_from_thread(self._show_error, str(e))

    def _update_status(self, status: str) -> None:
        """Update the status text."""
        with suppress(Exception):
            self.query_one("#status", Static).update(status)

    def _update_progress(self, info: Any) -> None:
        """Update progress display from callback."""
        try:
            # Update status
            if info.current_case:
                status = f"Evaluating: {info.current_case}"
                if info.current_metric:
                    status += f" ({info.current_metric})"
                self.query_one("#status", Static).update(status)

            # Update progress bar
            progress = self.query_one("#progress", ProgressBar)
            progress.update(progress=info.progress_percent)

            # Update counts
            self.query_one("#case-count", Static).update(
                f"{info.completed_cases} / {info.total_cases}"
            )
            self.query_one("#passed-count", Static).update(str(info.passed_cases))
            self.query_one("#failed-count", Static).update(str(info.failed_cases))

            # Update pass rate
            if info.completed_cases > 0:
                rate = info.passed_cases / info.completed_cases * 100
                self.query_one("#pass-rate", Static).update(f"{rate:.0f}%")

        except Exception:
            pass

    def _show_completion(self, result: Any) -> None:
        """Show completion state."""
        self._running = False

        # Update final stats
        self.query_one("#status", Static).update("Completed")
        self.query_one("#progress", ProgressBar).update(progress=100)
        self.query_one("#case-count", Static).update(f"{result.total_cases} / {result.total_cases}")
        self.query_one("#passed-count", Static).update(str(result.passed_cases))
        self.query_one("#failed-count", Static).update(str(result.failed_cases))
        self.query_one("#pass-rate", Static).update(f"{result.pass_rate * 100:.0f}%")

        # Show result
        result_widget = self.query_one("#result", Static)
        if result.overall_passed:
            result_widget.update(f"PASSED ({result.pass_rate * 100:.0f}%)")
            result_widget.add_class("passed")
        else:
            result_widget.update(f"FAILED ({result.pass_rate * 100:.0f}%)")
            result_widget.add_class("failed")

        # Enable close and view results buttons
        self.query_one("#close-btn", Button).disabled = False
        self.query_one("#view-results-btn", Button).disabled = False
        self.query_one("#cancel-btn", Button).disabled = True

    def _show_error(self, error: str) -> None:
        """Show error state."""
        self._running = False

        self.query_one("#status", Static).update(f"Error: {error}")
        result_widget = self.query_one("#result", Static)
        result_widget.update("FAILED")
        result_widget.add_class("failed")

        self.query_one("#close-btn", Button).disabled = False
        self.query_one("#cancel-btn", Button).disabled = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-btn":
            self._cancelled = True
            self.dismiss(None)
        elif event.button.id == "view-results-btn":
            self._view_results()
        elif event.button.id == "close-btn":
            self.dismiss(self._result)

    def _view_results(self) -> None:
        """Open the results viewer for the completed run."""
        if not self._result or not self._result.get("run_id"):
            return

        from tracecraft.tui.screens.eval_results_viewer import EvalResultsViewerScreen

        # Build run dict from result
        run_data = {
            "id": self._result["run_id"],
            "passed": self._result.get("passed"),
            "overall_pass_rate": self._result.get("pass_rate"),
            "passed_cases": self._result.get("passed_cases"),
            "failed_cases": self._result.get("failed_cases"),
            "total_cases": self._result.get("passed_cases", 0)
            + self._result.get("failed_cases", 0),
        }

        self.app.push_screen(
            EvalResultsViewerScreen(
                eval_run=run_data,
                eval_set=self.eval_set,
                store=self.store,
            )
        )

    def action_cancel(self) -> None:
        """Cancel and close."""
        self._cancelled = True
        self.dismiss(None)

    def action_close(self) -> None:
        """Close with results."""
        if not self._running:
            self.dismiss(self._result)
