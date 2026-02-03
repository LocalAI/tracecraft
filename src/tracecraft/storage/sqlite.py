"""
SQLite storage backend for TraceCraft.

Provides queryable local storage with SQL capabilities.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tracecraft.storage.base import BaseTraceStore, TraceQuery

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun

logger = logging.getLogger(__name__)

# Schema version for migrations
SCHEMA_VERSION = 5

SCHEMA_SQL = """
-- Agents table for organizing traces by agent (Added in schema v5)
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    project_id TEXT,
    agent_type TEXT,  -- e.g., 'langchain', 'openai', 'custom'
    config TEXT,  -- JSON config
    created_at TEXT NOT NULL,
    updated_at TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_agents_name ON agents(name);
CREATE INDEX IF NOT EXISTS idx_agents_project ON agents(project_id);

-- Traces table (run-level metadata)
CREATE TABLE IF NOT EXISTS traces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    start_time TEXT NOT NULL,
    end_time TEXT,
    duration_ms REAL,
    session_id TEXT,
    user_id TEXT,
    environment TEXT,
    total_tokens INTEGER DEFAULT 0,
    total_cost_usd REAL DEFAULT 0.0,
    error_count INTEGER DEFAULT 0,
    error TEXT,
    error_type TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    project_id TEXT,
    agent_id TEXT,  -- Link to agents table (Added in schema v5)

    -- JSON blob for full trace data
    data JSON NOT NULL,

    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE SET NULL
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_traces_name ON traces(name);
CREATE INDEX IF NOT EXISTS idx_traces_start_time ON traces(start_time DESC);
CREATE INDEX IF NOT EXISTS idx_traces_duration ON traces(duration_ms);
CREATE INDEX IF NOT EXISTS idx_traces_cost ON traces(total_cost_usd);
CREATE INDEX IF NOT EXISTS idx_traces_error ON traces(error_count);
CREATE INDEX IF NOT EXISTS idx_traces_session ON traces(session_id);
CREATE INDEX IF NOT EXISTS idx_traces_user ON traces(user_id);
CREATE INDEX IF NOT EXISTS idx_traces_environment ON traces(environment);
CREATE INDEX IF NOT EXISTS idx_traces_project ON traces(project_id);
CREATE INDEX IF NOT EXISTS idx_traces_agent ON traces(agent_id);

