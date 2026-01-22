"""
AgentTrace Terminal UI - k9s-style trace explorer.

A real-time, interactive terminal interface for exploring
and debugging LLM/Agent traces.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

__all__ = ["run_tui", "AgentTraceApp"]


def run_tui(
    source: str | None = None,
    watch: bool = False,
) -> None:
    """
    Run the AgentTrace TUI.

    Args:
        source: Trace source (JSONL file path or directory).
        watch: Watch for new traces in real-time.

    Example:
        from agenttrace.tui import run_tui
        run_tui("traces/agenttrace.jsonl", watch=True)
    """
    from agenttrace.tui.app import AgentTraceApp

    app = AgentTraceApp(trace_source=source, watch=watch)
    app.run()


def get_app_class() -> type:
    """Get the AgentTraceApp class (for lazy import)."""
    from agenttrace.tui.app import AgentTraceApp

    return AgentTraceApp
