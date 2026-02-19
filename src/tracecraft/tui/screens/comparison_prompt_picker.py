"""
Comparison prompt picker modal for selecting prompt and model.

NOIR SIGNAL theme styling.
"""

from __future__ import annotations

from typing import Any

from tracecraft.comparison.prompts import PromptManager
from tracecraft.tui.theme import (
    ACCENT_AMBER,
    BACKGROUND,
    BORDER,
    INFO_BLUE,
    SURFACE,
)

try:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.screen import ModalScreen
    from textual.widgets import Button, Footer, Label, Select

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    ComposeResult = Any  # type: ignore[misc,assignment]
    ModalScreen = object  # type: ignore[misc,assignment]


# Model options organized by provider
MODELS = [
    ("OpenAI: GPT-4o", "gpt-4o", "openai"),
    ("OpenAI: GPT-4o Mini", "gpt-4o-mini", "openai"),
    ("OpenAI: GPT-4 Turbo", "gpt-4-turbo", "openai"),
    ("Anthropic: Claude Sonnet 4", "claude-sonnet-4-20250514", "anthropic"),
    ("Anthropic: Claude Haiku 3.5", "claude-3-5-haiku-20241022", "anthropic"),
    ("Anthropic: Claude Opus 4", "claude-opus-4-20250514", "anthropic"),
]


class ComparisonPromptPicker(ModalScreen if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Modal screen for selecting comparison prompt and model.

    Returns tuple of (prompt_id, model, provider) when dismissed,
    or None if cancelled.
    """

    BINDINGS = (
        [
            Binding("escape", "cancel", "Cancel"),
            Binding("enter", "confirm", "Compare"),
        ]
        if TEXTUAL_AVAILABLE
        else []
    )

    CSS = f"""
    /* NOIR SIGNAL - Comparison Prompt Picker */
    ComparisonPromptPicker {{
        align: center middle;
        background: rgba(11, 14, 17, 0.85);
    }}

    #picker-container {{
        width: 60;
        height: auto;
        max-height: 80%;
        border: solid {ACCENT_AMBER};
        background: {SURFACE};
        padding: 1 2;
    }}

    #picker-title {{
        text-style: bold;
        text-align: center;
        margin-bottom: 1;
        color: {ACCENT_AMBER};
    }}

    .picker-label {{
        margin-top: 1;
        color: {INFO_BLUE};
    }}

    #prompt-select, #model-select {{
        width: 100%;
        margin-bottom: 1;
        background: {BACKGROUND};
        border: solid {BORDER};
    }}

    #prompt-select:focus, #model-select:focus {{
        border: solid {ACCENT_AMBER};
    }}

    #button-row {{
        margin-top: 1;
        height: auto;
        align: center middle;
    }}

    #confirm-btn {{
        margin-right: 2;
    }}

    Button {{
        min-width: 12;
    }}
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the comparison prompt picker."""
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__(*args, **kwargs)
        self._prompt_manager = PromptManager()

    def compose(self) -> ComposeResult:
        """Compose the picker layout."""
        prompts = self._prompt_manager.list_prompts()

        with Vertical(id="picker-container"):
            yield Label("COMPARE TRACES", id="picker-title")

            yield Label("Prompt:", classes="picker-label")
            yield Select(
                [(p.name, p.id) for p in prompts],
                value=prompts[0].id if prompts else None,
                id="prompt-select",
                allow_blank=False,
            )

            yield Label("Model:", classes="picker-label")
            yield Select(
                [(name, f"{model}|{provider}") for name, model, provider in MODELS],
                value=f"{MODELS[0][1]}|{MODELS[0][2]}",
                id="model-select",
                allow_blank=False,
            )

            with Horizontal(id="button-row"):
                yield Button("Compare", variant="primary", id="confirm-btn")
                yield Button("Cancel", id="cancel-btn")

        yield Footer()

    def on_button_pressed(self, event: Any) -> None:
        """Handle button press events."""
        if event.button.id == "confirm-btn":
            self._do_confirm()
        elif event.button.id == "cancel-btn":
            self.dismiss(None)

    def action_cancel(self) -> None:
        """Cancel and close the picker."""
        self.dismiss(None)

    def action_confirm(self) -> None:
        """Confirm selection and close."""
        self._do_confirm()

    def _do_confirm(self) -> None:
        """Perform the confirmation action."""
        prompt_select = self.query_one("#prompt-select", Select)
        model_select = self.query_one("#model-select", Select)

        prompt_id = prompt_select.value
        model_value = model_select.value

        if prompt_id and model_value:
            # Parse model|provider format
            model, provider = str(model_value).split("|")
            self.dismiss((str(prompt_id), model, provider))
        else:
            self.dismiss(None)
