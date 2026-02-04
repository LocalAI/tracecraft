"""
Run tree widget for displaying traces hierarchically.

Shows runs and their steps in a navigable tree structure.
Supports multiple view modes: traces and projects.
NOIR SIGNAL theme styling.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

from rich.text import Text

# Import theme constants for consistent styling
from tracecraft.tui.theme import (
    ACCENT_AMBER,
    BORDER,
    DANGER_RED,
    INFO_BLUE,
    SUCCESS_GREEN,
    SURFACE,
    SURFACE_HIGHLIGHT,
    TEXT_MUTED,
    TEXT_PRIMARY,
    format_duration,
    truncate_with_ellipsis,
)

try:
    from textual.widgets import Tree
    from textual.widgets.tree import TreeNode

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    Tree = object  # type: ignore[misc,assignment]
    TreeNode = Any  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun, Step


class TreeViewMode(str, Enum):
    """The view modes for the run tree."""

    TRACES = "traces"
    PROJECTS = "projects"
    PROJECT_TREE = "project_tree"  # Hierarchical view of a single project


# Additional step type color (purple for retrieval)
RETRIEVAL_PURPLE = "#9B7EDE"


class RunTree(Tree if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Tree widget for displaying agent runs and steps.

    Provides hierarchical navigation through traces with
    visual indicators for step types and errors.
    """

    # NOIR SIGNAL - Unicode step type indicators (visually distinct, no emojis)
    STEP_TYPE_ICONS = {
        "agent": "◆",  # Filled diamond - coordination/central
        "llm": "◉",  # Circle with dot - thinking/brain
        "tool": "▶",  # Play arrow - action/execution
        "retrieval": "◀",  # Back arrow - fetching/pulling
        "memory": "▬",  # Rectangle - storage
        "guardrail": "◇",  # Hollow diamond - protection
        "evaluation": "◈",  # Diamond with center - assessment
        "workflow": "▷",  # Hollow triangle - flow/process
        "error": "✕",  # X mark - failure
    }

    # Step type colors for visual distinction (using theme constants)
    STEP_TYPE_COLORS = {
        "agent": ACCENT_AMBER,  # Amber - primary/coordinator
        "llm": INFO_BLUE,  # Blue - LLM calls
        "tool": SUCCESS_GREEN,  # Green - tool execution
        "retrieval": RETRIEVAL_PURPLE,  # Purple - data retrieval
        "memory": TEXT_MUTED,  # Gray - memory ops
        "guardrail": ACCENT_AMBER,  # Amber - guardrails
        "evaluation": INFO_BLUE,  # Blue - evaluation
        "workflow": TEXT_MUTED,  # Gray - workflow
        "error": DANGER_RED,  # Red - errors
    }

    # Step type text labels for explicit display
    STEP_TYPE_LABELS = {
        "agent": "agent",
        "llm": "llm",
        "tool": "tool",
        "retrieval": "retrieval",
        "memory": "memory",
        "guardrail": "guardrail",
        "evaluation": "evaluation",
        "workflow": "workflow",
    }

    # Max length for truncation
    MAX_NAME_LENGTH = 40

    DEFAULT_CSS = f"""
    /* NOIR SIGNAL - Run Tree */
    RunTree {{
        background: {SURFACE};
        color: {TEXT_PRIMARY};
        border: solid {BORDER};
    }}

    RunTree:focus {{
        border: solid {ACCENT_AMBER};
    }}

    RunTree > .tree--cursor {{
        background: {SURFACE_HIGHLIGHT};
        color: {ACCENT_AMBER};
    }}

    RunTree > .tree--highlight {{
        background: {SURFACE_HIGHLIGHT};
    }}

    RunTree > .tree--guides {{
        color: {BORDER};
    }}
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the run tree."""
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__("Traces", *args, **kwargs)
        self._runs: list[AgentRun] = []
        self._step_cache: dict[str, Step] = {}  # O(1) step lookup cache
        self._selected_run_id: str | None = None
        self._selected_step_id: str | None = None
        self._view_mode: TreeViewMode = TreeViewMode.TRACES
        self._projects: list[dict[str, Any]] = []  # Cached projects

    def update_runs(self, runs: list[AgentRun], *, is_filtered: bool = False) -> None:
        """
        Update the tree with new runs.

        Args:
            runs: List of AgentRun objects to display.
            is_filtered: Whether the runs are a filtered subset.
        """
        self.show_traces(runs, is_filtered=is_filtered)

    def show_traces(self, runs: list[AgentRun], *, is_filtered: bool = False) -> None:
        """
        Show traces view - flat list of all runs.

        Args:
            runs: List of AgentRun objects to display.
            is_filtered: Whether the runs are a filtered subset.
        """
        self._view_mode = TreeViewMode.TRACES
        self._runs = runs
        self._step_cache.clear()  # Invalidate cache
        self.clear()

        if not runs:
            # Show empty state message
            if is_filtered:
                empty_label = Text("No matches. Try broadening your filter.", style=TEXT_MUTED)
            else:
                empty_label = Text(
                    "No traces found. Run your agent to capture traces.", style=TEXT_MUTED
                )
            self.root.add(empty_label, data={"type": "empty"})
        else:
            for run in reversed(runs):  # Most recent first
                self._add_run_node(run)
                # Build step cache for O(1) lookups
                self._cache_steps(run.steps)

        # Expand root by default so tree content is visible immediately
        self.root.expand()

    def show_projects(self, projects: list[dict[str, Any]]) -> None:
        """
        Show projects view - list of projects that can be expanded.

        Args:
            projects: List of project dicts from SQLite store.
        """
        self._view_mode = TreeViewMode.PROJECTS
        self._projects = projects
        self._runs = []
        self._step_cache.clear()
        self.clear()

        if not projects:
            empty_label = Text("No projects found. Create one with Shift+P.", style=TEXT_MUTED)
            self.root.add(empty_label, data={"type": "empty"})
        else:
            for project in projects:
                self._add_project_node(project)

        self.root.expand()

    def show_project_tree(self, structure: dict[str, Any]) -> None:
        """
        Show hierarchical project tree - project with traces.

        Args:
            structure: Project structure dict from get_project_structure() containing:
                - project: Project info dict
                - trace_count: Number of traces
                - traces: Optional list of trace dicts (for preview)
        """
        self._view_mode = TreeViewMode.PROJECT_TREE
        self._runs = []
        self._step_cache.clear()
        self.clear()

        project = structure.get("project", {})
        trace_count = structure.get("trace_count", 0)
        traces = structure.get("traces", [])

        if not project:
            empty_label = Text("No project data.", style=TEXT_MUTED)
            self.root.add(empty_label, data={"type": "empty"})
            self.root.expand()
            return

        # Update root label with project name
        project_name = project.get("name", "Unknown Project")
        self.root.set_label(Text(f"📁 {project_name}", style=f"{TEXT_PRIMARY} bold"))

        # Traces folder (shows count, can expand to load traces)
        traces_folder = self.root.add(
            self._create_folder_label("Traces", trace_count, SUCCESS_GREEN),
            data={"type": "folder", "folder_type": "traces", "project_id": project["id"]},
        )
        # Add preview traces if provided
        for trace in traces[:10]:  # Limit preview to 10
            self._add_trace_child_node(traces_folder, trace)

        if trace_count > 10 and len(traces) >= 10:
            traces_folder.add(
                Text(f"... and {trace_count - 10} more", style=TEXT_MUTED),
                data={"type": "more", "folder_type": "traces", "project_id": project["id"]},
            )

        self.root.expand()
        traces_folder.expand()

    def _create_folder_label(self, name: str, count: int, color: str) -> Text:
        """Create a rich text label for a folder node."""
        text = Text()
        text.append("▸ ", style=color)
        text.append(name, style=f"{TEXT_PRIMARY} bold")
        text.append(f" ({count})", style=TEXT_MUTED)
        return text

    def _add_trace_child_node(self, parent: TreeNode, trace: dict[str, Any]) -> TreeNode:
        """Add a trace node as child of a folder (from dict, not AgentRun)."""
        text = Text()
        # Status indicator
        if trace.get("error"):
            text.append("× ", style=f"{DANGER_RED} bold")
        else:
            text.append("› ", style=SUCCESS_GREEN)

        # Trace name
        name = truncate_with_ellipsis(trace.get("name", "unknown"), self.MAX_NAME_LENGTH)
        text.append(name, style=TEXT_PRIMARY)

        # Duration
        if trace.get("duration_ms"):
            duration_str = format_duration(trace["duration_ms"])
            text.append(f" {duration_str}", style=ACCENT_AMBER)

        return parent.add(
            text,
            data={"type": "trace", "id": trace["id"]},
        )

    def _add_project_node(self, project: dict[str, Any]) -> TreeNode:
        """Add a project node to the tree."""
        label = self._create_project_label(project)
        node = self.root.add(
            label,
            data={"type": "project", "id": project["id"], "name": project["name"]},
        )
        # Projects are collapsed by default - user clicks to expand/load traces
        return node

    def _create_project_label(self, project: dict[str, Any]) -> Text:
        """Create a rich text label for a project."""
        text = Text()

        # Project icon
        text.append("+ ", style=INFO_BLUE)

        # Project name
        name = truncate_with_ellipsis(project["name"], self.MAX_NAME_LENGTH)
        text.append(name, style=f"{TEXT_PRIMARY} bold")

        # Description if available
        if project.get("description"):
            desc = truncate_with_ellipsis(project["description"], 30)
            text.append(f" - {desc}", style=TEXT_MUTED)

        return text

    @property
    def view_mode(self) -> TreeViewMode:
        """Get the current view mode."""
        return self._view_mode

    def get_selected_project(self) -> dict[str, Any] | None:
        """Get the currently selected project."""
        data = self.get_selected_data()
        if data and data.get("type") == "project":
            project_id = data.get("id")
            for project in self._projects:
                if project["id"] == project_id:
                    return project
        return None

    def _cache_steps(self, steps: list[Step]) -> None:
        """Recursively cache all steps for O(1) lookup."""
        for step in steps:
            self._step_cache[str(step.id)] = step
            if step.children:
                self._cache_steps(step.children)

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

        # Status indicator - minimal, no emojis
        if run.error or run.error_count > 0:
            text.append("× ", style=f"{DANGER_RED} bold")
        else:
            text.append("› ", style=SUCCESS_GREEN)

        # Run name (truncated if too long)
        name = truncate_with_ellipsis(run.name, self.MAX_NAME_LENGTH)
        text.append(name, style=f"{TEXT_PRIMARY} bold")

        # Source file - show if available in attributes
        source_file = run.attributes.get("source_file")
        if source_file:
            # Show just the filename, not full path
            filename = source_file.rsplit("/", 1)[-1] if "/" in source_file else source_file
            text.append(f" ({filename})", style=f"{TEXT_MUTED} dim")

        # Time - muted
        time_str = run.start_time.strftime("%H:%M:%S")
        text.append(f" {time_str}", style=TEXT_MUTED)

        # Duration - amber accent
        if run.duration_ms:
            duration_str = format_duration(run.duration_ms)
            text.append(f" {duration_str}", style=ACCENT_AMBER)

        # Token summary - muted
        if run.total_tokens > 0:
            text.append(f" {run.total_tokens}t", style=TEXT_MUTED)

        # Cost - muted unless significant
        if run.total_cost_usd > 0:
            text.append(f" ${run.total_cost_usd:.4f}", style=TEXT_MUTED)

        return text

    def _create_step_label(self, step: Step) -> Text:
        """Create a rich text label for a step."""
        text = Text()

        # Type indicator - colored Unicode symbol
        icon = self.STEP_TYPE_ICONS.get(step.type.value, "?")
        if step.error:
            icon_color = DANGER_RED
        else:
            icon_color = self.STEP_TYPE_COLORS.get(step.type.value, TEXT_MUTED)
        text.append(f"{icon} ", style=icon_color)

        # Step type label - explicit text after icon (e.g., "llm:", "tool:")
        type_label = self.STEP_TYPE_LABELS.get(step.type.value, step.type.value)
        text.append(f"{type_label}: ", style=f"{icon_color} dim")

        # Step name (truncated if too long)
        name = truncate_with_ellipsis(step.name, self.MAX_NAME_LENGTH)
        if step.error:
            text.append(name, style=DANGER_RED)
        else:
            text.append(name, style=TEXT_PRIMARY)

        # Model info for LLM steps - info blue
        if step.model_name:
            text.append(f" {step.model_name}", style=f"{INFO_BLUE} dim")

        # Duration - amber
        if step.duration_ms:
            duration_str = format_duration(step.duration_ms)
            text.append(f" {duration_str}", style=f"{ACCENT_AMBER} dim")

        # Tokens - muted
        if step.input_tokens or step.output_tokens:
            tokens = (step.input_tokens or 0) + (step.output_tokens or 0)
            text.append(f" {tokens}t", style=TEXT_MUTED)

        # Error indicator - simple x
        if step.error:
            text.append(" ✕", style=f"{DANGER_RED} bold")

        return text

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
        """Get the currently selected step (O(1) cached lookup)."""
        data = self.get_selected_data()
        if data and data.get("type") == "step":
            step_id = data.get("id")
            if step_id:
                return self._step_cache.get(step_id)
        return None
