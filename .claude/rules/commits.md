# Commits and PRs

- Use conventional commits (enforced by pre-commit hook):
  - `feat:` new features
  - `fix:` bug fixes
  - `docs:` documentation only
  - `test:` test additions/changes
  - `refactor:` code restructuring
  - `chore:` maintenance, deps, CI
  - `perf:` performance improvements
- Keep commits focused: one logical change per commit.
- Run `uv run pre-commit run --all-files` before committing.
- PR titles should also follow conventional commit format.
- Link related issues in PR description with `Closes #123`.
