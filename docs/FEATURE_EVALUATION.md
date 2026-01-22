# Feature Evaluation: Proposed Enhancements

This document evaluates proposed features for AgentTrace, analyzing their value proposition, implementation approach, and integration with existing architecture.

---

## Executive Summary

| Feature | Recommendation | Complexity | Value |
|---------|----------------|------------|-------|
| Central SQLite with Projects/Versioning | **Implement** | Medium-High | High |
| Log Correlation in TUI | **Implement** | Medium | High |
| Evaluation Sets in TUI | **Implement** | Medium | High |
| AI Inspect for Failed Evaluations | **Implement** | Medium | High |

All four features are worth implementing. They build naturally on the existing architecture and address real workflow gaps.

---

## Feature 1: Enhanced SQLite Storage with Projects, Versioning, and Playground Persistence

### Current State

The SQLite backend (`src/agenttrace/storage/sqlite.py`) provides solid trace storage with:

- Denormalized schema for fast queries (traces, steps, trace_tags tables)
- WAL mode for concurrency
- Rich querying (name, duration, cost, tags, time range filtering)
- Statistics and analytics methods

However, it lacks:

- Multi-project/workspace organization
- Trace versioning (original vs. modified)
- Integration with playground changes (currently saved to separate JSON files via `IterationHistory`)

### Why This is Valuable

1. **Multi-project support**: Teams working on multiple agents need isolation and organization
2. **Version tracking**: Comparing original traces vs. playground modifications enables systematic prompt engineering
3. **Unified storage**: Playground iterations scattered in JSON files are not queryable or shareable
4. **Audit trail**: Understanding what changed and when is critical for production debugging

### Implementation Approach

#### 1. Schema Extensions

Add new tables to the SQLite schema:

```sql
-- Projects/workspaces for organizing traces
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    settings TEXT  -- JSON blob for project-specific config
);

-- Track trace versions (original, playground modifications, etc.)
CREATE TABLE trace_versions (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,  -- Original trace ID
    version_number INTEGER NOT NULL,
    version_type TEXT NOT NULL,  -- 'original', 'playground', 'manual'
    parent_version_id TEXT,  -- For branching history
    created_at TEXT NOT NULL,
    created_by TEXT,  -- user_id if available
    notes TEXT,
    data TEXT NOT NULL,  -- Full AgentRun JSON
    FOREIGN KEY (trace_id) REFERENCES traces(id),
    UNIQUE(trace_id, version_number)
);

-- Playground iterations linked to trace versions
CREATE TABLE playground_iterations (
    id TEXT PRIMARY KEY,
    trace_version_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    iteration_number INTEGER NOT NULL,
    prompt TEXT NOT NULL,
    output TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    duration_ms INTEGER,
    notes TEXT,
    is_best BOOLEAN DEFAULT FALSE,
    created_at TEXT NOT NULL,
    FOREIGN KEY (trace_version_id) REFERENCES trace_versions(id) ON DELETE CASCADE
);

-- Add project_id to traces table
ALTER TABLE traces ADD COLUMN project_id TEXT REFERENCES projects(id);
CREATE INDEX idx_traces_project ON traces(project_id);
```

#### 2. Storage Layer Changes

Extend `SQLiteTraceStore` in `src/agenttrace/storage/sqlite.py`:

```python
class SQLiteTraceStore(BaseTraceStore):
    # New methods for project management
    def create_project(self, name: str, description: str = "") -> str: ...
    def list_projects(self) -> list[dict]: ...
    def get_project(self, project_id: str) -> dict | None: ...
    def delete_project(self, project_id: str) -> bool: ...

    # Versioning support
    def create_version(
        self,
        trace_id: str,
        version_type: str = "playground",
        notes: str = "",
        modified_run: AgentRun | None = None
    ) -> str: ...

    def get_versions(self, trace_id: str) -> list[dict]: ...
    def get_version(self, version_id: str) -> AgentRun | None: ...
    def compare_versions(self, v1_id: str, v2_id: str) -> dict: ...

    # Playground persistence
    def save_playground_iteration(
        self,
        trace_id: str,
        step_id: str,
        prompt: str,
        output: str,
        tokens: dict,
        duration_ms: int,
        notes: str = ""
    ) -> str: ...

    def get_iterations(self, trace_id: str, step_id: str) -> list[dict]: ...
    def mark_best_iteration(self, iteration_id: str) -> bool: ...
```

