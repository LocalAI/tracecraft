# Architecture Rules

## Module Boundaries

- `core/` is the foundation: runtime, config, models, context. No imports from adapters/exporters/processors.
- `instrumentation/` provides decorators. Depends only on `core/`.
- `adapters/` bridge external frameworks to TraceCraft Steps. Each adapter is independent.
- `exporters/` send trace data to backends. Each exporter implements `BaseExporter`.
- `processors/` transform traces in-pipeline. Each implements `BaseProcessor`.
- `storage/` persists traces. Each backend implements `BaseTraceStore`.

## Key Patterns

- Runtime is a singleton created by `init()` in `core/runtime.py`. Use `get_runtime()` to access.
- Context propagation uses Python `contextvars`: `get_current_run()`, `get_current_step()`.
- Decorators create `Step` objects and attach them to the current `AgentRun` via context.
- Processor pipeline order is configurable: SAFETY (redact then sample) or EFFICIENCY (sample then redact).

## Adding New Components

- New exporters: subclass `BaseExporter` in `exporters/`, add optional dependency in pyproject.toml.
- New adapters: create module in `adapters/`, translate framework callbacks to TraceCraft Steps.
- New processors: subclass `BaseProcessor` in `processors/`.
- All new extras must be added to the `all` bundle in pyproject.toml.

## Thread Safety

- Runtime operations use `threading.Lock` for concurrent access.
- Step hierarchy modifications are protected by `_hierarchy_lock` in decorators.
- Adapter span tracking uses per-instance locks.