-- Tags table (many-to-many)
CREATE TABLE IF NOT EXISTS trace_tags (
    trace_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (trace_id, tag),
    FOREIGN KEY (trace_id) REFERENCES traces(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_trace_tags_tag ON trace_tags(tag);

-- Steps table (denormalized for querying)
CREATE TABLE IF NOT EXISTS steps (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    parent_id TEXT,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    duration_ms REAL,
    model_name TEXT,
    model_provider TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd REAL,
    error TEXT,
    error_type TEXT,
    FOREIGN KEY (trace_id) REFERENCES traces(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_steps_trace ON steps(trace_id);
CREATE INDEX IF NOT EXISTS idx_steps_type ON steps(type);
CREATE INDEX IF NOT EXISTS idx_steps_model ON steps(model_name);
CREATE INDEX IF NOT EXISTS idx_steps_error ON steps(error);

-- Projects table for organizing traces
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    settings TEXT
);

CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name);

-- Trace versions table for versioning
CREATE TABLE IF NOT EXISTS trace_versions (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    version_type TEXT NOT NULL CHECK(version_type IN ('original', 'playground', 'manual')),
    parent_version_id TEXT,
    created_at TEXT NOT NULL,
    created_by TEXT,
    notes TEXT,
    data TEXT NOT NULL,
    FOREIGN KEY (trace_id) REFERENCES traces(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_version_id) REFERENCES trace_versions(id) ON DELETE SET NULL,
    UNIQUE(trace_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_trace_versions_trace ON trace_versions(trace_id);
CREATE INDEX IF NOT EXISTS idx_trace_versions_type ON trace_versions(version_type);

-- Playground iterations table
CREATE TABLE IF NOT EXISTS playground_iterations (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    trace_version_id TEXT,
    step_id TEXT NOT NULL,
    iteration_number INTEGER NOT NULL,
    prompt TEXT NOT NULL,
    output TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    duration_ms REAL DEFAULT 0.0,
    notes TEXT,
    is_best BOOLEAN DEFAULT FALSE,
    created_at TEXT NOT NULL,
    FOREIGN KEY (trace_id) REFERENCES traces(id) ON DELETE CASCADE,
    FOREIGN KEY (trace_version_id) REFERENCES trace_versions(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_iterations_trace ON playground_iterations(trace_id);
CREATE INDEX IF NOT EXISTS idx_iterations_step ON playground_iterations(step_id);
CREATE INDEX IF NOT EXISTS idx_iterations_version ON playground_iterations(trace_version_id);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

-- =========================================================================
-- Evaluation Tables (Added in schema v3)
-- =========================================================================

-- Evaluation Sets: Collection of test cases with metric configuration
CREATE TABLE IF NOT EXISTS evaluation_sets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    project_id TEXT,
    metrics_config TEXT NOT NULL DEFAULT '[]',  -- JSON array of EvaluationMetricConfig
    default_threshold REAL DEFAULT 0.7,
    pass_rate_threshold REAL DEFAULT 0.8,
    tags TEXT,  -- JSON array
    created_at TEXT NOT NULL,
    updated_at TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_eval_sets_name ON evaluation_sets(name);
CREATE INDEX IF NOT EXISTS idx_eval_sets_project ON evaluation_sets(project_id);

-- Evaluation Cases: Individual test cases within a set
CREATE TABLE IF NOT EXISTS evaluation_cases (
    id TEXT PRIMARY KEY,
    evaluation_set_id TEXT NOT NULL,
    name TEXT NOT NULL,
    input TEXT NOT NULL,  -- JSON
    expected_output TEXT,  -- JSON
    actual_output TEXT,  -- JSON: Actual output from trace/step for comparison
    retrieval_context TEXT,  -- JSON array
    source_trace_id TEXT,
    source_step_id TEXT,
    tags TEXT,  -- JSON array
    created_at TEXT NOT NULL,
    FOREIGN KEY (evaluation_set_id) REFERENCES evaluation_sets(id) ON DELETE CASCADE,
    FOREIGN KEY (source_trace_id) REFERENCES traces(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_eval_cases_set ON evaluation_cases(evaluation_set_id);
CREATE INDEX IF NOT EXISTS idx_eval_cases_source ON evaluation_cases(source_trace_id);

-- Evaluation Runs: Single execution of an evaluation set
CREATE TABLE IF NOT EXISTS evaluation_runs (
    id TEXT PRIMARY KEY,
    evaluation_set_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    total_cases INTEGER DEFAULT 0,
    passed_cases INTEGER DEFAULT 0,
    failed_cases INTEGER DEFAULT 0,
    overall_pass_rate REAL,
    metric_averages TEXT,  -- JSON object
    passed BOOLEAN,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    duration_ms REAL,
    error TEXT,
    FOREIGN KEY (evaluation_set_id) REFERENCES evaluation_sets(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_eval_runs_set ON evaluation_runs(evaluation_set_id);
CREATE INDEX IF NOT EXISTS idx_eval_runs_status ON evaluation_runs(status);

-- Evaluation Results: Per-case results within a run
CREATE TABLE IF NOT EXISTS evaluation_results (
    id TEXT PRIMARY KEY,
    evaluation_run_id TEXT NOT NULL,
    evaluation_case_id TEXT NOT NULL,
    trace_id TEXT,
    actual_output TEXT,  -- JSON
    scores TEXT NOT NULL,  -- JSON array of MetricScore
    overall_score REAL,
    passed BOOLEAN NOT NULL,
    duration_ms REAL,
    error TEXT,
    FOREIGN KEY (evaluation_run_id) REFERENCES evaluation_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (evaluation_case_id) REFERENCES evaluation_cases(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_eval_results_run ON evaluation_results(evaluation_run_id);
CREATE INDEX IF NOT EXISTS idx_eval_results_case ON evaluation_results(evaluation_case_id);
CREATE INDEX IF NOT EXISTS idx_eval_results_passed ON evaluation_results(passed);
"""


class SQLiteTraceStore(BaseTraceStore):
    """
    SQLite-based trace storage.

    Features:
    - Single-file database
    - SQL queries on trace metadata
    - WAL mode for better concurrency
    - Automatic schema migrations
    - Full-text search on trace data

    Example:
        from tracecraft.storage.sqlite import SQLiteTraceStore

        store = SQLiteTraceStore("traces.db")

        # Save a trace
        store.save(run)

        # Query traces
        expensive = store.query(TraceQuery(min_cost_usd=0.10))
        errors = store.query(TraceQuery(has_error=True))

        # Raw SQL queries
        results = store.execute_sql(
            "SELECT name, total_cost_usd FROM traces WHERE duration_ms > ?",
            (1000,)
        )
    """

    def __init__(
        self,
        path: str | Path,
        *,
        wal_mode: bool = True,
        busy_timeout_ms: int = 5000,
    ) -> None:
        """
        Initialize SQLite storage.

        Args:
            path: Path to SQLite database file.
            wal_mode: Enable WAL mode for better concurrency.
            busy_timeout_ms: Timeout for locked database.
        """
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self._conn: sqlite3.Connection | None = None
        self._wal_mode = wal_mode
        self._busy_timeout_ms = busy_timeout_ms

        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.path),
                check_same_thread=False,
                timeout=self._busy_timeout_ms / 1000,
            )
            self._conn.row_factory = sqlite3.Row

            if self._wal_mode:
                self._conn.execute("PRAGMA journal_mode=WAL")

            self._conn.execute("PRAGMA foreign_keys=ON")

        return self._conn

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Cursor]:
        """Context manager for database transactions."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._transaction() as cursor:
            # Check if this is an existing database that needs migration
            cursor.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='schema_version'
                """
            )
            schema_table_exists = cursor.fetchone() is not None

            if schema_table_exists:
                # Check version and migrate if needed BEFORE running full schema
                cursor.execute("SELECT version FROM schema_version LIMIT 1")
                row = cursor.fetchone()
                if row and row["version"] < SCHEMA_VERSION:
                    self._migrate_schema(cursor, row["version"])

            # Run schema SQL (uses IF NOT EXISTS, safe to run on existing DBs)
            cursor.executescript(SCHEMA_SQL)

            # Update version if needed
            cursor.execute("SELECT version FROM schema_version LIMIT 1")
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (SCHEMA_VERSION,),
                )

    def _migrate_v1_to_v2(self, cursor: sqlite3.Cursor) -> None:
        """Migrate from v1 to v2: add projects, versions, iterations tables."""
        logger.info("Migrating schema from v1 to v2: adding projects, versions, iterations")

        # Create projects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                settings TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name)")

        # Create trace_versions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trace_versions (
                id TEXT PRIMARY KEY,
                trace_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                version_type TEXT NOT NULL,
                parent_version_id TEXT,
                created_at TEXT NOT NULL,
                created_by TEXT,
                notes TEXT,
                data TEXT NOT NULL,
                FOREIGN KEY (trace_id) REFERENCES traces(id) ON DELETE CASCADE,
                UNIQUE(trace_id, version_number)
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_trace_versions_trace ON trace_versions(trace_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_trace_versions_type ON trace_versions(version_type)"
        )

        # Create playground_iterations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS playground_iterations (
                id TEXT PRIMARY KEY,
                trace_id TEXT NOT NULL,
                trace_version_id TEXT,
                step_id TEXT NOT NULL,
                iteration_number INTEGER NOT NULL,
                prompt TEXT NOT NULL,
                output TEXT,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                duration_ms REAL DEFAULT 0.0,
                notes TEXT,
                is_best BOOLEAN DEFAULT FALSE,
                created_at TEXT NOT NULL,
                FOREIGN KEY (trace_id) REFERENCES traces(id) ON DELETE CASCADE
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_iterations_trace ON playground_iterations(trace_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_iterations_step ON playground_iterations(step_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_iterations_version ON playground_iterations(trace_version_id)"
        )

        # Add project_id column to traces (nullable for backward compat)
        cursor.execute("ALTER TABLE traces ADD COLUMN project_id TEXT")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_traces_project ON traces(project_id)")

    def _migrate_v2_to_v3(self, cursor: sqlite3.Cursor) -> None:
        """Migrate from v2 to v3: add evaluation tables."""
        logger.info("Migrating schema from v2 to v3: adding evaluation tables")

        # Create evaluation_sets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluation_sets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                project_id TEXT,
                metrics_config TEXT NOT NULL DEFAULT '[]',
                default_threshold REAL DEFAULT 0.7,
                pass_rate_threshold REAL DEFAULT 0.8,
                tags TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_eval_sets_name ON evaluation_sets(name)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_eval_sets_project ON evaluation_sets(project_id)"
        )

        # Create evaluation_cases table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluation_cases (
                id TEXT PRIMARY KEY,
                evaluation_set_id TEXT NOT NULL,
                name TEXT NOT NULL,
                input TEXT NOT NULL,
                expected_output TEXT,
                actual_output TEXT,
                retrieval_context TEXT,
                source_trace_id TEXT,
                source_step_id TEXT,
                tags TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (evaluation_set_id) REFERENCES evaluation_sets(id) ON DELETE CASCADE,
                FOREIGN KEY (source_trace_id) REFERENCES traces(id) ON DELETE SET NULL
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_eval_cases_set ON evaluation_cases(evaluation_set_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_eval_cases_source ON evaluation_cases(source_trace_id)"
        )

        # Create evaluation_runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluation_runs (
                id TEXT PRIMARY KEY,
                evaluation_set_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                total_cases INTEGER DEFAULT 0,
                passed_cases INTEGER DEFAULT 0,
                failed_cases INTEGER DEFAULT 0,
                overall_pass_rate REAL,
                metric_averages TEXT,
                passed BOOLEAN,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                duration_ms REAL,
                error TEXT,
                FOREIGN KEY (evaluation_set_id) REFERENCES evaluation_sets(id) ON DELETE CASCADE
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_eval_runs_set ON evaluation_runs(evaluation_set_id)"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_eval_runs_status ON evaluation_runs(status)")

        # Create evaluation_results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluation_results (
                id TEXT PRIMARY KEY,
                evaluation_run_id TEXT NOT NULL,
                evaluation_case_id TEXT NOT NULL,
                trace_id TEXT,
                actual_output TEXT,
                scores TEXT NOT NULL,
                overall_score REAL,
                passed BOOLEAN NOT NULL,
                duration_ms REAL,
                error TEXT,
                FOREIGN KEY (evaluation_run_id) REFERENCES evaluation_runs(id) ON DELETE CASCADE,
                FOREIGN KEY (evaluation_case_id) REFERENCES evaluation_cases(id) ON DELETE CASCADE
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_eval_results_run ON evaluation_results(evaluation_run_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_eval_results_case ON evaluation_results(evaluation_case_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_eval_results_passed ON evaluation_results(passed)"
        )

    def _migrate_v3_to_v4(self, cursor: sqlite3.Cursor) -> None:
        """Migrate from v3 to v4: add actual_output column to evaluation_cases."""
        logger.info("Migrating schema from v3 to v4: adding actual_output to evaluation_cases")

        # Add actual_output column to evaluation_cases table
        with suppress(Exception):
            cursor.execute("ALTER TABLE evaluation_cases ADD COLUMN actual_output TEXT")

    def _migrate_v4_to_v5(self, cursor: sqlite3.Cursor) -> None:
        """Migrate from v4 to v5: add agents table and agent_id to traces."""
        logger.info("Migrating schema from v4 to v5: adding agents table and agent_id")

        # Create agents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                project_id TEXT,
                agent_type TEXT,
                config TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_agents_name ON agents(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_agents_project ON agents(project_id)")

        # Add agent_id column to traces table
        try:
            cursor.execute("ALTER TABLE traces ADD COLUMN agent_id TEXT")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_traces_agent ON traces(agent_id)")
        except Exception:
            # Column may already exist
            pass

    def _migrate_schema(self, cursor: sqlite3.Cursor, from_version: int) -> None:
        """Run schema migrations."""
        logger.info(f"Migrating schema from v{from_version} to v{SCHEMA_VERSION}")

        if from_version < 2:
            self._migrate_v1_to_v2(cursor)

        if from_version < 3:
            self._migrate_v2_to_v3(cursor)

        if from_version < 4:
            self._migrate_v3_to_v4(cursor)

        if from_version < 5:
            self._migrate_v4_to_v5(cursor)

        cursor.execute(
            "UPDATE schema_version SET version = ?",
            (SCHEMA_VERSION,),
        )

    def _get_schema_version(self) -> int:
        """Get the current schema version."""
        with self._transaction() as cursor:
            cursor.execute("SELECT version FROM schema_version LIMIT 1")
            row = cursor.fetchone()
            return row["version"] if row else 0

    def save(self, run: AgentRun, project_id: str | None = None) -> None:
        """Save a trace to SQLite."""
        # Check for project_id in attributes if not explicitly provided
        if project_id is None:
            project_id = run.attributes.get("project_id") if run.attributes else None

        with self._transaction() as cursor:
            # Insert main trace record
            cursor.execute(
                """
                INSERT OR REPLACE INTO traces (
                    id, name, description, start_time, end_time, duration_ms,
                    session_id, user_id, environment, total_tokens, total_cost_usd,
                    error_count, error, error_type, project_id, data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(run.id),
                    run.name,
                    run.description,
                    run.start_time.isoformat(),
                    run.end_time.isoformat() if run.end_time else None,
                    run.duration_ms,
                    run.session_id,
                    run.user_id,
                    run.environment,
                    run.total_tokens,
                    run.total_cost_usd,
                    run.error_count,
                    run.error,
                    run.error_type,
                    project_id,
                    json.dumps(run.model_dump(mode="json"), default=str),
                ),
            )

            # Insert tags
            cursor.execute("DELETE FROM trace_tags WHERE trace_id = ?", (str(run.id),))
            for tag in run.tags:
                cursor.execute(
                    "INSERT INTO trace_tags (trace_id, tag) VALUES (?, ?)",
                    (str(run.id), tag),
                )

            # Insert steps (flattened)
            cursor.execute("DELETE FROM steps WHERE trace_id = ?", (str(run.id),))
            self._insert_steps(cursor, str(run.id), run.steps)

    def _insert_steps(
        self,
        cursor: sqlite3.Cursor,
        trace_id: str,
        steps: list[Any],
        parent_id: str | None = None,
    ) -> None:
        """Recursively insert steps."""
        for step in steps:
            cursor.execute(
                """
                INSERT INTO steps (
                    id, trace_id, parent_id, type, name, start_time, end_time,
                    duration_ms, model_name, model_provider, input_tokens,
                    output_tokens, cost_usd, error, error_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(step.id),
                    trace_id,
                    parent_id,
                    step.type.value,
                    step.name,
                    step.start_time.isoformat(),
                    step.end_time.isoformat() if step.end_time else None,
                    step.duration_ms,
                    step.model_name,
                    step.model_provider,
                    step.input_tokens,
                    step.output_tokens,
                    step.cost_usd,
                    step.error,
                    step.error_type,
                ),
            )

            # Recurse for children
            if step.children:
                self._insert_steps(cursor, trace_id, step.children, str(step.id))

    def get(self, trace_id: str) -> AgentRun | None:
        """Get a trace by ID."""
        from tracecraft.core.models import AgentRun

        with self._transaction() as cursor:
            cursor.execute("SELECT data FROM traces WHERE id = ?", (trace_id,))
            row = cursor.fetchone()

            if row is None:
                return None

            return AgentRun.model_validate_json(row["data"])

    def query(self, query: TraceQuery) -> list[AgentRun]:
        """Query traces with filters."""
        from tracecraft.core.models import AgentRun

        sql = "SELECT data FROM traces WHERE 1=1"
        params: list[Any] = []

        if query.name:
            sql += " AND name = ?"
            params.append(query.name)

        if query.name_contains:
            sql += " AND name LIKE ?"
            params.append(f"%{query.name_contains}%")

        if query.has_error is not None:
            if query.has_error:
                sql += " AND error_count > 0"
            else:
                sql += " AND error_count = 0"

        if query.min_duration_ms is not None:
            sql += " AND duration_ms >= ?"
            params.append(query.min_duration_ms)

        if query.max_duration_ms is not None:
            sql += " AND duration_ms <= ?"
            params.append(query.max_duration_ms)

        if query.min_cost_usd is not None:
            sql += " AND total_cost_usd >= ?"
            params.append(query.min_cost_usd)

        if query.max_cost_usd is not None:
            sql += " AND total_cost_usd <= ?"
            params.append(query.max_cost_usd)

        if query.session_id:
            sql += " AND session_id = ?"
            params.append(query.session_id)

        if query.user_id:
            sql += " AND user_id = ?"
            params.append(query.user_id)

        if query.environment:
            sql += " AND environment = ?"
            params.append(query.environment)

        if query.project_id:
            sql += " AND project_id = ?"
            params.append(query.project_id)

        if query.start_time_after:
            sql += " AND start_time >= ?"
            params.append(query.start_time_after)

        if query.start_time_before:
            sql += " AND start_time <= ?"
            params.append(query.start_time_before)

        if query.tags:
            # Subquery for tags (safe: using parameterized query with ? placeholders)
            tag_placeholders = ",".join("?" for _ in query.tags)
            sql += f"""
                AND id IN (
                    SELECT trace_id FROM trace_tags
                    WHERE tag IN ({tag_placeholders})
                    GROUP BY trace_id
                    HAVING COUNT(DISTINCT tag) = ?
                )
            """  # nosec B608 - parameterized query
            params.extend(query.tags)
            params.append(len(query.tags))

        # Order and pagination
        # Validate order_by to prevent SQL injection
        allowed_order_cols = {"start_time", "duration_ms", "total_cost_usd", "name", "error_count"}
        order_col = query.order_by if query.order_by in allowed_order_cols else "start_time"
        order_dir = "DESC" if query.order_desc else "ASC"
        sql += f" ORDER BY {order_col} {order_dir}"
        sql += " LIMIT ? OFFSET ?"
        params.extend([query.limit, query.offset])

        with self._transaction() as cursor:
            cursor.execute(sql, params)
            return [AgentRun.model_validate_json(row["data"]) for row in cursor.fetchall()]

    def list_all(self, limit: int = 100, offset: int = 0) -> list[AgentRun]:
        """List all traces with pagination."""
        return self.query(TraceQuery(limit=limit, offset=offset))

    def delete(self, trace_id: str) -> bool:
        """Delete a trace by ID."""
        with self._transaction() as cursor:
            cursor.execute("DELETE FROM traces WHERE id = ?", (trace_id,))
            return cursor.rowcount > 0

    def count(self, query: TraceQuery | None = None) -> int:
        """Count traces matching query."""
        if query is None:
            sql = "SELECT COUNT(*) FROM traces"
            params: list[Any] = []
        else:
            # Build WHERE clause (same as query method)
            sql = "SELECT COUNT(*) FROM traces WHERE 1=1"
            params = []

            if query.name:
                sql += " AND name = ?"
                params.append(query.name)

            if query.name_contains:
                sql += " AND name LIKE ?"
                params.append(f"%{query.name_contains}%")

            if query.has_error is not None:
                if query.has_error:
                    sql += " AND error_count > 0"
                else:
                    sql += " AND error_count = 0"

            if query.min_duration_ms is not None:
                sql += " AND duration_ms >= ?"
                params.append(query.min_duration_ms)

            if query.max_duration_ms is not None:
                sql += " AND duration_ms <= ?"
                params.append(query.max_duration_ms)

            if query.min_cost_usd is not None:
                sql += " AND total_cost_usd >= ?"
                params.append(query.min_cost_usd)

            if query.max_cost_usd is not None:
                sql += " AND total_cost_usd <= ?"
                params.append(query.max_cost_usd)

            if query.session_id:
                sql += " AND session_id = ?"
                params.append(query.session_id)

            if query.user_id:
                sql += " AND user_id = ?"
                params.append(query.user_id)

            if query.environment:
                sql += " AND environment = ?"
                params.append(query.environment)

            if query.project_id:
                sql += " AND project_id = ?"
                params.append(query.project_id)

            if query.start_time_after:
                sql += " AND start_time >= ?"
                params.append(query.start_time_after)

            if query.start_time_before:
                sql += " AND start_time <= ?"
                params.append(query.start_time_before)

            if query.tags:
                tag_placeholders = ",".join("?" for _ in query.tags)
                sql += f"""
                    AND id IN (
                        SELECT trace_id FROM trace_tags
                        WHERE tag IN ({tag_placeholders})
                        GROUP BY trace_id
                        HAVING COUNT(DISTINCT tag) = ?
                    )
                """  # nosec B608 - parameterized query with placeholders
                params.extend(query.tags)
                params.append(len(query.tags))

        with self._transaction() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchone()[0]

    def execute_sql(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        """
        Execute raw SQL query.

        For advanced queries not supported by TraceQuery.

        Example:
            # Find most expensive models
            results = store.execute_sql('''
                SELECT model_name, SUM(cost_usd) as total_cost
                FROM steps
                WHERE model_name IS NOT NULL
                GROUP BY model_name
                ORDER BY total_cost DESC
                LIMIT 10
            ''')
        """
        with self._transaction() as cursor:
            cursor.execute(sql, params)
            if cursor.description is None:
                return []
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def vacuum(self) -> None:
        """Reclaim disk space after deletions."""
        conn = self._get_conn()
        conn.execute("VACUUM")

    def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        with self._transaction() as cursor:
            cursor.execute("SELECT COUNT(*) FROM traces")
            trace_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM steps")
            step_count = cursor.fetchone()[0]

            cursor.execute("SELECT SUM(total_tokens), SUM(total_cost_usd) FROM traces")
            row = cursor.fetchone()
            total_tokens = row[0] or 0
            total_cost = row[1] or 0.0

            # File size
            file_size = self.path.stat().st_size if self.path.exists() else 0

        return {
            "trace_count": trace_count,
            "step_count": step_count,
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost,
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2),
        }

    def get_model_usage(self) -> list[dict[str, Any]]:
        """Get usage statistics per model."""
        return self.execute_sql(
            """
            SELECT
                model_name,
                model_provider,
                COUNT(*) as call_count,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens,
                SUM(cost_usd) as total_cost,
                AVG(duration_ms) as avg_duration_ms
            FROM steps
            WHERE model_name IS NOT NULL
            GROUP BY model_name, model_provider
            ORDER BY total_cost DESC
            """
        )

    def get_error_summary(self) -> list[dict[str, Any]]:
        """Get summary of errors by type."""
        return self.execute_sql(
            """
            SELECT
                error_type,
                COUNT(*) as count,
                GROUP_CONCAT(DISTINCT name) as affected_traces
            FROM traces
            WHERE error IS NOT NULL
            GROUP BY error_type
            ORDER BY count DESC
            """
        )

    # =========================================================================
    # Project Management Methods
    # =========================================================================

    def create_project(
        self,
        name: str,
        description: str = "",
        settings: dict[str, Any] | None = None,
    ) -> str:
        """
        Create a new project.

        Args:
            name: Unique project name.
            description: Optional project description.
            settings: Optional JSON-serializable settings dict.

        Returns:
            The new project ID.

        Raises:
            sqlite3.IntegrityError: If project name already exists.
        """
        import uuid
        from datetime import UTC, datetime

        project_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        with self._transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO projects (id, name, description, created_at, updated_at, settings)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    name,
                    description,
                    now,
                    now,
                    json.dumps(settings) if settings else None,
                ),
            )

        return project_id

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        """Get a project by ID."""
        with self._transaction() as cursor:
            cursor.execute(
                "SELECT id, name, description, created_at, updated_at, settings FROM projects WHERE id = ?",
                (project_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "settings": json.loads(row["settings"]) if row["settings"] else None,
            }

    def get_project_by_name(self, name: str) -> dict[str, Any] | None:
        """Get a project by name."""
        with self._transaction() as cursor:
            cursor.execute(
                "SELECT id, name, description, created_at, updated_at, settings FROM projects WHERE name = ?",
                (name,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "settings": json.loads(row["settings"]) if row["settings"] else None,
            }

    def list_projects(self) -> list[dict[str, Any]]:
        """List all projects."""
        with self._transaction() as cursor:
            cursor.execute(
                "SELECT id, name, description, created_at, updated_at, settings FROM projects ORDER BY name"
            )
            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "settings": json.loads(row["settings"]) if row["settings"] else None,
                }
                for row in cursor.fetchall()
            ]

    def update_project(
        self,
        project_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> bool:
        """
        Update a project.

        Args:
            project_id: Project ID to update.
            name: New name (optional).
            description: New description (optional).
            settings: New settings (optional).

        Returns:
            True if project was updated, False if not found.
        """
        from datetime import UTC, datetime

        updates = []
        params: list[Any] = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if settings is not None:
            updates.append("settings = ?")
            params.append(json.dumps(settings))

        if not updates:
            return False

        updates.append("updated_at = ?")
        params.append(datetime.now(UTC).isoformat())
        params.append(project_id)

        with self._transaction() as cursor:
            cursor.execute(
                f"UPDATE projects SET {', '.join(updates)} WHERE id = ?",  # nosec B608
                params,
            )
            return cursor.rowcount > 0

    def delete_project(self, project_id: str) -> bool:
        """
        Delete a project.

        Note: Traces assigned to this project will have their project_id set to NULL.

        Returns:
            True if deleted, False if not found.
        """
        with self._transaction() as cursor:
            cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            return cursor.rowcount > 0

    def assign_trace_to_project(self, trace_id: str, project_id: str | None) -> bool:
        """
        Assign a trace to a project (or unassign if project_id is None).

        Returns:
            True if trace was updated, False if trace not found.
        """
        with self._transaction() as cursor:
            cursor.execute(
                "UPDATE traces SET project_id = ? WHERE id = ?",
                (project_id, trace_id),
            )
            return cursor.rowcount > 0

    def get_project_stats(self, project_id: str) -> dict[str, Any]:
        """Get statistics for a project."""
        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*) as trace_count,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(total_cost_usd), 0.0) as total_cost_usd,
                    COALESCE(SUM(error_count), 0) as error_count
                FROM traces
                WHERE project_id = ?
                """,
                (project_id,),
            )
            row = cursor.fetchone()

            return {
                "trace_count": row["trace_count"],
                "total_tokens": row["total_tokens"],
                "total_cost_usd": row["total_cost_usd"],
                "error_count": row["error_count"],
            }

    # =========================================================================
    # Version Management Methods
    # =========================================================================

    def create_version(
        self,
        trace_id: str,
        *,
        version_type: str = "playground",
        notes: str = "",
        modified_run: AgentRun | None = None,
        created_by: str | None = None,
        parent_version_id: str | None = None,
    ) -> str:
        """
        Create a new version of a trace.

        Args:
            trace_id: The trace to version.
            version_type: One of 'original', 'playground', 'manual'.
            notes: Optional notes about this version.
            modified_run: Modified AgentRun data (uses current trace if None).
            created_by: Optional user ID who created the version.
            parent_version_id: Optional parent version for branching.

        Returns:
            The new version ID.
        """
        import uuid
        from datetime import UTC, datetime

        version_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        with self._transaction() as cursor:
            # Get next version number
            cursor.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 FROM trace_versions WHERE trace_id = ?",
                (trace_id,),
            )
            version_number = cursor.fetchone()[0]

            # Get data to store
            if modified_run is not None:
                data = json.dumps(modified_run.model_dump(mode="json"), default=str)
            else:
                # Use current trace data
                cursor.execute("SELECT data FROM traces WHERE id = ?", (trace_id,))
                row = cursor.fetchone()
                if row is None:
                    raise ValueError(f"Trace {trace_id} not found")
                data = row["data"]

            cursor.execute(
                """
                INSERT INTO trace_versions (
                    id, trace_id, version_number, version_type, parent_version_id,
                    created_at, created_by, notes, data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    trace_id,
                    version_number,
                    version_type,
                    parent_version_id,
                    now,
                    created_by,
                    notes,
                    data,
                ),
            )

        return version_id

    def get_version(self, version_id: str) -> AgentRun | None:
        """Get the AgentRun stored in a version."""
        from tracecraft.core.models import AgentRun

        with self._transaction() as cursor:
            cursor.execute("SELECT data FROM trace_versions WHERE id = ?", (version_id,))
            row = cursor.fetchone()

            if row is None:
                return None

            return AgentRun.model_validate_json(row["data"])

    def get_version_metadata(self, version_id: str) -> dict[str, Any] | None:
        """Get version metadata without the full AgentRun data."""
        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT id, trace_id, version_number, version_type, parent_version_id,
                       created_at, created_by, notes
                FROM trace_versions WHERE id = ?
                """,
                (version_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return {
                "id": row["id"],
                "trace_id": row["trace_id"],
                "version_number": row["version_number"],
                "version_type": row["version_type"],
                "parent_version_id": row["parent_version_id"],
                "created_at": row["created_at"],
                "created_by": row["created_by"],
                "notes": row["notes"],
            }

    def list_versions(self, trace_id: str) -> list[dict[str, Any]]:
        """List all versions for a trace (sorted by version_number)."""
        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT id, trace_id, version_number, version_type, parent_version_id,
                       created_at, created_by, notes
                FROM trace_versions
                WHERE trace_id = ?
                ORDER BY version_number
                """,
                (trace_id,),
            )
            return [
                {
                    "id": row["id"],
                    "trace_id": row["trace_id"],
                    "version_number": row["version_number"],
                    "version_type": row["version_type"],
                    "parent_version_id": row["parent_version_id"],
                    "created_at": row["created_at"],
                    "created_by": row["created_by"],
                    "notes": row["notes"],
                }
                for row in cursor.fetchall()
            ]

    def get_latest_version(self, trace_id: str) -> dict[str, Any] | None:
        """Get the most recent version for a trace."""
        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT id, trace_id, version_number, version_type, parent_version_id,
                       created_at, created_by, notes
                FROM trace_versions
                WHERE trace_id = ?
                ORDER BY version_number DESC
                LIMIT 1
                """,
                (trace_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return {
                "id": row["id"],
                "trace_id": row["trace_id"],
                "version_number": row["version_number"],
                "version_type": row["version_type"],
                "parent_version_id": row["parent_version_id"],
                "created_at": row["created_at"],
                "created_by": row["created_by"],
                "notes": row["notes"],
            }

    def delete_version(self, version_id: str) -> bool:
        """
        Delete a version.

        Returns:
            True if deleted, False if not found.
        """
        with self._transaction() as cursor:
            cursor.execute("DELETE FROM trace_versions WHERE id = ?", (version_id,))
            return cursor.rowcount > 0

    # =========================================================================
    # Playground Iteration Methods
    # =========================================================================

    def save_iteration(
        self,
        trace_id: str,
        step_id: str,
        prompt: str,
        output: str = "",
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        duration_ms: float = 0.0,
        notes: str = "",
        trace_version_id: str | None = None,
    ) -> str:
        """
        Save a playground iteration.

        Args:
            trace_id: The trace this iteration is for.
            step_id: The step this iteration modifies.
            prompt: The prompt used.
            output: The generated output.
            input_tokens: Input token count.
            output_tokens: Output token count.
            duration_ms: Duration of the call.
            notes: Optional notes.
            trace_version_id: Optional version to link to.

        Returns:
            The new iteration ID.
        """
        import uuid
        from datetime import UTC, datetime

        iteration_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        with self._transaction() as cursor:
            # Get next iteration number for this trace/step
            cursor.execute(
                """
                SELECT COALESCE(MAX(iteration_number), 0) + 1
                FROM playground_iterations
                WHERE trace_id = ? AND step_id = ?
                """,
                (trace_id, step_id),
            )
            iteration_number = cursor.fetchone()[0]

            cursor.execute(
                """
                INSERT INTO playground_iterations (
                    id, trace_id, trace_version_id, step_id, iteration_number,
                    prompt, output, input_tokens, output_tokens, duration_ms,
                    notes, is_best, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    iteration_id,
                    trace_id,
                    trace_version_id,
                    step_id,
                    iteration_number,
                    prompt,
                    output,
                    input_tokens,
                    output_tokens,
                    duration_ms,
                    notes,
                    False,
                    now,
                ),
            )

        return iteration_id

    def get_iteration(self, iteration_id: str) -> dict[str, Any] | None:
        """Get a single iteration by ID."""
        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT id, trace_id, trace_version_id, step_id, iteration_number,
                       prompt, output, input_tokens, output_tokens, duration_ms,
                       notes, is_best, created_at
                FROM playground_iterations
                WHERE id = ?
                """,
                (iteration_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return {
                "id": row["id"],
                "trace_id": row["trace_id"],
                "trace_version_id": row["trace_version_id"],
                "step_id": row["step_id"],
                "iteration_number": row["iteration_number"],
                "prompt": row["prompt"],
                "output": row["output"],
                "input_tokens": row["input_tokens"],
                "output_tokens": row["output_tokens"],
                "duration_ms": row["duration_ms"],
                "notes": row["notes"],
                "is_best": bool(row["is_best"]),
                "created_at": row["created_at"],
            }

    def get_iterations(
        self,
        trace_id: str,
        step_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get iterations for a trace, optionally filtered by step_id.

        Args:
            trace_id: The trace to get iterations for.
            step_id: Optional step ID to filter by.

        Returns:
            List of iteration dicts sorted by iteration_number.
        """
        with self._transaction() as cursor:
            if step_id:
                cursor.execute(
                    """
                    SELECT id, trace_id, trace_version_id, step_id, iteration_number,
                           prompt, output, input_tokens, output_tokens, duration_ms,
                           notes, is_best, created_at
                    FROM playground_iterations
                    WHERE trace_id = ? AND step_id = ?
                    ORDER BY iteration_number
                    """,
                    (trace_id, step_id),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, trace_id, trace_version_id, step_id, iteration_number,
                           prompt, output, input_tokens, output_tokens, duration_ms,
                           notes, is_best, created_at
                    FROM playground_iterations
                    WHERE trace_id = ?
                    ORDER BY step_id, iteration_number
                    """,
                    (trace_id,),
                )

            return [
                {
                    "id": row["id"],
                    "trace_id": row["trace_id"],
                    "trace_version_id": row["trace_version_id"],
                    "step_id": row["step_id"],
                    "iteration_number": row["iteration_number"],
                    "prompt": row["prompt"],
                    "output": row["output"],
                    "input_tokens": row["input_tokens"],
                    "output_tokens": row["output_tokens"],
                    "duration_ms": row["duration_ms"],
                    "notes": row["notes"],
                    "is_best": bool(row["is_best"]),
                    "created_at": row["created_at"],
                }
                for row in cursor.fetchall()
            ]

    def mark_best_iteration(self, iteration_id: str) -> bool:
        """
        Mark an iteration as best (clears other best marks for same trace/step).

        Returns:
            True if iteration was marked, False if not found.
        """
        with self._transaction() as cursor:
            # First get the trace_id and step_id for this iteration
            cursor.execute(
                "SELECT trace_id, step_id FROM playground_iterations WHERE id = ?",
                (iteration_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return False

            trace_id, step_id = row["trace_id"], row["step_id"]

            # Clear other best marks for this trace/step
            cursor.execute(
                """
                UPDATE playground_iterations
                SET is_best = FALSE
                WHERE trace_id = ? AND step_id = ? AND is_best = TRUE
                """,
                (trace_id, step_id),
            )

            # Mark this one as best
            cursor.execute(
                "UPDATE playground_iterations SET is_best = TRUE WHERE id = ?",
                (iteration_id,),
            )

            return True

    def get_best_iteration(self, trace_id: str, step_id: str) -> dict[str, Any] | None:
        """Get the iteration marked as best for a trace/step."""
        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT id, trace_id, trace_version_id, step_id, iteration_number,
                       prompt, output, input_tokens, output_tokens, duration_ms,
                       notes, is_best, created_at
                FROM playground_iterations
                WHERE trace_id = ? AND step_id = ? AND is_best = TRUE
                LIMIT 1
                """,
                (trace_id, step_id),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return {
                "id": row["id"],
                "trace_id": row["trace_id"],
                "trace_version_id": row["trace_version_id"],
                "step_id": row["step_id"],
                "iteration_number": row["iteration_number"],
                "prompt": row["prompt"],
                "output": row["output"],
                "input_tokens": row["input_tokens"],
                "output_tokens": row["output_tokens"],
                "duration_ms": row["duration_ms"],
                "notes": row["notes"],
                "is_best": True,
                "created_at": row["created_at"],
            }

    def delete_iteration(self, iteration_id: str) -> bool:
        """
        Delete an iteration.

        Returns:
            True if deleted, False if not found.
        """
        with self._transaction() as cursor:
            cursor.execute(
                "DELETE FROM playground_iterations WHERE id = ?",
                (iteration_id,),
            )
            return cursor.rowcount > 0

    # =========================================================================
    # Agent Methods (for grouping traces by agent)
    # =========================================================================

    def list_agents(self, include_legacy: bool = True) -> list[dict[str, Any]]:
        """
        List all agents (from agents table and optionally from trace JSON data).

        Args:
            include_legacy: If True, also include agents extracted from trace JSON data.

        Returns:
            List of agent dicts with id, name, and trace_count.
        """
        results = []

        with self._transaction() as cursor:
            # First, get agents from the agents table (first-class agents)
            cursor.execute(
                """
                SELECT a.id, a.name, a.description, a.project_id, a.agent_type,
                       COUNT(t.id) as trace_count,
                       COALESCE(SUM(t.total_tokens), 0) as total_tokens,
                       COALESCE(SUM(t.total_cost_usd), 0.0) as total_cost_usd,
                       COALESCE(SUM(t.error_count), 0) as error_count
                FROM agents a
                LEFT JOIN traces t ON t.agent_id = a.id
                GROUP BY a.id
                ORDER BY a.name
                """
            )
            for row in cursor.fetchall():
                results.append(
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "description": row["description"],
                        "project_id": row["project_id"],
                        "agent_type": row["agent_type"],
                        "trace_count": row["trace_count"],
                        "total_tokens": row["total_tokens"] or 0,
                        "total_cost_usd": row["total_cost_usd"] or 0.0,
                        "error_count": row["error_count"] or 0,
                        "source": "table",
                    }
                )

            if include_legacy:
                # Also get agents extracted from trace data JSON (legacy)
                cursor.execute(
                    """
                    SELECT
                        json_extract(data, '$.agent_id') as agent_id,
                        json_extract(data, '$.agent_name') as agent_name,
                        COUNT(*) as trace_count,
                        SUM(total_tokens) as total_tokens,
                        SUM(total_cost_usd) as total_cost_usd,
                        SUM(error_count) as error_count
                    FROM traces
                    WHERE (json_extract(data, '$.agent_id') IS NOT NULL
                           OR json_extract(data, '$.agent_name') IS NOT NULL)
                      AND agent_id IS NULL  -- Only include traces not linked to agents table
                    GROUP BY agent_id, agent_name
                    ORDER BY agent_name
                    """
                )
                for row in cursor.fetchall():
                    results.append(
                        {
                            "id": row["agent_id"] or row["agent_name"],
                            "name": row["agent_name"] or row["agent_id"] or "Unknown Agent",
                            "trace_count": row["trace_count"],
                            "total_tokens": row["total_tokens"] or 0,
                            "total_cost_usd": row["total_cost_usd"] or 0.0,
                            "error_count": row["error_count"] or 0,
                            "source": "legacy",
                        }
                    )

        return results

    def get_agent_stats(self, agent_id: str) -> dict[str, Any]:
        """
        Get statistics for a specific agent.

        Args:
            agent_id: The agent ID or name to get stats for.

        Returns:
            Dict with trace_count, total_tokens, total_cost_usd, error_count.
        """
        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*) as trace_count,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(total_cost_usd), 0.0) as total_cost_usd,
                    COALESCE(SUM(error_count), 0) as error_count
                FROM traces
                WHERE json_extract(data, '$.agent_id') = ?
                   OR json_extract(data, '$.agent_name') = ?
                """,
                (agent_id, agent_id),
            )
            row = cursor.fetchone()

            return {
                "trace_count": row["trace_count"],
                "total_tokens": row["total_tokens"],
                "total_cost_usd": row["total_cost_usd"],
                "error_count": row["error_count"],
            }

    def get_traces_by_agent(
        self, agent_id: str, limit: int = 100, offset: int = 0
    ) -> list[AgentRun]:
        """
        Get traces for a specific agent (by JSON data - legacy method).

        Args:
            agent_id: The agent ID or name to filter by.
            limit: Maximum number of traces to return.
            offset: Number of traces to skip.

        Returns:
            List of AgentRun objects for the agent.
        """
        from tracecraft.core.models import AgentRun

        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT data FROM traces
                WHERE json_extract(data, '$.agent_id') = ?
                   OR json_extract(data, '$.agent_name') = ?
                ORDER BY start_time DESC
                LIMIT ? OFFSET ?
                """,
                (agent_id, agent_id, limit, offset),
            )
            return [AgentRun.model_validate_json(row["data"]) for row in cursor.fetchall()]

    # =========================================================================
    # Agent Table Methods (First-Class Agents - Schema v5+)
    # =========================================================================

    def create_agent(
        self,
        name: str,
        *,
        description: str | None = None,
        project_id: str | None = None,
        agent_type: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> str:
        """
        Create a new agent.

        Args:
            name: Agent name.
            description: Optional description.
            project_id: Optional associated project ID.
            agent_type: Type of agent (e.g., 'langchain', 'openai', 'custom').
            config: Optional JSON config.

        Returns:
            The new agent ID.
        """
        import uuid
        from datetime import UTC, datetime

        agent_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        with self._transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO agents (id, name, description, project_id, agent_type, config, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_id,
                    name,
                    description,
                    project_id,
                    agent_type,
                    json.dumps(config) if config else None,
                    now,
                    now,
                ),
            )

        return agent_id

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        """
        Get an agent by ID.

        Args:
            agent_id: The agent ID.

        Returns:
            Agent dict or None if not found.
        """
        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT id, name, description, project_id, agent_type, config, created_at, updated_at
                FROM agents WHERE id = ?
                """,
                (agent_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "project_id": row["project_id"],
                "agent_type": row["agent_type"],
                "config": json.loads(row["config"]) if row["config"] else None,
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }

    def update_agent(
        self,
        agent_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        project_id: str | None = None,
        agent_type: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> bool:
        """
        Update an agent.

        Args:
            agent_id: The agent ID.
            name: New name (optional).
            description: New description (optional).
            project_id: New project ID (optional).
            agent_type: New agent type (optional).
            config: New config (optional).

        Returns:
            True if updated, False if not found.
        """
        from datetime import UTC, datetime

        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if project_id is not None:
            updates.append("project_id = ?")
            params.append(project_id if project_id else None)
        if agent_type is not None:
            updates.append("agent_type = ?")
            params.append(agent_type)
        if config is not None:
            updates.append("config = ?")
            params.append(json.dumps(config))

        if not updates:
            return True  # Nothing to update

        updates.append("updated_at = ?")
        params.append(datetime.now(UTC).isoformat())
        params.append(agent_id)

        with self._transaction() as cursor:
            cursor.execute(
                f"UPDATE agents SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            return cursor.rowcount > 0

    def delete_agent(self, agent_id: str) -> bool:
        """
        Delete an agent.

        Unlinks all traces from the agent before deletion to prevent orphaned data.

        Args:
            agent_id: The agent ID.

        Returns:
            True if deleted, False if not found.
        """
        with self._transaction() as cursor:
            # First unlink all traces from this agent
            cursor.execute(
                "UPDATE traces SET agent_id = NULL WHERE agent_id = ?",
                (agent_id,),
            )
            # Then delete the agent
            cursor.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
            return cursor.rowcount > 0

    def assign_agent_to_project(self, agent_id: str, project_id: str | None) -> bool:
        """
        Assign an agent to a project (or unassign).

        Args:
            agent_id: The agent ID.
            project_id: The project ID (None to unassign).

        Returns:
            True if updated, False if agent not found.
        """
        from datetime import UTC, datetime

        with self._transaction() as cursor:
            cursor.execute(
                "UPDATE agents SET project_id = ?, updated_at = ? WHERE id = ?",
                (project_id, datetime.now(UTC).isoformat(), agent_id),
            )
            return cursor.rowcount > 0

    def list_agents_for_project(self, project_id: str) -> list[dict[str, Any]]:
        """
        List agents associated with a project.

        Args:
            project_id: The project ID.

        Returns:
            List of agent dicts.
        """
        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT a.id, a.name, a.description, a.project_id, a.agent_type,
                       a.config, a.created_at, a.updated_at,
                       COUNT(t.id) as trace_count,
                       COALESCE(SUM(t.total_tokens), 0) as total_tokens,
                       COALESCE(SUM(t.total_cost_usd), 0.0) as total_cost_usd
                FROM agents a
                LEFT JOIN traces t ON t.agent_id = a.id
                WHERE a.project_id = ?
                GROUP BY a.id
                ORDER BY a.name
                """,
                (project_id,),
            )
            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                    "project_id": row["project_id"],
                    "agent_type": row["agent_type"],
                    "config": json.loads(row["config"]) if row["config"] else None,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "trace_count": row["trace_count"],
                    "total_tokens": row["total_tokens"],
                    "total_cost_usd": row["total_cost_usd"],
                }
                for row in cursor.fetchall()
            ]

    def assign_trace_to_agent(self, trace_id: str, agent_id: str | None) -> bool:
        """
        Assign a trace to an agent.

        Args:
            trace_id: The trace ID.
            agent_id: The agent ID (None to unassign).

        Returns:
            True if updated, False if trace not found.
        """
        with self._transaction() as cursor:
            cursor.execute(
                "UPDATE traces SET agent_id = ? WHERE id = ?",
                (agent_id, trace_id),
            )
            return cursor.rowcount > 0

    def get_traces_by_agent_id(
        self, agent_id: str, limit: int = 100, offset: int = 0
    ) -> list[AgentRun]:
        """
        Get traces for a specific agent by agent_id column.

        Args:
            agent_id: The agent ID.
            limit: Maximum number of traces to return.
            offset: Number of traces to skip.

        Returns:
            List of AgentRun objects for the agent.
        """
        from tracecraft.core.models import AgentRun

        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT data FROM traces
                WHERE agent_id = ?
                ORDER BY start_time DESC
                LIMIT ? OFFSET ?
                """,
                (agent_id, limit, offset),
            )
            return [AgentRun.model_validate_json(row["data"]) for row in cursor.fetchall()]

    def get_agent_stats_by_id(self, agent_id: str) -> dict[str, Any]:
        """
        Get statistics for an agent by ID.

        Args:
            agent_id: The agent ID.

        Returns:
            Dict with trace_count, total_tokens, total_cost_usd, error_count.
        """
        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*) as trace_count,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(total_cost_usd), 0.0) as total_cost_usd,
                    COALESCE(SUM(error_count), 0) as error_count
                FROM traces
                WHERE agent_id = ?
                """,
                (agent_id,),
            )
            row = cursor.fetchone()

            return {
                "trace_count": row["trace_count"],
                "total_tokens": row["total_tokens"],
                "total_cost_usd": row["total_cost_usd"],
                "error_count": row["error_count"],
            }

    def get_project_structure(self, project_id: str) -> dict[str, Any]:
        """
        Get the full project structure with agents, evals, and trace count.

        Args:
            project_id: The project ID.

        Returns:
            Dict with project, agents, eval_sets, and trace_count.
        """
        project = self.get_project(project_id)
        if project is None:
            return {
                "project": None,
                "agents": [],
                "eval_sets": [],
                "trace_count": 0,
            }

        agents = self.list_agents_for_project(project_id)
        eval_sets = self.list_evaluation_sets(project_id=project_id)

        # Get trace count for project
        with self._transaction() as cursor:
            cursor.execute(
                "SELECT COUNT(*) as count FROM traces WHERE project_id = ?",
                (project_id,),
            )
            trace_count = cursor.fetchone()["count"]

        return {
            "project": project,
            "agents": agents,
            "eval_sets": eval_sets,
            "trace_count": trace_count,
        }

    # =========================================================================
    # Evaluation Set Methods
    # =========================================================================

    def create_evaluation_set(
        self,
        name: str,
        metrics: list[dict[str, Any]] | None = None,
        *,
        description: str | None = None,
        project_id: str | None = None,
        default_threshold: float = 0.7,
        pass_rate_threshold: float = 0.8,
        tags: list[str] | None = None,
    ) -> str:
        """
        Create a new evaluation set.

        Args:
            name: Unique name for the evaluation set.
            metrics: List of metric configurations (EvaluationMetricConfig dicts).
            description: Optional description.
            project_id: Optional associated project ID.
            default_threshold: Default pass threshold for metrics.
            pass_rate_threshold: Required pass rate for overall success.
            tags: Optional list of tags.

        Returns:
            The new evaluation set ID.

        Raises:
            sqlite3.IntegrityError: If name already exists.
        """
        import uuid
        from datetime import UTC, datetime

        set_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        with self._transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO evaluation_sets (
                    id, name, description, project_id, metrics_config,
                    default_threshold, pass_rate_threshold, tags, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    set_id,
                    name,
                    description,
                    project_id,
                    json.dumps(metrics or []),
                    default_threshold,
                    pass_rate_threshold,
                    json.dumps(tags or []),
                    now,
                ),
            )

        return set_id

    def get_evaluation_set(self, set_id: str) -> dict[str, Any] | None:
        """Get an evaluation set by ID."""
        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT id, name, description, project_id, metrics_config,
                       default_threshold, pass_rate_threshold, tags,
                       created_at, updated_at
                FROM evaluation_sets WHERE id = ?
                """,
                (set_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "project_id": row["project_id"],
                "metrics": json.loads(row["metrics_config"]) if row["metrics_config"] else [],
                "default_threshold": row["default_threshold"],
                "pass_rate_threshold": row["pass_rate_threshold"],
                "tags": json.loads(row["tags"]) if row["tags"] else [],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }

    def get_evaluation_set_by_name(self, name: str) -> dict[str, Any] | None:
        """Get an evaluation set by name."""
        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT id, name, description, project_id, metrics_config,
                       default_threshold, pass_rate_threshold, tags,
                       created_at, updated_at
                FROM evaluation_sets WHERE name = ?
                """,
                (name,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "project_id": row["project_id"],
                "metrics": json.loads(row["metrics_config"]) if row["metrics_config"] else [],
                "default_threshold": row["default_threshold"],
                "pass_rate_threshold": row["pass_rate_threshold"],
                "tags": json.loads(row["tags"]) if row["tags"] else [],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }

    def list_evaluation_sets(
        self, project_id: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        """
        List evaluation sets, optionally filtered by project.

        Args:
            project_id: Optional project ID to filter by.
            limit: Maximum number of sets to return.
            offset: Number of sets to skip.

        Returns:
            List of evaluation set dicts.
        """
        with self._transaction() as cursor:
            if project_id:
                cursor.execute(
                    """
                    SELECT id, name, description, project_id, metrics_config,
                           default_threshold, pass_rate_threshold, tags,
                           created_at, updated_at
                    FROM evaluation_sets
                    WHERE project_id = ?
                    ORDER BY name
                    LIMIT ? OFFSET ?
                    """,
                    (project_id, limit, offset),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, name, description, project_id, metrics_config,
                           default_threshold, pass_rate_threshold, tags,
                           created_at, updated_at
                    FROM evaluation_sets
                    ORDER BY name
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )

            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                    "project_id": row["project_id"],
                    "metrics": json.loads(row["metrics_config"]) if row["metrics_config"] else [],
                    "default_threshold": row["default_threshold"],
                    "pass_rate_threshold": row["pass_rate_threshold"],
                    "tags": json.loads(row["tags"]) if row["tags"] else [],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
                for row in cursor.fetchall()
            ]

    def update_evaluation_set(
        self,
        set_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        project_id: str | None = None,
        metrics: list[dict[str, Any]] | None = None,
        default_threshold: float | None = None,
        pass_rate_threshold: float | None = None,
        tags: list[str] | None = None,
    ) -> bool:
        """
        Update an evaluation set.

        Returns:
            True if set was updated, False if not found.
        """
        from datetime import UTC, datetime

        updates = []
        params: list[Any] = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if project_id is not None:
            updates.append("project_id = ?")
            params.append(project_id)
        if metrics is not None:
            updates.append("metrics_config = ?")
            params.append(json.dumps(metrics))
        if default_threshold is not None:
            updates.append("default_threshold = ?")
            params.append(default_threshold)
        if pass_rate_threshold is not None:
            updates.append("pass_rate_threshold = ?")
            params.append(pass_rate_threshold)
        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags))

        if not updates:
            return False

        updates.append("updated_at = ?")
        params.append(datetime.now(UTC).isoformat())
        params.append(set_id)

        with self._transaction() as cursor:
            cursor.execute(
                f"UPDATE evaluation_sets SET {', '.join(updates)} WHERE id = ?",  # nosec B608
                params,
            )
            return cursor.rowcount > 0

    def delete_evaluation_set(self, set_id: str) -> bool:
        """
        Delete an evaluation set and all its cases, runs, and results.

        Returns:
            True if deleted, False if not found.
        """
        with self._transaction() as cursor:
            cursor.execute("DELETE FROM evaluation_sets WHERE id = ?", (set_id,))
            return cursor.rowcount > 0

    # =========================================================================
    # Evaluation Case Methods
    # =========================================================================

    def add_evaluation_case(
        self,
        set_id: str,
        name: str,
        input_data: dict[str, Any],
        *,
        expected_output: dict[str, Any] | None = None,
        actual_output: dict[str, Any] | None = None,
        retrieval_context: list[str] | None = None,
        source_trace_id: str | None = None,
        source_step_id: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """
        Add a test case to an evaluation set.

        Args:
            set_id: The evaluation set ID.
            name: Human-readable case name.
            input_data: Input data for the case.
            expected_output: Optional expected output for comparison.
            actual_output: Optional actual output from trace/step for comparison.
            retrieval_context: Optional retrieved context for RAG metrics.
            source_trace_id: Optional trace this case was extracted from.
            source_step_id: Optional step this case was extracted from.
            tags: Optional list of tags.

        Returns:
            The new case ID.
        """
        import uuid
        from datetime import UTC, datetime

        case_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        with self._transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO evaluation_cases (
                    id, evaluation_set_id, name, input, expected_output, actual_output,
                    retrieval_context, source_trace_id, source_step_id, tags, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case_id,
                    set_id,
                    name,
                    json.dumps(input_data),
                    json.dumps(expected_output) if expected_output else None,
                    json.dumps(actual_output) if actual_output else None,
                    json.dumps(retrieval_context) if retrieval_context else None,
                    source_trace_id,
                    source_step_id,
                    json.dumps(tags or []),
                    now,
                ),
            )

        return case_id

    def create_case_from_trace(
        self,
        set_id: str,
        trace_id: str,
        step_id: str | None = None,
        name: str | None = None,
    ) -> str:
        """
        Create an evaluation case from an existing trace or step.

        Args:
            set_id: The evaluation set ID.
            trace_id: The source trace ID.
            step_id: Optional specific step ID (uses trace root if None).
            name: Optional case name (auto-generated if None).

        Returns:
            The new case ID.

        Raises:
            ValueError: If trace or step not found.
        """
        from tracecraft.core.models import AgentRun

        trace = self.get(trace_id)
        if trace is None:
            raise ValueError(f"Trace {trace_id} not found")

        # Find the step if specified
        if step_id:
            step = self._find_step(trace.steps, step_id)
            if step is None:
                raise ValueError(f"Step {step_id} not found in trace {trace_id}")
            input_data = step.inputs
            # Store trace/step output as both expected (golden baseline) and actual
            actual_output = step.outputs
            expected_output = step.outputs
            case_name = name or f"{trace.name} - {step.name}"
        else:
            input_data = {"input": trace.input} if trace.input else {}
            # Store trace output as both expected (golden baseline) and actual
            actual_output = {"output": trace.output} if trace.output else None
            expected_output = {"output": trace.output} if trace.output else None
            case_name = name or trace.name

        return self.add_evaluation_case(
            set_id=set_id,
            name=case_name,
            input_data=input_data,
            expected_output=expected_output,
            actual_output=actual_output,
            source_trace_id=trace_id,
            source_step_id=step_id,
        )

    def _find_step(self, steps: list[Any], step_id: str) -> Any | None:
        """Recursively find a step by ID."""
        for step in steps:
            if str(step.id) == step_id:
                return step
            if step.children:
                found = self._find_step(step.children, step_id)
                if found:
                    return found
        return None

    def get_evaluation_case(self, case_id: str) -> dict[str, Any] | None:
        """Get a single evaluation case by ID."""
        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT id, evaluation_set_id, name, input, expected_output, actual_output,
                       retrieval_context, source_trace_id, source_step_id,
                       tags, created_at
                FROM evaluation_cases WHERE id = ?
                """,
                (case_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return {
                "id": row["id"],
                "evaluation_set_id": row["evaluation_set_id"],
                "name": row["name"],
                "input": json.loads(row["input"]),
                "expected_output": json.loads(row["expected_output"])
                if row["expected_output"]
                else None,
                "actual_output": json.loads(row["actual_output"]) if row["actual_output"] else None,
                "retrieval_context": json.loads(row["retrieval_context"])
                if row["retrieval_context"]
                else [],
                "source_trace_id": row["source_trace_id"],
                "source_step_id": row["source_step_id"],
                "tags": json.loads(row["tags"]) if row["tags"] else [],
                "created_at": row["created_at"],
            }

    def get_evaluation_cases(self, set_id: str) -> list[dict[str, Any]]:
        """Get all cases in an evaluation set."""
        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT id, evaluation_set_id, name, input, expected_output, actual_output,
                       retrieval_context, source_trace_id, source_step_id,
                       tags, created_at
                FROM evaluation_cases
                WHERE evaluation_set_id = ?
                ORDER BY created_at
                """,
                (set_id,),
            )
            return [
                {
                    "id": row["id"],
                    "evaluation_set_id": row["evaluation_set_id"],
                    "name": row["name"],
                    "input": json.loads(row["input"]),
                    "expected_output": json.loads(row["expected_output"])
                    if row["expected_output"]
                    else None,
                    "actual_output": json.loads(row["actual_output"])
                    if row["actual_output"]
                    else None,
                    "retrieval_context": json.loads(row["retrieval_context"])
                    if row["retrieval_context"]
                    else [],
                    "source_trace_id": row["source_trace_id"],
                    "source_step_id": row["source_step_id"],
                    "tags": json.loads(row["tags"]) if row["tags"] else [],
                    "created_at": row["created_at"],
                }
                for row in cursor.fetchall()
            ]

    def delete_evaluation_case(self, case_id: str) -> bool:
        """
        Delete an evaluation case.

        Returns:
            True if deleted, False if not found.
        """
        with self._transaction() as cursor:
            cursor.execute("DELETE FROM evaluation_cases WHERE id = ?", (case_id,))
            return cursor.rowcount > 0

    def count_evaluation_cases(self, set_id: str) -> int:
        """Count cases in an evaluation set."""
        with self._transaction() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM evaluation_cases WHERE evaluation_set_id = ?",
                (set_id,),
            )
            return cursor.fetchone()[0]

    # =========================================================================
    # Evaluation Run Methods
    # =========================================================================

    def create_evaluation_run(self, set_id: str) -> str:
        """
        Create a new evaluation run.

        Args:
            set_id: The evaluation set to run.

        Returns:
            The new run ID.
        """
        import uuid
        from datetime import UTC, datetime

        run_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        # Count cases in the set
        case_count = self.count_evaluation_cases(set_id)

        with self._transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO evaluation_runs (
                    id, evaluation_set_id, status, total_cases, started_at
                ) VALUES (?, ?, 'pending', ?, ?)
                """,
                (run_id, set_id, case_count, now),
            )

        return run_id

    def update_evaluation_run(
        self,
        run_id: str,
        *,
        status: str | None = None,
        passed_cases: int | None = None,
        failed_cases: int | None = None,
        overall_pass_rate: float | None = None,
        metric_averages: dict[str, float] | None = None,
        passed: bool | None = None,
        completed_at: str | None = None,
        duration_ms: float | None = None,
        error: str | None = None,
    ) -> bool:
        """
        Update an evaluation run.

        Returns:
            True if run was updated, False if not found.
        """
        updates = []
        params: list[Any] = []

        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if passed_cases is not None:
            updates.append("passed_cases = ?")
            params.append(passed_cases)
        if failed_cases is not None:
            updates.append("failed_cases = ?")
            params.append(failed_cases)
        if overall_pass_rate is not None:
            updates.append("overall_pass_rate = ?")
            params.append(overall_pass_rate)
        if metric_averages is not None:
            updates.append("metric_averages = ?")
            params.append(json.dumps(metric_averages))
        if passed is not None:
            updates.append("passed = ?")
            params.append(passed)
        if completed_at is not None:
            updates.append("completed_at = ?")
            params.append(completed_at)
        if duration_ms is not None:
            updates.append("duration_ms = ?")
            params.append(duration_ms)
        if error is not None:
            updates.append("error = ?")
            params.append(error)

        if not updates:
            return False

        params.append(run_id)

        with self._transaction() as cursor:
            cursor.execute(
                f"UPDATE evaluation_runs SET {', '.join(updates)} WHERE id = ?",  # nosec B608
                params,
            )
            return cursor.rowcount > 0

    def get_evaluation_run(self, run_id: str) -> dict[str, Any] | None:
        """Get an evaluation run by ID."""
        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT id, evaluation_set_id, status, total_cases, passed_cases,
                       failed_cases, overall_pass_rate, metric_averages, passed,
                       started_at, completed_at, duration_ms, error
                FROM evaluation_runs WHERE id = ?
                """,
                (run_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return {
                "id": row["id"],
                "evaluation_set_id": row["evaluation_set_id"],
                "status": row["status"],
                "total_cases": row["total_cases"],
                "passed_cases": row["passed_cases"],
                "failed_cases": row["failed_cases"],
                "overall_pass_rate": row["overall_pass_rate"],
                "metric_averages": json.loads(row["metric_averages"])
                if row["metric_averages"]
                else {},
                "passed": row["passed"],
                "started_at": row["started_at"],
                "completed_at": row["completed_at"],
                "duration_ms": row["duration_ms"],
                "error": row["error"],
            }

    def list_evaluation_runs(
        self, set_id: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        """
        List evaluation runs, optionally filtered by set.

        Args:
            set_id: Optional evaluation set ID to filter by.
            limit: Maximum number of runs to return.
            offset: Number of runs to skip.

        Returns:
            List of evaluation run dicts.
        """
        with self._transaction() as cursor:
            if set_id:
                cursor.execute(
                    """
                    SELECT r.id, r.evaluation_set_id, s.name as evaluation_set_name,
                           r.status, r.total_cases, r.passed_cases, r.failed_cases,
                           r.overall_pass_rate, r.metric_averages, r.passed,
                           r.started_at, r.completed_at, r.duration_ms, r.error
                    FROM evaluation_runs r
                    JOIN evaluation_sets s ON r.evaluation_set_id = s.id
                    WHERE r.evaluation_set_id = ?
                    ORDER BY r.started_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (set_id, limit, offset),
                )
            else:
                cursor.execute(
                    """
                    SELECT r.id, r.evaluation_set_id, s.name as evaluation_set_name,
                           r.status, r.total_cases, r.passed_cases, r.failed_cases,
                           r.overall_pass_rate, r.metric_averages, r.passed,
                           r.started_at, r.completed_at, r.duration_ms, r.error
                    FROM evaluation_runs r
                    JOIN evaluation_sets s ON r.evaluation_set_id = s.id
                    ORDER BY r.started_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )

            return [
                {
                    "id": row["id"],
                    "evaluation_set_id": row["evaluation_set_id"],
                    "evaluation_set_name": row["evaluation_set_name"],
                    "status": row["status"],
                    "total_cases": row["total_cases"],
                    "passed_cases": row["passed_cases"],
                    "failed_cases": row["failed_cases"],
                    "overall_pass_rate": row["overall_pass_rate"],
                    "metric_averages": json.loads(row["metric_averages"])
                    if row["metric_averages"]
                    else {},
                    "passed": row["passed"],
                    "started_at": row["started_at"],
                    "completed_at": row["completed_at"],
                    "duration_ms": row["duration_ms"],
                    "error": row["error"],
                }
                for row in cursor.fetchall()
            ]

    def get_latest_evaluation_run(self, set_id: str) -> dict[str, Any] | None:
        """Get the most recent run for an evaluation set."""
        runs = self.list_evaluation_runs(set_id=set_id, limit=1)
        return runs[0] if runs else None

    def delete_evaluation_run(self, run_id: str) -> bool:
        """
        Delete an evaluation run and all its results.

        Returns:
            True if deleted, False if not found.
        """
        with self._transaction() as cursor:
            cursor.execute("DELETE FROM evaluation_runs WHERE id = ?", (run_id,))
            return cursor.rowcount > 0

    # =========================================================================
    # Evaluation Result Methods
    # =========================================================================

    def save_evaluation_result(
        self,
        run_id: str,
        case_id: str,
        scores: list[dict[str, Any]],
        passed: bool,
        *,
        trace_id: str | None = None,
        actual_output: dict[str, Any] | None = None,
        overall_score: float | None = None,
        duration_ms: float | None = None,
        error: str | None = None,
    ) -> str:
        """
        Save an evaluation result for a case.

        Args:
            run_id: The evaluation run ID.
            case_id: The evaluation case ID.
            scores: List of MetricScore dicts.
            passed: Whether the case passed.
            trace_id: Optional trace generated during evaluation.
            actual_output: The actual output produced.
            overall_score: Weighted average score.
            duration_ms: Evaluation duration.
            error: Error message if evaluation failed.

        Returns:
            The new result ID.
        """
        import uuid

        result_id = str(uuid.uuid4())

        with self._transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO evaluation_results (
                    id, evaluation_run_id, evaluation_case_id, trace_id,
                    actual_output, scores, overall_score, passed, duration_ms, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result_id,
                    run_id,
                    case_id,
                    trace_id,
                    json.dumps(actual_output) if actual_output else None,
                    json.dumps(scores),
                    overall_score,
                    passed,
                    duration_ms,
                    error,
                ),
            )

        return result_id

    def get_evaluation_results(self, run_id: str) -> list[dict[str, Any]]:
        """Get all results for an evaluation run."""
        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT r.id, r.evaluation_run_id, r.evaluation_case_id, c.name as case_name,
                       c.input as case_input, c.expected_output as case_expected_output,
                       r.trace_id, r.actual_output, r.scores, r.overall_score,
                       r.passed, r.duration_ms, r.error
                FROM evaluation_results r
                JOIN evaluation_cases c ON r.evaluation_case_id = c.id
                WHERE r.evaluation_run_id = ?
                ORDER BY c.name
                """,
                (run_id,),
            )
            return [
                {
                    "id": row["id"],
                    "evaluation_run_id": row["evaluation_run_id"],
                    "evaluation_case_id": row["evaluation_case_id"],
                    "case_name": row["case_name"],
                    "input": json.loads(row["case_input"]) if row["case_input"] else None,
                    "expected_output": json.loads(row["case_expected_output"])
                    if row["case_expected_output"]
                    else None,
                    "trace_id": row["trace_id"],
                    "actual_output": json.loads(row["actual_output"])
                    if row["actual_output"]
                    else None,
                    "scores": json.loads(row["scores"]) if row["scores"] else [],
                    "overall_score": row["overall_score"],
                    "passed": row["passed"],
                    "duration_ms": row["duration_ms"],
                    "error": row["error"],
                }
                for row in cursor.fetchall()
            ]

    def get_evaluation_result(self, result_id: str) -> dict[str, Any] | None:
        """Get a single evaluation result by ID."""
        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT r.id, r.evaluation_run_id, r.evaluation_case_id, c.name as case_name,
                       c.input as case_input, c.expected_output as case_expected_output,
                       r.trace_id, r.actual_output, r.scores, r.overall_score,
                       r.passed, r.duration_ms, r.error
                FROM evaluation_results r
                JOIN evaluation_cases c ON r.evaluation_case_id = c.id
                WHERE r.id = ?
                """,
                (result_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return {
                "id": row["id"],
                "evaluation_run_id": row["evaluation_run_id"],
                "evaluation_case_id": row["evaluation_case_id"],
                "case_name": row["case_name"],
                "input": json.loads(row["case_input"]) if row["case_input"] else None,
                "expected_output": json.loads(row["case_expected_output"])
                if row["case_expected_output"]
                else None,
                "trace_id": row["trace_id"],
                "actual_output": json.loads(row["actual_output"]) if row["actual_output"] else None,
                "scores": json.loads(row["scores"]) if row["scores"] else [],
                "overall_score": row["overall_score"],
                "passed": row["passed"],
                "duration_ms": row["duration_ms"],
                "error": row["error"],
            }

    # =========================================================================
    # Evaluation Statistics Methods
    # =========================================================================

    def get_evaluation_set_stats(self, set_id: str) -> dict[str, Any]:
        """
        Get statistics for an evaluation set.

        Returns:
            Dict with case_count, run_count, latest_run info, pass rates.
        """
        with self._transaction() as cursor:
            # Case count
            cursor.execute(
                "SELECT COUNT(*) FROM evaluation_cases WHERE evaluation_set_id = ?",
                (set_id,),
            )
            case_count = cursor.fetchone()[0]

            # Run count and latest run stats
            cursor.execute(
                """
                SELECT COUNT(*) as run_count,
                       AVG(CASE WHEN passed = 1 THEN 1.0 ELSE 0.0 END) as avg_pass_rate
                FROM evaluation_runs
                WHERE evaluation_set_id = ? AND status = 'completed'
                """,
                (set_id,),
            )
            row = cursor.fetchone()
            run_count = row["run_count"]
            avg_pass_rate = row["avg_pass_rate"]

            # Latest run
            latest_run = self.get_latest_evaluation_run(set_id)

            return {
                "case_count": case_count,
                "run_count": run_count,
                "avg_pass_rate": avg_pass_rate,
                "latest_run": latest_run,
            }

    # =========================================================================
    # Bidirectional Navigation Methods (Trace <-> Eval)
    # =========================================================================

    def get_evaluation_sets_for_trace(self, trace_id: str) -> list[dict[str, Any]]:
        """
        Get all evaluation sets that have cases derived from this trace.

        Args:
            trace_id: The trace ID to look up.

        Returns:
            List of evaluation sets containing cases from this trace.
        """
        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT es.id, es.name, es.description, es.project_id,
                       es.metrics_config, es.default_threshold, es.pass_rate_threshold,
                       es.tags, es.created_at, es.updated_at
                FROM evaluation_sets es
                JOIN evaluation_cases ec ON es.id = ec.evaluation_set_id
                WHERE ec.source_trace_id = ?
                ORDER BY es.name
                """,
                (trace_id,),
            )
            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "description": row["description"],
                        "project_id": row["project_id"],
                        "metrics": json.loads(row["metrics_config"])
                        if row["metrics_config"]
                        else [],
                        "default_threshold": row["default_threshold"],
                        "pass_rate_threshold": row["pass_rate_threshold"],
                        "tags": json.loads(row["tags"]) if row["tags"] else [],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    }
                )
            return results

    def get_evaluation_cases_from_trace(self, trace_id: str) -> list[dict[str, Any]]:
        """
        Get all evaluation cases derived from this trace.

        Args:
            trace_id: The trace ID to look up.

        Returns:
            List of evaluation cases with their set name included.
        """
        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT ec.id, ec.evaluation_set_id, ec.name, ec.input, ec.expected_output,
                       ec.actual_output, ec.retrieval_context, ec.source_trace_id,
                       ec.source_step_id, ec.tags, ec.created_at, es.name as set_name
                FROM evaluation_cases ec
                JOIN evaluation_sets es ON ec.evaluation_set_id = es.id
                WHERE ec.source_trace_id = ?
                ORDER BY es.name, ec.name
                """,
                (trace_id,),
            )
            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "id": row["id"],
                        "evaluation_set_id": row["evaluation_set_id"],
                        "name": row["name"],
                        "input": json.loads(row["input"]) if row["input"] else None,
                        "expected_output": json.loads(row["expected_output"])
                        if row["expected_output"]
                        else None,
                        "actual_output": json.loads(row["actual_output"])
                        if row["actual_output"]
                        else None,
                        "retrieval_context": json.loads(row["retrieval_context"])
                        if row["retrieval_context"]
                        else [],
                        "source_trace_id": row["source_trace_id"],
                        "source_step_id": row["source_step_id"],
                        "tags": json.loads(row["tags"]) if row["tags"] else [],
                        "created_at": row["created_at"],
                        "set_name": row["set_name"],
                    }
                )
            return results

    def get_source_trace_for_case(self, case_id: str) -> dict[str, Any] | None:
        """
        Get the source trace for an evaluation case.

        Args:
            case_id: The evaluation case ID.

        Returns:
            The trace data dict, or None if no source trace.
        """
        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT t.*
                FROM traces t
                JOIN evaluation_cases ec ON t.id = ec.source_trace_id
                WHERE ec.id = ?
                """,
                (case_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_latest_eval_result_for_case(self, case_id: str) -> dict[str, Any] | None:
        """
        Get the most recent evaluation result for a case.

        Args:
            case_id: The evaluation case ID.

        Returns:
            The latest result dict, or None if no results exist.
        """
        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT er.*
                FROM evaluation_results er
                JOIN evaluation_runs run ON er.evaluation_run_id = run.id
                WHERE er.evaluation_case_id = ?
                ORDER BY run.started_at DESC
                LIMIT 1
                """,
                (case_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def count_eval_sets_for_trace(self, trace_id: str) -> int:
        """
        Count distinct evaluation sets containing cases from this trace.

        Args:
            trace_id: The trace ID to look up.

        Returns:
            Count of distinct evaluation sets.
        """
        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT COUNT(DISTINCT es.id)
                FROM evaluation_sets es
                JOIN evaluation_cases ec ON es.id = ec.evaluation_set_id
                WHERE ec.source_trace_id = ?
                """,
                (trace_id,),
            )
            return cursor.fetchone()[0]
