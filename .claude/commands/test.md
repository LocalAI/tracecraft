Run the test suite with coverage and report results.

1. Run: `uv run pytest --cov=src/tracecraft --cov-report=term-missing --tb=short $ARGUMENTS`
2. Summarize:
   - Total tests passed/failed/skipped
   - Overall coverage percentage
   - Any files below 80% coverage
   - Failed test details with file paths and line numbers
3. If tests fail, investigate the failures and suggest fixes.
