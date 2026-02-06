# Testing

- Tests live in `tests/unit/`, `tests/integration/`, and `tests/e2e/`.
- Use pytest with `pytest-asyncio` (auto mode configured in pyproject.toml).
- Test files: `test_<module>.py`. Test functions: `test_<behavior>`.
- Use descriptive test names: `test_agent_raises_error_on_invalid_input`.
- Follow Arrange-Act-Assert pattern.
- Use `pytest.fixture` for shared setup. Prefer function-scoped fixtures.
- Mock external dependencies, never call real APIs in unit tests.
- Coverage minimum is 80% overall, enforced by CI.
- Run tests: `uv run pytest`
- Run with coverage: `uv run pytest --cov=src/tracecraft --cov-report=html`
- Snapshot tests for TUI use `pytest-textual-snapshot`.
