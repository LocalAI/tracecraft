"""TUI screens for the TraceCraft terminal interface."""

from __future__ import annotations

try:
    from tracecraft.tui.screens.help_screen import HelpScreen
    from tracecraft.tui.screens.llm_picker import LLMPickerScreen
    from tracecraft.tui.screens.playground import PlaygroundScreen
    from tracecraft.tui.screens.project_create import ProjectCreateScreen
    from tracecraft.tui.screens.project_manager import ConfirmScreen, ProjectManagerScreen
    from tracecraft.tui.screens.setup_wizard import SetupWizardScreen
    from tracecraft.tui.screens.trace_assign import TraceAssignScreen

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    HelpScreen = None  # type: ignore[misc,assignment]
    LLMPickerScreen = None  # type: ignore[misc,assignment]
    PlaygroundScreen = None  # type: ignore[misc,assignment]
    ProjectCreateScreen = None  # type: ignore[misc,assignment]
    ProjectManagerScreen = None  # type: ignore[misc,assignment]
    ConfirmScreen = None  # type: ignore[misc,assignment]
    SetupWizardScreen = None  # type: ignore[misc,assignment]
    TraceAssignScreen = None  # type: ignore[misc,assignment]

__all__ = [
    "ConfirmScreen",
    "HelpScreen",
    "LLMPickerScreen",
    "PlaygroundScreen",
    "ProjectCreateScreen",
    "ProjectManagerScreen",
    "SetupWizardScreen",
    "TraceAssignScreen",
]
