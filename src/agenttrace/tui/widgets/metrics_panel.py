"""
Metrics panel widget for displaying trace statistics.

Shows token counts, costs, durations, and other metrics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

try:
    from textual.widgets import Static

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    Static = object  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from agenttrace.core.models import AgentRun, Step


class MetricsPanel(Static if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Panel widget for displaying metrics.

    Shows detailed metrics for the selected run or step,
    including token counts, costs, and timing information.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the metrics panel."""
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install agenttrace[tui]")
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
        """Render metrics for a run."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style="bold")
        table.add_column("Value")

        # Basic info
        table.add_row("Name", run.name)
        table.add_row("ID", str(run.id)[:8] + "...")

        # Timing
        table.add_row("Started", run.start_time.strftime("%Y-%m-%d %H:%M:%S"))
        if run.duration_ms:
            table.add_row("Duration", self._format_duration(run.duration_ms))

        table.add_row("", "")  # Spacer

        # Tokens
        table.add_row("Total Tokens", f"{run.total_tokens:,}")
        table.add_row("Total Cost", f"${run.total_cost_usd:.4f}")

        # Steps
        table.add_row("Steps", str(len(run.steps)))
        table.add_row("Errors", str(run.error_count))

        # Tags
        if run.tags:
            table.add_row("Tags", ", ".join(run.tags))

        # Error
        if run.error:
            table.add_row("", "")
            error_text = Text(f"Error: {run.error}", style="red")
            table.add_row("", error_text)

        return Panel(table, title="Run Metrics", border_style="blue")

    def _render_step_metrics(self, step: Step) -> Panel:
        """Render metrics for a step."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style="bold")
        table.add_column("Value")

        # Basic info
        table.add_row("Name", step.name)
        table.add_row("Type", step.type.value.upper())
        table.add_row("ID", str(step.id)[:8] + "...")

        # Timing
        table.add_row("Started", step.start_time.strftime("%H:%M:%S.%f")[:-3])
        if step.duration_ms:
            table.add_row("Duration", self._format_duration(step.duration_ms))

        # LLM-specific
        if step.model_name:
            table.add_row("", "")  # Spacer
            table.add_row("Model", step.model_name)
            if step.model_provider:
                table.add_row("Provider", step.model_provider)

        # Tokens
        if step.input_tokens or step.output_tokens:
            table.add_row("", "")  # Spacer
            table.add_row("Input Tokens", f"{step.input_tokens or 0:,}")
            table.add_row("Output Tokens", f"{step.output_tokens or 0:,}")
            if step.cost_usd:
                table.add_row("Cost", f"${step.cost_usd:.6f}")

        # Streaming
        if step.is_streaming:
            table.add_row("", "")
            table.add_row("Streaming", "Yes")
            if step.streaming_chunks:
                table.add_row("Chunks", str(len(step.streaming_chunks)))

        # Children
        if step.children:
            table.add_row("", "")
            table.add_row("Children", str(len(step.children)))

        # Error
        if step.error:
            table.add_row("", "")
            error_text = Text(f"Error: {step.error}", style="red")
            if step.error_type:
                error_text = Text(f"{step.error_type}: {step.error}", style="red")
            table.add_row("", error_text)

        return Panel(table, title="Step Metrics", border_style="green")

    def _render_empty(self) -> Panel:
        """Render empty state."""
        text = Text("Select a run or step to view metrics", style="dim italic")
        return Panel(text, title="Metrics", border_style="dim")

    def _format_duration(self, ms: float) -> str:
        """Format duration in human-readable form."""
        if ms < 1:
            return f"{ms * 1000:.0f}μs"
        elif ms < 1000:
            return f"{ms:.1f}ms"
        elif ms < 60000:
            return f"{ms / 1000:.2f}s"
        else:
            minutes = int(ms / 60000)
            seconds = (ms % 60000) / 1000
            return f"{minutes}m {seconds:.1f}s"