#### 3. Playground Integration

Modify `src/agenttrace/playground/runner.py` to persist iterations:

```python
async def replay_step(
    run: AgentRun,
    step_id: str | None = None,
    step_name: str | None = None,
    modified_prompt: str | None = None,
    provider: BaseReplayProvider | None = None,
    store: SQLiteTraceStore | None = None,  # NEW: optional persistence
    save_iteration: bool = True,  # NEW: control persistence
) -> ReplayResult:
    # ... existing replay logic ...

    # Persist iteration if store provided
    if store and save_iteration:
        store.save_playground_iteration(
            trace_id=run.id,
            step_id=step.id,
            prompt=modified_prompt or original_prompt,
            output=result.output,
            tokens={"input": result.input_tokens, "output": result.output_tokens},
            duration_ms=result.duration_ms
        )

    return result
```

#### 4. Migration Strategy

Add schema migration support in `_ensure_schema()`:

```python
def _ensure_schema(self) -> None:
    current_version = self._get_schema_version()

    migrations = [
        (2, self._migrate_v2_projects),
        (3, self._migrate_v3_versions),
        (4, self._migrate_v4_iterations),
    ]

    for version, migration_fn in migrations:
        if current_version < version:
            migration_fn()
            self._set_schema_version(version)
```

### Files to Modify/Create

| File | Changes |
|------|---------|
| `src/agenttrace/storage/sqlite.py` | Schema extensions, new methods |
| `src/agenttrace/storage/base.py` | Add versioning protocol methods |
| `src/agenttrace/playground/runner.py` | Persistence integration |
| `src/agenttrace/playground/comparison.py` | Remove file-based `IterationHistory.save/load`, use store |
| `src/agenttrace/tui/app.py` | Project selection, version navigation |

---

## Feature 2: Log Correlation in Terminal UI

### Current State

The TUI displays trace hierarchy, inputs/outputs, and metrics but has no visibility into application logs. The `IOViewer` widget shows:

- Input mode (step inputs)
- Output mode (step outputs)
- Attributes mode (metadata)
- JSON mode (full serialization)
- Error mode (error details)

There is no log capture or display mechanism.

### Why This is Valuable

1. **Debug context**: Logs often contain critical debugging information not in structured trace data
2. **Correlation**: Seeing "what the code was doing" alongside "what the LLM returned" is essential
3. **Industry standard**: Jaeger, Datadog, and other observability tools correlate logs with traces
4. **Searchability**: Finding traces via log content is a common workflow

### Implementation Approach

#### 1. Log Capture via Context

Create a log handler that captures logs during traced execution:

**New file: `src/agenttrace/instrumentation/log_capture.py`**

```python
import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class CapturedLog:
    timestamp: datetime
    level: str
    logger_name: str
    message: str
    step_id: str | None = None
    trace_id: str | None = None
    extra: dict = field(default_factory=dict)

# Context var for current log buffer
_log_buffer: ContextVar[list[CapturedLog]] = ContextVar("log_buffer", default=[])

class TracingLogHandler(logging.Handler):
    """Handler that captures logs during traced execution."""

    def emit(self, record: logging.LogRecord) -> None:
        from agenttrace.core.context import get_current_run, get_current_step

        buffer = _log_buffer.get()
        run = get_current_run()
        step = get_current_step()

        if run is not None:  # Only capture during traced execution
            log = CapturedLog(
                timestamp=datetime.fromtimestamp(record.created),
                level=record.levelname,
                logger_name=record.name,
                message=record.getMessage(),
                step_id=step.id if step else None,
                trace_id=run.id,
                extra=getattr(record, "extra", {}),
            )
            buffer.append(log)

def install_log_capture(level: int = logging.DEBUG) -> TracingLogHandler:
    """Install the tracing log handler on the root logger."""
    handler = TracingLogHandler()
    handler.setLevel(level)
    logging.root.addHandler(handler)
    return handler

def get_captured_logs() -> list[CapturedLog]:
    """Get logs captured in current context."""
    return _log_buffer.get().copy()

def clear_captured_logs() -> None:
    """Clear the log buffer."""
    _log_buffer.set([])
```

