"""
Rich console tree exporter.

Displays agent traces as beautiful tree structures in the terminal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TextIO

from rich.console import Console
from rich.tree import Tree

from tracecraft.core.models import StepType
from tracecraft.exporters.base import BaseExporter

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun, Step


# Icons for different step types
STEP_ICONS: dict[StepType, str] = {
    StepType.AGENT: "\U0001f916",  # Robot
    StepType.LLM: "\U0001f4ac",  # Speech bubble
    StepType.TOOL: "\U0001f527",  # Wrench
    StepType.RETRIEVAL: "\U0001f4da",  # Books
    StepType.MEMORY: "\U0001f4be",  # Floppy disk
    StepType.GUARDRAIL: "\U0001f6e1",  # Shield
    StepType.WORKFLOW: "\U0001f4c2",  # Folder
    StepType.ERROR: "\u274c",  # Red X
}

# Colors for different step types
STEP_COLORS: dict[StepType, str] = {
    StepType.AGENT: "bold cyan",
    StepType.LLM: "bold green",
    StepType.TOOL: "bold yellow",
    StepType.RETRIEVAL: "bold blue",
    StepType.MEMORY: "bold magenta",
    StepType.GUARDRAIL: "bold white",
    StepType.WORKFLOW: "dim",
    StepType.ERROR: "bold red",
}


class ConsoleExporter(BaseExporter):
    """
    Exports traces as Rich tree structures to the console.

    Creates a visual tree representation of the agent run with icons,
    timing information, and optional verbose output.
    """

    def __init__(
        self,
        file: TextIO | None = None,
        no_color: bool = False,
        verbose: bool = False,
    ) -> None:
        """
        Initialize the console exporter.

        Args:
            file: Output file (defaults to stdout).
            no_color: Disable color output.
            verbose: Show detailed inputs/outputs.
        """
        self.verbose = verbose
        self.console = Console(
            file=file,
            force_terminal=not no_color if file else None,
            no_color=no_color,
        )

    def export(self, run: AgentRun) -> None:
        """
        Export an agent run as a Rich tree.

        Args:
            run: The AgentRun to display.
        """
        # Create root tree with run info
        run_label = self._format_run_label(run)
        tree = Tree(run_label)

        # Add steps recursively
        for step in run.steps:
            self._add_step_to_tree(tree, step)

        # Print the tree
        self.console.print(tree)

    def _format_run_label(self, run: AgentRun) -> str:
        """Format the label for the root run node."""
        parts = [f"[bold]{run.name}[/bold]"]

        if run.duration_ms is not None:
            parts.append(f"[dim]({run.duration_ms:.1f}ms)[/dim]")

        if run.total_tokens > 0:
            parts.append(f"[dim][{run.total_tokens} tokens][/dim]")

        if run.total_cost_usd > 0:
            parts.append(f"[dim][${run.total_cost_usd:.4f}][/dim]")

        return " ".join(parts)

    def _add_step_to_tree(self, tree: Tree, step: Step) -> None:
        """Recursively add a step and its children to the tree."""
        label = self._format_step_label(step)
        branch = tree.add(label)

        # Add verbose info if enabled
        if self.verbose:
            if step.inputs:
                branch.add(f"[dim]inputs: {step.inputs}[/dim]")
            if step.outputs:
                branch.add(f"[dim]outputs: {step.outputs}[/dim]")

        # Recursively add children
        for child in step.children:
            self._add_step_to_tree(branch, child)

    def _format_step_label(self, step: Step) -> str:
        """Format the label for a step node."""
        icon = STEP_ICONS.get(step.type, "\u2022")  # Bullet as fallback
        color = STEP_COLORS.get(step.type, "white")

        parts = [icon, f"[{color}]{step.name}[/{color}]"]

        # Add model info for LLM steps
        if step.model_name:
            parts.append(f"[dim]({step.model_name})[/dim]")

        # Add timing
        if step.duration_ms is not None:
            parts.append(f"[dim]{step.duration_ms:.1f}ms[/dim]")

        # Add token counts
        if step.input_tokens is not None or step.output_tokens is not None:
            input_tok = step.input_tokens or 0
            output_tok = step.output_tokens or 0
            parts.append(f"[dim][{input_tok}/{output_tok} tokens][/dim]")

        # Add error indicator
        if step.error:
            parts.append(f"[red]ERROR: {step.error}[/red]")

        return " ".join(parts)
