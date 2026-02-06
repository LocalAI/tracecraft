## Documentation Standards

- Documentation site uses MkDocs Material in `docs/`
- All docs builds must pass `mkdocs build --strict` with zero warnings
- Every page in `docs/` must be referenced in the `nav` section of `mkdocs.yml`
- Use Google-style docstrings for all public classes, methods, and functions
- Integration docs go in `docs/integrations/<name>.md` and must include: installation, quick start, and feature reference
- API docs go in `docs/api/` and should reference actual class/function names from the source
- Always verify class names, function signatures, and import paths against the actual source code before writing docs
- Abbreviations are defined in `includes/abbreviations.md` at project root (used by pymdownx.snippets)
