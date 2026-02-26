# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- SHA-pinned all GitHub Actions for supply-chain security
- SBOM generation (CycloneDX) in release workflow
- Build provenance attestations via `actions/attest-build-provenance`
- PyPI trusted publishing with attestation support
- `pip-audit` job in CI for dependency vulnerability scanning
- Version consistency check between `pyproject.toml` and `__init__.py`
- OpenSSF Scorecard workflow (weekly + on push to main)
- CodeQL analysis workflow (weekly + on push/PR to main)
- sdist excludes in `pyproject.toml` to keep published package minimal
- Reproducible sdist builds via `reproducible = true`
- CHANGELOG.md (this file)

### Changed

- CI workflow now uses explicit `permissions: contents: read`
- Release workflow adds `attestations: write` permission
- Docs deploy trigger workflow now uses SHA-pinned action ref

### Removed

- `mlflow.db` and `tui_screenshot.svg` from version control (kept on disk)

## [0.1.0] - 2025-01-01

### Added

- Initial release of TraceCraft
- Core tracing runtime with decorator-based instrumentation
- Framework adapters for LangChain, LlamaIndex, PydanticAI, and Claude SDK
- Exporters: console, JSONL, OTLP, MLflow, HTML
- Processors: redaction, sampling, enrichment
- Storage backends: SQLite, JSONL, MLflow
- Textual-based TUI for trace exploration
- CLI via Typer (`tracecraft` command)
- MkDocs documentation site

[Unreleased]: https://github.com/LocalAI/tracecraft/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/LocalAI/tracecraft/releases/tag/v0.1.0
