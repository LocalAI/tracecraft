"""
Setup wizard screen for first-time Trace Craft TUI users.

Provides a welcome screen with options to initialize Trace Craft
with a global or local database, or open an existing file.
NOIR SIGNAL theme styling.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Import theme constants
from tracecraft.tui.theme import (
    ACCENT_AMBER,
    BACKGROUND,
    BORDER,
    DANGER_RED,
    SUCCESS_GREEN,
    SURFACE,
    SURFACE_HIGHLIGHT,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

try:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Center, Vertical
    from textual.screen import Screen
    from textual.widgets import Button, Footer, Label, Static

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    ComposeResult = Any  # type: ignore[misc,assignment]
    Screen = object  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    pass


class SetupChoice(str, Enum):
    """User's choice from the setup wizard."""

    GLOBAL = "global"
    LOCAL = "local"
    OPEN_FILE = "open_file"
    DEMO = "demo"
    CANCEL = "cancel"


@dataclass
class SetupResult:
    """Result from the setup wizard."""

    choice: SetupChoice
    source: str | None = None  # The source string to use
    error: str | None = None


class SetupWizardScreen(Screen if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Setup wizard screen for first-time users.

    Displays options for initializing Trace Craft:
    - Global database (~/.tracecraft/)
    - Local database (.tracecraft/ in current directory)
    - Open existing file
    - Demo mode with sample data
    """

    BINDINGS = (
        [
            Binding("g", "choose_global", "Global"),
            Binding("l", "choose_local", "Local"),
            Binding("o", "choose_open", "Open File"),
            Binding("d", "choose_demo", "Demo"),
            Binding("escape", "cancel", "Cancel"),
            Binding("q", "cancel", "Quit"),
        ]
        if TEXTUAL_AVAILABLE
        else []
    )

    CSS = f"""
    /* NOIR SIGNAL - Setup Wizard */
    SetupWizardScreen {{
        align: center middle;
        background: {BACKGROUND};
    }}

    #wizard-container {{
        width: 70;
        min-width: 50;
        max-width: 90;
        height: auto;
        max-height: 90%;
        border: solid {ACCENT_AMBER};
        background: {SURFACE};
        padding: 1 2;
    }}

    #wizard-header {{
        text-align: center;
        padding: 1;
        margin-bottom: 1;
    }}

    #wizard-title {{
        text-style: bold;
        color: {ACCENT_AMBER};
    }}

    #wizard-subtitle {{
        color: {TEXT_MUTED};
        margin-top: 1;
    }}

    #wizard-message {{
        text-align: center;
        margin-bottom: 1;
        color: {TEXT_PRIMARY};
    }}

    #wizard-options {{
        margin-top: 1;
    }}

    .option-button {{
        width: 100%;
        margin: 1 0;
        background: {SURFACE_HIGHLIGHT};
        border: solid {BORDER};
    }}

    .option-button:hover {{
        background: #252B33;
        border: solid {ACCENT_AMBER};
        color: {ACCENT_AMBER};
    }}

    .option-button:focus {{
        border: solid {ACCENT_AMBER};
        background: {SURFACE_HIGHLIGHT};
    }}

    #option-global {{
        background: {ACCENT_AMBER};
        color: {BACKGROUND};
    }}

    #option-global:hover {{
        background: #D4A836;
    }}

    #option-local {{
        background: {SURFACE_HIGHLIGHT};
    }}

    .option-description {{
        color: {TEXT_MUTED};
        text-align: center;
        margin-bottom: 1;
        padding: 0 2;
    }}

    #wizard-footer {{
        margin-top: 2;
        text-align: center;
        color: {TEXT_MUTED};
    }}

    #setup-status {{
        text-align: center;
        margin-top: 1;
        color: {SUCCESS_GREEN};
    }}

    #setup-error {{
        text-align: center;
        margin-top: 1;
        color: {DANGER_RED};
    }}
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the setup wizard screen."""
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__(*args, **kwargs)
        self._result: SetupResult | None = None

    def compose(self) -> ComposeResult:
        """Compose the setup wizard layout."""
        with Vertical(id="wizard-container"):
            # Header
            with Vertical(id="wizard-header"):
                yield Label("TRACE CRAFT", id="wizard-title")
                yield Static("Trace Observatory", id="wizard-subtitle")

            # Message
            yield Static(
                "No database found. Select an option to begin.",
                id="wizard-message",
            )

            # Options
            with Vertical(id="wizard-options"):
                # Global option (recommended)
                yield Button(
                    "[G] GLOBAL DATABASE (Recommended)",
                    id="option-global",
                    classes="option-button",
                )
                yield Static(
                    "Store in ~/.tracecraft/ for system-wide access.",
                    classes="option-description",
                )

                # Local option
                yield Button(
                    "[L] LOCAL DATABASE",
                    id="option-local",
                    classes="option-button",
                )
                yield Static(
                    "Store in .tracecraft/ for this project only.",
                    classes="option-description",
                )

                # Open file option
                yield Button(
                    "[O] OPEN FILE",
                    id="option-open",
                    classes="option-button",
                )
                yield Static(
                    "Browse for an existing database or JSONL file.",
                    classes="option-description",
                )

                # Demo option
                yield Button(
                    "[D] DEMO MODE",
                    id="option-demo",
                    classes="option-button",
                )
                yield Static(
                    "Explore with sample trace data.",
                    classes="option-description",
                )

            # Status area
            yield Static("", id="setup-status")
            yield Static("", id="setup-error")

            # Footer hint
            yield Static(
                "Press key or select option.",
                id="wizard-footer",
            )

        yield Footer()

    def on_button_pressed(self, event: Any) -> None:
        """Handle button presses."""
        button_id = event.button.id
        if button_id == "option-global":
            self._do_global_setup()
        elif button_id == "option-local":
            self._do_local_setup()
        elif button_id == "option-open":
            self._do_open_file()
        elif button_id == "option-demo":
            self._do_demo()

    def action_choose_global(self) -> None:
        """Handle global database choice."""
        self._do_global_setup()

    def action_choose_local(self) -> None:
        """Handle local database choice."""
        self._do_local_setup()

    def action_choose_open(self) -> None:
        """Handle open file choice."""
        self._do_open_file()

    def action_choose_demo(self) -> None:
        """Handle demo mode choice."""
        self._do_demo()

    def action_cancel(self) -> None:
        """Cancel and exit."""
        self._result = SetupResult(choice=SetupChoice.CANCEL)
        self.dismiss(self._result)

    def _do_global_setup(self) -> None:
        """Initialize global database."""
        self._update_status("Initializing global database.")
        self._clear_error()

        try:
            from tracecraft.core.init import InitLocation, get_source_for_location, initialize

            result = initialize(InitLocation.GLOBAL)

            if result.success:
                source = get_source_for_location(InitLocation.GLOBAL)
                self._result = SetupResult(choice=SetupChoice.GLOBAL, source=source)
                self.dismiss(self._result)
            else:
                self._show_error(f"Failed: {result.error}")

        except Exception as e:
            self._show_error(f"Error: {e}")

    def _do_local_setup(self) -> None:
        """Initialize local database."""
        self._update_status("Initializing local database.")
        self._clear_error()

        try:
            from tracecraft.core.init import InitLocation, get_source_for_location, initialize

            result = initialize(InitLocation.LOCAL)

            if result.success:
                source = get_source_for_location(InitLocation.LOCAL)
                self._result = SetupResult(choice=SetupChoice.LOCAL, source=source)
                self.dismiss(self._result)
            else:
                self._show_error(f"Failed: {result.error}")

        except Exception as e:
            self._show_error(f"Error: {e}")

    def _do_open_file(self) -> None:
        """Open file browser (placeholder - will use simple input for now)."""
        # For now, just return open_file choice and let the app handle it
        # In future, could integrate with a file picker
        self._result = SetupResult(choice=SetupChoice.OPEN_FILE)
        self.dismiss(self._result)

    def _do_demo(self) -> None:
        """Start demo mode with sample data."""
        self._update_status("Loading demo data.")

        try:
            # Create in-memory database with sample data
            source = self._create_demo_database()
            self._result = SetupResult(choice=SetupChoice.DEMO, source=source)
            self.dismiss(self._result)

        except Exception as e:
            self._show_error(f"Error creating demo: {e}")

    def _create_demo_database(self) -> str:
        """Create a temporary database with sample trace data, agents, and evals."""
        import tempfile
        from datetime import UTC, datetime
        from uuid import uuid4

        from tracecraft.core.init import _create_example_data
        from tracecraft.core.models import AgentRun, Step, StepType
        from tracecraft.storage.sqlite import SQLiteTraceStore

        # Create temp database
        temp_dir = tempfile.mkdtemp(prefix="tracecraft_demo_")
        db_path = Path(temp_dir) / "demo.db"

        store = SQLiteTraceStore(db_path)

        # Create a demo project
        project_id = store.create_project(
            name="Demo Project",
            description="Sample project with demo traces",
        )

        # Create sample traces
        sample_traces = self._generate_sample_traces()

        for trace in sample_traces:
            store.save(trace)
            # Assign to demo project
            store.assign_trace_to_project(str(trace.id), project_id)

        store.close()

        # Add example data with sample traces
        # This creates "Example Project" with sample traces
        _create_example_data(db_path)

        return f"sqlite://{db_path}"

    def _generate_sample_traces(self) -> list:
        """Generate comprehensive sample trace data for demo mode."""
        from datetime import UTC, datetime, timedelta
        from uuid import uuid4

        from tracecraft.core.models import AgentRun, Step, StepType

        traces = []
        base_time = datetime.now(UTC)

        # =====================================================================
        # TRACE 1: Simple GPT-4o Chat
        # =====================================================================
        t1_id = uuid4()
        traces.append(
            AgentRun(
                id=t1_id,
                name="chat_completion",
                description="Simple question-answer with GPT-4o",
                start_time=base_time - timedelta(hours=6),
                duration_ms=1523.5,
                total_tokens=847,
                total_cost_usd=0.0127,
                tags=["chat", "openai"],
                steps=[
                    Step(
                        trace_id=t1_id,
                        type=StepType.LLM,
                        name="gpt-4o",
                        start_time=base_time - timedelta(hours=6),
                        duration_ms=1523.5,
                        model_name="gpt-4o",
                        model_provider="openai",
                        input_tokens=312,
                        output_tokens=535,
                        cost_usd=0.0127,
                        inputs={
                            "messages": [
                                {"role": "system", "content": "You are a helpful assistant."},
                                {
                                    "role": "user",
                                    "content": "Explain quantum computing in simple terms.",
                                },
                            ]
                        },
                        outputs={
                            "content": "Quantum computing harnesses quantum mechanics to process information differently than classical computers. While traditional computers use bits (0 or 1), quantum computers use qubits that can exist in multiple states simultaneously through superposition. This allows them to explore many solutions at once, making them potentially much faster for certain types of problems like cryptography and drug discovery."
                        },
                    )
                ],
            )
        )

        # =====================================================================
        # TRACE 2: Claude Sonnet with System Prompt
        # =====================================================================
        t2_id = uuid4()
        traces.append(
            AgentRun(
                id=t2_id,
                name="code_review",
                description="Code review with Claude 3.5 Sonnet",
                start_time=base_time - timedelta(hours=5, minutes=30),
                duration_ms=4821.3,
                total_tokens=2456,
                total_cost_usd=0.0221,
                tags=["code", "anthropic", "review"],
                steps=[
                    Step(
                        trace_id=t2_id,
                        type=StepType.LLM,
                        name="claude-3-5-sonnet",
                        start_time=base_time - timedelta(hours=5, minutes=30),
                        duration_ms=4821.3,
                        model_name="claude-3-5-sonnet-20241022",
                        model_provider="anthropic",
                        input_tokens=1856,
                        output_tokens=600,
                        cost_usd=0.0221,
                        inputs={
                            "system": "You are an expert code reviewer. Analyze code for bugs, security issues, and best practices.",
                            "messages": [
                                {
                                    "role": "user",
                                    "content": "Review this Python function:\n\ndef process_user(data):\n    query = f\"SELECT * FROM users WHERE id = {data['id']}\"\n    return db.execute(query)",
                                }
                            ],
                        },
                        outputs={
                            "content": "CRITICAL: SQL Injection vulnerability detected. Never use f-strings for SQL queries. Use parameterized queries: `db.execute('SELECT * FROM users WHERE id = ?', (data['id'],))`"
                        },
                    )
                ],
            )
        )

        # =====================================================================
        # TRACE 3: RAG Pipeline with Vector Search
        # =====================================================================
        t3_id = uuid4()
        traces.append(
            AgentRun(
                id=t3_id,
                name="rag_financial_query",
                description="RAG query for financial data",
                start_time=base_time - timedelta(hours=5),
                duration_ms=3421.8,
                total_tokens=3156,
                total_cost_usd=0.0315,
                tags=["rag", "finance", "retrieval"],
                steps=[
                    Step(
                        trace_id=t3_id,
                        type=StepType.RETRIEVAL,
                        name="vector_search",
                        start_time=base_time - timedelta(hours=5),
                        duration_ms=245.3,
                        inputs={"query": "Q3 2024 revenue breakdown by region", "top_k": 5},
                        outputs={
                            "num_results": 5,
                            "chunks": [
                                "North America revenue: $45.2M (+12% YoY)",
                                "EMEA revenue: $28.7M (+8% YoY)",
                                "APAC revenue: $18.3M (+22% YoY)",
                            ],
                        },
                        attributes={"vector_db": "pinecone", "similarity": "cosine"},
                    ),
                    Step(
                        trace_id=t3_id,
                        type=StepType.LLM,
                        name="synthesis",
                        start_time=base_time - timedelta(hours=5) + timedelta(milliseconds=250),
                        duration_ms=3176.5,
                        model_name="claude-3-5-sonnet-20241022",
                        model_provider="anthropic",
                        input_tokens=2456,
                        output_tokens=700,
                        cost_usd=0.0315,
                        inputs={
                            "system": "Synthesize financial data into a clear summary.",
                            "context": "[Retrieved chunks about Q3 revenue]",
                        },
                        outputs={
                            "content": "Q3 2024 Total Revenue: $92.2M (+13.3% YoY). APAC showed strongest growth at 22%, driven by expansion in Japan and Singapore."
                        },
                    ),
                ],
            )
        )

        # =====================================================================
        # TRACE 4: Research Agent with Multiple Tools
        # =====================================================================
        t4_id = uuid4()
        traces.append(
            AgentRun(
                id=t4_id,
                name="research_agent",
                description="AI research agent with web search and analysis",
                agent_name="ResearchAgent",
                agent_id="research-v2",
                start_time=base_time - timedelta(hours=4),
                duration_ms=15734.2,
                total_tokens=8523,
                total_cost_usd=0.1278,
                tags=["agent", "research", "tools"],
                steps=[
                    Step(
                        trace_id=t4_id,
                        type=StepType.AGENT,
                        name="research_coordinator",
                        start_time=base_time - timedelta(hours=4),
                        duration_ms=15734.2,
                        children=[
                            Step(
                                trace_id=t4_id,
                                type=StepType.LLM,
                                name="planning",
                                start_time=base_time - timedelta(hours=4),
                                duration_ms=1200.0,
                                model_name="gpt-4o",
                                model_provider="openai",
                                input_tokens=500,
                                output_tokens=350,
                                cost_usd=0.0125,
                                inputs={"task": "Research latest developments in AI safety"},
                                outputs={
                                    "plan": "1. Search recent papers 2. Analyze trends 3. Synthesize findings"
                                },
                            ),
                            Step(
                                trace_id=t4_id,
                                type=StepType.TOOL,
                                name="web_search",
                                start_time=base_time - timedelta(hours=4) + timedelta(seconds=2),
                                duration_ms=2500.0,
                                inputs={"query": "AI safety research 2024 papers"},
                                outputs={
                                    "results": 10,
                                    "sources": ["arxiv", "openai", "anthropic"],
                                },
                            ),
                            Step(
                                trace_id=t4_id,
                                type=StepType.TOOL,
                                name="web_search",
                                start_time=base_time - timedelta(hours=4) + timedelta(seconds=5),
                                duration_ms=1800.0,
                                inputs={"query": "constitutional AI RLHF alignment"},
                                outputs={"results": 8},
                            ),
                            Step(
                                trace_id=t4_id,
                                type=StepType.TOOL,
                                name="fetch_url",
                                start_time=base_time - timedelta(hours=4) + timedelta(seconds=7),
                                duration_ms=3200.0,
                                inputs={"url": "https://arxiv.org/abs/2024.12345"},
                                outputs={"title": "Scalable Oversight Methods", "abstract": "..."},
                            ),
                            Step(
                                trace_id=t4_id,
                                type=StepType.LLM,
                                name="analysis",
                                start_time=base_time - timedelta(hours=4) + timedelta(seconds=11),
                                duration_ms=3800.0,
                                model_name="gpt-4o",
                                model_provider="openai",
                                input_tokens=4500,
                                output_tokens=1200,
                                cost_usd=0.0678,
                            ),
                            Step(
                                trace_id=t4_id,
                                type=StepType.LLM,
                                name="synthesis",
                                start_time=base_time - timedelta(hours=4) + timedelta(seconds=15),
                                duration_ms=3234.2,
                                model_name="gpt-4o",
                                model_provider="openai",
                                input_tokens=1523,
                                output_tokens=450,
                                cost_usd=0.0475,
                                outputs={
                                    "summary": "Key AI safety trends: 1) Constitutional AI advances 2) Scalable oversight research 3) Interpretability breakthroughs"
                                },
                            ),
                        ],
                    )
                ],
            )
        )

        # =====================================================================
        # TRACE 5: Code Generation Agent with Execution
        # =====================================================================
        t5_id = uuid4()
        traces.append(
            AgentRun(
                id=t5_id,
                name="code_gen_agent",
                description="Code generation with execution and debugging",
                agent_name="CodeAgent",
                start_time=base_time - timedelta(hours=3, minutes=30),
                duration_ms=22456.7,
                total_tokens=12934,
                total_cost_usd=0.1934,
                tags=["agent", "code", "execution"],
                steps=[
                    Step(
                        trace_id=t5_id,
                        type=StepType.AGENT,
                        name="code_assistant",
                        start_time=base_time - timedelta(hours=3, minutes=30),
                        duration_ms=22456.7,
                        children=[
                            Step(
                                trace_id=t5_id,
                                type=StepType.LLM,
                                name="understand_task",
                                start_time=base_time - timedelta(hours=3, minutes=30),
                                duration_ms=1500.0,
                                model_name="claude-3-5-sonnet-20241022",
                                model_provider="anthropic",
                                input_tokens=800,
                                output_tokens=400,
                                cost_usd=0.0108,
                                inputs={
                                    "task": "Write a function to merge two sorted lists efficiently"
                                },
                            ),
                            Step(
                                trace_id=t5_id,
                                type=StepType.LLM,
                                name="generate_code",
                                start_time=base_time
                                - timedelta(hours=3, minutes=30)
                                + timedelta(seconds=2),
                                duration_ms=3200.0,
                                model_name="claude-3-5-sonnet-20241022",
                                model_provider="anthropic",
                                input_tokens=1200,
                                output_tokens=600,
                                cost_usd=0.0162,
                                outputs={
                                    "code": "def merge_sorted(list1, list2):\n    result = []\n    i = j = 0\n    while i < len(list1) and j < len(list2):\n        if list1[i] <= list2[j]:\n            result.append(list1[i])\n            i += 1\n        else:\n            result.append(list2[j])\n            j += 1\n    result.extend(list1[i:])\n    result.extend(list2[j:])\n    return result"
                                },
                            ),
                            Step(
                                trace_id=t5_id,
                                type=StepType.TOOL,
                                name="code_execute",
                                start_time=base_time
                                - timedelta(hours=3, minutes=30)
                                + timedelta(seconds=6),
                                duration_ms=856.2,
                                inputs={
                                    "code": "merge_sorted([1,3,5], [2,4,6])",
                                    "language": "python",
                                },
                                outputs={"result": "[1, 2, 3, 4, 5, 6]", "exit_code": 0},
                            ),
                            Step(
                                trace_id=t5_id,
                                type=StepType.LLM,
                                name="generate_tests",
                                start_time=base_time
                                - timedelta(hours=3, minutes=30)
                                + timedelta(seconds=8),
                                duration_ms=2800.0,
                                model_name="claude-3-5-sonnet-20241022",
                                model_provider="anthropic",
                                input_tokens=1500,
                                output_tokens=800,
                                cost_usd=0.0207,
                            ),
                            Step(
                                trace_id=t5_id,
                                type=StepType.TOOL,
                                name="code_execute",
                                start_time=base_time
                                - timedelta(hours=3, minutes=30)
                                + timedelta(seconds=12),
                                duration_ms=1234.5,
                                inputs={"code": "pytest test_merge.py", "language": "shell"},
                                outputs={"result": "5 passed", "exit_code": 0},
                            ),
                            Step(
                                trace_id=t5_id,
                                type=StepType.EVALUATION,
                                name="code_quality",
                                start_time=base_time
                                - timedelta(hours=3, minutes=30)
                                + timedelta(seconds=14),
                                duration_ms=1866.0,
                                model_name="gpt-4o",
                                model_provider="openai",
                                input_tokens=2000,
                                output_tokens=300,
                                cost_usd=0.0245,
                                outputs={
                                    "quality_score": 0.95,
                                    "time_complexity": "O(n+m)",
                                    "space_complexity": "O(n+m)",
                                },
                            ),
                        ],
                    )
                ],
            )
        )

        # =====================================================================
        # TRACE 6: Customer Support Agent with Memory
        # =====================================================================
        t6_id = uuid4()
        traces.append(
            AgentRun(
                id=t6_id,
                name="support_agent",
                description="Customer support with memory and tools",
                agent_name="SupportBot",
                session_id="session_abc123",
                user_id="user_42",
                start_time=base_time - timedelta(hours=3),
                duration_ms=9823.4,
                total_tokens=5678,
                total_cost_usd=0.0851,
                tags=["agent", "support", "memory"],
                steps=[
                    Step(
                        trace_id=t6_id,
                        type=StepType.AGENT,
                        name="support_coordinator",
                        start_time=base_time - timedelta(hours=3),
                        duration_ms=9823.4,
                        children=[
                            Step(
                                trace_id=t6_id,
                                type=StepType.MEMORY,
                                name="load_context",
                                start_time=base_time - timedelta(hours=3),
                                duration_ms=123.4,
                                inputs={"user_id": "user_42", "session_id": "session_abc123"},
                                outputs={
                                    "previous_tickets": 3,
                                    "tier": "premium",
                                    "last_interaction": "2024-01-10",
                                },
                            ),
                            Step(
                                trace_id=t6_id,
                                type=StepType.LLM,
                                name="understand_intent",
                                start_time=base_time
                                - timedelta(hours=3)
                                + timedelta(milliseconds=150),
                                duration_ms=1200.0,
                                model_name="gpt-4o-mini",
                                model_provider="openai",
                                input_tokens=600,
                                output_tokens=150,
                                cost_usd=0.0011,
                                inputs={
                                    "message": "My order hasn't arrived yet, it's been 2 weeks!"
                                },
                                outputs={
                                    "intent": "order_status",
                                    "sentiment": "frustrated",
                                    "priority": "high",
                                },
                            ),
                            Step(
                                trace_id=t6_id,
                                type=StepType.TOOL,
                                name="db_query",
                                start_time=base_time - timedelta(hours=3) + timedelta(seconds=2),
                                duration_ms=234.5,
                                inputs={
                                    "query": "SELECT * FROM orders WHERE user_id = 'user_42' AND status != 'delivered'"
                                },
                                outputs={
                                    "order_id": "ORD-78923",
                                    "status": "in_transit",
                                    "carrier": "FedEx",
                                    "tracking": "1234567890",
                                },
                            ),
                            Step(
                                trace_id=t6_id,
                                type=StepType.TOOL,
                                name="carrier_api",
                                start_time=base_time - timedelta(hours=3) + timedelta(seconds=3),
                                duration_ms=1500.0,
                                inputs={"carrier": "FedEx", "tracking": "1234567890"},
                                outputs={
                                    "status": "Out for Delivery",
                                    "eta": "Today by 5pm",
                                    "location": "Local Distribution Center",
                                },
                            ),
                            Step(
                                trace_id=t6_id,
                                type=StepType.LLM,
                                name="compose_response",
                                start_time=base_time - timedelta(hours=3) + timedelta(seconds=5),
                                duration_ms=2800.0,
                                model_name="gpt-4o",
                                model_provider="openai",
                                input_tokens=1800,
                                output_tokens=400,
                                cost_usd=0.026,
                                outputs={
                                    "response": "Good news! Your order ORD-78923 is out for delivery and should arrive today by 5pm. I apologize for the delay - I've added a 10% credit to your account."
                                },
                            ),
                            Step(
                                trace_id=t6_id,
                                type=StepType.MEMORY,
                                name="save_interaction",
                                start_time=base_time - timedelta(hours=3) + timedelta(seconds=8),
                                duration_ms=89.5,
                                inputs={
                                    "interaction_type": "order_inquiry",
                                    "resolution": "provided_tracking",
                                    "compensation": "10% credit",
                                },
                            ),
                            Step(
                                trace_id=t6_id,
                                type=StepType.GUARDRAIL,
                                name="tone_check",
                                start_time=base_time - timedelta(hours=3) + timedelta(seconds=9),
                                duration_ms=156.0,
                                outputs={
                                    "passed": True,
                                    "tone_score": 0.92,
                                    "empathy_detected": True,
                                },
                            ),
                        ],
                    )
                ],
            )
        )

        # =====================================================================
        # TRACE 7: Multi-Agent Orchestration
        # =====================================================================
        t7_id = uuid4()
        traces.append(
            AgentRun(
                id=t7_id,
                name="multi_agent_report",
                description="Multi-agent system for report generation",
                agent_name="OrchestratorAgent",
                start_time=base_time - timedelta(hours=2, minutes=30),
                duration_ms=45678.9,
                total_tokens=28456,
                total_cost_usd=0.4267,
                tags=["multi-agent", "orchestration", "report"],
                steps=[
                    Step(
                        trace_id=t7_id,
                        type=StepType.AGENT,
                        name="orchestrator",
                        start_time=base_time - timedelta(hours=2, minutes=30),
                        duration_ms=45678.9,
                        children=[
                            Step(
                                trace_id=t7_id,
                                type=StepType.LLM,
                                name="task_decomposition",
                                start_time=base_time - timedelta(hours=2, minutes=30),
                                duration_ms=2500.0,
                                model_name="gpt-4o",
                                model_provider="openai",
                                input_tokens=1200,
                                output_tokens=800,
                                cost_usd=0.032,
                                inputs={"task": "Generate Q4 market analysis report"},
                                outputs={
                                    "subtasks": [
                                        "data_collection",
                                        "competitor_analysis",
                                        "trend_analysis",
                                        "report_writing",
                                    ]
                                },
                            ),
                            Step(
                                trace_id=t7_id,
                                type=StepType.AGENT,
                                name="data_collector",
                                start_time=base_time
                                - timedelta(hours=2, minutes=30)
                                + timedelta(seconds=3),
                                duration_ms=12000.0,
                                children=[
                                    Step(
                                        trace_id=t7_id,
                                        type=StepType.TOOL,
                                        name="api_call",
                                        start_time=base_time
                                        - timedelta(hours=2, minutes=30)
                                        + timedelta(seconds=3),
                                        duration_ms=3500.0,
                                        inputs={
                                            "endpoint": "market_data_api",
                                            "params": {"quarter": "Q4", "year": 2024},
                                        },
                                        outputs={"data_points": 1250},
                                    ),
                                    Step(
                                        trace_id=t7_id,
                                        type=StepType.RETRIEVAL,
                                        name="internal_docs",
                                        start_time=base_time
                                        - timedelta(hours=2, minutes=30)
                                        + timedelta(seconds=7),
                                        duration_ms=2500.0,
                                        inputs={"query": "Q4 sales projections"},
                                        outputs={"documents": 12},
                                    ),
                                    Step(
                                        trace_id=t7_id,
                                        type=StepType.LLM,
                                        name="data_summarization",
                                        start_time=base_time
                                        - timedelta(hours=2, minutes=30)
                                        + timedelta(seconds=10),
                                        duration_ms=6000.0,
                                        model_name="gpt-4o-mini",
                                        model_provider="openai",
                                        input_tokens=8000,
                                        output_tokens=1500,
                                        cost_usd=0.0143,
                                    ),
                                ],
                            ),
                            Step(
                                trace_id=t7_id,
                                type=StepType.AGENT,
                                name="competitor_analyst",
                                start_time=base_time
                                - timedelta(hours=2, minutes=30)
                                + timedelta(seconds=3),
                                duration_ms=15000.0,
                                children=[
                                    Step(
                                        trace_id=t7_id,
                                        type=StepType.TOOL,
                                        name="web_search",
                                        start_time=base_time
                                        - timedelta(hours=2, minutes=30)
                                        + timedelta(seconds=3),
                                        duration_ms=4000.0,
                                        inputs={"query": "competitor earnings Q4 2024"},
                                        outputs={"results": 25},
                                    ),
                                    Step(
                                        trace_id=t7_id,
                                        type=StepType.LLM,
                                        name="competitor_analysis",
                                        start_time=base_time
                                        - timedelta(hours=2, minutes=30)
                                        + timedelta(seconds=8),
                                        duration_ms=11000.0,
                                        model_name="claude-3-5-sonnet-20241022",
                                        model_provider="anthropic",
                                        input_tokens=6000,
                                        output_tokens=2000,
                                        cost_usd=0.072,
                                    ),
                                ],
                            ),
                            Step(
                                trace_id=t7_id,
                                type=StepType.LLM,
                                name="report_synthesis",
                                start_time=base_time
                                - timedelta(hours=2, minutes=30)
                                + timedelta(seconds=20),
                                duration_ms=8000.0,
                                model_name="claude-3-5-sonnet-20241022",
                                model_provider="anthropic",
                                input_tokens=8000,
                                output_tokens=4000,
                                cost_usd=0.108,
                            ),
                            Step(
                                trace_id=t7_id,
                                type=StepType.EVALUATION,
                                name="quality_review",
                                start_time=base_time
                                - timedelta(hours=2, minutes=30)
                                + timedelta(seconds=30),
                                duration_ms=3500.0,
                                model_name="gpt-4o",
                                model_provider="openai",
                                input_tokens=4000,
                                output_tokens=500,
                                cost_usd=0.0475,
                                outputs={
                                    "quality_score": 0.94,
                                    "completeness": 0.96,
                                    "accuracy": 0.92,
                                },
                            ),
                        ],
                    )
                ],
            )
        )

        # =====================================================================
        # TRACE 8: Rate Limit Error
        # =====================================================================
        t8_id = uuid4()
        traces.append(
            AgentRun(
                id=t8_id,
                name="failed_generation",
                description="Request failed due to rate limit",
                start_time=base_time - timedelta(hours=2),
                duration_ms=523.1,
                total_tokens=150,
                error="RateLimitError: Rate limit exceeded",
                error_count=1,
                tags=["error", "rate-limit"],
                steps=[
                    Step(
                        trace_id=t8_id,
                        type=StepType.LLM,
                        name="gpt-4o",
                        start_time=base_time - timedelta(hours=2),
                        duration_ms=523.1,
                        model_name="gpt-4o",
                        model_provider="openai",
                        input_tokens=150,
                        output_tokens=0,
                        error="RateLimitError: Rate limit exceeded. Please retry after 60 seconds.",
                        error_type="RateLimitError",
                        inputs={"messages": [{"role": "user", "content": "Generate a story"}]},
                    )
                ],
            )
        )

        # =====================================================================
        # TRACE 9: Validation Error with Retry
        # =====================================================================
        t9_id = uuid4()
        traces.append(
            AgentRun(
                id=t9_id,
                name="structured_output_retry",
                description="Structured output with validation retry",
                start_time=base_time - timedelta(hours=1, minutes=45),
                duration_ms=6234.5,
                total_tokens=3200,
                total_cost_usd=0.048,
                error_count=1,
                tags=["structured", "validation", "retry"],
                steps=[
                    Step(
                        trace_id=t9_id,
                        type=StepType.LLM,
                        name="generate_json_attempt_1",
                        start_time=base_time - timedelta(hours=1, minutes=45),
                        duration_ms=2100.0,
                        model_name="gpt-4o-mini",
                        model_provider="openai",
                        input_tokens=500,
                        output_tokens=300,
                        cost_usd=0.0012,
                        error="ValidationError: Missing required field 'email'",
                        error_type="ValidationError",
                        outputs={"raw": '{"name": "John", "age": 30}'},
                    ),
                    Step(
                        trace_id=t9_id,
                        type=StepType.GUARDRAIL,
                        name="schema_validation",
                        start_time=base_time
                        - timedelta(hours=1, minutes=45)
                        + timedelta(seconds=3),
                        duration_ms=34.5,
                        outputs={
                            "passed": False,
                            "missing_fields": ["email"],
                            "error": "Required field missing",
                        },
                    ),
                    Step(
                        trace_id=t9_id,
                        type=StepType.LLM,
                        name="generate_json_attempt_2",
                        start_time=base_time
                        - timedelta(hours=1, minutes=45)
                        + timedelta(seconds=4),
                        duration_ms=2300.0,
                        model_name="gpt-4o-mini",
                        model_provider="openai",
                        input_tokens=800,
                        output_tokens=350,
                        cost_usd=0.0017,
                        outputs={"raw": '{"name": "John", "age": 30, "email": "john@example.com"}'},
                    ),
                    Step(
                        trace_id=t9_id,
                        type=StepType.GUARDRAIL,
                        name="schema_validation",
                        start_time=base_time
                        - timedelta(hours=1, minutes=45)
                        + timedelta(seconds=7),
                        duration_ms=28.0,
                        outputs={
                            "passed": True,
                            "validated_object": {
                                "name": "John",
                                "age": 30,
                                "email": "john@example.com",
                            },
                        },
                    ),
                ],
            )
        )

        # =====================================================================
        # TRACE 10: Content Moderation Pipeline
        # =====================================================================
        t10_id = uuid4()
        traces.append(
            AgentRun(
                id=t10_id,
                name="content_moderation",
                description="Content moderation with multiple guardrails",
                start_time=base_time - timedelta(hours=1, minutes=30),
                duration_ms=4567.8,
                total_tokens=2100,
                total_cost_usd=0.0315,
                tags=["moderation", "guardrail", "safety"],
                steps=[
                    Step(
                        trace_id=t10_id,
                        type=StepType.WORKFLOW,
                        name="moderation_pipeline",
                        start_time=base_time - timedelta(hours=1, minutes=30),
                        duration_ms=4567.8,
                        children=[
                            Step(
                                trace_id=t10_id,
                                type=StepType.GUARDRAIL,
                                name="toxicity_check",
                                start_time=base_time - timedelta(hours=1, minutes=30),
                                duration_ms=234.5,
                                inputs={"text": "User submitted content for review"},
                                outputs={"passed": True, "toxicity_score": 0.02, "categories": []},
                            ),
                            Step(
                                trace_id=t10_id,
                                type=StepType.GUARDRAIL,
                                name="pii_detection",
                                start_time=base_time
                                - timedelta(hours=1, minutes=30)
                                + timedelta(milliseconds=300),
                                duration_ms=156.0,
                                outputs={"passed": True, "pii_found": [], "redacted": False},
                            ),
                            Step(
                                trace_id=t10_id,
                                type=StepType.GUARDRAIL,
                                name="prompt_injection_check",
                                start_time=base_time
                                - timedelta(hours=1, minutes=30)
                                + timedelta(milliseconds=500),
                                duration_ms=189.0,
                                outputs={"passed": True, "injection_probability": 0.01},
                            ),
                            Step(
                                trace_id=t10_id,
                                type=StepType.LLM,
                                name="generate_response",
                                start_time=base_time
                                - timedelta(hours=1, minutes=30)
                                + timedelta(seconds=1),
                                duration_ms=2800.0,
                                model_name="gpt-4o",
                                model_provider="openai",
                                input_tokens=800,
                                output_tokens=600,
                                cost_usd=0.021,
                            ),
                            Step(
                                trace_id=t10_id,
                                type=StepType.GUARDRAIL,
                                name="output_safety_check",
                                start_time=base_time
                                - timedelta(hours=1, minutes=30)
                                + timedelta(seconds=4),
                                duration_ms=188.3,
                                outputs={"passed": True, "safety_score": 0.98},
                            ),
                        ],
                    )
                ],
            )
        )

        # =====================================================================
        # TRACE 11: Streaming Long-Form Content
        # =====================================================================
        t11_id = uuid4()
        traces.append(
            AgentRun(
                id=t11_id,
                name="blog_generation",
                description="Streaming blog post generation",
                start_time=base_time - timedelta(hours=1),
                duration_ms=18234.5,
                total_tokens=6500,
                total_cost_usd=0.0975,
                tags=["streaming", "content", "long-form"],
                steps=[
                    Step(
                        trace_id=t11_id,
                        type=StepType.LLM,
                        name="outline_generation",
                        start_time=base_time - timedelta(hours=1),
                        duration_ms=2500.0,
                        model_name="gpt-4o",
                        model_provider="openai",
                        input_tokens=500,
                        output_tokens=400,
                        cost_usd=0.0135,
                        inputs={"topic": "The Future of AI in Healthcare"},
                        outputs={
                            "outline": [
                                "1. Introduction",
                                "2. Current Applications",
                                "3. Emerging Technologies",
                                "4. Challenges",
                                "5. Future Outlook",
                            ]
                        },
                    ),
                    Step(
                        trace_id=t11_id,
                        type=StepType.LLM,
                        name="content_generation",
                        start_time=base_time - timedelta(hours=1) + timedelta(seconds=3),
                        duration_ms=15734.5,
                        model_name="claude-3-5-sonnet-20241022",
                        model_provider="anthropic",
                        input_tokens=1200,
                        output_tokens=4400,
                        cost_usd=0.084,
                        is_streaming=True,
                        streaming_chunks=["chunk_1", "chunk_2", "...", "chunk_n"],
                        outputs={"word_count": 2200, "sections": 5},
                    ),
                ],
            )
        )

        # =====================================================================
        # TRACE 12: Azure OpenAI Deployment
        # =====================================================================
        t12_id = uuid4()
        traces.append(
            AgentRun(
                id=t12_id,
                name="azure_enterprise_chat",
                description="Enterprise chat via Azure OpenAI",
                cloud_provider="azure",
                start_time=base_time - timedelta(minutes=45),
                duration_ms=3456.7,
                total_tokens=1850,
                total_cost_usd=0.0278,
                tags=["azure", "enterprise", "chat"],
                steps=[
                    Step(
                        trace_id=t12_id,
                        type=StepType.LLM,
                        name="gpt-4-deployment",
                        start_time=base_time - timedelta(minutes=45),
                        duration_ms=3456.7,
                        model_name="gpt-4",
                        model_provider="azure",
                        input_tokens=950,
                        output_tokens=900,
                        cost_usd=0.0278,
                        attributes={
                            "azure_deployment": "gpt-4-east-us",
                            "azure_endpoint": "https://mycompany.openai.azure.com",
                            "api_version": "2024-02-01",
                        },
                        inputs={
                            "messages": [
                                {"role": "system", "content": "You are an enterprise assistant."},
                                {
                                    "role": "user",
                                    "content": "Summarize the quarterly compliance report.",
                                },
                            ]
                        },
                    )
                ],
            )
        )

        # =====================================================================
        # TRACE 13: AWS Bedrock with Claude
        # =====================================================================
        t13_id = uuid4()
        traces.append(
            AgentRun(
                id=t13_id,
                name="bedrock_analysis",
                description="Document analysis via AWS Bedrock",
                cloud_provider="aws",
                start_time=base_time - timedelta(minutes=30),
                duration_ms=5678.9,
                total_tokens=3200,
                total_cost_usd=0.048,
                tags=["aws", "bedrock", "analysis"],
                steps=[
                    Step(
                        trace_id=t13_id,
                        type=StepType.RETRIEVAL,
                        name="s3_document_load",
                        start_time=base_time - timedelta(minutes=30),
                        duration_ms=1200.0,
                        inputs={"bucket": "company-docs", "key": "reports/annual-2024.pdf"},
                        outputs={"pages": 45, "size_kb": 2340},
                        attributes={"aws_region": "us-east-1"},
                    ),
                    Step(
                        trace_id=t13_id,
                        type=StepType.LLM,
                        name="claude-3-sonnet",
                        start_time=base_time - timedelta(minutes=30) + timedelta(seconds=2),
                        duration_ms=4478.9,
                        model_name="anthropic.claude-3-sonnet-20240229-v1:0",
                        model_provider="bedrock",
                        input_tokens=2400,
                        output_tokens=800,
                        cost_usd=0.048,
                        attributes={
                            "aws_region": "us-east-1",
                            "bedrock_model_id": "anthropic.claude-3-sonnet-20240229-v1:0",
                        },
                    ),
                ],
            )
        )

        # =====================================================================
        # TRACE 14: GCP Vertex AI with Gemini
        # =====================================================================
        t14_id = uuid4()
        traces.append(
            AgentRun(
                id=t14_id,
                name="vertex_multimodal",
                description="Multimodal analysis via Vertex AI",
                cloud_provider="gcp",
                start_time=base_time - timedelta(minutes=20),
                duration_ms=4234.5,
                total_tokens=2800,
                total_cost_usd=0.042,
                tags=["gcp", "vertex", "multimodal", "gemini"],
                steps=[
                    Step(
                        trace_id=t14_id,
                        type=StepType.LLM,
                        name="gemini-1.5-pro",
                        start_time=base_time - timedelta(minutes=20),
                        duration_ms=4234.5,
                        model_name="gemini-1.5-pro",
                        model_provider="vertex",
                        input_tokens=2000,
                        output_tokens=800,
                        cost_usd=0.042,
                        attributes={
                            "gcp_project": "my-ai-project",
                            "gcp_location": "us-central1",
                            "vertex_endpoint": "us-central1-aiplatform.googleapis.com",
                        },
                        inputs={
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Analyze this product image and describe it.",
                                },
                                {"type": "image", "source": "gs://bucket/product.jpg"},
                            ]
                        },
                    )
                ],
            )
        )

        # =====================================================================
        # TRACE 15: Timeout Error
        # =====================================================================
        t15_id = uuid4()
        traces.append(
            AgentRun(
                id=t15_id,
                name="timeout_failure",
                description="Request timed out during processing",
                start_time=base_time - timedelta(minutes=15),
                duration_ms=30000.0,
                total_tokens=500,
                error="TimeoutError: Request timed out after 30s",
                error_count=1,
                tags=["error", "timeout"],
                steps=[
                    Step(
                        trace_id=t15_id,
                        type=StepType.LLM,
                        name="gpt-4o",
                        start_time=base_time - timedelta(minutes=15),
                        duration_ms=30000.0,
                        model_name="gpt-4o",
                        model_provider="openai",
                        input_tokens=500,
                        output_tokens=0,
                        error="TimeoutError: Request timed out after 30 seconds",
                        error_type="TimeoutError",
                        inputs={
                            "messages": [
                                {"role": "user", "content": "Process this very large document..."}
                            ],
                            "max_tokens": 8000,
                        },
                    )
                ],
            )
        )

        # =====================================================================
        # TRACE 16: Complex Document Processing Workflow
        # =====================================================================
        t16_id = uuid4()
        traces.append(
            AgentRun(
                id=t16_id,
                name="document_processing",
                description="End-to-end document processing pipeline",
                start_time=base_time - timedelta(minutes=10),
                duration_ms=28456.7,
                total_tokens=15934,
                total_cost_usd=0.2391,
                tags=["workflow", "document", "pipeline"],
                steps=[
                    Step(
                        trace_id=t16_id,
                        type=StepType.WORKFLOW,
                        name="document_pipeline",
                        start_time=base_time - timedelta(minutes=10),
                        duration_ms=28456.7,
                        children=[
                            Step(
                                trace_id=t16_id,
                                type=StepType.RETRIEVAL,
                                name="document_load",
                                start_time=base_time - timedelta(minutes=10),
                                duration_ms=856.2,
                                inputs={"path": "/documents/contract.pdf"},
                                outputs={"pages": 25, "text_length": 45000},
                            ),
                            Step(
                                trace_id=t16_id,
                                type=StepType.LLM,
                                name="chunk_classification",
                                start_time=base_time - timedelta(minutes=10) + timedelta(seconds=1),
                                duration_ms=3500.0,
                                model_name="gpt-4o-mini",
                                model_provider="openai",
                                input_tokens=4000,
                                output_tokens=500,
                                cost_usd=0.0068,
                                outputs={
                                    "chunks": 12,
                                    "types": ["header", "clause", "signature", "appendix"],
                                },
                            ),
                            Step(
                                trace_id=t16_id,
                                type=StepType.LLM,
                                name="entity_extraction",
                                start_time=base_time - timedelta(minutes=10) + timedelta(seconds=5),
                                duration_ms=4500.0,
                                model_name="claude-3-5-sonnet-20241022",
                                model_provider="anthropic",
                                input_tokens=5000,
                                output_tokens=1500,
                                cost_usd=0.0585,
                                outputs={
                                    "entities": {
                                        "parties": ["Acme Corp", "Beta Inc"],
                                        "dates": ["2024-01-15", "2025-01-14"],
                                        "amounts": ["$500,000", "$50,000/month"],
                                    }
                                },
                            ),
                            Step(
                                trace_id=t16_id,
                                type=StepType.LLM,
                                name="risk_analysis",
                                start_time=base_time
                                - timedelta(minutes=10)
                                + timedelta(seconds=10),
                                duration_ms=6200.0,
                                model_name="gpt-4o",
                                model_provider="openai",
                                input_tokens=3500,
                                output_tokens=1200,
                                cost_usd=0.059,
                                outputs={
                                    "risk_score": 0.35,
                                    "flags": [
                                        "non-standard termination clause",
                                        "unusual liability cap",
                                    ],
                                },
                            ),
                            Step(
                                trace_id=t16_id,
                                type=StepType.GUARDRAIL,
                                name="compliance_check",
                                start_time=base_time
                                - timedelta(minutes=10)
                                + timedelta(seconds=17),
                                duration_ms=234.5,
                                outputs={
                                    "passed": True,
                                    "compliance_score": 0.92,
                                    "regulations_checked": ["GDPR", "SOC2"],
                                },
                            ),
                            Step(
                                trace_id=t16_id,
                                type=StepType.LLM,
                                name="summary_generation",
                                start_time=base_time
                                - timedelta(minutes=10)
                                + timedelta(seconds=18),
                                duration_ms=5500.0,
                                model_name="claude-3-5-sonnet-20241022",
                                model_provider="anthropic",
                                input_tokens=2500,
                                output_tokens=1234,
                                cost_usd=0.0336,
                            ),
                            Step(
                                trace_id=t16_id,
                                type=StepType.EVALUATION,
                                name="quality_assessment",
                                start_time=base_time
                                - timedelta(minutes=10)
                                + timedelta(seconds=24),
                                duration_ms=2666.0,
                                model_name="gpt-4o",
                                model_provider="openai",
                                input_tokens=800,
                                output_tokens=200,
                                cost_usd=0.012,
                                outputs={
                                    "quality_score": 0.94,
                                    "completeness": 0.96,
                                    "accuracy": 0.92,
                                    "readability": 0.95,
                                },
                            ),
                            Step(
                                trace_id=t16_id,
                                type=StepType.TOOL,
                                name="save_results",
                                start_time=base_time
                                - timedelta(minutes=10)
                                + timedelta(seconds=27),
                                duration_ms=500.0,
                                inputs={
                                    "format": "json",
                                    "destination": "s3://results/contract_analysis.json",
                                },
                                outputs={"saved": True, "size_kb": 45},
                            ),
                        ],
                    )
                ],
            )
        )

        # =====================================================================
        # TRACE 17: Quick Embedding Generation
        # =====================================================================
        t17_id = uuid4()
        traces.append(
            AgentRun(
                id=t17_id,
                name="embedding_batch",
                description="Batch embedding generation",
                start_time=base_time - timedelta(minutes=5),
                duration_ms=1234.5,
                total_tokens=2400,
                total_cost_usd=0.00024,
                tags=["embedding", "batch"],
                steps=[
                    Step(
                        trace_id=t17_id,
                        type=StepType.LLM,
                        name="text-embedding-3-small",
                        start_time=base_time - timedelta(minutes=5),
                        duration_ms=1234.5,
                        model_name="text-embedding-3-small",
                        model_provider="openai",
                        input_tokens=2400,
                        output_tokens=0,
                        cost_usd=0.00024,
                        inputs={
                            "texts": ["Document 1 text...", "Document 2 text...", "..."],
                            "batch_size": 50,
                        },
                        outputs={"embeddings_count": 50, "dimensions": 1536},
                    )
                ],
            )
        )

        # =====================================================================
        # TRACE 18: Real-time Chat with Tools
        # =====================================================================
        t18_id = uuid4()
        traces.append(
            AgentRun(
                id=t18_id,
                name="chat_with_tools",
                description="Interactive chat with calculator and weather tools",
                session_id="chat_session_xyz",
                start_time=base_time - timedelta(minutes=3),
                duration_ms=4567.8,
                total_tokens=1800,
                total_cost_usd=0.027,
                tags=["chat", "tools", "interactive"],
                steps=[
                    Step(
                        trace_id=t18_id,
                        type=StepType.LLM,
                        name="tool_selection",
                        start_time=base_time - timedelta(minutes=3),
                        duration_ms=1200.0,
                        model_name="gpt-4o",
                        model_provider="openai",
                        input_tokens=400,
                        output_tokens=100,
                        cost_usd=0.006,
                        inputs={
                            "messages": [
                                {
                                    "role": "user",
                                    "content": "What's 15% tip on $85.50 and what's the weather in NYC?",
                                }
                            ],
                            "tools": ["calculator", "weather"],
                        },
                        outputs={"tool_calls": ["calculator", "weather"]},
                    ),
                    Step(
                        trace_id=t18_id,
                        type=StepType.TOOL,
                        name="calculator",
                        start_time=base_time - timedelta(minutes=3) + timedelta(seconds=2),
                        duration_ms=50.0,
                        inputs={"expression": "85.50 * 0.15"},
                        outputs={"result": 12.825},
                    ),
                    Step(
                        trace_id=t18_id,
                        type=StepType.TOOL,
                        name="weather",
                        start_time=base_time - timedelta(minutes=3) + timedelta(seconds=2),
                        duration_ms=800.0,
                        inputs={"location": "New York, NY"},
                        outputs={
                            "temperature": "45°F",
                            "conditions": "Partly cloudy",
                            "humidity": "65%",
                        },
                    ),
                    Step(
                        trace_id=t18_id,
                        type=StepType.LLM,
                        name="response_synthesis",
                        start_time=base_time - timedelta(minutes=3) + timedelta(seconds=3),
                        duration_ms=1500.0,
                        model_name="gpt-4o",
                        model_provider="openai",
                        input_tokens=800,
                        output_tokens=300,
                        cost_usd=0.0135,
                        outputs={
                            "response": "A 15% tip on $85.50 would be $12.83. As for the weather in NYC, it's currently 45°F and partly cloudy with 65% humidity."
                        },
                    ),
                ],
            )
        )

        # =====================================================================
        # TRACE 19: Anthropic Claude Opus (Expensive)
        # =====================================================================
        t19_id = uuid4()
        traces.append(
            AgentRun(
                id=t19_id,
                name="deep_analysis",
                description="Complex reasoning with Claude Opus",
                start_time=base_time - timedelta(minutes=2),
                duration_ms=45678.9,
                total_tokens=18500,
                total_cost_usd=0.5550,
                tags=["opus", "reasoning", "expensive"],
                steps=[
                    Step(
                        trace_id=t19_id,
                        type=StepType.LLM,
                        name="claude-opus",
                        start_time=base_time - timedelta(minutes=2),
                        duration_ms=45678.9,
                        model_name="claude-opus-4-20250514",
                        model_provider="anthropic",
                        input_tokens=12000,
                        output_tokens=6500,
                        cost_usd=0.5550,
                        inputs={
                            "system": "You are an expert analyst. Provide deep, nuanced analysis.",
                            "messages": [
                                {
                                    "role": "user",
                                    "content": "Analyze the long-term implications of quantum computing on global cybersecurity infrastructure, considering economic, political, and technical dimensions.",
                                }
                            ],
                        },
                        outputs={
                            "analysis_sections": 8,
                            "word_count": 3250,
                            "citations": 12,
                        },
                    )
                ],
            )
        )

        # =====================================================================
        # TRACE 20: Quick GPT-4o-mini Response
        # =====================================================================
        t20_id = uuid4()
        traces.append(
            AgentRun(
                id=t20_id,
                name="quick_answer",
                description="Fast response with GPT-4o-mini",
                start_time=base_time - timedelta(minutes=1),
                duration_ms=456.7,
                total_tokens=180,
                total_cost_usd=0.00027,
                tags=["fast", "mini", "cheap"],
                steps=[
                    Step(
                        trace_id=t20_id,
                        type=StepType.LLM,
                        name="gpt-4o-mini",
                        start_time=base_time - timedelta(minutes=1),
                        duration_ms=456.7,
                        model_name="gpt-4o-mini",
                        model_provider="openai",
                        input_tokens=80,
                        output_tokens=100,
                        cost_usd=0.00027,
                        inputs={"messages": [{"role": "user", "content": "What is 2+2?"}]},
                        outputs={"content": "2 + 2 = 4"},
                    )
                ],
            )
        )

        return traces

    def _update_status(self, message: str) -> None:
        """Update the status message."""
        status = self.query_one("#setup-status", Static)
        status.update(f"+ {message}")

    def _show_error(self, message: str) -> None:
        """Show an error message."""
        error = self.query_one("#setup-error", Static)
        error.update(f"x {message}")

    def _clear_error(self) -> None:
        """Clear the error message."""
        error = self.query_one("#setup-error", Static)
        error.update("")
