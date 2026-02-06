Set up a development environment for a new contributor.

1. Run `uv sync --all-extras` to install all dependencies
2. Run `uv run pre-commit install` to set up git hooks
3. Run `uv run pytest --tb=short -q` to verify the test suite passes
4. Run `uv run ruff check src tests` to verify linting passes
5. Run `uv run mypy src` to verify type checking passes
6. Report the status of each step. If any step fails, diagnose the issue and suggest a fix.
