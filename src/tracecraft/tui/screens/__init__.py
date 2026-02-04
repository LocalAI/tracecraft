"""TUI screens for the TraceCraft terminal interface."""

from __future__ import annotations

try:
    from tracecraft.tui.screens.help_screen import HelpScreen
    from tracecraft.tui.screens.llm_picker import LLMPickerScreen
    from tracecraft.tui.screens.playground import PlaygroundScreen
    from tracecraft.tui.screens.setup_wizard import SetupWizardScreen

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    HelpScreen = None  # type: ignore[misc,assignment]
    LLMPickerScreen = None  # type: ignore[misc,assignment]
    PlaygroundScreen = None  # type: ignore[misc,assignment]
    SetupWizardScreen = None  # type: ignore[misc,assignment]

__all__ = [
    "HelpScreen",
    "LLMPickerScreen",
    "PlaygroundScreen",
    "SetupWizardScreen",
]
