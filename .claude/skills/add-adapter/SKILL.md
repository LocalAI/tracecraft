---
name: add-adapter
description: Scaffold a new TraceCraft framework adapter with tests and docs
---

Create a new TraceCraft adapter for the framework "$ARGUMENTS". Follow these steps:

1. **Study existing adapters** - Read these files first to understand the patterns:
   - `src/tracecraft/adapters/langchain.py` (callback handler pattern)
   - `src/tracecraft/adapters/llamaindex.py` (span handler pattern)
   - `src/tracecraft/adapters/pydantic_ai.py` (OTel span processor pattern)

2. **Create the adapter module** at `src/tracecraft/adapters/<name>.py`:
   - Translate framework-specific callbacks/events into TraceCraft `Step` objects
   - Use `get_current_run()` from `tracecraft.core.context` to find the active run
   - Map framework operations to appropriate `StepType` values
   - Capture inputs, outputs, timing, and model metadata
   - Handle errors gracefully - adapter failures must not break the user's code
   - Use thread-safe patterns (locks for shared state)

3. **Add optional dependency** in `pyproject.toml`:
   - Add a new extras group with the framework's package
   - Add it to the `all` bundle

4. **Create unit tests** at `tests/unit/test_adapter_<name>.py`:
   - Test step creation from framework events
   - Test step type inference
   - Test error capture
   - Mock the framework's types - don't require it as a test dependency

5. **Create integration doc** at `docs/integrations/<name>.md`:
   - Installation, Quick Start, and feature documentation
   - Add to the nav in `mkdocs.yml` under Integrations
   - Update `docs/integrations/index.md` with a summary

6. Run `uv run pytest tests/unit/test_adapter_<name>.py` to verify tests pass.