#### 2. Extend Data Models

Add logs to `AgentRun` in `src/agenttrace/core/models.py`:

```python
@dataclass
class AgentRun:
    # ... existing fields ...

    # Log entries captured during execution
    logs: list[dict] = field(default_factory=list)
```

#### 3. Storage Schema Extension

Add logs table to SQLite:

```sql
CREATE TABLE trace_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id TEXT NOT NULL,
    step_id TEXT,
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL,
    logger_name TEXT,
    message TEXT NOT NULL,
    extra TEXT,  -- JSON blob
    FOREIGN KEY (trace_id) REFERENCES traces(id) ON DELETE CASCADE
);

CREATE INDEX idx_logs_trace ON trace_logs(trace_id);
CREATE INDEX idx_logs_step ON trace_logs(step_id);
CREATE INDEX idx_logs_level ON trace_logs(level);
CREATE INDEX idx_logs_message ON trace_logs(message);  -- For search
```

#### 4. TUI Log Viewer Widget

**New file: `src/agenttrace/tui/widgets/log_viewer.py`**

```python
from textual.widgets import DataTable, Input
from textual.containers import Vertical

class LogViewer(Vertical):
    """Widget for viewing and searching logs associated with a trace."""

    BINDINGS = [
        ("d", "toggle_debug", "Toggle DEBUG"),
        ("i", "toggle_info", "Toggle INFO"),
        ("w", "toggle_warning", "Toggle WARN"),
        ("e", "toggle_error", "Toggle ERROR"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.logs: list[dict] = []
        self.filter_text: str = ""
        self.show_levels: set[str] = {"DEBUG", "INFO", "WARNING", "ERROR"}

    def compose(self):
        yield Input(placeholder="Search logs...", id="log-search")
        yield DataTable(id="log-table")

    def on_mount(self) -> None:
        table = self.query_one("#log-table", DataTable)
        table.add_columns("Time", "Level", "Logger", "Message")
        table.cursor_type = "row"

    def set_logs(self, logs: list[dict]) -> None:
        self.logs = logs
        self._refresh_table()

    def filter_by_step(self, step_id: str | None) -> None:
        """Filter logs to show only those for a specific step."""
        # ... implementation

    def _refresh_table(self) -> None:
        table = self.query_one("#log-table", DataTable)
        table.clear()

        for log in self.logs:
            if log["level"] not in self.show_levels:
                continue
            if self.filter_text and self.filter_text.lower() not in log["message"].lower():
                continue

            table.add_row(
                log["timestamp"][:19],  # Trim to seconds
                log["level"],
                log["logger_name"][:20],
                log["message"][:100],
            )
```

#### 5. TUI Integration

Add log viewer as a new mode in `app.py`:

```python
class AgentTraceApp(App):
    BINDINGS = [
        # ... existing bindings ...
        ("l", "show_logs", "Logs"),
    ]

    def compose(self):
        # ... existing layout ...
        yield LogViewer(id="log-viewer", classes="hidden")

    def action_show_logs(self) -> None:
        self.query_one("#log-viewer").toggle_class("hidden")
        self.query_one("#io-viewer").toggle_class("hidden")
```

### Files to Modify/Create

| File | Changes |
|------|---------|
| `src/agenttrace/instrumentation/log_capture.py` | **New** - Log capture handler |
| `src/agenttrace/core/models.py` | Add `logs` field to `AgentRun` |
| `src/agenttrace/storage/sqlite.py` | Add `trace_logs` table, query methods |
| `src/agenttrace/tui/widgets/log_viewer.py` | **New** - Log display widget |
| `src/agenttrace/tui/app.py` | Add log viewer, keybinding, layout |

---

## Feature 3: Evaluation Set Creation and Results Viewing in TUI

### Current State

Evaluation capabilities exist but are code-only:

