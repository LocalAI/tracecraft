"""TUI screens for the TraceCraft terminal interface."""

from __future__ import annotations

try:
    from tracecraft.tui.screens.agent_manager import AgentEditScreen, AgentManagerScreen
    from tracecraft.tui.screens.eval_case_creator import EvalCaseCreatorScreen
    from tracecraft.tui.screens.eval_case_selector import EvalCaseSelectorScreen
    from tracecraft.tui.screens.eval_cases_viewer import EvalCasesViewerScreen
    from tracecraft.tui.screens.eval_results_viewer import EvalResultsViewerScreen
    from tracecraft.tui.screens.eval_run_history import EvalRunHistoryScreen
    from tracecraft.tui.screens.eval_runner import EvalRunnerScreen
    from tracecraft.tui.screens.eval_set_creator import EvalSetCreatorScreen
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
    AgentEditScreen = None  # type: ignore[misc,assignment]
    AgentManagerScreen = None  # type: ignore[misc,assignment]
    EvalCaseCreatorScreen = None  # type: ignore[misc,assignment]
    EvalCaseSelectorScreen = None  # type: ignore[misc,assignment]
    EvalCasesViewerScreen = None  # type: ignore[misc,assignment]
    EvalResultsViewerScreen = None  # type: ignore[misc,assignment]
    EvalRunHistoryScreen = None  # type: ignore[misc,assignment]
    EvalRunnerScreen = None  # type: ignore[misc,assignment]
    EvalSetCreatorScreen = None  # type: ignore[misc,assignment]
    HelpScreen = None  # type: ignore[misc,assignment]
    LLMPickerScreen = None  # type: ignore[misc,assignment]
    PlaygroundScreen = None  # type: ignore[misc,assignment]
    ProjectCreateScreen = None  # type: ignore[misc,assignment]
    ProjectManagerScreen = None  # type: ignore[misc,assignment]
    ConfirmScreen = None  # type: ignore[misc,assignment]
    SetupWizardScreen = None  # type: ignore[misc,assignment]
    TraceAssignScreen = None  # type: ignore[misc,assignment]

__all__ = [
    "AgentEditScreen",
    "AgentManagerScreen",
    "ConfirmScreen",
    "EvalCaseCreatorScreen",
    "EvalCaseSelectorScreen",
    "EvalCasesViewerScreen",
    "EvalResultsViewerScreen",
    "EvalRunHistoryScreen",
    "EvalRunnerScreen",
    "EvalSetCreatorScreen",
    "HelpScreen",
    "LLMPickerScreen",
    "PlaygroundScreen",
    "ProjectCreateScreen",
    "ProjectManagerScreen",
    "SetupWizardScreen",
    "TraceAssignScreen",
]
