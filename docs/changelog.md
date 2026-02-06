# Changelog

All notable changes to TraceCraft will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Documentation site with MkDocs and Material theme

## [0.1.0] - 2024-01-15

### Added

- Initial release of TraceCraft
- Core instrumentation decorators (`@trace_agent`, `@trace_tool`, `@trace_llm`, `@trace_retrieval`)
- Console and JSONL exporters
- OTLP exporter for OpenTelemetry Protocol support
- PII redaction processor with built-in patterns
- Sampling processor for trace volume control
- LangChain integration via `TraceCraftCallbackHandler`
- LlamaIndex integration via `TraceCraftSpanHandler`
- PydanticAI adapter
- Claude SDK wrapper
- Auto-instrumentation for OpenAI and Anthropic SDKs
- Terminal UI (TUI) for interactive trace exploration
- Multi-tenant runtime support
- AWS AgentCore integration
- Azure AI Foundry integration
- GCP Vertex Agent Builder integration
- MLflow exporter
- HTML report exporter
- Comprehensive test suite
- Documentation and examples

### Changed

- N/A (initial release)

### Deprecated

- N/A (initial release)

### Removed

- N/A (initial release)

### Fixed

- N/A (initial release)

### Security

- Built-in PII redaction enabled by default
- Secure defaults for all exporters

## Release Notes

### 0.1.0 - Initial Release

TraceCraft is now available as a vendor-neutral LLM observability SDK. Key features:

- **Local-First Development** - Beautiful console output and JSONL files without any backend
- **Built on OpenTelemetry** - Industry-standard foundation
- **Framework Agnostic** - Works with LangChain, LlamaIndex, PydanticAI, and custom code
- **Privacy by Default** - PII redaction built into the SDK
- **Multiple Export Targets** - Console, JSONL, OTLP, MLflow, HTML

Install with:

```bash
pip install tracecraft
```

See the [documentation](https://tracecraft.dev) for complete usage guide.

---

[Unreleased]: https://github.com/LocalAI/tracecraft/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/LocalAI/tracecraft/releases/tag/v0.1.0
