Build and validate the MkDocs documentation site.

1. Run `uv run mkdocs build --strict` - must pass with zero warnings
2. If there are errors, diagnose and fix them:
   - Orphaned pages: add to nav in mkdocs.yml or remove the file
   - Broken links: fix the reference path
   - Missing files: create them or remove the nav entry
3. Report the build status and any issues found.
