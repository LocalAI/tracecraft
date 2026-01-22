"""
Input/Output viewer widget.

Displays inputs, outputs, and attributes as formatted JSON.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

try:
    from textual.widgets import RichLog

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    RichLog = object  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from agenttrace.core.models import AgentRun, Step


class IOViewer(RichLog if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Widget for viewing inputs, outputs, and attributes.

    Provides syntax-highlighted, scrollable JSON viewing with tabs for
    different data sections. Uses RichLog for built-in scrolling support.
    """

    # View modes
    MODE_INPUT = "input"
    MODE_OUTPUT = "output"
    MODE_ATTRIBUTES = "attributes"
    MODE_JSON = "json"
    MODE_ERROR = "error"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the IO viewer."""
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install agenttrace[tui]")
        # RichLog configuration: enable highlighting and markup for rich content
        super().__init__(*args, highlight=True, markup=True, **kwargs)
        self._current_run: AgentRun | None = None
        self._current_step: Step | None = None
        self._mode: str = self.MODE_OUTPUT

    def show_run(self, run: AgentRun | None) -> None:
        """
        Display data for a run.

        Args:
            run: The AgentRun to display, or None to clear.
        """
        self._current_run = run
        self._current_step = None
        self._update_display()

    def show_step(self, step: Step | None) -> None:
        """
        Display data for a step.

        Args:
            step: The Step to display, or None to clear.
        """
        self._current_step = step
        self._update_display()

    def set_mode(self, mode: str) -> None:
        """
        Set the viewing mode.

        Args:
            mode: One of MODE_INPUT, MODE_OUTPUT, MODE_ATTRIBUTES, MODE_JSON, MODE_ERROR.
        """
        self._mode = mode
        self._update_display()

    def cycle_mode(self) -> None:
        """Cycle through viewing modes."""
        modes = [
            self.MODE_INPUT,
            self.MODE_OUTPUT,
            self.MODE_ATTRIBUTES,
            self.MODE_JSON,
        ]

        # Add error mode if there's an error
        if (self._current_step and self._current_step.error) or (
            self._current_run and self._current_run.error
        ):
            modes.append(self.MODE_ERROR)

        try:
            current_idx = modes.index(self._mode)
            next_idx = (current_idx + 1) % len(modes)
            self._mode = modes[next_idx]
        except ValueError:
            self._mode = self.MODE_OUTPUT

        self._update_display()

    def _update_display(self) -> None:
        """Update the viewer content."""
        # Clear existing content for RichLog
        self.clear()

        if self._current_step:
            content = self._render_step_content(self._current_step)
        elif self._current_run:
            content = self._render_run_content(self._current_run)
        else:
            content = self._render_empty()

        # Write content to RichLog (supports scrolling)
        self.write(content)

    def _render_run_content(self, run: AgentRun) -> Panel:
        """Render content for a run."""
        title = f"Run: {run.name} [{self._mode.upper()}]"

        if self._mode == self.MODE_INPUT:
            data = run.input
        elif self._mode == self.MODE_OUTPUT:
            data = run.output
        elif self._mode == self.MODE_ATTRIBUTES:
            data = {"tags": run.tags, "session_id": run.session_id, "user_id": run.user_id}
        elif self._mode == self.MODE_ERROR:
            if run.error:
                return Panel(
                    Text(f"{run.error_type or 'Error'}: {run.error}", style="red"),
                    title=title,
                    border_style="red",
                )
            data = None
        else:  # JSON mode
            data = run.model_dump(mode="json", exclude={"steps"})

        return self._render_json_panel(data, title)

    def _render_step_content(self, step: Step) -> Panel:
        """Render content for a step."""
        title = f"Step: {step.name} [{self._mode.upper()}]"

        if self._mode == self.MODE_INPUT:
            data = step.inputs
        elif self._mode == self.MODE_OUTPUT:
            data = step.outputs
        elif self._mode == self.MODE_ATTRIBUTES:
            data = step.attributes
        elif self._mode == self.MODE_ERROR:
            if step.error:
                return Panel(
                    Text(f"{step.error_type or 'Error'}: {step.error}", style="red"),
                    title=title,
                    border_style="red",
                )
            data = None
        else:  # JSON mode
            data = step.model_dump(mode="json", exclude={"children"})

        return self._render_json_panel(data, title)

    def _render_json_panel(self, data: Any, title: str) -> Panel:
        """Render data as a JSON panel with syntax highlighting."""
        if data is None:
            content = Text("No data", style="dim italic")
            return Panel(content, title=title, border_style="dim")

        try:
            json_str = json.dumps(data, indent=2, default=str)
            # No truncation needed - RichLog handles scrolling
            content = Syntax(json_str, "json", theme="monokai", line_numbers=True)
        except (TypeError, ValueError):
            content = Text(str(data))

        return Panel(content, title=title, border_style="cyan")

    def _render_empty(self) -> Panel:
        """Render empty state."""
        text = Text("Select a run or step to view data", style="dim italic")
        return Panel(text, title="Data Viewer", border_style="dim")

    @property
    def mode(self) -> str:
        """Get the current viewing mode."""
        return self._mode