- `src/agenttrace/contrib/evaluation.py` - Context managers and decorators
- `src/agenttrace/datasets/converters.py` - Export to CSV, HuggingFace, JSONL, golden datasets
- `src/agenttrace/integrations/ragas.py` - RAGAS integration
- `src/agenttrace/integrations/deepeval.py` - DeepEval integration

The TUI has no evaluation functionality - users cannot:

- Select traces/steps to include in an evaluation set
- Define expected outputs interactively
- View evaluation results

### Why This is Valuable

1. **Accessibility**: Creating evaluation sets should not require writing code
2. **Iterative curation**: Selecting specific traces, editing expected outputs, refining datasets
3. **Results visibility**: Seeing pass/fail rates, score distributions, failure patterns
4. **Workflow integration**: Natural flow from trace inspection to evaluation to improvement

### Implementation Approach

#### 1. Evaluation Set Data Model

**New file: `src/agenttrace/evaluation/models.py`**

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

class EvalSetStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"

@dataclass
class EvalCase:
    """Single evaluation case derived from a trace step."""
    id: str
    trace_id: str
    step_id: str
    input: str
    expected_output: str | None = None
    actual_output: str | None = None
    context: list[str] = field(default_factory=list)  # For RAG
    metadata: dict = field(default_factory=dict)

    # Results (populated after evaluation)
    scores: dict = field(default_factory=dict)
    passed: bool | None = None
    notes: str = ""

@dataclass
class EvalSet:
    """Collection of evaluation cases."""
    id: str
    name: str
    description: str = ""
    project_id: str | None = None
    cases: list[EvalCase] = field(default_factory=list)

    # Evaluation config
    evaluator_type: str = "custom"  # "ragas", "deepeval", "custom"
    metrics: list[str] = field(default_factory=list)
    thresholds: dict = field(default_factory=dict)

    # Status tracking
    status: EvalSetStatus = EvalSetStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    last_run_at: datetime | None = None

    # Aggregate results
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    avg_scores: dict = field(default_factory=dict)

@dataclass
class EvalResult:
    """Results from a single evaluation run."""
    id: str
    eval_set_id: str
    run_at: datetime
    duration_ms: int
    case_results: list[dict]  # Per-case scores
    aggregate_scores: dict
    passed_count: int
    failed_count: int
    total_count: int
```

#### 2. Storage Schema

```sql
CREATE TABLE eval_sets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    project_id TEXT,
    evaluator_type TEXT DEFAULT 'custom',
    metrics TEXT,  -- JSON array
    thresholds TEXT,  -- JSON dict
    status TEXT DEFAULT 'draft',
    created_at TEXT NOT NULL,
    last_run_at TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE eval_cases (
    id TEXT PRIMARY KEY,
    eval_set_id TEXT NOT NULL,
    trace_id TEXT,
    step_id TEXT,
    input TEXT NOT NULL,
    expected_output TEXT,
    actual_output TEXT,
    context TEXT,  -- JSON array for RAG
    metadata TEXT,  -- JSON dict
    FOREIGN KEY (eval_set_id) REFERENCES eval_sets(id) ON DELETE CASCADE
);

CREATE TABLE eval_results (
    id TEXT PRIMARY KEY,
    eval_set_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    run_id TEXT NOT NULL,  -- Groups results from same run
    run_at TEXT NOT NULL,
    scores TEXT NOT NULL,  -- JSON dict
    passed BOOLEAN,
    notes TEXT,
    FOREIGN KEY (eval_set_id) REFERENCES eval_sets(id) ON DELETE CASCADE,
    FOREIGN KEY (case_id) REFERENCES eval_cases(id) ON DELETE CASCADE
);
```

#### 3. TUI Screens

**New file: `src/agenttrace/tui/screens/eval_set_builder.py`**

```python
from textual.screen import Screen
from textual.widgets import DataTable, Button, Input, Select

