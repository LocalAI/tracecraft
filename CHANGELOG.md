# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1](https://github.com/LocalAI/tracecraft/compare/v0.2.0...v0.2.1) (2026-03-02)


### Bug Fixes

* **ci:** update scorecard action to use correct SHA for publish verification ([#6](https://github.com/LocalAI/tracecraft/issues/6)) ([51676d3](https://github.com/LocalAI/tracecraft/commit/51676d3f1f3c8e55962caf1bdb32ab1179606ecb))

## [0.2.0](https://github.com/LocalAI/tracecraft/compare/v0.1.0...v0.2.0) (2026-03-02)


### ⚠ BREAKING CHANGES

* This simplifies TraceCraft to focus solely on tracing.
* Package renamed from `agenttrace` to `tracecraft`

### Features

* Add Azure AI Foundry, AWS Bedrock AgentCore, and GCP Vertex AI integration ([84ab05a](https://github.com/LocalAI/tracecraft/commit/84ab05a21a18a729b3b8a74554f177cde9a12763))
* **auto:** add framework auto-instrumentation for LangChain and LlamaIndex ([52d7e10](https://github.com/LocalAI/tracecraft/commit/52d7e10a93d342a0258c44e5d6b5c62f1677bd32))
* **cli,docs:** rename tui command, simplest-path docs, nav restructure ([6f645ed](https://github.com/LocalAI/tracecraft/commit/6f645ed3ba1d502f195969b16d43165fb5591f23))
* **docs:** add sync script to convert MkDocs to Nextra format ([bdfcbdf](https://github.com/LocalAI/tracecraft/commit/bdfcbdfe72a3232b651a3bedd12de115d89b3772))
* **docs:** sync MkDocs documentation to Nextra format ([e0e7b07](https://github.com/LocalAI/tracecraft/commit/e0e7b072dd984430f23d76a381b9648a70c6be98))
* **examples:** add real OpenAI and Anthropic receiver examples ([7d318ec](https://github.com/LocalAI/tracecraft/commit/7d318ec4b33d84c9c0b887d79df38ab68759f7db))
* **examples:** add variety of trace patterns to receiver demo ([ac503cc](https://github.com/LocalAI/tracecraft/commit/ac503cc46254169cb5a13cb5709d2c053c67f9b3))
* **examples:** add variety to receiver demo traces ([67ef1ba](https://github.com/LocalAI/tracecraft/commit/67ef1ba7a464740a437906861db10db3984c4fd3))
* **otel:** add simple setup_exporter() API for seamless OTel configuration ([c83bce7](https://github.com/LocalAI/tracecraft/commit/c83bce7901824820f24d379e393acd2cfcd40431))
* **receiver:** add cost calculation and improve TUI panel resizing ([735a887](https://github.com/LocalAI/tracecraft/commit/735a88709e089818bf2427eeb1d0aa211f26140b))
* **receiver:** add OTLP HTTP receiver for live trace ingestion ([3bd99a6](https://github.com/LocalAI/tracecraft/commit/3bd99a66f4cba38a7aa79bfbbe0c4d5e0bdbbc55))
* Rename package from agenttrace to tracecraft and simplify TUI UX ([65dd6c0](https://github.com/LocalAI/tracecraft/commit/65dd6c098b90a1e227e3fdf2228e6613f7990554))
* **storage:** add remote trace backends for X-Ray, Cloud Trace, Azure Monitor, DataDog ([3619b6a](https://github.com/LocalAI/tracecraft/commit/3619b6a4a650ef72f7e6190b23af000a96f11e1a))
* **tui:** add comparison view, notes editor, and confirm delete screens ([4d36ce6](https://github.com/LocalAI/tracecraft/commit/4d36ce6a158d2f04b166276d4c0c80481da8ca58))


### Bug Fixes

* **auto:** add provider-specific unpatcher and safer handler cleanup ([bff0290](https://github.com/LocalAI/tracecraft/commit/bff029050e16d8f103adc366bb891f4c57a91fb9))
* **auto:** improve thread safety and uninstrumentation in AutoInstrumentor ([6b0fd78](https://github.com/LocalAI/tracecraft/commit/6b0fd78890fd77260aa910e641e0ca0401f1c891))
* **ci:** add --snapshot-warn-unused to prevent unused snapshots failing CI ([2c5866c](https://github.com/LocalAI/tracecraft/commit/2c5866c6117da18c62c3cbbe63386061787c9008))
* **ci:** fix docs trigger secret guard and scorecard permissions ([5c83128](https://github.com/LocalAI/tracecraft/commit/5c831282ed86e35a30343be3062e3118928aacdd))
* **ci:** increase test timeout to 30 minutes ([1610654](https://github.com/LocalAI/tracecraft/commit/1610654a049bcb12587bd89a3491f3491c47af37))
* **ci:** lower coverage threshold to 55% and add test timeout ([a4bf75a](https://github.com/LocalAI/tracecraft/commit/a4bf75a714c032af9e01e0c4b1b2878ac39cbf6b))
* **ci:** resolve all mypy errors and pip-audit failures ([415e3be](https://github.com/LocalAI/tracecraft/commit/415e3be0c1108d7d753433dc878fd9722ea10f20))
* **ci:** resolve test deadlock in conftest runtime reset fixture ([85e7cc1](https://github.com/LocalAI/tracecraft/commit/85e7cc1f6b3e9d73b51650e1d2bcf842a17301d5))
* **ci:** resolve workflow failures across all CI pipelines ([8d3b6b4](https://github.com/LocalAI/tracecraft/commit/8d3b6b4d62953dc75aa74abc13baf4f19fb427ef))
* construct slack test tokens programmatically to avoid secret scanning ([d63cc21](https://github.com/LocalAI/tracecraft/commit/d63cc21c7437ea4c7358e846ebfed269695a5681))
* construct stripe test keys programmatically to avoid secret scanning ([5641eb6](https://github.com/LocalAI/tracecraft/commit/5641eb67bfce644ebc8c33cac63f005fb8a09ab2))
* **deps:** resolve Dependabot security alerts by bumping dependency minimums ([a5c2d92](https://github.com/LocalAI/tracecraft/commit/a5c2d925a594fac0f25343b42f0c3d415e826229))
* **docs:** correct OTLPReceiver usage in Quick Start ([b364450](https://github.com/LocalAI/tracecraft/commit/b3644507258d59292bb79b0ce5ff58a797fb5101))
* **docs:** correct two broken internal links ([2369a82](https://github.com/LocalAI/tracecraft/commit/2369a82167c6eed7fab3e6ebb3975fa97d415803))
* **docs:** handle nested admonitions inside tabs ([90fbe9c](https://github.com/LocalAI/tracecraft/commit/90fbe9ce78c41c38f1795b24fa8b62329cab3299))
* **examples:** wrap OpenAI calls in parent spans for proper hierarchy ([116d595](https://github.com/LocalAI/tracecraft/commit/116d595590037c8adbdc34649d7fea3c0c1564f3))
* **otel:** improve robustness and add comprehensive tests ([3a57540](https://github.com/LocalAI/tracecraft/commit/3a57540b86dc1ff9aac421e36f619ab64ef50a9f))
* **receiver:** improve response accuracy and add SQLite watch test ([2e23cc6](https://github.com/LocalAI/tracecraft/commit/2e23cc6a546e796931d14419d37934f6bd9dcfe1))
* **receiver:** improve robustness and handle edge cases ([0690a90](https://github.com/LocalAI/tracecraft/commit/0690a9038c04abcb6945a30f0a66d2d33f77239f))
* **receiver:** populate AgentRun input/output from root step ([01a0fcc](https://github.com/LocalAI/tracecraft/commit/01a0fcc1803d40257b479e763637717ecaeaef99))
* **receiver:** support OpenAI instrumentation attribute formats ([0b35035](https://github.com/LocalAI/tracecraft/commit/0b35035e9c2e7c20ea9b27821691c14326f84dc8))
* **release:** prevent major version bumps during pre-1.0 development ([#4](https://github.com/LocalAI/tracecraft/issues/4)) ([c056bd8](https://github.com/LocalAI/tracecraft/commit/c056bd865c63496d1e33ac230a3256718d3cda4c))
* Remove remaining eval/agent references from help screen ([0d5f177](https://github.com/LocalAI/tracecraft/commit/0d5f1771ed8c4697ba36fc27509507851a0db99f))
* **tests:** resolve 8 test failures on CI ([c1e4339](https://github.com/LocalAI/tracecraft/commit/c1e433913bc730e3edc9d53c15662fc35164912e))
* **tests:** use bool() for skipif CI env check to avoid eval error ([ef4dcd7](https://github.com/LocalAI/tracecraft/commit/ef4dcd7728726fc19e0685a727c61c8e6f5a9a65))
* use obviously fake test secrets to avoid GitHub secret scanning ([a19b2ba](https://github.com/LocalAI/tracecraft/commit/a19b2bad54b4bcaeb12b0ac4db69b8f26385b97c))


### Documentation

* **examples:** add OTLP receiver examples ([9c74fba](https://github.com/LocalAI/tracecraft/commit/9c74fbafd61bbecaf1319e963fab296074756237))
* **otel:** add comprehensive OpenTelemetry receiver documentation ([23394ba](https://github.com/LocalAI/tracecraft/commit/23394ba8fe83b2be4531fcc8aae55f9dd98ae92b))
* **otel:** add missing API documentation and advanced usage section ([7c04a5a](https://github.com/LocalAI/tracecraft/commit/7c04a5a0457588010fa3a5d8a7088de3b68f04f5))
* **otel:** add missing EVALUATION step type to documentation ([c49179c](https://github.com/LocalAI/tracecraft/commit/c49179c32f85bbb641e7a6dc6e1ad8d5a01883d8))
* **otel:** enhance documentation with comprehensive examples and navigation ([58cad7c](https://github.com/LocalAI/tracecraft/commit/58cad7cd837cec256b76c8a25decac45dc296da7))
* rename TraceCraft → Trace Craft, update copyright to Local AI ([b0ab6d4](https://github.com/LocalAI/tracecraft/commit/b0ab6d483910546004687754b3378bc9183ba790))


### Code Refactoring

* Remove evaluation and agent functionality ([187541f](https://github.com/LocalAI/tracecraft/commit/187541f8a435136adc4b95aaf49aa09190224217))

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
