# TraceCraft

Vendor-neutral LLM observability SDK - instrument once, observe anywhere.

## Quick Reference

```bash
# Development
uv sync --all-extras            # Install all dependencies
uv run pytest                   # Run tests
uv run pytest --cov             # Run tests with coverage
uv run ruff check src tests     # Lint
uv run ruff format src tests    # Format
uv run mypy src                 # Type check
uv run pre-commit run --all-files  # All checks

# Documentation (MkDocs - legacy)
uv run mkdocs serve             # Local docs server at http://127.0.0.1:8000
uv run mkdocs build --strict    # Build docs (must pass with zero warnings)


# CLI
uv run tracecraft tui                          # Launch TUI (reads from .tracecraft/config.yaml)
uv run tracecraft tui --serve                  # Start OTLP receiver :4318 + TUI
```

## Architecture

```
src/tracecraft/
  core/           # Runtime, config, models, context management
  instrumentation/  # Decorators (@trace_agent, @trace_tool, etc.) and auto-instrumentation
  adapters/       # Framework integrations (LangChain, LlamaIndex, PydanticAI, Claude SDK)
  exporters/      # Output backends (console, JSONL, OTLP, MLflow, HTML)
  processors/     # Trace pipeline (redaction, sampling, enrichment)
  storage/        # Persistence (SQLite, JSONL, MLflow)
  tui/            # Textual-based terminal UI for trace exploration
  cli/            # Typer CLI (`tracecraft` command)
  alerting/       # Alert rules and notifications
  propagation/    # Cross-service trace context propagation
  schema/         # Schema standards (OTel GenAI, OpenInference, canonical mapping)
  datasets/       # Trace-to-dataset converters for fine-tuning
  contrib/        # Cloud helpers (AWS, Azure, GCP), async utils, memory
  integrations/   # Third-party platform connectors (e.g., Langfuse prompts)
  playground/     # Interactive prompt runner and comparison tools
```

## Key Types

- `TraceCraftRuntime` (alias `TALRuntime`) - Main runtime, manages exporters and run lifecycle
- `TraceCraftConfig` - Dataclass for all configuration (service_name, redaction, sampling, cloud)
- `AgentRun` - Represents a complete traced execution (contains Steps)
- `Step` - Single operation in a trace (has type, inputs, outputs, attributes, children)
- `StepType` - Enum: AGENT, LLM, TOOL, RETRIEVAL, MEMORY, GUARDRAIL, EVALUATION, WORKFLOW, ERROR

## Public API

```python
import tracecraft

# Initialize (returns TraceCraftRuntime)
runtime = tracecraft.init(console=True, jsonl=True)

# Decorators
@tracecraft.trace_agent(name="my_agent")
@tracecraft.trace_tool(name="search")
@tracecraft.trace_llm(name="summarize", model="gpt-4", provider="openai")
@tracecraft.trace_retrieval(name="fetch_docs")

# Context manager
with tracecraft.step("processing", type=StepType.WORKFLOW) as s:
    s.outputs["result"] = result

# Multi-tenant
with runtime.run("task_name") as run:
    ...
```

## Code Standards

- Python 3.11+, strict mypy, ruff for lint/format
- Line length: 100 characters
- Google-style docstrings
- Type hints required on all public functions
- Conventional commits enforced by pre-commit hook
- Test coverage minimum: 80% (enforced by CI)
- Build system: hatchling

## Project Layout

- `src/tracecraft/` - Library source
- `tests/unit/` - Unit tests
- `tests/integration/` - Integration tests
- `tests/e2e/` - End-to-end tests
- `examples/` - Usage examples
- `docs/` - MkDocs documentation site (legacy)

## Important Patterns

- The `init()` function in `core/runtime.py` is the main entry point - it creates a global singleton runtime
- Decorators in `instrumentation/decorators.py` create Steps and attach them to the current AgentRun via context vars
- Adapters translate framework-specific callbacks/spans into TraceCraft Steps
- Processors run in a pipeline (configurable order: SAFETY or EFFICIENCY) before export
- The TUI reads from JSONL/SQLite storage for offline trace exploration