class EvalSetBuilderScreen(Screen):
    """Screen for creating/editing evaluation sets."""

    BINDINGS = [
        ("a", "add_selected", "Add to Set"),
        ("e", "edit_expected", "Edit Expected"),
        ("s", "save_set", "Save"),
        ("escape", "go_back", "Back"),
    ]

    def __init__(self, store, selected_traces: list[str] = None):
        super().__init__()
        self.store = store
        self.selected_traces = selected_traces or []
        self.eval_set = EvalSet(id=str(uuid4()), name="New Evaluation Set")

    def compose(self):
        yield Input(placeholder="Evaluation set name...", id="name-input")
        yield Select(
            options=[
                ("Custom Evaluator", "custom"),
                ("RAGAS (RAG)", "ragas"),
                ("DeepEval", "deepeval"),
            ],
            id="evaluator-select"
        )
        yield DataTable(id="cases-table")
        yield Button("Run Evaluation", id="run-btn")

    def action_add_selected(self) -> None:
        """Add currently selected trace/step as eval case."""
        # Creates EvalCase from selected step
        # Opens modal to set expected output
        ...

    def action_edit_expected(self) -> None:
        """Edit expected output for selected case."""
        # Opens text editor for expected output
        ...
```

**New file: `src/agenttrace/tui/screens/eval_results.py`**

```python
from textual.screen import Screen
from textual.widgets import DataTable, Static, ProgressBar

class EvalResultsScreen(Screen):
    """Screen for viewing evaluation results."""

    BINDINGS = [
        ("f", "filter_failed", "Failed Only"),
        ("d", "show_details", "Details"),
        ("r", "re_run", "Re-run"),
        ("escape", "go_back", "Back"),
    ]

    def compose(self):
        yield Static(id="summary-panel")  # Pass rate, avg scores
        yield ProgressBar(id="pass-rate-bar")
        yield DataTable(id="results-table")

    def set_results(self, eval_set: EvalSet, results: list[EvalResult]) -> None:
        """Populate the screen with evaluation results."""
        # Update summary panel with aggregates
        # Populate table with per-case results
        # Color-code passed/failed rows
        ...
```

#### 4. Main App Integration

Add keybindings and actions to `app.py`:

```python
class AgentTraceApp(App):
    BINDINGS = [
        # ... existing ...
        ("E", "create_eval_set", "Create Eval Set"),
        ("R", "view_eval_results", "Eval Results"),
    ]

    def action_create_eval_set(self) -> None:
        """Open evaluation set builder with selected traces."""
        selected = self.get_selected_traces()  # Multi-select support
        self.push_screen(EvalSetBuilderScreen(self.store, selected))

    def action_view_eval_results(self) -> None:
        """Open evaluation results viewer."""
        self.push_screen(EvalResultsListScreen(self.store))
```

### Files to Modify/Create

| File | Changes |
|------|---------|
| `src/agenttrace/evaluation/models.py` | **New** - EvalSet, EvalCase, EvalResult |
| `src/agenttrace/storage/sqlite.py` | Add eval tables, CRUD methods |
| `src/agenttrace/tui/screens/eval_set_builder.py` | **New** - Creation screen |
| `src/agenttrace/tui/screens/eval_results.py` | **New** - Results screen |
| `src/agenttrace/tui/app.py` | Add keybindings, screen navigation |
| `src/agenttrace/evaluation/runner.py` | **New** - Orchestrate evaluation runs |

---

## Feature 4: AI Inspect for Failed Evaluations

### Current State

No AI-assisted analysis exists. When evaluations fail, users must manually:

1. Read the input/output
2. Compare to expected output
3. Identify why it failed
4. Determine what to fix

This is time-consuming and requires expertise.

### Why This is Valuable

1. **Root cause analysis**: AI can identify patterns humans might miss
2. **Actionable recommendations**: Suggests specific prompt/code changes
3. **Learning acceleration**: Helps users understand failure modes
4. **Batch analysis**: Can analyze multiple failures to find common issues

### Implementation Approach

#### 1. Inspector Module

**New file: `src/agenttrace/evaluation/inspector.py`**

```python
from dataclasses import dataclass
from enum import Enum

class FailureCategory(str, Enum):
    HALLUCINATION = "hallucination"
    INCOMPLETE = "incomplete"
    FORMAT_ERROR = "format_error"
    WRONG_FACTS = "wrong_facts"
    CONTEXT_IGNORED = "context_ignored"
    INSTRUCTION_MISSED = "instruction_missed"
    TONE_MISMATCH = "tone_mismatch"
    OTHER = "other"

