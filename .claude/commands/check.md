Run the full pre-commit quality check suite on the codebase. Run each step sequentially:

1. `uv run ruff check src tests` - Lint check
2. `uv run ruff format --check src tests` - Format check
3. `uv run mypy src` - Type check
4. `uv run pytest --tb=short` - Run tests
5. `uv run mkdocs build --strict` - Docs build (must pass with zero warnings)

Report any failures with file paths and line numbers. If there are failures, offer to fix them.
