# Python Standards

- Target Python 3.11+. Use modern syntax: `X | Y` unions, `list[str]` generics.
- All public functions and methods must have type annotations.
- Use Google-style docstrings with Args, Returns, Raises, and Example sections.
- Line length limit is 100 characters (enforced by ruff).
- Use `from __future__ import annotations` in all modules for forward references.
- Prefer `dataclass` or Pydantic `BaseModel` over plain dicts for structured data.
- Use `pathlib.Path` instead of string paths.
- Use `datetime.now(UTC)` not `datetime.utcnow()`.
- Imports: stdlib first, third-party second, local third (enforced by ruff isort).
- Use `TYPE_CHECKING` guard for imports only needed at type-check time.
- Never use bare `except:`. Always catch specific exceptions.
- Use `contextlib.suppress()` instead of try/except/pass for simple ignores.
