"""TUI screens for the AgentTrace terminal interface."""

from __future__ import annotations

try:
    from agenttrace.tui.screens.llm_picker import LLMPickerScreen
    from agenttrace.tui.screens.playground import PlaygroundScreen

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    LLMPickerScreen = None  # type: ignore[misc,assignment]
    PlaygroundScreen = None  # type: ignore[misc,assignment]

__all__ = ["LLMPickerScreen", "PlaygroundScreen"]
