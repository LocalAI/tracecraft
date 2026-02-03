"""
Initialization utilities for TraceCraft.

Provides functions to set up directories, databases, and configuration files
for first-time users or new projects.
"""

from __future__ import annotations

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
    Create example data including project and traces.

    This provides users with sample data to explore TraceCraft features.
    """
    from datetime import UTC, datetime

    from tracecraft.storage.sqlite import SQLiteTraceStore

    store = SQLiteTraceStore(database_path)
    try:
        # 1. Create Example Project
        project_id = store.create_project(
            name="Example Project",
            description="Demo project with sample traces. "
            "Explore this to see TraceCraft features in action.",
        )

        # 2. Generate and save traces
        base_time = datetime.now(UTC)
        traces = _generate_example_traces(base_time)

        for trace in traces:
            store.save(trace, project_id=project_id)

    except Exception:  # noqa: BLE001  # nosec B110
        # If example data creation fails, don't block initialization
        pass
    finally:
        store.close()


def _generate_example_traces(base_time: datetime) -> list[AgentRun]:
    """
    Generate example traces for demonstration.

    Returns list of AgentRun objects.
    """
    from datetime import timedelta
    from uuid import uuid4

    from tracecraft.core.models import AgentRun, Step, StepType

    traces: list[AgentRun] = []

    # Trace 1: Climate Research Query (RAG success)
    t1_id = uuid4()
    t1_s1_id = uuid4()
    t1_s2_id = uuid4()
    t1_s3_id = uuid4()
    traces.append(
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
                "growing seasons."
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
                    inputs={"prompt": "Analyze and expand this query for retrieval"},
                    outputs={"expanded_query": "climate change agriculture impacts"},
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
                    outputs={"documents": ["doc_1.pdf", "doc_2.pdf"], "scores": [0.92, 0.87]},
                    attributes={"index": "climate_research", "retrieved_count": 2},
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
                    inputs={"context": "[Retrieved documents...]", "query": "Climate impacts?"},
                    outputs={"answer": "Climate change affects agriculture through..."},
                ),
            ],
        )
    )

    # Trace 2: Python Code Generation
    t2_id = uuid4()
    traces.append(
        AgentRun(
            id=t2_id,
            name="Python Function Generation",
            description="Generate a Python function with tests",
            start_time=base_time - timedelta(hours=4),
            end_time=base_time - timedelta(hours=4) + timedelta(seconds=3),
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
                    trace_id=t2_id,
                    type=StepType.LLM,
                    name="code_generation",
                    start_time=base_time - timedelta(hours=4),
                    duration_ms=2000.0,
                    model_name="claude-3-5-sonnet-20241022",
                    model_provider="anthropic",
                    input_tokens=150,
                    output_tokens=800,
                    cost_usd=0.0195,
                    inputs={"request": "Write a function to calculate fibonacci numbers"},
                    outputs={"code": "def fibonacci(n): ..."},
                ),
                Step(
                    id=uuid4(),
                    trace_id=t2_id,
                    type=StepType.TOOL,
                    name="code_execution",
                    start_time=base_time - timedelta(hours=4) + timedelta(milliseconds=2000),
                    duration_ms=1200.0,
                    inputs={"code": "def fibonacci(n): ...", "test_cases": [[5], [10]]},
                    outputs={"results": [5, 55], "success": True},
                    attributes={"runtime": "python3.11", "sandbox": True},
                ),
            ],
        )
    )

    # Trace 3: Customer Support Query
    t3_id = uuid4()
    traces.append(
        AgentRun(
            id=t3_id,
            name="Order Status Inquiry",
            description="Customer asking about order status",
            start_time=base_time - timedelta(hours=3),
            end_time=base_time - timedelta(hours=3) + timedelta(seconds=2),
            duration_ms=2500.0,
            total_tokens=780,
            total_cost_usd=0.0045,
            tags=["support", "order"],
            session_id="session_cust_123",
            user_id="user_456",
            input={"message": "Where is my order #12345?"},
            output={"response": "Your order #12345 shipped yesterday and will arrive by Friday."},
            steps=[
                Step(
                    id=uuid4(),
                    trace_id=t3_id,
                    type=StepType.MEMORY,
                    name="load_customer_context",
                    start_time=base_time - timedelta(hours=3),
                    duration_ms=200.0,
                    inputs={"user_id": "user_456", "session_id": "session_cust_123"},
                    outputs={"context": {"previous_orders": ["#12345"], "name": "John"}},
                    attributes={"memory_type": "session"},
                ),
                Step(
                    id=uuid4(),
                    trace_id=t3_id,
                    type=StepType.LLM,
                    name="response_generation",
                    start_time=base_time - timedelta(hours=3) + timedelta(milliseconds=200),
                    duration_ms=1800.0,
                    model_name="gpt-4o-mini",
                    model_provider="openai",
                    input_tokens=280,
                    output_tokens=500,
                    cost_usd=0.0025,
                    inputs={"message": "Where is my order #12345?", "context": "..."},
                    outputs={"response": "Your order #12345 shipped yesterday..."},
                ),
            ],
        )
    )

    # Trace 4: Error case - API Timeout
    t4_id = uuid4()
    traces.append(
        AgentRun(
            id=t4_id,
            name="API Timeout Error",
            description="Research query that failed due to API timeout",
            start_time=base_time - timedelta(hours=2),
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
                    trace_id=t4_id,
                    type=StepType.LLM,
                    name="initial_analysis",
                    start_time=base_time - timedelta(hours=2),
                    duration_ms=30500.0,
                    model_name="gpt-4o",
                    model_provider="openai",
                    error="Request timed out after 30 seconds",
                    error_type="APITimeoutError",
                    inputs={"prompt": "Analyze this complex query..."},
                    outputs={},
                ),
            ],
        )
    )

    # Trace 5: Debug Session (iterative)
    t5_id = uuid4()
    traces.append(
        AgentRun(
            id=t5_id,
            name="Debug Session",
            description="Iterative debugging of code issue",
            start_time=base_time - timedelta(hours=1),
            duration_ms=8500.0,
            total_tokens=3200,
            total_cost_usd=0.0523,
            tags=["code", "debug", "iterative"],
            input={"code": "def broken_sort(arr): ...", "error": "IndexError"},
            output={"fixed_code": "def sort(arr): ...", "explanation": "Fixed off-by-one error"},
            steps=[
                Step(
                    id=uuid4(),
                    trace_id=t5_id,
                    type=StepType.LLM,
                    name="error_analysis",
                    start_time=base_time - timedelta(hours=1),
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
                    trace_id=t5_id,
                    type=StepType.TOOL,
                    name="test_run",
                    start_time=base_time - timedelta(hours=1) + timedelta(milliseconds=1500),
                    duration_ms=800.0,
                    inputs={"code": "proposed_fix"},
                    outputs={"success": True, "tests_passed": 5},
                ),
            ],
        )
    )

    return traces


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