@dataclass
class InspectionResult:
    case_id: str
    failure_category: FailureCategory
    root_cause: str
    evidence: list[str]  # Specific quotes/examples
    suggested_fixes: list[str]
    confidence: float  # 0-1
    analysis_tokens: int

@dataclass
class BatchInspectionResult:
    results: list[InspectionResult]
    common_patterns: list[str]
    priority_fixes: list[str]  # Most impactful changes
    summary: str

INSPECTION_PROMPT = '''You are an expert at analyzing LLM evaluation failures.

## Task
Analyze why this evaluation case failed and provide actionable recommendations.

## Input
{input}

## Expected Output
{expected_output}

## Actual Output
{actual_output}

## Evaluation Scores
{scores}

## Analysis Required
1. **Failure Category**: Classify as one of: hallucination, incomplete, format_error, wrong_facts, context_ignored, instruction_missed, tone_mismatch, other
2. **Root Cause**: Explain specifically why the output doesn't match expectations
3. **Evidence**: Quote specific parts of the output that demonstrate the issue
4. **Suggested Fixes**: List 2-3 concrete changes to the prompt or system that could fix this

Respond in JSON format:
```json
{
  "failure_category": "...",
  "root_cause": "...",
  "evidence": ["...", "..."],
  "suggested_fixes": ["...", "..."],
  "confidence": 0.85
}
```'''

class AIInspector:
    """AI-powered evaluation failure analysis."""

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4o",
        api_key: str | None = None,
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")

    async def inspect_case(self, case: EvalCase) -> InspectionResult:
        """Analyze a single failed evaluation case."""
        prompt = INSPECTION_PROMPT.format(
            input=case.input,
            expected_output=case.expected_output,
            actual_output=case.actual_output,
            scores=json.dumps(case.scores, indent=2),
        )

        # Call LLM (OpenAI or Anthropic)
        response = await self._call_llm(prompt)
        result = json.loads(response)

        return InspectionResult(
            case_id=case.id,
            failure_category=FailureCategory(result["failure_category"]),
            root_cause=result["root_cause"],
            evidence=result["evidence"],
            suggested_fixes=result["suggested_fixes"],
            confidence=result["confidence"],
            analysis_tokens=...,
        )

    async def inspect_batch(
        self,
        cases: list[EvalCase],
        find_patterns: bool = True,
    ) -> BatchInspectionResult:
        """Analyze multiple failures and identify patterns."""
        # Inspect each case
        results = await asyncio.gather(*[
            self.inspect_case(case) for case in cases
        ])

        if find_patterns:
            # Additional LLM call to find common patterns
            patterns = await self._find_patterns(results)
        else:
            patterns = []

        return BatchInspectionResult(
            results=results,
            common_patterns=patterns,
            priority_fixes=self._prioritize_fixes(results),
            summary=self._generate_summary(results),
        )

    async def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM provider."""
        if self.provider == "openai":
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key)
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content
        elif self.provider == "anthropic":
            # Similar for Anthropic
            ...
```

#### 2. TUI Integration

**New file: `src/agenttrace/tui/screens/ai_inspect.py`**

```python
from textual.screen import Screen
from textual.widgets import Static, Button, LoadingIndicator

class AIInspectScreen(Screen):
    """Screen for AI-powered failure analysis."""

    BINDINGS = [
        ("r", "re_inspect", "Re-analyze"),
        ("a", "apply_fix", "Apply Fix"),
        ("n", "next_failure", "Next"),
        ("escape", "go_back", "Back"),
    ]

    def __init__(self, case: EvalCase, inspector: AIInspector):
        super().__init__()
        self.case = case
        self.inspector = inspector
        self.result: InspectionResult | None = None

    def compose(self):
        yield Static(id="case-summary")
        yield LoadingIndicator(id="loading")
        yield Static(id="analysis-result", classes="hidden")
        yield Button("Apply Suggested Fix", id="apply-btn", classes="hidden")

    async def on_mount(self) -> None:
        """Run inspection when screen mounts."""
        self.result = await self.inspector.inspect_case(self.case)
        self._display_result()

    def _display_result(self) -> None:
        """Display the inspection result."""
        self.query_one("#loading").add_class("hidden")

        result_widget = self.query_one("#analysis-result")
        result_widget.update(self._format_result())
        result_widget.remove_class("hidden")

        self.query_one("#apply-btn").remove_class("hidden")

    def _format_result(self) -> str:
        """Format inspection result for display."""
        r = self.result
        return f"""
