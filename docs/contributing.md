# Contributing to Trace Craft

Thank you for your interest in contributing to Trace Craft! This guide will help you get started.

## Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please read and follow our Code of Conduct (coming soon).

## Ways to Contribute

### Reporting Bugs

Found a bug? Please report it:

1. Check [existing issues](https://github.com/LocalAI/tracecraft/issues) to avoid duplicates
2. Create a new issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Your environment (OS, Python version, Trace Craft version)
   - Minimal code example if possible

### Suggesting Features

Have an idea? We'd love to hear it:

1. Check [existing discussions](https://github.com/LocalAI/tracecraft/discussions)
2. Create a new discussion explaining:
   - The problem you're trying to solve
   - Your proposed solution
   - Why this would benefit others
   - Examples of how it would be used

### Contributing Code

Ready to contribute code? Great! Follow these steps:

1. Fork the repository
2. Set up your development environment
3. Create a feature branch
4. Make your changes
5. Write tests
6. Submit a pull request

## Development Setup

### Prerequisites

- Python 3.11 or later
- uv (recommended) or pip
- Git

### Clone and Install

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/tracecraft.git
cd tracecraft

# Install with all development dependencies
uv sync --all-extras

# Or using pip
pip install -e ".[all,dev]"
```

### Install Pre-Commit Hooks

```bash
uv run pre-commit install
```

This will run checks on every commit:

- Code formatting (ruff)
- Type checking (mypy)
- Security scanning (bandit)
- Test suite (pytest)

### Verify Installation

```bash
# Run tests
uv run pytest

# Run linter
uv run ruff check src tests

# Run type checker
uv run mypy src

# Run all checks
uv run pre-commit run --all-files
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

Use prefixes:

- `feature/` for new features
- `fix/` for bug fixes
- `docs/` for documentation
- `refactor/` for refactoring
- `test/` for test improvements

### 2. Make Changes

Write clean, well-documented code:

```python
def my_function(arg: str) -> str:
    """Short description of what this does.

    Longer explanation if needed.

    Args:
        arg: Description of the argument

    Returns:
        Description of the return value

    Example:
        >>> my_function("test")
        "result"
    """
    return f"processed: {arg}"
```

### 3. Write Tests

Every feature needs tests:

```python
# tests/unit/test_my_feature.py
import pytest
from tracecraft.my_module import my_function

def test_my_function():
    """Test my_function with valid input."""
    result = my_function("test")
    assert result == "processed: test"

def test_my_function_error():
    """Test my_function with invalid input."""
    with pytest.raises(ValueError):
        my_function(None)

@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await my_async_function()
    assert result is not None
```

Run tests:

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/unit/test_my_feature.py

# Run with coverage
uv run pytest --cov=src/tracecraft --cov-report=html

# Run specific test
uv run pytest tests/unit/test_my_feature.py::test_my_function
```

### 4. Update Documentation

If you're adding a feature:

1. Add docstrings to your code
2. Update relevant documentation pages in `docs/`
3. Add examples if appropriate
4. Update the changelog

### 5. Commit Your Changes

Write clear commit messages:

```bash
git add .
git commit -m "feat: add support for new exporter

- Implement NewExporter class
- Add tests for NewExporter
- Update documentation
- Add example usage

Closes #123"
```

Use conventional commit prefixes:

- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation
- `test:` for tests
- `refactor:` for refactoring
- `chore:` for maintenance

### 6. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub with:

- Clear title and description
- Reference to related issues
- Summary of changes
- Test results
- Screenshots if applicable

## Code Style

### Python Style

We use:

- **Ruff** for linting and formatting
- **mypy** for type checking
- **Black-compatible** formatting

Run formatters:

```bash
# Format code
uv run ruff format src tests

# Fix linting issues
uv run ruff check --fix src tests
```

### Type Hints

All code must be fully typed:

```python
from typing import Any

def process(data: dict[str, Any], count: int = 10) -> list[str]:
    """Process data with type hints."""
    results: list[str] = []
    # Implementation
    return results
```

### Docstring Style

Use Google-style docstrings:

```python
def my_function(arg1: str, arg2: int = 0) -> bool:
    """One-line summary.

    Longer description if needed.

    Args:
        arg1: Description of arg1
        arg2: Description of arg2 with default

    Returns:
        Description of return value

    Raises:
        ValueError: When arg1 is invalid

    Example:
        >>> my_function("test")
        True
    """
    pass
```

## Testing Guidelines

### Test Structure

```
tests/
├── unit/           # Unit tests
├── integration/    # Integration tests
└── e2e/           # End-to-end tests
```

### Writing Good Tests

1. **Test one thing** - Each test should verify one behavior
2. **Use descriptive names** - `test_agent_raises_error_on_invalid_input`
3. **Arrange-Act-Assert** - Clear structure
4. **Test edge cases** - Not just the happy path
5. **Use fixtures** - Share setup code

Example:

```python
import pytest
from tracecraft import TraceCraftRuntime, TraceCraftConfig

@pytest.fixture
def runtime():
    """Create test runtime."""
    config = TraceCraftConfig(console_enabled=False)
    return TraceCraftRuntime(config=config)

def test_runtime_initialization(runtime):
    """Test runtime is initialized correctly."""
    # Arrange is done in fixture

    # Act
    result = runtime.get_config()

    # Assert
    assert result is not None
    assert result.console_enabled is False

@pytest.mark.asyncio
async def test_async_tracing(runtime):
    """Test async function tracing."""
    # Test implementation
    pass
```

### Test Coverage

Maintain high test coverage:

```bash
# Generate coverage report
uv run pytest --cov=src/tracecraft --cov-report=html

# View report
open htmlcov/index.html
```

Aim for:

- 80%+ overall coverage (enforced by CI)
- 100% for critical paths
- 90%+ for new features

## Documentation

### Building Docs Locally

```bash
# Install docs dependencies
pip install ".[docs]"

# Serve docs locally
mkdocs serve

# Open http://127.0.0.1:8000 in browser
```

### Documentation Structure

```
docs/
├── index.md                    # Home page
├── getting-started/            # Getting started guides
├── user-guide/                 # User documentation
├── integrations/               # Framework integrations
├── api/                        # API reference
├── deployment/                 # Deployment guides
└── migration/                  # Migration guides
```

### Writing Documentation

1. Use clear, simple language
2. Include code examples
3. Add diagrams where helpful (Mermaid)
4. Cross-reference related pages
5. Test all code examples

## Pull Request Process

### Before Submitting

Checklist:

- [ ] Tests pass locally
- [ ] Code is formatted and linted
- [ ] Type checking passes
- [ ] Documentation is updated
- [ ] Changelog is updated (if applicable)
- [ ] Commit messages are clear

### PR Template

```markdown
## Description
Brief description of changes

## Related Issues
Closes #123

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## How Has This Been Tested?
Describe the tests you ran

## Checklist
- [ ] Tests pass
- [ ] Documentation updated
- [ ] Changelog updated
```

### Review Process

1. Automated checks run (CI)
2. Maintainer reviews code
3. Feedback is provided
4. You address feedback
5. PR is approved and merged

## Release Process

Releases are handled by maintainers:

1. Version bump in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create git tag
4. GitHub Actions builds and publishes to PyPI

## Community

### Getting Help

- **GitHub Discussions** - Ask questions, share ideas
- **GitHub Issues** - Report bugs, request features
- **Discord** (coming soon) - Real-time chat

### Recognition

Contributors are recognized:

- In release notes
- In the README contributors section
- With GitHub contributor badge

## License

By contributing, you agree that your contributions will be licensed under the Apache-2.0 License.

## Questions?

Don't hesitate to ask! Create a discussion or reach out to maintainers.

Thank you for contributing to Trace Craft!
