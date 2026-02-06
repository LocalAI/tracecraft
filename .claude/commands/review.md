Review the current staged or unstaged changes for quality. Run `git diff` (or `git diff --cached` if there are staged changes) and analyze:

1. **Correctness** - Logic errors, edge cases, off-by-one errors
2. **Type safety** - Missing type hints, incorrect types, mypy compatibility
3. **Security** - OWASP top 10, injection risks, credential exposure
4. **Thread safety** - Race conditions, missing locks (TraceCraft uses threading)
5. **API consistency** - Does it follow existing patterns in the codebase?
6. **Test coverage** - Are there tests for the changes? Are edge cases covered?
7. **Documentation** - Are docstrings added/updated for public API changes?

Be specific: reference file paths and line numbers. Flag issues by severity (critical/warning/suggestion).
