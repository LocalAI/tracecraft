"""
Metrics panel widget for displaying trace statistics.

Shows token counts, costs, durations, and other metrics.
NOIR SIGNAL theme styling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Import theme constants for consistent styling
from tracecraft.tui.theme import (
    ACCENT_AMBER,
    BORDER,
    DANGER_RED,
    INFO_BLUE,
    PANEL_BACKGROUND,
    PANEL_BORDER_DANGER,
    PANEL_BORDER_DEFAULT,
    PANEL_BORDER_INFO,
    SURFACE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    format_duration,
)

try:
    from textual.widgets import Static

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    Static = object  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun, Step


class MetricsPanel(Static if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Panel widget for displaying metrics.

    Shows detailed metrics for the selected run or step,
    including token counts, costs, and timing information.
    """

    DEFAULT_CSS = f"""
    /* NOIR SIGNAL - Metrics Panel */
    MetricsPanel {{
        background: {SURFACE};
        border: solid {BORDER};
        padding: 0;
    }}
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the metrics panel."""
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__(*args, **kwargs)
        self._current_run: AgentRun | None = None
        self._current_step: Step | None = None

    def show_run(self, run: AgentRun | None) -> None:
        """
        Display metrics for a run.

        Args:
            run: The AgentRun to display, or None to clear.
        """
        self._current_run = run
        self._current_step = None
        self._update_display()

    def show_step(self, step: Step | None) -> None:
        """
        Display metrics for a step.

        Args:
            step: The Step to display, or None to clear.
        """
        self._current_step = step
        self._update_display()

    def _update_display(self) -> None:
        """Update the panel content."""
        if self._current_step:
            content = self._render_step_metrics(self._current_step)
        elif self._current_run:
            content = self._render_run_metrics(self._current_run)
        else:
            content = self._render_empty()

        self.update(content)

    def _render_run_metrics(self, run: AgentRun) -> Panel:
        """Render compact metrics for a run - only essential info."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style=TEXT_MUTED)
        table.add_column("Value", style=TEXT_PRIMARY)

        # Essential info only
        table.add_row("NAME", run.name)
        if run.duration_ms:
            table.add_row("DURATION", Text(format_duration(run.duration_ms), style=ACCENT_AMBER))

        # Resource usage
        table.add_row("TOKENS", f"{run.total_tokens:,}")
        table.add_row("COST", f"${run.total_cost_usd:.4f}")

        # Errors only if present
        if run.error_count > 0:
            table.add_row("ERRORS", Text(str(run.error_count), style=DANGER_RED))

        # Error message if present
        if run.error:
            error_text = Text(run.error, style=DANGER_RED)
            table.add_row("ERROR", error_text)

        return Panel(
            table,
            title="RUN",
            title_align="left",
            border_style=PANEL_BORDER_DEFAULT,
            style=PANEL_BACKGROUND,
        )

    def _render_step_metrics(self, step: Step) -> Panel:
        """Render compact metrics for a step - only essential info."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style=TEXT_MUTED)
        table.add_column("Value", style=TEXT_PRIMARY)

        # Essential info
        table.add_row("NAME", step.name)
        table.add_row("TYPE", step.type.value.upper())
        if step.duration_ms:
            table.add_row("DURATION", Text(format_duration(step.duration_ms), style=ACCENT_AMBER))

        # Model name (important for LLM steps)
        if step.model_name:
            table.add_row("MODEL", Text(step.model_name, style=INFO_BLUE))

        # Token usage (combined for compactness)
        if step.input_tokens or step.output_tokens:
            tokens = f"{step.input_tokens or 0:,} → {step.output_tokens or 0:,}"
            table.add_row("TOKENS", tokens)
            if step.cost_usd:
                table.add_row("COST", f"${step.cost_usd:.6f}")

        # Error only if present
        if step.error:
            error_msg = step.error
            if step.error_type:
                error_msg = f"{step.error_type}: {step.error}"
            table.add_row("ERROR", Text(error_msg, style=DANGER_RED))

        # Determine border color by step type
        border_color = PANEL_BORDER_DEFAULT
        if step.error:
            border_color = PANEL_BORDER_DANGER
        elif step.type.value == "llm":
            border_color = PANEL_BORDER_INFO

        return Panel(
            table,
            title="STEP",
            title_align="left",
            border_style=border_color,
            style=PANEL_BACKGROUND,
        )

    def _render_empty(self) -> Panel:
        """Render empty state."""
        text = Text("Select a trace or step", style=TEXT_MUTED)
        return Panel(
            text,
            title="METRICS",
            title_align="left",
            border_style=PANEL_BORDER_DEFAULT,
            style=PANEL_BACKGROUND,
        )
