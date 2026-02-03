"""
Evaluation case creator screen for TraceCraft TUI.

Allows users to manually create evaluation test cases with input,
expected output, and optional retrieval context for RAG evaluations.
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
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.screen import ModalScreen
    from textual.widgets import Button, Input, Label, Static, TextArea

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    ModalScreen = object  # type: ignore[misc,assignment]
    ComposeResult = Any  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from tracecraft.storage.sqlite import SQLiteTraceStore


class EvalCaseCreatorScreen(ModalScreen if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Modal screen for creating manual evaluation test cases.

    Provides a form for:
    - Case name
    - Input data (JSON or text)
    - Expected output (JSON or text)
    - Optional retrieval context (for RAG evaluations)
    - Tags
    """

    BINDINGS = (
        [
            Binding("escape", "cancel", "Cancel"),
            Binding("ctrl+s", "submit", "Save"),
        ]
        if TEXTUAL_AVAILABLE
        else []
    )

    CSS = f"""
    /* NOIR SIGNAL - Eval Case Creator */
    EvalCaseCreatorScreen {{
        align: center middle;
        background: rgba(11, 14, 17, 0.8);
    }}

    #case-creator-container {{
        width: 80%;
        max-width: 100;
        height: 85%;
        background: {SURFACE};
        border: solid {ACCENT_AMBER};
    }}

    #case-creator-header {{
        height: 3;
        background: {SURFACE_HIGHLIGHT};
        padding: 0 1;
        content-align: center middle;
        border-bottom: solid {BORDER};
    }}

    #case-creator-header Label {{
        text-style: bold;
        color: {ACCENT_AMBER};
    }}

    #case-creator-content {{
        height: 1fr;
        padding: 1 2;
    }}

    .form-section {{
        margin-bottom: 1;
    }}

    .section-label {{
        color: {TEXT_MUTED};
        text-style: bold;
        margin-bottom: 0;
    }}

    .section-hint {{
        color: {TEXT_MUTED};
        margin-bottom: 0;
    }}

    #name-input {{
        width: 100%;
        background: {BACKGROUND};
        border: solid {BORDER};
    }}

    #name-input:focus {{
        border: solid {ACCENT_AMBER};
    }}

    .json-area {{
        height: 8;
        width: 100%;
        background: {BACKGROUND};
        border: solid {BORDER};
    }}

    .json-area:focus {{
        border: solid {ACCENT_AMBER};
    }}

    #retrieval-area {{
        height: 5;
    }}

    #tags-input {{
        width: 100%;
        background: {BACKGROUND};
        border: solid {BORDER};
    }}

    #tags-input:focus {{
        border: solid {ACCENT_AMBER};
    }}

    #case-creator-footer {{
        height: 4;
        background: {SURFACE_HIGHLIGHT};
        padding: 0 2;
        content-align: center middle;
        border-top: solid {BORDER};
    }}

    #case-creator-footer Horizontal {{
        width: 100%;
        align: center middle;
    }}

    #case-creator-footer Button {{
        margin: 0 1;
    }}

    .error-msg {{
        color: {DANGER_RED};
        text-align: center;
        padding: 0 1;
    }}
    """

    def __init__(
        self,
        eval_set_id: str,
        store: SQLiteTraceStore,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the case creator screen.

        Args:
            eval_set_id: The evaluation set to add the case to.
            store: SQLite store for persistence.
        """
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__(*args, **kwargs)
        self._eval_set_id = eval_set_id
        self._store = store

    def compose(self) -> ComposeResult:
        """Compose the case creator screen layout."""
        with Vertical(id="case-creator-container"):
            # Header
            with Vertical(id="case-creator-header"):
                yield Label("CREATE EVALUATION CASE")

            # Content - scrollable form
            with VerticalScroll(id="case-creator-content"):
                # Case name
                with Vertical(classes="form-section"):
                    yield Static("CASE NAME", classes="section-label")
                    yield Input(
                        placeholder="e.g., test-addition, qa-sample-1",
                        id="name-input",
                    )

                # Input data
                with Vertical(classes="form-section"):
                    yield Static("INPUT (JSON)", classes="section-label")
                    yield Static("The input data for this test case", classes="section-hint")
                    yield TextArea(
                        '{\n  "prompt": "Your prompt here"\n}',
                        id="input-area",
                        classes="json-area",
                    )

                # Expected output
                with Vertical(classes="form-section"):
                    yield Static("EXPECTED OUTPUT (JSON)", classes="section-label")
                    yield Static("The expected response for comparison", classes="section-hint")
                    yield TextArea(
                        '{\n  "answer": "Expected answer"\n}',
                        id="expected-area",
                        classes="json-area",
                    )

                # Retrieval context (optional)
                with Vertical(classes="form-section"):
                    yield Static(
                        "RETRIEVAL CONTEXT (Optional, one per line)", classes="section-label"
                    )
                    yield Static("For RAG evaluations - context documents", classes="section-hint")
                    yield TextArea(
                        "",
                        id="retrieval-area",
                        classes="json-area",
                    )

                # Tags
                with Vertical(classes="form-section"):
                    yield Static("TAGS (comma-separated, optional)", classes="section-label")
                    yield Input(
                        placeholder="e.g., math, qa, regression",
                        id="tags-input",
                    )

                # Error message placeholder
                yield Static("", id="error-msg", classes="error-msg")

            # Footer with buttons
            with Vertical(id="case-creator-footer"), Horizontal():
                yield Button("Cancel", variant="default", id="cancel-btn")
                yield Button("Create Case", variant="primary", id="create-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-btn":
            self.dismiss(None)
        elif event.button.id == "create-btn":
            self._create_case()

    def action_cancel(self) -> None:
        """Cancel and close."""
        self.dismiss(None)

    def action_submit(self) -> None:
        """Submit the form."""
        self._create_case()

    def _show_error(self, message: str) -> None:
        """Display an error message."""
        error_widget = self.query_one("#error-msg", Static)
        error_widget.update(message)

    def _clear_error(self) -> None:
        """Clear the error message."""
        error_widget = self.query_one("#error-msg", Static)
        error_widget.update("")

    def _create_case(self) -> None:
        """Create the evaluation case from form data."""
        self._clear_error()

        try:
            # Get form values
            name = self.query_one("#name-input", Input).value.strip()
            input_text = self.query_one("#input-area", TextArea).text.strip()
            expected_text = self.query_one("#expected-area", TextArea).text.strip()
            retrieval_text = self.query_one("#retrieval-area", TextArea).text.strip()
            tags_text = self.query_one("#tags-input", Input).value.strip()

            # Validate name
            if not name:
                self._show_error("Case name is required")
                return

            # Parse input JSON
            try:
                input_data = json.loads(input_text) if input_text else {}
            except json.JSONDecodeError as e:
                self._show_error(f"Invalid input JSON: {e}")
                return

            # Parse expected output JSON
            expected_output = None
            if expected_text:
                try:
                    expected_output = json.loads(expected_text)
                except json.JSONDecodeError as e:
                    self._show_error(f"Invalid expected output JSON: {e}")
                    return

            # Parse retrieval context (one item per line)
            retrieval_context = []
            if retrieval_text:
                retrieval_context = [
                    line.strip() for line in retrieval_text.split("\n") if line.strip()
                ]

            # Parse tags
            tags = []
            if tags_text:
                tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()]

            # Create the case
            case_id = self._store.add_evaluation_case(
                set_id=self._eval_set_id,
                name=name,
                input_data=input_data,
                expected_output=expected_output,
                retrieval_context=retrieval_context if retrieval_context else None,
                tags=tags if tags else None,
            )

            # Return success info
            self.dismiss(
                {
                    "case_id": case_id,
                    "name": name,
                }
            )

        except Exception as e:
            self._show_error(f"Error creating case: {e}")
