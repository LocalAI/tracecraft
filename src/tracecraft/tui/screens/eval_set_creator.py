"""
Evaluation set creator screen for TraceCraft TUI.

Allows users to create and configure evaluation sets with multiple metrics.
NOIR SIGNAL theme styling.
"""

from __future__ import annotations

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
    from textual.containers import Container, Horizontal, Vertical, VerticalScroll
    from textual.screen import ModalScreen
    from textual.widgets import Button, Input, Label, OptionList, Select, Static
    from textual.widgets.option_list import Option

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    ModalScreen = object  # type: ignore[misc,assignment]
    ComposeResult = Any  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from tracecraft.storage.sqlite import SQLiteTraceStore


# Available metrics by framework
AVAILABLE_METRICS = [
    ("exact_match", "builtin", "Exact string match"),
    ("contains", "builtin", "String contains check"),
    ("regex_match", "builtin", "Regex pattern match"),
    ("json_valid", "builtin", "Valid JSON check"),
    ("length_check", "builtin", "Response length check"),
    ("llm_judge", "builtin", "LLM-as-judge evaluation"),
    ("faithfulness", "deepeval", "DeepEval faithfulness"),
    ("answer_relevancy", "deepeval", "DeepEval answer relevancy"),
    ("hallucination", "deepeval", "DeepEval hallucination check"),
    ("faithfulness", "ragas", "RAGAS faithfulness"),
    ("context_precision", "ragas", "RAGAS context precision"),
    ("context_recall", "ragas", "RAGAS context recall"),
]


