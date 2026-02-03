"""
Initialization utilities for TraceCraft.

Provides functions to set up directories, databases, and configuration files
for first-time users or new projects.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun
    from tracecraft.storage.sqlite import SQLiteTraceStore


class InitLocation(str, Enum):
    """Location for TraceCraft initialization."""

    GLOBAL = "global"  # ~/.tracecraft/
    LOCAL = "local"  # .tracecraft/ in current directory


@dataclass
class InitResult:
    """Result of initialization."""

    success: bool
    location: InitLocation
    config_path: Path
    database_path: Path
    error: str | None = None


def get_global_dir() -> Path:
    """Get the global TraceCraft directory path."""
    return Path.home() / ".tracecraft"


def get_local_dir(base_path: Path | None = None) -> Path:
    """Get the local TraceCraft directory path."""
    if base_path is None:
        base_path = Path.cwd()
    return base_path / ".tracecraft"


def config_exists(location: InitLocation | None = None) -> bool:
    """
    Check if an TraceCraft configuration exists.

    Args:
        location: Specific location to check, or None to check both.

    Returns:
        True if config exists at the specified location(s).
    """
    if location == InitLocation.GLOBAL:
        return (get_global_dir() / "config.yaml").exists()
    elif location == InitLocation.LOCAL:
        return (get_local_dir() / "config.yaml").exists()
    else:
        # Check both
        return (get_global_dir() / "config.yaml").exists() or (
            get_local_dir() / "config.yaml"
        ).exists()


def database_exists(location: InitLocation | None = None) -> bool:
    """
    Check if an TraceCraft database exists.

    Args:
        location: Specific location to check, or None to check both.

    Returns:
        True if database exists at the specified location(s).
    """
    if location == InitLocation.GLOBAL:
        return (get_global_dir() / "traces.db").exists()
    elif location == InitLocation.LOCAL:
        return (get_local_dir() / "traces.db").exists()
    else:
        # Check both
        return (get_global_dir() / "traces.db").exists() or (get_local_dir() / "traces.db").exists()


def find_existing_config() -> Path | None:
    """
    Find an existing config file.

    Returns:
        Path to config file if found, None otherwise.
    """
    # Check local first (takes precedence)
    local_config = get_local_dir() / "config.yaml"
    if local_config.exists():
        return local_config

    # Then check global
    global_config = get_global_dir() / "config.yaml"
    if global_config.exists():
        return global_config

    return None


def find_existing_database() -> Path | None:
    """
    Find an existing database file.

    Returns:
        Path to database file if found, None otherwise.
    """
    # Check local first (takes precedence)
    local_db = get_local_dir() / "traces.db"
    if local_db.exists():
        return local_db

    # Then check global
    global_db = get_global_dir() / "traces.db"
    if global_db.exists():
        return global_db

    return None


def get_default_config(location: InitLocation, database_path: Path) -> dict[str, Any]:
    """
    Generate default configuration for a location.

    Args:
        location: Where the config will be stored.
        database_path: Path to the SQLite database.

    Returns:
        Configuration dictionary.
    """
    # Use relative path for local, absolute for global
    if location == InitLocation.LOCAL:
        db_path_str = str(database_path.name)  # Just the filename
    else:
        db_path_str = str(database_path)

    return {
        "env": "development",
        "default": {
            "storage": {
                "type": "sqlite",
                "sqlite_path": db_path_str,
                "sqlite_wal_mode": True,
            },
            "exporters": {
                "console": True,
                "jsonl": False,  # SQLite is primary storage
                "otlp": False,
            },
            "processors": {
                "redaction_enabled": False,
                "sampling_enabled": False,
                "enrichment_enabled": True,
            },
        },
        "environments": {
            "development": {
                "exporters": {
                    "console": True,
                },
            },
            "production": {
                "storage": {
                    "type": "none",
                },
                "exporters": {
                    "console": False,
                    "otlp": True,
                    "otlp_endpoint": "${OTEL_EXPORTER_OTLP_ENDPOINT}",
                },
                "processors": {
                    "redaction_enabled": True,
                },
            },
        },
    }


def write_config(config_path: Path, config: dict[str, Any]) -> None:
    """
    Write configuration to a YAML file.

    Args:
        config_path: Path to write the config file.
        config: Configuration dictionary.
    """
    try:
        import yaml

        config_content = yaml.dump(config, default_flow_style=False, sort_keys=False)
    except ImportError:
        # Fall back to simple YAML-like format
        config_content = _dict_to_yaml(config)

    # Add header comment
    header = """# TraceCraft Configuration
# Generated automatically by the setup wizard.
#
# Configuration is loaded from (in order of precedence):
# 1. Environment variables (TRACECRAFT_*)
# 2. .tracecraft/config.yaml in current directory
# 3. ~/.tracecraft/config.yaml
# 4. Default values

