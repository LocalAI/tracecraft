"""
Run tree widget for displaying traces hierarchically.

Shows runs and their steps in a navigable tree structure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.text import Text

try:
    from textual.widgets import Tree
    from textual.widgets.tree import TreeNode

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    Tree = object  # type: ignore[misc,assignment]
    TreeNode = Any  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from agenttrace.core.models import AgentRun, Step


class RunTree(Tree if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Tree widget for displaying agent runs and steps.

    Provides hierarchical navigation through traces with
    visual indicators for step types and errors.
    """

    STEP_TYPE_ICONS = {
        "agent": "🤖",
        "llm": "💬",
        "tool": "🔧",
        "retrieval": "🔍",
        "memory": "💾",
        "guardrail": "🛡️",
        "evaluation": "📊",
        "workflow": "📋",
        "error": "❌",
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the run tree."""
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install agenttrace[tui]")
        super().__init__("Traces", *args, **kwargs)
        self._runs: list[AgentRun] = []
        self._selected_run_id: str | None = None
        self._selected_step_id: str | None = None

    def update_runs(self, runs: list[AgentRun]) -> None:
        """
        Update the tree with new runs.

        Args:
            runs: List of AgentRun objects to display.
        """
        self._runs = runs
        self.clear()

        for run in reversed(runs):  # Most recent first
            self._add_run_node(run)

        # Expand root by default so tree content is visible immediately
        self.root.expand()

    def _add_run_node(self, run: AgentRun) -> TreeNode:
        """Add a run node to the tree."""
        # Create label with status indicator
        label = self._create_run_label(run)
        node = self.root.add(label, data={"type": "run", "id": str(run.id)})

        # Add step children
        for step in run.steps:
            self._add_step_node(node, step)

        return node

    def _add_step_node(self, parent: TreeNode, step: Step) -> TreeNode:
        """Add a step node to the tree."""
        label = self._create_step_label(step)
        node = parent.add(label, data={"type": "step", "id": str(step.id)})

        # Add children recursively
        for child in step.children:
            self._add_step_node(node, child)

        return node

    def _create_run_label(self, run: AgentRun) -> Text:
        """Create a rich text label for a run."""
        text = Text()

        # Status indicator
        if run.error or run.error_count > 0:
            text.append("● ", style="red bold")
        else:
            text.append("● ", style="green bold")

        # Run name
        text.append(run.name, style="bold")

        # Time
        time_str = run.start_time.strftime("%H:%M:%S")
        text.append(f" [{time_str}]", style="dim")

        # Duration
        if run.duration_ms:
            duration_str = self._format_duration(run.duration_ms)
            text.append(f" ({duration_str})", style="cyan")

        # Token/cost summary
        if run.total_tokens > 0:
            text.append(f" 📊{run.total_tokens}", style="yellow")
        if run.total_cost_usd > 0:
            text.append(f" ${run.total_cost_usd:.4f}", style="magenta")

        return text

    def _create_step_label(self, step: Step) -> Text:
        """Create a rich text label for a step."""
        text = Text()

        # Type icon
        icon = self.STEP_TYPE_ICONS.get(step.type.value, "◯")
        text.append(f"{icon} ", style="bold")

        # Step name
        if step.error:
            text.append(step.name, style="red")
        else:
            text.append(step.name)

        # Model info for LLM steps
        if step.model_name:
            text.append(f" [{step.model_name}]", style="blue")

        # Duration
        if step.duration_ms:
            duration_str = self._format_duration(step.duration_ms)
            text.append(f" ({duration_str})", style="cyan dim")

        # Tokens
        if step.input_tokens or step.output_tokens:
            tokens = (step.input_tokens or 0) + (step.output_tokens or 0)
            text.append(f" {tokens}t", style="yellow dim")

        # Error indicator
        if step.error:
            text.append(" ❌", style="red")

        return text

    def _format_duration(self, ms: float) -> str:
        """Format duration in human-readable form."""
        if ms < 1000:
            return f"{ms:.0f}ms"
        elif ms < 60000:
            return f"{ms / 1000:.1f}s"
        else:
            return f"{ms / 60000:.1f}m"

    def get_selected_data(self) -> dict[str, Any] | None:
        """Get the data for the currently selected node."""
        if self.cursor_node:
            return self.cursor_node.data
        return None

    def get_selected_run(self) -> AgentRun | None:
        """Get the currently selected run."""
        data = self.get_selected_data()
        if data and data.get("type") == "run":
            run_id = data.get("id")
            for run in self._runs:
                if str(run.id) == run_id:
                    return run
        return None

    def get_selected_step(self) -> Step | None:
        """Get the currently selected step."""
        data = self.get_selected_data()
        if data and data.get("type") == "step":
            step_id = data.get("id")
            for run in self._runs:
                step = self._find_step(run.steps, step_id)
                if step:
                    return step
        return None

    def _find_step(self, steps: list[Step], step_id: str) -> Step | None:
        """Recursively find a step by ID."""
        for step in steps:
            if str(step.id) == step_id:
                return step
            found = self._find_step(step.children, step_id)
            if found:
                return found
        return None
