# Contributing to TraceCraft

Thank you for your interest in contributing to TraceCraft! This document provides guidelines and instructions for contributing.

## Code of Conduct

Please be respectful and constructive in all interactions. We welcome contributors of all experience levels.

## Getting Started

### Prerequisites

- Python 3.11 or 3.12
- [uv](https://docs.astral.sh/uv/) package manager

### Development Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/LocalAI/tracecraft.git
   cd tracecraft
   ```

2. Install dependencies:

   ```bash
   uv sync --all-extras
   ```

3. Install pre-commit hooks:

   ```bash
   uv run pre-commit install
   uv run pre-commit install --hook-type commit-msg
   ```

4. Verify your setup:

   ```bash
   uv run pytest
   ```

## Development Workflow

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/tracecraft --cov-report=term-missing

# Run specific test file
uv run pytest tests/unit/test_core.py

# Run tests matching a pattern
uv run pytest -k "test_trace"
```

### Code Quality

We use several tools to maintain code quality:

```bash
# Linting
uv run ruff check .

# Auto-fix linting issues
uv run ruff check --fix .

# Formatting
uv run ruff format .

# Type checking
uv run mypy src/

# Security scanning
uv run bandit -r src/ -c pyproject.toml

# Run all pre-commit hooks
uv run pre-commit run --all-files
```

### Code Style

- We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Type hints are required (enforced by mypy in strict mode)
- Maximum line length is 100 characters
- Imports are sorted automatically by Ruff

## Making Changes

### Branching Strategy

1. Create a branch from `main`:

   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

2. Make your changes with clear, focused commits

3. Push and open a pull request

### Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/). Your commit messages must follow this format:

```text
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

**Types:**

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**

```text
feat(exporters): add Datadog exporter support
fix(adapters): handle empty response in LangChain adapter
docs: update installation instructions
test(core): add tests for trace context propagation
```

### Pull Request Guidelines

1. **Keep PRs focused**: One feature or fix per PR
2. **Update tests**: Add or update tests for your changes
3. **Maintain coverage**: The project requires 80% test coverage
4. **Update documentation**: If your change affects the API or usage
5. **Pass CI**: All checks must pass before merging

## Project Structure

```text
src/tracecraft/
├── adapters/       # Framework integrations (LangChain, LlamaIndex, etc.)
├── alerting/       # Quality alerts and webhooks
├── cli/            # Command-line interface
├── contrib/        # Cloud provider integrations and utilities
├── core/           # Core functionality and models
├── datasets/       # Dataset converters
├── exporters/      # Trace exporters (OTLP, MLflow, etc.)
├── instrumentation/# Decorators and auto-instrumentation
├── integrations/   # External service integrations
├── playground/     # LLM comparison playground
├── processors/     # Trace processors (redaction, sampling, etc.)
├── propagation/    # Context propagation (W3C, X-Ray, etc.)
├── schema/         # Schema definitions (OTel GenAI, OpenInference)
├── storage/        # Trace storage backends
└── tui/            # Terminal user interface
```

## Adding New Features

### Adding a New Exporter

1. Create a new file in `src/tracecraft/exporters/`
2. Inherit from the base exporter class
3. Implement required methods
4. Add tests in `tests/unit/`
5. Update `__init__.py` exports

### Adding a New Adapter

1. Create a new file in `src/tracecraft/adapters/`
2. Follow the existing adapter patterns
3. Add optional dependency in `pyproject.toml` if needed
4. Add tests and documentation

## Testing

### Test Structure

```text
tests/
├── unit/           # Unit tests
├── integration/    # Integration tests
└── conftest.py     # Shared fixtures
```

### Writing Tests

- Use pytest fixtures for common setup
- Use `pytest.mark.asyncio` for async tests
- Mock external services appropriately
- Aim for clear, descriptive test names

```python
def test_trace_agent_captures_input_and_output():
    """Test that trace_agent decorator captures function I/O."""
    ...
```

## Getting Help

- Open an issue for bugs or feature requests
- Check existing issues before creating new ones
- For questions, use GitHub Discussions

## License

By contributing, you agree that your contributions will be licensed under the Apache-2.0 License.