class EvalSetCreatorScreen(ModalScreen if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Modal screen for creating evaluation sets with multiple metrics.

    Provides a form for configuring:
    - Name and description
    - Default threshold and pass rate threshold
    - Multiple metrics with individual thresholds
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "submit", "Save"),
    ]

    CSS = f"""
    EvalSetCreatorScreen {{
        align: center middle;
        background: rgba(11, 14, 17, 0.8);
    }}

    #set-creator-container {{
        width: 80%;
        max-width: 90;
        height: 85%;
        background: {SURFACE};
        border: solid {ACCENT_AMBER};
    }}

    #set-creator-header {{
        height: 3;
        background: {SURFACE_HIGHLIGHT};
        padding: 0 1;
        content-align: center middle;
        border-bottom: solid {BORDER};
    }}

    #set-creator-header Label {{
        text-style: bold;
        color: {ACCENT_AMBER};
    }}

    #set-creator-content {{
        height: 1fr;
        padding: 1 2;
    }}

    .form-row {{
        width: 100%;
        height: auto;
        margin: 0 0 1 0;
    }}

    .form-label {{
        width: 15;
        color: {TEXT_MUTED};
    }}

    .section-title {{
        color: {ACCENT_AMBER};
        text-style: bold;
        margin: 1 0 0 0;
    }}

    Input {{
        width: 1fr;
        background: {BACKGROUND};
        border: solid {BORDER};
    }}

    Input:focus {{
        border: solid {ACCENT_AMBER};
    }}

    Select {{
        width: 1fr;
        background: {BACKGROUND};
    }}

    #metrics-list {{
        height: 8;
        background: {BACKGROUND};
        border: solid {BORDER};
        margin: 0 0 1 0;
    }}

    #metrics-list:focus {{
        border: solid {ACCENT_AMBER};
    }}

    .metric-row {{
        width: 100%;
        height: 3;
        margin: 0 0 1 0;
    }}

    .metric-buttons {{
        width: 100%;
        height: 3;
        margin: 0 0 1 0;
    }}

    .metric-buttons Button {{
        margin: 0 1 0 0;
    }}

    #set-creator-footer {{
        height: 4;
        background: {SURFACE_HIGHLIGHT};
        padding: 0 2;
        content-align: center middle;
        border-top: solid {BORDER};
    }}

    #set-creator-footer Horizontal {{
        width: 100%;
        align: center middle;
    }}

    #set-creator-footer Button {{
        margin: 0 1;
    }}

    .hint {{
        color: {TEXT_MUTED};
        text-align: center;
    }}

    .error-msg {{
        color: {DANGER_RED};
        text-align: center;
    }}
    """

    def __init__(
        self,
        store: SQLiteTraceStore,
        edit_set: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize the creator screen.

        Args:
            store: SQLite store for saving the set.
            edit_set: Existing set to edit (None for new).
        """
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__()
        self.store = store
        self.edit_set = edit_set
        self._selected_metrics: list[dict[str, Any]] = []

        # Load existing metrics if editing
        if edit_set and edit_set.get("metrics"):
            self._selected_metrics = list(edit_set["metrics"])

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        title = "Edit Evaluation Set" if self.edit_set else "Create Evaluation Set"

        with Vertical(id="set-creator-container"):
            # Header
            with Vertical(id="set-creator-header"):
                yield Label(title.upper())

            # Content
            with VerticalScroll(id="set-creator-content"):
                # Name
                with Horizontal(classes="form-row"):
                    yield Label("Name:", classes="form-label")
                    yield Input(
                        value=self.edit_set.get("name", "") if self.edit_set else "",
                        placeholder="e.g., quality-baseline",
                        id="name-input",
                    )

                # Description
                with Horizontal(classes="form-row"):
                    yield Label("Description:", classes="form-label")
                    yield Input(
                        value=self.edit_set.get("description", "") if self.edit_set else "",
                        placeholder="Optional description",
                        id="desc-input",
                    )

                # Thresholds
                with Horizontal(classes="form-row"):
                    yield Label("Threshold:", classes="form-label")
                    yield Input(
                        value=str(
                            self.edit_set.get("default_threshold", 0.7) if self.edit_set else "0.7"
                        ),
                        placeholder="0.7 (metric pass threshold)",
                        id="threshold-input",
                    )

                with Horizontal(classes="form-row"):
                    yield Label("Pass Rate:", classes="form-label")
                    yield Input(
                        value=str(
                            self.edit_set.get("pass_rate_threshold", 0.8)
                            if self.edit_set
                            else "0.8"
                        ),
                        placeholder="0.8 (% of cases that must pass)",
                        id="pass-rate-input",
                    )

                # Metrics section
                yield Static("METRICS", classes="section-title")

                # Metric selection row
                with Horizontal(classes="metric-row"):
                    yield Select(
                        [(f"{m[0]} ({m[1]})", f"{m[0]}:{m[1]}") for m in AVAILABLE_METRICS],
                        prompt="Select metric to add",
                        id="metric-select",
                    )
                    yield Input(
                        value="0.7",
                        placeholder="Threshold",
                        id="metric-threshold",
                    )

                # Add metric button
                with Horizontal(classes="metric-buttons"):
                    yield Button("+ Add Metric", variant="primary", id="add-metric-btn")
                    yield Button("- Remove Selected", variant="default", id="remove-metric-btn")

                # List of selected metrics
                yield OptionList(id="metrics-list")

                # Error/hint
                yield Static("", id="error-msg", classes="error-msg")
                yield Static("Add at least one metric for evaluation", classes="hint")

            # Footer
            with Vertical(id="set-creator-footer"), Horizontal():
                yield Button("Cancel", variant="default", id="cancel-btn")
                yield Button(
                    "Save" if self.edit_set else "Create",
                    variant="primary",
                    id="create-btn",
                )

    def on_mount(self) -> None:
        """Initialize the metrics list on mount."""
        self._refresh_metrics_list()

    def _refresh_metrics_list(self) -> None:
        """Update the metrics list display."""
        option_list = self.query_one("#metrics-list", OptionList)
        option_list.clear_options()

        if not self._selected_metrics:
            option_list.add_option(Option("(no metrics added)", id="__empty__"))
        else:
            for i, metric in enumerate(self._selected_metrics):
                name = metric.get("name", "unknown")
                framework = metric.get("framework", "unknown")
                threshold = metric.get("threshold", 0.7)
                label = f"{name} ({framework}) - threshold: {threshold}"
                option_list.add_option(Option(label, id=str(i)))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-btn":
            self.dismiss(None)
        elif event.button.id == "create-btn":
            self._create_eval_set()
        elif event.button.id == "add-metric-btn":
            self._add_metric()
        elif event.button.id == "remove-metric-btn":
            self._remove_metric()

    def _add_metric(self) -> None:
        """Add a metric to the selected list."""
        self._clear_error()

        select = self.query_one("#metric-select", Select)
        threshold_input = self.query_one("#metric-threshold", Input)

        metric_value = select.value
        if not metric_value or metric_value == Select.BLANK:
            self._show_error("Select a metric to add")
            return

        try:
            threshold = float(threshold_input.value.strip() or "0.7")
            if not 0 <= threshold <= 1:
                raise ValueError("Threshold must be between 0 and 1")
        except ValueError as e:
            self._show_error(f"Invalid threshold: {e}")
            return

        # Parse metric name and framework
        metric_name, framework = metric_value.split(":", 1)

        # Check for duplicates
        for existing in self._selected_metrics:
            if existing["name"] == metric_name and existing["framework"] == framework:
                self._show_error(f"Metric '{metric_name}' already added")
                return

        # Add the metric
        self._selected_metrics.append(
            {
                "name": metric_name,
                "framework": framework,
                "metric_type": metric_name,
                "threshold": threshold,
            }
        )

        self._refresh_metrics_list()

    def _remove_metric(self) -> None:
        """Remove the selected metric from the list."""
        self._clear_error()

        option_list = self.query_one("#metrics-list", OptionList)
        if option_list.highlighted is None:
            self._show_error("Select a metric to remove")
            return

        option = option_list.get_option_at_index(option_list.highlighted)
        if option.id == "__empty__":
            return

        try:
            index = int(option.id)
            if 0 <= index < len(self._selected_metrics):
                self._selected_metrics.pop(index)
                self._refresh_metrics_list()
        except (ValueError, IndexError):
            pass

    def _show_error(self, message: str) -> None:
        """Display an error message."""
        error_widget = self.query_one("#error-msg", Static)
        error_widget.update(message)

    def _clear_error(self) -> None:
        """Clear the error message."""
        error_widget = self.query_one("#error-msg", Static)
        error_widget.update("")

    def action_cancel(self) -> None:
        """Cancel and close."""
        self.dismiss(None)

    def action_submit(self) -> None:
        """Submit the form."""
        self._create_eval_set()

    def _create_eval_set(self) -> None:
        """Create the evaluation set from form data."""
        self._clear_error()

        try:
            name = self.query_one("#name-input", Input).value.strip()
            description = self.query_one("#desc-input", Input).value.strip()
            threshold_str = self.query_one("#threshold-input", Input).value.strip()
            pass_rate_str = self.query_one("#pass-rate-input", Input).value.strip()

            if not name:
                self._show_error("Name is required")
                return

            if not self._selected_metrics:
                self._show_error("Add at least one metric")
                return

            # Parse thresholds
            try:
                threshold = float(threshold_str) if threshold_str else 0.7
                pass_rate = float(pass_rate_str) if pass_rate_str else 0.8
            except ValueError:
                self._show_error("Invalid threshold value")
                return

            if self.edit_set:
                # Update existing
                self.store.update_evaluation_set(
                    self.edit_set["id"],
                    name=name,
                    description=description or None,
                    metrics=self._selected_metrics,
                    default_threshold=threshold,
                    pass_rate_threshold=pass_rate,
                )
                result = {"id": self.edit_set["id"], "name": name}
            else:
                # Create new
                set_id = self.store.create_evaluation_set(
                    name=name,
                    description=description or None,
                    metrics=self._selected_metrics,
                    default_threshold=threshold,
                    pass_rate_threshold=pass_rate,
                )
                result = {"id": set_id, "name": name}

            self.dismiss(result)

        except Exception as e:
            self._show_error(f"Error: {e}")
