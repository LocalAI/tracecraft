"""
Agent manager screen for browsing and managing agents.

Provides a modal dialog for viewing agents, creating new ones,
editing existing ones, assigning to projects, and deleting.
NOIR SIGNAL theme styling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

# Import theme constants
from tracecraft.tui.theme import (
    ACCENT_AMBER,
    BACKGROUND,
    BORDER,
    DANGER_RED,
    INFO_BLUE,
    SUCCESS_GREEN,
    SURFACE,
    SURFACE_HIGHLIGHT,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

try:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.screen import ModalScreen
    from textual.widgets import Button, Footer, Input, Label, OptionList, Select, Static
    from textual.widgets.option_list import Option

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    ComposeResult = Any  # type: ignore[misc,assignment]
    ModalScreen = object  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from tracecraft.storage.sqlite import SQLiteTraceStore


class AgentManagerScreen(ModalScreen if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Modal screen for browsing and managing agents.

    Features:
    - List all agents with stats
    - Create new agents (n key)
    - Edit agents (e key)
    - Delete agents (d key)
    - Assign to project (p key)
    - Select agent to filter traces (Enter)

    Returns the selected agent dict when dismissed, or None if cancelled.
    """

    BINDINGS = (
        [
            Binding("escape", "cancel", "Back"),
            Binding("enter", "select", "Select"),
            Binding("n", "new_agent", "New"),
            Binding("e", "edit_agent", "Edit"),
            Binding("d", "delete_agent", "Delete"),
            Binding("p", "assign_project", "Assign Project"),
        ]
        if TEXTUAL_AVAILABLE
        else []
    )

    CSS = f"""
    /* NOIR SIGNAL - Agent Manager */
    AgentManagerScreen {{
        align: center middle;
        background: rgba(11, 14, 17, 0.8);
    }}

    #agent-container {{
        width: 85%;
        height: 75%;
        min-width: 70;
        max-width: 140;
        border: solid {ACCENT_AMBER};
        background: {SURFACE};
    }}

    #agent-header {{
        height: 3;
        background: {SURFACE_HIGHLIGHT};
        padding: 0 1;
        content-align: center middle;
        border-bottom: solid {BORDER};
    }}

    #agent-header Label {{
        text-style: bold;
        color: {ACCENT_AMBER};
    }}

    #agent-content {{
        height: 1fr;
    }}

    #agent-list-panel {{
        width: 55%;
        padding: 1;
        border-right: solid {BORDER};
    }}

    #agent-list {{
        height: 1fr;
        border: solid {BORDER};
        background: {BACKGROUND};
    }}

    #agent-list:focus {{
        border: solid {ACCENT_AMBER};
    }}

    #agent-stats-panel {{
        width: 45%;
        padding: 1;
        background: {SURFACE};
    }}

    #agent-stats {{
        height: 1fr;
        color: {TEXT_PRIMARY};
    }}

    .stats-title {{
        text-style: bold;
        margin-bottom: 1;
        color: {TEXT_MUTED};
    }}

    .stat-row {{
        margin-bottom: 0;
    }}

    .stat-value {{
        color: {ACCENT_AMBER};
    }}
    """

    def __init__(
        self,
        store: SQLiteTraceStore,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the agent manager screen.

        Args:
            store: SQLite store for agent operations.
        """
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__(*args, **kwargs)
        self._store = store
        self._agents: list[dict[str, Any]] = []
        self._selected_index: int = 0

    def compose(self) -> ComposeResult:
        """Compose the agent manager layout."""
        with Vertical(id="agent-container"):
            # Header
            with Horizontal(id="agent-header"):
                yield Label("AGENTS")

            # Content area
            with Horizontal(id="agent-content"):
                # Left panel: Agent list
                with Vertical(id="agent-list-panel"):
                    yield OptionList(id="agent-list")

                # Right panel: Stats
                with Vertical(id="agent-stats-panel"):
                    yield Label("DETAILS", classes="stats-title")
                    yield Static("Select an agent to view details.", id="agent-stats")

        yield Footer()

    def on_mount(self) -> None:
        """Load agents when mounted."""
        self._load_agents()

    def _load_agents(self) -> None:
        """Load agents from store and populate list."""
        self._agents = self._store.list_agents(include_legacy=True)

        option_list = self.query_one("#agent-list", OptionList)
        option_list.clear_options()

        # Add "All Agents" option first
        option_list.add_option(Option("All Agents", id="__all__"))

        # Add each agent
        for agent in self._agents:
            name = agent.get("name", "Unknown")
            trace_count = agent.get("trace_count", 0)
            # Add indicator for project assignment
            project_indicator = " [P]" if agent.get("project_id") else ""
            label = f"{name} ({trace_count} traces){project_indicator}"
            option_list.add_option(Option(label, id=agent["id"]))

        # Select first item
        if option_list.option_count > 0:
            option_list.highlighted = 0

    def on_option_list_option_highlighted(self, event: Any) -> None:
        """Update stats when an agent is highlighted."""
        self._update_stats(event.option.id)

    def _update_stats(self, agent_id: str) -> None:
        """Update the stats panel for the selected agent."""
        stats_widget = self.query_one("#agent-stats", Static)

        if agent_id == "__all__":
            # Show summary for all agents
            total_agents = len(self._agents)
            total_traces = sum(a.get("trace_count", 0) for a in self._agents)
            stats_widget.update(
                f"TOTAL AGENTS: {total_agents}\n"
                f"TOTAL TRACES: {total_traces}\n\n"
                f"Select agent to filter traces.\n\n"
                f"[n] New agent\n"
                f"[e] Edit agent\n"
                f"[d] Delete agent\n"
                f"[p] Assign to project"
            )
            return

        # Find the agent
        agent = next((a for a in self._agents if a["id"] == agent_id), None)
        if not agent:
            stats_widget.update("Agent not found.")
            return

        # Get stats for this agent
        try:
            stats = self._store.get_agent_stats_by_id(agent_id)
            project_name = "None"
            if agent.get("project_id"):
                project = self._store.get_project(agent["project_id"])
                project_name = project["name"] if project else "Unknown"

            stats_text = (
                f"NAME: {agent['name']}\n"
                f"TYPE: {agent.get('agent_type') or 'N/A'}\n"
                f"DESC: {agent.get('description') or '—'}\n\n"
                f"PROJECT: {project_name}\n\n"
                f"TRACES: {stats.get('trace_count', 0)}\n"
                f"TOKENS: {stats.get('total_tokens', 0):,}\n"
                f"COST: ${stats.get('total_cost_usd', 0):.4f}\n"
                f"ERRORS: {stats.get('error_count', 0)}\n\n"
                f"CREATED: {agent.get('created_at', 'N/A')[:10] if agent.get('created_at') else 'N/A'}"
            )
        except Exception:
            stats_text = (
                f"NAME: {agent['name']}\n"
                f"DESC: {agent.get('description') or '—'}\n\n"
                f"Stats unavailable."
            )

        stats_widget.update(stats_text)

    def action_cancel(self) -> None:
        """Cancel and close the manager."""
        self.dismiss(None)

    def action_select(self) -> None:
        """Select the highlighted agent and close."""
        option_list = self.query_one("#agent-list", OptionList)
        if option_list.highlighted is None:
            self.dismiss(None)
            return

        option = option_list.get_option_at_index(option_list.highlighted)
        agent_id = option.id

        if agent_id == "__all__":
            # Return special "All Agents" value to clear filter
            self.dismiss({"id": None, "name": "All Agents"})
        else:
            # Return the selected agent
            agent = next((a for a in self._agents if a["id"] == agent_id), None)
            self.dismiss(agent)

    def on_option_list_option_selected(self, event: Any) -> None:
        """Handle double-click or Enter on an option."""
        agent_id = event.option.id

        if agent_id == "__all__":
            self.dismiss({"id": None, "name": "All Agents"})
        else:
            agent = next((a for a in self._agents if a["id"] == agent_id), None)
            self.dismiss(agent)

    def action_new_agent(self) -> None:
        """Open the create agent dialog."""

        def on_agent_created(agent: dict[str, Any] | None) -> None:
            if agent:
                self._load_agents()
                self.notify(f"Agent created: {agent['name']}", title="CREATED")

        self.app.push_screen(AgentEditScreen(store=self._store), on_agent_created)

    def action_edit_agent(self) -> None:
        """Edit the selected agent."""
        option_list = self.query_one("#agent-list", OptionList)
        if option_list.highlighted is None:
            return

        option = option_list.get_option_at_index(option_list.highlighted)
        agent_id = option.id

        if agent_id == "__all__":
            self.notify("Cannot edit all agents.", title="INFO", severity="information")
            return

        agent = next((a for a in self._agents if a["id"] == agent_id), None)
        if not agent:
            return

        def on_agent_edited(result: dict[str, Any] | None) -> None:
            if result:
                self._load_agents()
                self.notify(f"Agent updated: {result['name']}", title="UPDATED")

        self.app.push_screen(AgentEditScreen(store=self._store, edit_agent=agent), on_agent_edited)

    def action_delete_agent(self) -> None:
        """Delete the selected agent."""
        from tracecraft.tui.screens.project_manager import ConfirmScreen

        option_list = self.query_one("#agent-list", OptionList)
        if option_list.highlighted is None:
            return

        option = option_list.get_option_at_index(option_list.highlighted)
        agent_id = option.id

        if agent_id == "__all__":
            self.notify("Cannot delete all agents.", title="WARNING", severity="warning")
            return

        agent = next((a for a in self._agents if a["id"] == agent_id), None)
        if not agent:
            return

        # Confirm deletion
        def confirm_delete(confirmed: bool) -> None:
            if confirmed:
                try:
                    self._store.delete_agent(agent_id)
                    self._load_agents()
                    self.notify(f"Agent deleted: {agent['name']}", title="DELETED")
                except Exception as e:
                    self.notify(f"Delete failed: {e}", title="ERROR", severity="error")

        # Show confirmation
        self.app.push_screen(
            ConfirmScreen(
                message=f"Delete agent '{agent['name']}'?\n\nTraces will be unlinked, not deleted.",
                title="CONFIRM DELETE",
            ),
            confirm_delete,
        )

    def action_assign_project(self) -> None:
        """Assign the selected agent to a project."""
        option_list = self.query_one("#agent-list", OptionList)
        if option_list.highlighted is None:
            return

        option = option_list.get_option_at_index(option_list.highlighted)
        agent_id = option.id

        if agent_id == "__all__":
            self.notify("Select a specific agent first.", title="INFO", severity="information")
            return

        agent = next((a for a in self._agents if a["id"] == agent_id), None)
        if not agent:
            return

        def on_project_selected(project: dict[str, Any] | None) -> None:
            if project is not None:
                project_id = project.get("id")
                try:
                    self._store.assign_agent_to_project(agent_id, project_id)
                    self._load_agents()
                    if project_id:
                        self.notify(
                            f"Agent '{agent['name']}' assigned to '{project['name']}'",
                            title="ASSIGNED",
                        )
                    else:
                        self.notify(
                            f"Agent '{agent['name']}' unassigned from project",
                            title="UNASSIGNED",
                        )
                except Exception as e:
                    self.notify(f"Assignment failed: {e}", title="ERROR", severity="error")

        # Show project selection
        from tracecraft.tui.screens.project_manager import ProjectManagerScreen

        self.app.push_screen(ProjectManagerScreen(store=self._store), on_project_selected)


class AgentEditScreen(ModalScreen if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """Modal screen for creating or editing an agent."""

    BINDINGS = (
        [
            Binding("escape", "cancel", "Cancel"),
            Binding("ctrl+s", "save", "Save"),
        ]
        if TEXTUAL_AVAILABLE
        else []
    )

    CSS = f"""
    /* NOIR SIGNAL - Agent Edit */
    AgentEditScreen {{
        align: center middle;
        background: rgba(11, 14, 17, 0.8);
    }}

    #edit-container {{
        width: 60%;
        height: auto;
        max-height: 70%;
        border: solid {ACCENT_AMBER};
        background: {SURFACE};
        padding: 1 2;
    }}

    #edit-title {{
        text-style: bold;
        margin-bottom: 1;
        color: {ACCENT_AMBER};
    }}

    .form-row {{
        width: 100%;
        height: auto;
        margin: 0 0 1 0;
    }}

    .form-label {{
        width: 12;
        color: {TEXT_MUTED};
    }}

    Input {{
        width: 1fr;
        background: {BACKGROUND};
        border: solid {BORDER};
    }}

    Input:focus {{
        border: solid {ACCENT_AMBER};
    }}

    Select {{
        width: 1fr;
        background: {BACKGROUND};
    }}

    #button-row {{
        margin-top: 1;
        width: 100%;
        align: center middle;
    }}

    #button-row Button {{
        margin: 0 1;
    }}

    .error-msg {{
        color: {DANGER_RED};
        text-align: center;
    }}
    """

    def __init__(
        self,
        store: SQLiteTraceStore,
        edit_agent: dict[str, Any] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the edit screen.

        Args:
            store: SQLite store for agent operations.
            edit_agent: Existing agent to edit (None for new).
        """
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI")
        super().__init__(*args, **kwargs)
        self._store = store
        self._edit_agent = edit_agent

    def compose(self) -> ComposeResult:
        """Compose the edit form."""
        title = "Edit Agent" if self._edit_agent else "Create Agent"

        with Vertical(id="edit-container"):
            yield Label(title.upper(), id="edit-title")

            # Name field
            with Horizontal(classes="form-row"):
                yield Label("Name:", classes="form-label")
                yield Input(
                    value=self._edit_agent.get("name", "") if self._edit_agent else "",
                    placeholder="e.g., my-chatbot",
                    id="name-input",
                )

            # Description field
            with Horizontal(classes="form-row"):
                yield Label("Description:", classes="form-label")
                yield Input(
                    value=self._edit_agent.get("description", "") if self._edit_agent else "",
                    placeholder="Optional description",
                    id="desc-input",
                )

            # Agent type field
            with Horizontal(classes="form-row"):
                yield Label("Type:", classes="form-label")
                yield Input(
                    value=self._edit_agent.get("agent_type", "") if self._edit_agent else "",
                    placeholder="e.g., langchain, langgraph, custom",
                    id="type-input",
                )

            # Error message
            yield Static("", id="error-msg", classes="error-msg")

            # Buttons
            with Horizontal(id="button-row"):
                yield Button("Cancel", variant="default", id="cancel-btn")
                yield Button(
                    "Save" if self._edit_agent else "Create", variant="primary", id="save-btn"
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-btn":
            self.dismiss(None)
        elif event.button.id == "save-btn":
            self._save_agent()

    def action_cancel(self) -> None:
        """Cancel and close."""
        self.dismiss(None)

    def action_save(self) -> None:
        """Save the agent."""
        self._save_agent()

    def _save_agent(self) -> None:
        """Save or create the agent."""
        name = self.query_one("#name-input", Input).value.strip()
        description = self.query_one("#desc-input", Input).value.strip() or None
        agent_type = self.query_one("#type-input", Input).value.strip() or None

        error_widget = self.query_one("#error-msg", Static)

        if not name:
            error_widget.update("Name is required")
            return

        try:
            if self._edit_agent:
                # Update existing
                self._store.update_agent(
                    self._edit_agent["id"],
                    name=name,
                    description=description,
                    agent_type=agent_type,
                )
                result = {"id": self._edit_agent["id"], "name": name}
            else:
                # Create new
                agent_id = self._store.create_agent(
                    name=name,
                    description=description,
                    agent_type=agent_type,
                )
                result = {"id": agent_id, "name": name}

            self.dismiss(result)

        except Exception as e:
            error_widget.update(f"Error: {e}")
