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
        """Render metrics for a run."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style=TEXT_MUTED)
        table.add_column("Value", style=TEXT_PRIMARY)

        # Basic info
        table.add_row("NAME", run.name)
        table.add_row("ID", str(run.id)[:8])

        # Source file
        source_file = run.attributes.get("source_file")
        if source_file:
            # Show just the filename
            filename = source_file.rsplit("/", 1)[-1] if "/" in source_file else source_file
            table.add_row("SOURCE", filename)

        # Timing
        table.add_row("STARTED", run.start_time.strftime("%Y-%m-%d %H:%M:%S"))
        if run.duration_ms:
            table.add_row("DURATION", Text(format_duration(run.duration_ms), style=ACCENT_AMBER))

        # Section break for tokens
        table.add_section()

        # Tokens
        table.add_row("TOKENS", f"{run.total_tokens:,}")
        table.add_row("COST", f"${run.total_cost_usd:.4f}")

        # Steps
        table.add_row("STEPS", str(len(run.steps)))
        if run.error_count > 0:
            table.add_row("ERRORS", Text(str(run.error_count), style=DANGER_RED))
        else:
            table.add_row("ERRORS", "0")

        # Tags
        if run.tags:
            table.add_row("TAGS", ", ".join(run.tags))

        # Error
        if run.error:
            table.add_section()
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
        """Render metrics for a step."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style=TEXT_MUTED)
        table.add_column("Value", style=TEXT_PRIMARY)

        # Basic info
        table.add_row("NAME", step.name)
        table.add_row("TYPE", step.type.value.upper())
        table.add_row("ID", str(step.id)[:8])

        # Timing
        table.add_row("STARTED", step.start_time.strftime("%H:%M:%S.%f")[:-3])
        if step.duration_ms:
            table.add_row("DURATION", Text(format_duration(step.duration_ms), style=ACCENT_AMBER))

        # LLM-specific
        if step.model_name:
            table.add_section()
            table.add_row("MODEL", Text(step.model_name, style=INFO_BLUE))
            if step.model_provider:
                table.add_row("PROVIDER", step.model_provider)

        # Tokens
        if step.input_tokens or step.output_tokens:
            table.add_section()
            table.add_row("IN TOKENS", f"{step.input_tokens or 0:,}")
            table.add_row("OUT TOKENS", f"{step.output_tokens or 0:,}")
            if step.cost_usd:
                table.add_row("COST", f"${step.cost_usd:.6f}")

        # Streaming
        if step.is_streaming:
            table.add_section()
            table.add_row("STREAMING", "yes")
            if step.streaming_chunks:
                table.add_row("CHUNKS", str(len(step.streaming_chunks)))

        # Children
        if step.children:
            table.add_section()
            table.add_row("CHILDREN", str(len(step.children)))

        # Error
        if step.error:
            table.add_section()
            error_msg = step.error
            if step.error_type:
                error_msg = f"{step.error_type}: {step.error}"
            error_text = Text(error_msg, style=DANGER_RED)
            table.add_row("ERROR", error_text)

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

    def show_project(self, project: dict[str, Any], stats: dict[str, Any] | None = None) -> None:
        """
        Display metrics for a project as a compact panel.

        Args:
            project: The project dict to display.
            stats: Optional stats dict from get_project_stats().
        """
        self._current_run = None
        self._current_step = None

        name = project.get("name", "Unknown")
        description = project.get("description", "")
        trace_count = stats.get("trace_count", 0) if stats else project.get("trace_count", 0)

        # Build compact text display
        content = Text()
        content.append(f"{name}\n", style=f"{TEXT_PRIMARY} bold")
        if description:
            content.append(f"{description}\n", style=TEXT_MUTED)
        content.append("\n")
        content.append(f"Traces: {trace_count:,}", style=TEXT_MUTED)

        if stats:
            total_tokens = stats.get("total_tokens", 0)
            total_cost = stats.get("total_cost_usd", 0)
            if total_tokens:
                content.append(f"    Tokens: {total_tokens:,}", style=TEXT_MUTED)
            if total_cost:
                content.append(f"    Cost: ${total_cost:.4f}", style=TEXT_MUTED)

        panel = Panel(
            content,
            title="PROJECT",
            title_align="left",
            border_style=INFO_BLUE,
            style=PANEL_BACKGROUND,
        )
        self.update(panel)

    def show_agent(self, agent: dict[str, Any], stats: dict[str, Any] | None = None) -> None:
        """
        Display metrics for an agent as a compact panel.

        Args:
            agent: The agent dict to display.
            stats: Optional stats dict from get_agent_stats().
        """
        self._current_run = None
        self._current_step = None

        name = agent.get("name", "Unknown")
        description = agent.get("description", "")
        effective_stats = stats or agent
        trace_count = effective_stats.get("trace_count", 0)

        # Build compact text display
        content = Text()
        content.append(f"{name}\n", style=f"{TEXT_PRIMARY} bold")
        if description:
            content.append(f"{description}\n", style=TEXT_MUTED)
        content.append("\n")
        content.append(f"Traces: {trace_count:,}", style=TEXT_MUTED)

        total_tokens = effective_stats.get("total_tokens", 0)
        total_cost = effective_stats.get("total_cost_usd", 0)
        if total_tokens:
            content.append(f"    Tokens: {total_tokens:,}", style=TEXT_MUTED)
        if total_cost:
            content.append(f"    Cost: ${total_cost:.4f}", style=TEXT_MUTED)

        panel = Panel(
            content,
            title="AGENT",
            title_align="left",
            border_style=ACCENT_AMBER,
            style=PANEL_BACKGROUND,
        )
        self.update(panel)

    def show_eval_set(self, eval_set: dict[str, Any]) -> None:
        """
        Display metrics for an evaluation set as a compact panel.

        Args:
            eval_set: The evaluation set dict to display.
        """
        self._current_run = None
        self._current_step = None

        from tracecraft.tui.theme import SUCCESS_GREEN

        name = eval_set.get("name", "Unknown")
        description = eval_set.get("description", "")
        case_count = eval_set.get("case_count", 0)
        latest_run = eval_set.get("latest_run")

        # Build compact text display
        content = Text()
        content.append(f"{name}\n", style=f"{TEXT_PRIMARY} bold")
        if description:
            content.append(f"{description}\n", style=TEXT_MUTED)
        content.append("\n")

        # Status line
        if latest_run:
            passed = latest_run.get("passed")
            pass_rate = latest_run.get("overall_pass_rate")
            rate_pct = int((pass_rate or 0) * 100)

            if passed:
                content.append("Status: ", style=TEXT_MUTED)
                content.append(f"+ PASSING ({rate_pct}%)", style=SUCCESS_GREEN)
            else:
                content.append("Status: ", style=TEXT_MUTED)
                content.append(f"x FAILING ({rate_pct}%)", style=DANGER_RED)

            content.append(f"    Cases: {case_count}", style=TEXT_MUTED)

            # Passed/Failed counts
            passed_cases = latest_run.get("passed_cases", 0)
            failed_cases = latest_run.get("failed_cases", 0)
            content.append(f"    ({passed_cases} passed, {failed_cases} failed)", style=TEXT_MUTED)
        else:
            content.append("Status: ", style=TEXT_MUTED)
            content.append("Not run yet", style=TEXT_MUTED)
            content.append(f"    Cases: {case_count}", style=TEXT_MUTED)

        # Determine border color
        border_color = INFO_BLUE
        if latest_run:
            if latest_run.get("passed"):
                border_color = SUCCESS_GREEN
            elif latest_run.get("passed") is False:
                border_color = DANGER_RED

        panel = Panel(
            content,
            title="EVAL SET",
            title_align="left",
            border_style=border_color,
            style=PANEL_BACKGROUND,
        )
        self.update(panel)