## Failure Category: {r.failure_category.value}
Confidence: {r.confidence:.0%}

## Root Cause
{r.root_cause}

## Evidence
{chr(10).join(f'- "{e}"' for e in r.evidence)}

## Suggested Fixes
{chr(10).join(f'{i+1}. {fix}' for i, fix in enumerate(r.suggested_fixes))}
"""
```

#### 3. Batch Analysis Screen

```python
class BatchInspectScreen(Screen):
    """Analyze multiple failures to find patterns."""

    def compose(self):
        yield Static("Analyzing failures...", id="status")
        yield ProgressBar(id="progress")
        yield Static(id="patterns", classes="hidden")
        yield DataTable(id="fixes-table", classes="hidden")

    async def analyze(self, cases: list[EvalCase]) -> None:
        """Run batch analysis."""
        result = await self.inspector.inspect_batch(cases)

        # Display common patterns
        self.query_one("#patterns").update(
            "## Common Patterns\n" +
            "\n".join(f"- {p}" for p in result.common_patterns)
        )

        # Display priority fixes in table
        table = self.query_one("#fixes-table")
        table.add_columns("Priority", "Fix", "Affected Cases")
        for i, fix in enumerate(result.priority_fixes, 1):
            table.add_row(str(i), fix, "...")
```

#### 4. Integration with Eval Results Screen

Add AI Inspect action to `eval_results.py`:

```python
class EvalResultsScreen(Screen):
    BINDINGS = [
        # ... existing ...
        ("I", "ai_inspect", "AI Inspect"),
        ("B", "batch_inspect", "Batch Inspect Failed"),
    ]

    def action_ai_inspect(self) -> None:
        """Inspect selected failed case with AI."""
        case = self.get_selected_case()
        if case and not case.passed:
            inspector = AIInspector()
            self.app.push_screen(AIInspectScreen(case, inspector))

    def action_batch_inspect(self) -> None:
        """Analyze all failed cases for patterns."""
        failed = [c for c in self.cases if not c.passed]
        if failed:
            inspector = AIInspector()
            self.app.push_screen(BatchInspectScreen(failed, inspector))
```

### Files to Modify/Create

| File | Changes |
|------|---------|
| `src/agenttrace/evaluation/inspector.py` | **New** - AI inspection logic |
| `src/agenttrace/tui/screens/ai_inspect.py` | **New** - Single case inspection |
| `src/agenttrace/tui/screens/batch_inspect.py` | **New** - Batch pattern analysis |
| `src/agenttrace/tui/screens/eval_results.py` | Add AI inspect keybindings |

---

## Implementation Priority

Based on dependencies and value:

### Phase 1: Foundation

1. **Enhanced SQLite with Projects/Versioning** - Required foundation for other features

### Phase 2: Core Features (can be parallelized)

2. **Evaluation Sets in TUI** - High user value, builds on storage
3. **Log Correlation** - Independent, high debugging value

### Phase 3: Advanced

4. **AI Inspect** - Requires evaluation infrastructure from Phase 2

---

## Summary

All four features are recommended for implementation:

| Feature | Key Value | Key Challenge |
|---------|-----------|---------------|
| SQLite Projects/Versioning | Unified storage, team workflows | Schema migration, backward compatibility |
| Log Correlation | Debug context, searchability | Log capture without performance impact |
| Evaluation Sets in TUI | No-code evaluation, iteration | UI complexity, evaluator integration |
| AI Inspect | Automated root cause analysis | LLM cost, response quality |

Each feature builds naturally on AgentTrace's existing architecture and addresses genuine workflow gaps for LLM application developers.