"""
    config_path.write_text(header + config_content)


def _dict_to_yaml(d: dict[str, Any], indent: int = 0) -> str:
    """Simple dict to YAML converter (fallback if PyYAML not installed)."""
    lines = []
    prefix = "  " * indent

    for key, value in d.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_dict_to_yaml(value, indent + 1))
        elif isinstance(value, bool):
            lines.append(f"{prefix}{key}: {str(value).lower()}")
        elif isinstance(value, (int, float)):
            lines.append(f"{prefix}{key}: {value}")
        elif value is None:
            lines.append(f"{prefix}{key}: null")
        else:
            lines.append(f"{prefix}{key}: {value}")

    return "\n".join(lines)


def initialize_database(database_path: Path) -> None:
    """
    Initialize a SQLite database with the TraceCraft schema.

    Args:
        database_path: Path to create the database.
    """
    from tracecraft.storage.sqlite import SQLiteTraceStore

    # Creating the store initializes the schema
    store = SQLiteTraceStore(database_path)
    store.close()


def initialize(
    location: InitLocation,
    base_path: Path | None = None,
    create_sample_project: bool = True,
) -> InitResult:
    """
    Initialize TraceCraft at the specified location.

    Creates:
    - Directory structure
    - SQLite database with schema
    - Configuration file

    Args:
        location: Where to initialize (global or local).
        base_path: Base path for local initialization (defaults to cwd).
        create_sample_project: Whether to create a sample project in the database.

    Returns:
        InitResult with paths and status.
    """
    try:
        # Determine paths
        if location == InitLocation.GLOBAL:
            tracecraft_dir = get_global_dir()
        else:
            tracecraft_dir = get_local_dir(base_path)

        config_path = tracecraft_dir / "config.yaml"
        database_path = tracecraft_dir / "traces.db"

        # Create directory
        tracecraft_dir.mkdir(parents=True, exist_ok=True)

        # Create .gitignore for local to exclude database
        if location == InitLocation.LOCAL:
            gitignore_path = tracecraft_dir / ".gitignore"
            if not gitignore_path.exists():
                gitignore_path.write_text(
                    "# TraceCraft local files\ntraces.db\n*.db-wal\n*.db-shm\n"
                )

        # Initialize database
        initialize_database(database_path)

        # Create sample project if requested
        if create_sample_project:
            _create_sample_project(database_path)

        # Generate and write config
        config = get_default_config(location, database_path)
        write_config(config_path, config)

        return InitResult(
            success=True,
            location=location,
            config_path=config_path,
            database_path=database_path,
        )

    except Exception as e:
        return InitResult(
            success=False,
            location=location,
            config_path=config_path if "config_path" in dir() else Path(),
            database_path=database_path if "database_path" in dir() else Path(),
            error=str(e),
        )


def _create_sample_project(database_path: Path) -> None:
    """Create a sample project in the database (legacy, calls _create_example_data)."""
    _create_example_data(database_path)


def _create_example_data(database_path: Path) -> None:
    """
    Create comprehensive example data including project, agents, traces, and evals.

    This provides users with sample data to explore all TraceCraft features.
    """
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from tracecraft.core.models import AgentRun, Step, StepType
    from tracecraft.storage.sqlite import SQLiteTraceStore

    store = SQLiteTraceStore(database_path)
    try:
        # 1. Create Example Project
        project_id = store.create_project(
            name="Example Project",
            description="Demo project with sample traces, agents, and evaluations. "
            "Explore this to see all TraceCraft features in action.",
        )

        # 2. Create 3 Agents
        research_agent_id = store.create_agent(
            name="Research Assistant",
            description="RAG-based research agent using retrieval and synthesis",
            project_id=project_id,
            agent_type="rag",
            config={"model": "gpt-4o", "temperature": 0.7},
        )

        code_agent_id = store.create_agent(
            name="Code Helper",
            description="Code generation and debugging assistant",
            project_id=project_id,
            agent_type="code",
            config={"model": "claude-3-5-sonnet", "temperature": 0.2},
        )

        support_agent_id = store.create_agent(
            name="Customer Support",
            description="Customer support bot with memory and safety guardrails",
            project_id=project_id,
            agent_type="support",
            config={"model": "gpt-4o-mini", "temperature": 0.5},
        )

        # 3. Generate and save traces
        base_time = datetime.now(UTC)
        traces_with_agents = _generate_example_traces(
            base_time, research_agent_id, code_agent_id, support_agent_id
        )

        saved_traces: dict[str, list[AgentRun]] = {
            research_agent_id: [],
            code_agent_id: [],
            support_agent_id: [],
        }

        for trace, agent_id in traces_with_agents:
            store.save(trace, project_id=project_id)
            store.assign_trace_to_agent(str(trace.id), agent_id)
            saved_traces[agent_id].append(trace)

        # 4. Create Evaluation Sets with Cases
        eval_sets = _create_example_eval_sets(store, project_id, saved_traces)

        # 5. Create Evaluation Runs with Results
        _create_example_eval_runs(store, eval_sets, saved_traces)

    except Exception:
        # If example data creation fails, don't block initialization
        pass
    finally:
        store.close()


def _generate_example_traces(
    base_time: datetime,
    research_agent_id: str,
    code_agent_id: str,
    support_agent_id: str,
) -> list[tuple[AgentRun, str]]:
    """
    Generate example traces for each agent type.

    Returns list of (AgentRun, agent_id) tuples.
    """
    from datetime import UTC, timedelta
    from uuid import uuid4

    from tracecraft.core.models import AgentRun, Step, StepType

    traces = []

    # =========================================================================
    # RESEARCH ASSISTANT TRACES
    # =========================================================================

    # Trace 1: Climate Research Query (RAG success)
    t1_id = uuid4()
    t1_s1_id = uuid4()
    t1_s2_id = uuid4()
    t1_s3_id = uuid4()
    traces.append(
        (
            AgentRun(
                id=t1_id,
                name="Climate Research Query",
                description="Researching climate change impacts using RAG pipeline",
                start_time=base_time - timedelta(hours=5),
                end_time=base_time - timedelta(hours=5) + timedelta(seconds=3),
                duration_ms=3245.5,
                total_tokens=1523,
                total_cost_usd=0.0234,
                tags=["research", "rag", "climate"],
                environment="production",
                input={"query": "What are the main impacts of climate change on agriculture?"},
                output={
                    "answer": "Climate change affects agriculture through rising temperatures, "
                    "altered precipitation patterns, increased extreme weather events, and shifting "
                    "growing seasons. Key impacts include reduced crop yields, water stress, and "
                    "new pest and disease pressures."
                },
                steps=[
                    Step(
                        id=t1_s1_id,
                        trace_id=t1_id,
                        type=StepType.LLM,
                        name="query_understanding",
                        start_time=base_time - timedelta(hours=5),
                        end_time=base_time - timedelta(hours=5) + timedelta(milliseconds=850),
                        duration_ms=850.0,
                        model_name="gpt-4o",
                        model_provider="openai",
                        input_tokens=45,
                        output_tokens=120,
                        cost_usd=0.0045,
                        inputs={
                            "prompt": "Analyze and expand this query for retrieval: What are the main impacts of climate change on agriculture?"
                        },
                        outputs={
                            "expanded_query": "climate change agriculture impacts crop yields temperature precipitation"
                        },
                    ),
                    Step(
                        id=t1_s2_id,
                        trace_id=t1_id,
                        type=StepType.RETRIEVAL,
                        name="vector_search",
                        start_time=base_time - timedelta(hours=5) + timedelta(milliseconds=850),
                        end_time=base_time - timedelta(hours=5) + timedelta(milliseconds=1200),
                        duration_ms=350.0,
                        inputs={"query": "climate change agriculture impacts", "top_k": 5},
                        outputs={
                            "documents": ["doc_1.pdf", "doc_2.pdf", "doc_3.pdf"],
                            "scores": [0.92, 0.87, 0.81],
                        },
                        attributes={"index": "climate_research", "retrieved_count": 3},
                    ),
                    Step(
                        id=t1_s3_id,
                        trace_id=t1_id,
                        type=StepType.LLM,
                        name="answer_synthesis",
                        start_time=base_time - timedelta(hours=5) + timedelta(milliseconds=1200),
                        end_time=base_time - timedelta(hours=5) + timedelta(seconds=3),
                        duration_ms=1800.0,
                        model_name="gpt-4o",
                        model_provider="openai",
                        input_tokens=580,
                        output_tokens=778,
                        cost_usd=0.0189,
                        inputs={
                            "context": "[Retrieved documents...]",
                            "query": "What are the main impacts of climate change on agriculture?",
                        },
                        outputs={
                            "answer": "Climate change affects agriculture through rising temperatures..."
                        },
                    ),
                ],
            ),
            research_agent_id,
        )
    )

    # Trace 2: Market Analysis (multi-step with tool)
    t2_id = uuid4()
    t2_s1_id = uuid4()
    t2_s2_id = uuid4()
    t2_s3_id = uuid4()
    t2_s4_id = uuid4()
    traces.append(
        (
            AgentRun(
                id=t2_id,
                name="Market Analysis",
                description="Analyzing market trends using web search and retrieval",
                start_time=base_time - timedelta(hours=4),
                end_time=base_time - timedelta(hours=4) + timedelta(seconds=5),
                duration_ms=5123.0,
                total_tokens=2345,
                total_cost_usd=0.0412,
                tags=["research", "market", "analysis"],
                environment="production",
                input={"query": "What are the current trends in renewable energy investment?"},
                output={
                    "answer": "Renewable energy investment has reached record highs with solar and wind leading..."
                },
                steps=[
                    Step(
                        id=t2_s1_id,
                        trace_id=t2_id,
                        type=StepType.LLM,
                        name="query_planning",
                        start_time=base_time - timedelta(hours=4),
                        duration_ms=650.0,
                        model_name="gpt-4o",
                        model_provider="openai",
                        input_tokens=50,
                        output_tokens=95,
                        cost_usd=0.0035,
                        inputs={
                            "query": "What are the current trends in renewable energy investment?"
                        },
                        outputs={
                            "plan": "1. Search recent news, 2. Retrieve historical data, 3. Synthesize"
                        },
                    ),
                    Step(
                        id=t2_s2_id,
                        trace_id=t2_id,
                        type=StepType.TOOL,
                        name="web_search",
                        start_time=base_time - timedelta(hours=4) + timedelta(milliseconds=650),
                        duration_ms=1200.0,
                        inputs={
                            "query": "renewable energy investment trends 2024",
                            "max_results": 10,
                        },
                        outputs={"results": [{"title": "Solar Investment Soars", "url": "..."}]},
                        attributes={"tool": "serper", "results_count": 10},
                    ),
                    Step(
                        id=t2_s3_id,
                        trace_id=t2_id,
                        type=StepType.RETRIEVAL,
                        name="historical_data_retrieval",
                        start_time=base_time - timedelta(hours=4) + timedelta(milliseconds=1850),
                        duration_ms=450.0,
                        inputs={"query": "renewable energy investment statistics"},
                        outputs={"documents": ["report_2023.pdf", "iea_outlook.pdf"]},
                    ),
                    Step(
                        id=t2_s4_id,
                        trace_id=t2_id,
                        type=StepType.LLM,
                        name="synthesis",
                        start_time=base_time - timedelta(hours=4) + timedelta(milliseconds=2300),
                        duration_ms=2800.0,
                        model_name="gpt-4o",
                        model_provider="openai",
                        input_tokens=1200,
                        output_tokens=1000,
                        cost_usd=0.0377,
                        inputs={"search_results": "...", "retrieved_docs": "...", "query": "..."},
                        outputs={
                            "answer": "Renewable energy investment has reached record highs..."
                        },
                    ),
                ],
            ),
            research_agent_id,
        )
    )

    # Trace 3: News Summary (nested agent structure)
    t3_id = uuid4()
    t3_s1_id = uuid4()
    t3_s2_id = uuid4()
    t3_s3_id = uuid4()
    traces.append(
        (
            AgentRun(
                id=t3_id,
                name="News Summary",
                description="Summarizing multiple news sources with nested agents",
                start_time=base_time - timedelta(hours=3),
                duration_ms=4500.0,
                total_tokens=1890,
                total_cost_usd=0.0298,
                tags=["research", "news", "summary"],
                input={"topic": "AI regulation developments"},
                output={
                    "summary": "Recent AI regulation developments include the EU AI Act implementation..."
                },
                steps=[
                    Step(
                        id=t3_s1_id,
                        trace_id=t3_id,
                        type=StepType.AGENT,
                        name="news_aggregator",
                        start_time=base_time - timedelta(hours=3),
                        duration_ms=4500.0,
                        inputs={"topic": "AI regulation developments"},
                        outputs={"summary": "Recent AI regulation developments..."},
                        children=[
                            Step(
                                id=t3_s2_id,
                                trace_id=t3_id,
                                parent_id=t3_s1_id,
                                type=StepType.LLM,
                                name="source_selection",
                                start_time=base_time - timedelta(hours=3),
                                duration_ms=800.0,
                                model_name="gpt-4o-mini",
                                model_provider="openai",
                                input_tokens=100,
                                output_tokens=150,
                                cost_usd=0.0008,
                                inputs={"topic": "AI regulation"},
                                outputs={"sources": ["reuters", "techcrunch", "wired"]},
                            ),
                            Step(
                                id=t3_s3_id,
                                trace_id=t3_id,
                                parent_id=t3_s1_id,
                                type=StepType.TOOL,
                                name="fetch_articles",
                                start_time=base_time
                                - timedelta(hours=3)
                                + timedelta(milliseconds=800),
                                duration_ms=1500.0,
                                inputs={"sources": ["reuters", "techcrunch"], "limit": 5},
                                outputs={"articles": [{"title": "EU AI Act...", "content": "..."}]},
                            ),
                        ],
                    ),
                ],
            ),
            research_agent_id,
        )
    )

    # Trace 4: Historical Research (simple success)
    t4_id = uuid4()
    traces.append(
        (
            AgentRun(
                id=t4_id,
                name="Historical Research",
                description="Simple retrieval for historical data",
                start_time=base_time - timedelta(hours=2),
                duration_ms=2100.0,
                total_tokens=980,
                total_cost_usd=0.0156,
                tags=["research", "history"],
                input={"query": "When was the first electric car invented?"},
                output={"answer": "The first practical electric car was developed in the 1880s..."},
                steps=[
                    Step(
                        id=uuid4(),
                        trace_id=t4_id,
                        type=StepType.RETRIEVAL,
                        name="knowledge_search",
                        start_time=base_time - timedelta(hours=2),
                        duration_ms=400.0,
                        inputs={"query": "first electric car invention history"},
                        outputs={"documents": ["ev_history.md"]},
                    ),
                    Step(
                        id=uuid4(),
                        trace_id=t4_id,
                        type=StepType.LLM,
                        name="answer_generation",
                        start_time=base_time - timedelta(hours=2) + timedelta(milliseconds=400),
                        duration_ms=1700.0,
                        model_name="gpt-4o",
                        model_provider="openai",
                        input_tokens=380,
                        output_tokens=600,
                        cost_usd=0.0156,
                        inputs={
                            "context": "...",
                            "query": "When was the first electric car invented?",
                        },
                        outputs={
                            "answer": "The first practical electric car was developed in the 1880s..."
                        },
                    ),
                ],
            ),
            research_agent_id,
        )
    )

    # Trace 5: API Timeout Error (error case)
    t5_id = uuid4()
    traces.append(
        (
            AgentRun(
                id=t5_id,
                name="API Timeout Error",
                description="Research query that failed due to API timeout",
                start_time=base_time - timedelta(hours=1, minutes=30),
                duration_ms=30500.0,
                total_tokens=0,
                total_cost_usd=0.0,
                error_count=1,
                tags=["research", "error"],
                error="APITimeoutError: Request timed out after 30 seconds",
                error_type="APITimeoutError",
                input={"query": "Complex multi-part research question..."},
                output=None,
                steps=[
                    Step(
                        id=uuid4(),
                        trace_id=t5_id,
                        type=StepType.LLM,
                        name="initial_analysis",
                        start_time=base_time - timedelta(hours=1, minutes=30),
                        duration_ms=30500.0,
                        model_name="gpt-4o",
                        model_provider="openai",
                        error="Request timed out after 30 seconds",
                        error_type="APITimeoutError",
                        inputs={"prompt": "Analyze this complex query..."},
                        outputs={},
                    ),
                ],
            ),
            research_agent_id,
        )
    )

    # =========================================================================
    # CODE HELPER TRACES
    # =========================================================================

    # Trace 6: Python Function (code gen + test)
    t6_id = uuid4()
    traces.append(
        (
            AgentRun(
                id=t6_id,
                name="Python Function",
                description="Generate a Python function with tests",
                start_time=base_time - timedelta(hours=4, minutes=30),
                duration_ms=3200.0,
                total_tokens=1650,
                total_cost_usd=0.0285,
                tags=["code", "python", "generation"],
                input={"request": "Write a function to calculate fibonacci numbers"},
                output={
                    "code": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)"
                },
                steps=[
                    Step(
                        id=uuid4(),
                        trace_id=t6_id,
                        type=StepType.LLM,
                        name="code_generation",
                        start_time=base_time - timedelta(hours=4, minutes=30),
                        duration_ms=2000.0,
                        model_name="claude-3-5-sonnet-20241022",
                        model_provider="anthropic",
                        input_tokens=150,
                        output_tokens=800,
                        cost_usd=0.0195,
                        inputs={"request": "Write a function to calculate fibonacci numbers"},
                        outputs={
                            "code": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)"
                        },
                    ),
                    Step(
                        id=uuid4(),
                        trace_id=t6_id,
                        type=StepType.TOOL,
                        name="code_execution",
                        start_time=base_time
                        - timedelta(hours=4, minutes=30)
                        + timedelta(milliseconds=2000),
                        duration_ms=1200.0,
                        inputs={"code": "def fibonacci(n):\n    ...", "test_cases": [[5], [10]]},
                        outputs={"results": [5, 55], "success": True},
                        attributes={"runtime": "python3.11", "sandbox": True},
                    ),
                ],
            ),
            code_agent_id,
        )
    )

    # Trace 7: Debug Session (iterative)
    t7_id = uuid4()
    traces.append(
        (
            AgentRun(
                id=t7_id,
                name="Debug Session",
                description="Iterative debugging of code issue",
                start_time=base_time - timedelta(hours=3, minutes=30),
                duration_ms=8500.0,
                total_tokens=3200,
                total_cost_usd=0.0523,
                tags=["code", "debug", "iterative"],
                input={"code": "def broken_sort(arr):\n    ...", "error": "IndexError"},
                output={
                    "fixed_code": "def sort(arr):\n    ...",
                    "explanation": "Fixed off-by-one error",
                },
                steps=[
                    Step(
                        id=uuid4(),
                        trace_id=t7_id,
                        type=StepType.LLM,
                        name="error_analysis",
                        start_time=base_time - timedelta(hours=3, minutes=30),
                        duration_ms=1500.0,
                        model_name="claude-3-5-sonnet-20241022",
                        model_provider="anthropic",
                        input_tokens=400,
                        output_tokens=600,
                        cost_usd=0.012,
                        inputs={"code": "...", "error": "IndexError"},
                        outputs={"analysis": "The error is in the loop boundary..."},
                    ),
                    Step(
                        id=uuid4(),
                        trace_id=t7_id,
                        type=StepType.TOOL,
                        name="test_run_1",
                        start_time=base_time
                        - timedelta(hours=3, minutes=30)
                        + timedelta(milliseconds=1500),
                        duration_ms=800.0,
                        inputs={"code": "proposed_fix_1"},
                        outputs={"success": False, "error": "Still failing"},
                    ),
                    Step(
                        id=uuid4(),
                        trace_id=t7_id,
                        type=StepType.LLM,
                        name="refined_fix",
                        start_time=base_time
                        - timedelta(hours=3, minutes=30)
                        + timedelta(milliseconds=2300),
                        duration_ms=2200.0,
                        model_name="claude-3-5-sonnet-20241022",
                        model_provider="anthropic",
                        input_tokens=800,
                        output_tokens=900,
                        cost_usd=0.022,
                        inputs={"previous_attempt": "...", "test_output": "Still failing"},
                        outputs={"fixed_code": "def sort(arr):\n    ..."},
                    ),
                    Step(
                        id=uuid4(),
                        trace_id=t7_id,
                        type=StepType.TOOL,
                        name="test_run_2",
                        start_time=base_time
                        - timedelta(hours=3, minutes=30)
                        + timedelta(milliseconds=4500),
                        duration_ms=500.0,
                        inputs={"code": "fixed_code"},
                        outputs={"success": True, "tests_passed": 5},
                    ),
                ],
            ),
            code_agent_id,
        )
    )

    # Trace 8: Refactoring Task (nested agent)
    t8_id = uuid4()
    t8_s1_id = uuid4()
    traces.append(
        (
            AgentRun(
                id=t8_id,
                name="Refactoring Task",
                description="Refactor legacy code with nested analysis",
                start_time=base_time - timedelta(hours=2, minutes=30),
                duration_ms=6200.0,
                total_tokens=2800,
                total_cost_usd=0.0445,
                tags=["code", "refactor"],
                input={"code": "legacy_module.py", "goal": "Improve readability and performance"},
                output={
                    "refactored_code": "...",
                    "changes": ["Extracted methods", "Added type hints"],
                },
                steps=[
                    Step(
                        id=t8_s1_id,
                        trace_id=t8_id,
                        type=StepType.AGENT,
                        name="refactor_coordinator",
                        start_time=base_time - timedelta(hours=2, minutes=30),
                        duration_ms=6200.0,
                        inputs={"code": "legacy_module.py"},
                        outputs={"refactored_code": "..."},
                        children=[
                            Step(
                                id=uuid4(),
                                trace_id=t8_id,
                                parent_id=t8_s1_id,
                                type=StepType.LLM,
                                name="code_analysis",
                                start_time=base_time - timedelta(hours=2, minutes=30),
                                duration_ms=1800.0,
                                model_name="claude-3-5-sonnet-20241022",
                                model_provider="anthropic",
                                input_tokens=1200,
                                output_tokens=600,
                                cost_usd=0.018,
                                inputs={"code": "..."},
                                outputs={"issues": ["Long functions", "No types", "Magic numbers"]},
                            ),
                            Step(
                                id=uuid4(),
                                trace_id=t8_id,
                                parent_id=t8_s1_id,
                                type=StepType.TOOL,
                                name="static_analysis",
                                start_time=base_time
                                - timedelta(hours=2, minutes=30)
                                + timedelta(milliseconds=1800),
                                duration_ms=600.0,
                                inputs={"code": "..."},
                                outputs={"complexity": 15, "lint_errors": 8},
                                attributes={"tools": ["ruff", "mypy"]},
                            ),
                            Step(
                                id=uuid4(),
                                trace_id=t8_id,
                                parent_id=t8_s1_id,
                                type=StepType.LLM,
                                name="refactor_execution",
                                start_time=base_time
                                - timedelta(hours=2, minutes=30)
                                + timedelta(milliseconds=2400),
                                duration_ms=3800.0,
                                model_name="claude-3-5-sonnet-20241022",
                                model_provider="anthropic",
                                input_tokens=1000,
                                output_tokens=1400,
                                cost_usd=0.0265,
                                inputs={"analysis": "...", "code": "..."},
                                outputs={
                                    "refactored_code": "def process_data(data: list) -> dict: ...",
                                    "changes": [
                                        "Extracted helper methods",
                                        "Added type hints",
                                        "Improved naming",
                                    ],
                                },
                            ),
                        ],
                    ),
                ],
            ),
            code_agent_id,
        )
    )

    # Trace 9: Syntax Error (error case)
    t9_id = uuid4()
    traces.append(
        (
            AgentRun(
                id=t9_id,
                name="Syntax Error",
                description="Code generation that produced invalid syntax",
                start_time=base_time - timedelta(hours=1, minutes=45),
                duration_ms=2800.0,
                total_tokens=850,
                total_cost_usd=0.0125,
                error_count=1,
                tags=["code", "error"],
                error="SyntaxError: Generated code has invalid syntax",
                error_type="SyntaxError",
                input={"request": "Generate a complex async function with error handling"},
                output=None,
                steps=[
                    Step(
                        id=uuid4(),
                        trace_id=t9_id,
                        type=StepType.LLM,
                        name="code_generation",
                        start_time=base_time - timedelta(hours=1, minutes=45),
                        duration_ms=2000.0,
                        model_name="gpt-4o-mini",
                        model_provider="openai",
                        input_tokens=200,
                        output_tokens=650,
                        cost_usd=0.0025,
                        inputs={"request": "Generate a complex async function..."},
                        outputs={"code": "async def broken(\n    ...\n    missing_parenthesis"},
                    ),
                    Step(
                        id=uuid4(),
                        trace_id=t9_id,
                        type=StepType.TOOL,
                        name="syntax_check",
                        start_time=base_time
                        - timedelta(hours=1, minutes=45)
                        + timedelta(milliseconds=2000),
                        duration_ms=100.0,
                        error="SyntaxError: invalid syntax at line 3",
                        error_type="SyntaxError",
                        inputs={"code": "..."},
                        outputs={},
                    ),
                ],
            ),
            code_agent_id,
        )
    )

    # =========================================================================
    # CUSTOMER SUPPORT TRACES
    # =========================================================================

    # Trace 10: Order Inquiry (with memory)
    t10_id = uuid4()
    traces.append(
        (
            AgentRun(
                id=t10_id,
                name="Order Inquiry",
                description="Customer asking about order status with memory context",
                start_time=base_time - timedelta(hours=4, minutes=15),
                duration_ms=2500.0,
                total_tokens=780,
                total_cost_usd=0.0045,
                tags=["support", "order", "memory"],
                session_id="session_cust_123",
                user_id="user_456",
                input={"message": "Where is my order #12345?"},
                output={
                    "response": "Your order #12345 shipped yesterday and will arrive by Friday."
                },
                steps=[
                    Step(
                        id=uuid4(),
                        trace_id=t10_id,
                        type=StepType.MEMORY,
                        name="load_customer_context",
                        start_time=base_time - timedelta(hours=4, minutes=15),
                        duration_ms=200.0,
                        inputs={"user_id": "user_456", "session_id": "session_cust_123"},
                        outputs={
                            "context": {"previous_orders": ["#12340", "#12345"], "name": "John"}
                        },
                        attributes={"memory_type": "session"},
                    ),
                    Step(
                        id=uuid4(),
                        trace_id=t10_id,
                        type=StepType.LLM,
                        name="response_generation",
                        start_time=base_time
                        - timedelta(hours=4, minutes=15)
                        + timedelta(milliseconds=200),
                        duration_ms=1800.0,
                        model_name="gpt-4o-mini",
                        model_provider="openai",
                        input_tokens=280,
                        output_tokens=500,
                        cost_usd=0.0025,
                        inputs={"message": "Where is my order #12345?", "context": "..."},
                        outputs={"response": "Your order #12345 shipped yesterday..."},
                    ),
                    Step(
                        id=uuid4(),
                        trace_id=t10_id,
                        type=StepType.MEMORY,
                        name="save_interaction",
                        start_time=base_time
                        - timedelta(hours=4, minutes=15)
                        + timedelta(milliseconds=2000),
                        duration_ms=150.0,
                        inputs={"interaction": {"query": "...", "response": "..."}},
                        outputs={"saved": True},
                        attributes={"memory_type": "session"},
                    ),
                ],
            ),
            support_agent_id,
        )
    )

    # Trace 11: Complaint Handling (with guardrail)
    t11_id = uuid4()
    traces.append(
        (
            AgentRun(
                id=t11_id,
                name="Complaint Handling",
                description="Handling upset customer with safety guardrails",
                start_time=base_time - timedelta(hours=3, minutes=45),
                duration_ms=3200.0,
                total_tokens=1100,
                total_cost_usd=0.0065,
                tags=["support", "complaint", "guardrail"],
                input={"message": "This is ridiculous! Your service is terrible!"},
                output={
                    "response": "I sincerely apologize for your frustration. Let me help resolve this immediately."
                },
                steps=[
                    Step(
                        id=uuid4(),
                        trace_id=t11_id,
                        type=StepType.LLM,
                        name="initial_response",
                        start_time=base_time - timedelta(hours=3, minutes=45),
                        duration_ms=1500.0,
                        model_name="gpt-4o-mini",
                        model_provider="openai",
                        input_tokens=150,
                        output_tokens=400,
                        cost_usd=0.002,
                        inputs={"message": "This is ridiculous! Your service is terrible!"},
                        outputs={"draft_response": "I understand you're frustrated..."},
                    ),
                    Step(
                        id=uuid4(),
                        trace_id=t11_id,
                        type=StepType.GUARDRAIL,
                        name="safety_check",
                        start_time=base_time
                        - timedelta(hours=3, minutes=45)
                        + timedelta(milliseconds=1500),
                        duration_ms=300.0,
                        inputs={
                            "response": "I understand you're frustrated...",
                            "customer_message": "...",
                        },
                        outputs={"safe": True, "tone_score": 0.92, "empathy_score": 0.88},
                        attributes={"guardrail": "tone_checker", "version": "1.2"},
                    ),
                    Step(
                        id=uuid4(),
                        trace_id=t11_id,
                        type=StepType.LLM,
                        name="enhanced_response",
                        start_time=base_time
                        - timedelta(hours=3, minutes=45)
                        + timedelta(milliseconds=1800),
                        duration_ms=1200.0,
                        model_name="gpt-4o-mini",
                        model_provider="openai",
                        input_tokens=200,
                        output_tokens=350,
                        cost_usd=0.0018,
                        inputs={"draft": "...", "guardrail_feedback": "Increase empathy"},
                        outputs={"response": "I sincerely apologize for your frustration..."},
                    ),
                ],
            ),
            support_agent_id,
        )
    )

    # Trace 12: FAQ Response (simple)
    t12_id = uuid4()
    traces.append(
        (
            AgentRun(
                id=t12_id,
                name="FAQ Response",
                description="Simple FAQ question",
                start_time=base_time - timedelta(hours=2, minutes=45),
                duration_ms=800.0,
                total_tokens=320,
                total_cost_usd=0.0012,
                tags=["support", "faq"],
                input={"message": "What are your business hours?"},
                output={"response": "We're open Monday to Friday, 9 AM to 6 PM EST."},
                steps=[
                    Step(
                        id=uuid4(),
                        trace_id=t12_id,
                        type=StepType.LLM,
                        name="faq_response",
                        start_time=base_time - timedelta(hours=2, minutes=45),
                        duration_ms=800.0,
                        model_name="gpt-4o-mini",
                        model_provider="openai",
                        input_tokens=80,
                        output_tokens=240,
                        cost_usd=0.0012,
                        inputs={"message": "What are your business hours?"},
                        outputs={"response": "We're open Monday to Friday, 9 AM to 6 PM EST."},
                    ),
                ],
            ),
            support_agent_id,
        )
    )

    # Trace 13: Escalation Flow (multi-step with tool)
    t13_id = uuid4()
    traces.append(
        (
            AgentRun(
                id=t13_id,
                name="Escalation Flow",
                description="Complex issue requiring escalation to human agent",
                start_time=base_time - timedelta(hours=1, minutes=15),
                duration_ms=4500.0,
                total_tokens=1450,
                total_cost_usd=0.0085,
                tags=["support", "escalation", "tool"],
                input={"message": "I need to speak with a manager about a billing dispute"},
                output={
                    "response": "I've created ticket #ESC-789 and a supervisor will contact you within 2 hours."
                },
                steps=[
                    Step(
                        id=uuid4(),
                        trace_id=t13_id,
                        type=StepType.LLM,
                        name="intent_classification",
                        start_time=base_time - timedelta(hours=1, minutes=15),
                        duration_ms=600.0,
                        model_name="gpt-4o-mini",
                        model_provider="openai",
                        input_tokens=100,
                        output_tokens=150,
                        cost_usd=0.001,
                        inputs={"message": "I need to speak with a manager..."},
                        outputs={"intent": "escalation", "urgency": "high", "category": "billing"},
                    ),
                    Step(
                        id=uuid4(),
                        trace_id=t13_id,
                        type=StepType.TOOL,
                        name="create_escalation_ticket",
                        start_time=base_time
                        - timedelta(hours=1, minutes=15)
                        + timedelta(milliseconds=600),
                        duration_ms=1200.0,
                        inputs={
                            "category": "billing",
                            "urgency": "high",
                            "customer_message": "...",
                        },
                        outputs={
                            "ticket_id": "ESC-789",
                            "assigned_to": "supervisor_team",
                            "sla_hours": 2,
                        },
                        attributes={"tool": "zendesk", "queue": "escalations"},
                    ),
                    Step(
                        id=uuid4(),
                        trace_id=t13_id,
                        type=StepType.LLM,
                        name="confirmation_response",
                        start_time=base_time
                        - timedelta(hours=1, minutes=15)
                        + timedelta(milliseconds=1800),
                        duration_ms=1000.0,
                        model_name="gpt-4o-mini",
                        model_provider="openai",
                        input_tokens=250,
                        output_tokens=350,
                        cost_usd=0.002,
                        inputs={
                            "ticket_info": {"id": "ESC-789", "sla": 2},
                            "original_message": "...",
                        },
                        outputs={
                            "response": "I've created ticket #ESC-789 and a supervisor will contact you..."
                        },
                    ),
                ],
            ),
            support_agent_id,
        )
    )

    return traces


def _create_example_eval_sets(
    store: SQLiteTraceStore,
    project_id: str,
    saved_traces: dict[str, list[AgentRun]],
) -> dict[str, dict]:
    """
    Create example evaluation sets with cases linked to traces.

    Returns dict mapping eval_set_id to {set_id, cases: [case_ids], agent_id}.
    """
    eval_sets = {}

    # Get agent IDs from saved_traces keys
    agent_ids = list(saved_traces.keys())
    if len(agent_ids) < 3:
        return eval_sets

    research_agent_id = agent_ids[0]
    code_agent_id = agent_ids[1]
    support_agent_id = agent_ids[2]

    # Eval Set 1: Response Quality Eval (for Research Assistant)
    quality_set_id = store.create_evaluation_set(
        name="Response Quality Eval",
        description="Evaluate research response quality, relevance, and completeness",
        project_id=project_id,
        metrics=[
            {
                "name": "relevance",
                "framework": "builtin",
                "metric_type": "contains",
                "threshold": 0.8,
                "parameters": {"text": "climate"},
            },
            {
                "name": "completeness",
                "framework": "builtin",
                "metric_type": "regex",
                "threshold": 0.8,
                "parameters": {"pattern": r".{100,}"},  # At least 100 chars
            },
        ],
        default_threshold=0.8,
        pass_rate_threshold=0.8,
        tags=["quality", "research"],
    )

    quality_cases = []
    research_traces = saved_traces.get(research_agent_id, [])
    for i, trace in enumerate(research_traces[:4]):  # First 4 non-error traces
        if not trace.error:
            case_id = store.add_evaluation_case(
                set_id=quality_set_id,
                name=f"research_case_{i + 1}",
                input_data=trace.input or {},
                expected_output=trace.output,
                source_trace_id=str(trace.id),
                tags=["research"],
            )
            quality_cases.append(case_id)

    eval_sets[quality_set_id] = {
        "set_id": quality_set_id,
        "cases": quality_cases,
        "agent_id": research_agent_id,
    }

    # Eval Set 2: Code Generation Eval (for Code Helper)
    code_set_id = store.create_evaluation_set(
        name="Code Generation Eval",
        description="Evaluate generated code quality and correctness",
        project_id=project_id,
        metrics=[
            {
                "name": "has_function_def",
                "framework": "builtin",
                "metric_type": "contains",
                "threshold": 1.0,
                "parameters": {"text": "def "},
            },
            {
                "name": "has_return",
                "framework": "builtin",
                "metric_type": "contains",
                "threshold": 0.8,
                "parameters": {"text": "return"},
            },
        ],
        default_threshold=0.8,
        pass_rate_threshold=0.75,
        tags=["code", "generation"],
    )

    code_cases = []
    code_traces = saved_traces.get(code_agent_id, [])
    for i, trace in enumerate(code_traces[:3]):  # First 3 non-error traces
        if not trace.error:
            case_id = store.add_evaluation_case(
                set_id=code_set_id,
                name=f"code_case_{i + 1}",
                input_data=trace.input or {},
                expected_output=trace.output,
                source_trace_id=str(trace.id),
                tags=["code"],
            )
            code_cases.append(case_id)

    eval_sets[code_set_id] = {
        "set_id": code_set_id,
        "cases": code_cases,
        "agent_id": code_agent_id,
    }

    # Eval Set 3: Safety & Compliance Eval (for Customer Support)
    safety_set_id = store.create_evaluation_set(
        name="Safety & Compliance Eval",
        description="Evaluate support responses for safety and compliance",
        project_id=project_id,
        metrics=[
            {
                "name": "no_pii",
                "framework": "builtin",
                "metric_type": "regex",
                "threshold": 1.0,
                "parameters": {"pattern": r"^(?!.*\b\d{3}-\d{2}-\d{4}\b).*$"},  # No SSN pattern
            },
            {
                "name": "professional_tone",
                "framework": "builtin",
                "metric_type": "contains",
                "threshold": 0.7,
                "parameters": {"text": "apologize"},
            },
        ],
        default_threshold=0.8,
        pass_rate_threshold=0.8,
        tags=["safety", "compliance", "support"],
    )

    safety_cases = []
    support_traces = saved_traces.get(support_agent_id, [])
    for i, trace in enumerate(support_traces[:3]):  # First 3 traces
        if not trace.error:
            case_id = store.add_evaluation_case(
                set_id=safety_set_id,
                name=f"safety_case_{i + 1}",
                input_data=trace.input or {},
                expected_output=trace.output,
                source_trace_id=str(trace.id),
                tags=["safety"],
            )
            safety_cases.append(case_id)

    eval_sets[safety_set_id] = {
        "set_id": safety_set_id,
        "cases": safety_cases,
        "agent_id": support_agent_id,
    }

    return eval_sets


def _create_example_eval_runs(
    store: SQLiteTraceStore,
    eval_sets: dict[str, dict],
    _saved_traces: dict[str, list[AgentRun]],
) -> None:
    """
    Create example evaluation runs with results for each eval set.

    Creates mix of passing and failing runs to demonstrate all states.
    """
    from datetime import UTC, datetime, timedelta

    base_time = datetime.now(UTC)

    for set_id, set_info in eval_sets.items():
        cases = set_info["cases"]
        if not cases:
            continue

        # Create Run 1: Mix of pass/fail
        run1_id = store.create_evaluation_run(set_id)
        store.update_evaluation_run(run1_id, status="running")

        passed_count = 0
        failed_count = 0

        for i, case_id in enumerate(cases):
            # Alternate pass/fail to show both states
            passed = i % 3 != 2  # Every 3rd case fails

            scores = [
                {
                    "metric_name": "metric_1",
                    "framework": "builtin",
                    "score": 0.9 if passed else 0.5,
                    "threshold": 0.8,
                    "passed": passed,
                    "reason": "Meets threshold" if passed else "Below threshold",
                    "details": {},
                },
            ]

            store.save_evaluation_result(
                run_id=run1_id,
                case_id=case_id,
                scores=scores,
                passed=passed,
                overall_score=0.9 if passed else 0.5,
                duration_ms=150.0 + i * 50,
            )

            if passed:
                passed_count += 1
            else:
                failed_count += 1

        total = passed_count + failed_count
        pass_rate = passed_count / total if total > 0 else 0

        store.update_evaluation_run(
            run1_id,
            status="completed",
            passed_cases=passed_count,
            failed_cases=failed_count,
            overall_pass_rate=pass_rate,
            passed=pass_rate >= 0.8,  # 80% threshold
            completed_at=(base_time - timedelta(hours=1)).isoformat(),
            duration_ms=500.0 + len(cases) * 100,
        )

        # Create Run 2 for first eval set only: All passing
        if set_id == list(eval_sets.keys())[0]:
            run2_id = store.create_evaluation_run(set_id)
            store.update_evaluation_run(run2_id, status="running")

            for case_id in cases:
                scores = [
                    {
                        "metric_name": "metric_1",
                        "framework": "builtin",
                        "score": 0.95,
                        "threshold": 0.8,
                        "passed": True,
                        "reason": "Excellent match",
                        "details": {},
                    },
                ]

                store.save_evaluation_result(
                    run_id=run2_id,
                    case_id=case_id,
                    scores=scores,
                    passed=True,
                    overall_score=0.95,
                    duration_ms=120.0,
                )

            store.update_evaluation_run(
                run2_id,
                status="completed",
                passed_cases=len(cases),
                failed_cases=0,
                overall_pass_rate=1.0,
                passed=True,
                completed_at=base_time.isoformat(),
                duration_ms=400.0,
            )


def get_source_for_location(location: InitLocation, base_path: Path | None = None) -> str:
    """
    Get the source string for a location.

    Args:
        location: The initialization location.
        base_path: Base path for local (defaults to cwd).

    Returns:
        Source string suitable for TraceLoader.from_source().
    """
    if location == InitLocation.GLOBAL:
        db_path = get_global_dir() / "traces.db"
    else:
        db_path = get_local_dir(base_path) / "traces.db"

    return f"sqlite://{db_path}"


def needs_setup() -> bool:
    """
    Check if TraceCraft needs initial setup.

    Returns:
        True if no config or database exists anywhere.
    """
    return not config_exists() and not database_exists()
