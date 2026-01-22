"""
LLM step picker screen for selecting from nested LLM calls.

Provides a modal dialog for selecting which LLM step to open
in the playground when an agent step contains multiple LLM children.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Vertical
    from textual.screen import ModalScreen
    from textual.widgets import Footer, Label, OptionList
    from textual.widgets.option_list import Option

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    ComposeResult = Any  # type: ignore[misc,assignment]
    ModalScreen = object  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from agenttrace.core.models import Step


class LLMPickerScreen(ModalScreen if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Modal screen for selecting an LLM step from a list.

    Returns the selected Step when dismissed, or None if cancelled.
    """

    BINDINGS = (
        [
            Binding("escape", "cancel", "Back"),
            Binding("enter", "select", "Select"),
        ]
        if TEXTUAL_AVAILABLE
        else []
    )

    CSS = """
    LLMPickerScreen {
        align: center middle;
    }

    #picker-container {
        width: 70%;
        height: 60%;
        border: solid $primary;
        background: $surface;
        padding: 1;
    }

    #picker-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #llm-list {
        height: 1fr;
        border: solid $primary-darken-2;
    }
    """

    def __init__(
        self,
        llm_steps: list[Step],
        parent_name: str = "Agent",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the LLM picker screen.

        Args:
            llm_steps: List of LLM steps to choose from.
            parent_name: Name of the parent step for display.
        """
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install agenttrace[tui]")
        super().__init__(*args, **kwargs)
        self._llm_steps = llm_steps
        self._parent_name = parent_name

    def compose(self) -> ComposeResult:
        """Compose the picker layout."""
        with Vertical(id="picker-container"):
            yield Label(
                f"Select LLM step from '{self._parent_name}':",  # nosec B608 - not SQL
                id="picker-title",
            )

            options = []
            for i, step in enumerate(self._llm_steps):
                model = step.model_name or "unknown"
                tokens = (step.input_tokens or 0) + (step.output_tokens or 0)
                duration = f"{step.duration_ms:.0f}ms" if step.duration_ms else "N/A"
                label = f"{step.name} [{model}] - {tokens}t, {duration}"
                options.append(Option(label, id=str(i)))

            yield OptionList(*options, id="llm-list")

        yield Footer()

    def action_cancel(self) -> None:
        """Cancel and close the picker."""
        self.dismiss(None)

    def action_select(self) -> None:
        """Select the highlighted option and close."""
        option_list = self.query_one("#llm-list", OptionList)
        if option_list.highlighted is not None:
            idx = int(option_list.get_option_at_index(option_list.highlighted).id)
            self.dismiss(self._llm_steps[idx])
        else:
            self.dismiss(None)

    def on_option_list_option_selected(self, event: Any) -> None:
        """Handle double-click or Enter on an option."""
        idx = int(event.option.id)
        self.dismiss(self._llm_steps[idx])
