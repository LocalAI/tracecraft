---
name: add-exporter
description: Scaffold a new TraceCraft exporter with base class, tests, and docs
---

Create a new TraceCraft exporter named "$ARGUMENTS". Follow these steps:

1. **Create the exporter module** at `src/tracecraft/exporters/<name>.py`:
   - Subclass `BaseExporter` from `tracecraft.exporters.base`
   - Implement required methods: `export(run: AgentRun)`, `flush()`, `shutdown()`
   - Add proper type annotations and Google-style docstrings
   - Use the existing exporters as reference (read `src/tracecraft/exporters/console.py` and `src/tracecraft/exporters/jsonl.py` first)

2. **Register in `__init__.py`** at `src/tracecraft/exporters/__init__.py`:
   - Add the import and export in `__all__`

3. **Add optional dependency** in `pyproject.toml`:
   - Create a new optional extra group if the exporter needs third-party packages
   - Add it to the `all` bundle

4. **Create unit tests** at `tests/unit/test_exporter_<name>.py`:
   - Test export with a sample AgentRun
   - Test flush and shutdown
   - Test error handling
   - Mock any external dependencies

5. **Add documentation** at `docs/user-guide/exporters.md`:
   - Add a section describing the new exporter
   - Include configuration example

6. Run `uv run pytest tests/unit/test_exporter_<name>.py` to verify tests pass.
