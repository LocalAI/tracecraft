# Documentation Site Plan for AgentTrace

## Current State Assessment

### Documentation Quality by Category

| Aspect | Quality | Notes |
|--------|---------|-------|
| Type hints | ★★★★★ | Comprehensive, strict mypy mode |
| Docstrings | ★★★★☆ | Google-style, consistent across modules |
| Examples | ★★★★☆ | 13+ organized examples with clear structure |
| API reference site | ☆☆☆☆☆ | None exists |
| User guides | ★☆☆☆☆ | Only README and examples |

### Current Documentation Assets

- **README.md**: High-level project overview, quick start, core features
- **examples/README.md**: Comprehensive learning path, dependency guides, troubleshooting
- **docs/**: Contains research files and deployment guides (not user-facing)
- **Code docstrings**: Google-style throughout, excellent coverage

### Critical Gaps

1. No API reference website
2. No architectural decision records (ADRs)
3. No troubleshooting/FAQ beyond examples
4. No deployment/configuration guides
5. No performance tuning documentation
6. No contribution guidelines
7. No migration guides for version upgrades
8. No integration guides for backends (Langfuse, Datadog, etc.)

---

## Recommended Approach: MkDocs + Material Theme

### Why MkDocs over Sphinx

| Factor | MkDocs | Sphinx |
|--------|--------|--------|
| Markup language | Markdown (matches existing docs) | reStructuredText (would require conversion) |
| Setup complexity | Single YAML file | Multiple config files |
| Live preview | Built-in dev server | Requires rebuild each change |
| Theme quality | Material theme is modern out-of-box | Requires customization |
| Docstring extraction | mkdocstrings plugin | sphinx-autodoc (native) |
| Learning curve | Low | Medium-High |

### When to Consider Sphinx Instead

- Need PDF/ePub output for offline documentation
- Need intersphinx linking to Python stdlib, OpenTelemetry docs
- Require complex cross-referencing between API elements

---

## Required Plugins

```yaml
plugins:
  - search                    # Built-in search functionality
  - mkdocstrings:             # Auto-generate API docs from docstrings
      handlers:
        python:
          options:
            docstring_style: google
            show_source: true
            show_root_heading: true
            members_order: source
  - autorefs                  # Cross-referencing between pages
  - gen-files                 # Generate pages programmatically
  - literate-nav              # Navigation from markdown
  - mike                      # Documentation versioning
```

---

## Proposed Documentation Structure

```
docs/
├── index.md                    # Landing page (adapted from README)
├── getting-started/
│   ├── installation.md         # pip/uv install, requirements
│   ├── quickstart.md           # 5-minute hello world
│   └── configuration.md        # Environment variables, config options
├── user-guide/
│   ├── decorators.md           # @trace_agent, @trace_tool, @trace_llm, etc.
│   ├── exporters.md            # Console, JSONL, HTML, OTLP
│   ├── processors.md           # Enrichment, redaction, sampling
│   ├── adapters.md             # LangChain, LlamaIndex, PydanticAI
│   └── storage.md              # JSONL, SQLite, MLflow backends
├── tutorials/
│   ├── basic-tracing.md        # Link to examples/01-getting-started
│   ├── framework-integration.md # Link to examples/02-frameworks
│   ├── production-setup.md     # Link to examples/04-production
│   └── evaluation.md           # Link to examples/06-evaluation
├── reference/
│   ├── api/                    # Auto-generated from docstrings
│   │   ├── core.md             # agenttrace.core module
│   │   ├── instrumentation.md  # agenttrace.instrumentation module
│   │   ├── exporters.md        # agenttrace.exporters module
│   │   ├── processors.md       # agenttrace.processors module
│   │   ├── adapters.md         # agenttrace.adapters module
│   │   ├── schema.md           # agenttrace.schema module
│   │   └── storage.md          # agenttrace.storage module
│   ├── cli.md                  # Command-line interface reference
│   └── configuration.md        # All config options with defaults
├── integrations/
│   ├── langfuse.md             # Langfuse backend setup
│   ├── datadog.md              # Datadog APM integration
│   ├── phoenix.md              # Arize Phoenix setup
│   └── grafana-tempo.md        # Tempo + Grafana setup
├── deployment/
│   ├── production.md           # Production best practices
│   ├── kubernetes.md           # K8s deployment patterns
│   └── serverless.md           # Lambda/Cloud Functions
├── architecture/
│   ├── overview.md             # System design
│   ├── schema-design.md        # Dual-dialect schema explanation
│   └── decisions.md            # ADRs
└── contributing.md             # Development setup, guidelines
```

---

## Implementation Steps

### Phase 1: Basic Setup

1. Install dependencies:

   ```bash
   uv add --dev mkdocs-material mkdocstrings[python] mkdocs-autorefs mike
   ```

2. Create `mkdocs.yml` configuration

3. Create initial `docs/index.md` from README

4. Set up API reference auto-generation

### Phase 2: Content Migration

1. Migrate existing docs/ content to proper structure
2. Create getting-started guides from examples
3. Write user guide pages for each major feature
4. Add integration guides for each backend

### Phase 3: CI/CD Integration

1. Add GitHub Actions workflow:

   ```yaml
   # .github/workflows/docs.yml
   name: Documentation
   on:
     push:
       branches: [main]
     pull_request:

   jobs:
     build:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: astral-sh/setup-uv@v4
         - run: uv sync --dev
         - run: uv run mkdocs build --strict

     deploy:
       if: github.ref == 'refs/heads/main'
       needs: build
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: astral-sh/setup-uv@v4
         - run: uv sync --dev
         - run: uv run mkdocs gh-deploy --force
   ```

2. Configure GitHub Pages for hosting

### Phase 4: Versioning

1. Set up mike for version management
2. Configure version switcher in theme
3. Document release process for docs

---

## Example mkdocs.yml Configuration

```yaml
site_name: AgentTrace
site_url: https://agenttrace.dev
site_description: Vendor-neutral LLM observability SDK

repo_name: agenttrace/agenttrace
repo_url: https://github.com/agenttrace/agenttrace

theme:
  name: material
  palette:
    - scheme: default
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode
    - scheme: slate
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-4
        name: Switch to light mode
  features:
    - navigation.tabs
    - navigation.sections
    - navigation.expand
    - navigation.top
    - search.suggest
    - search.highlight
    - content.code.copy
    - content.code.annotate

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          options:
            docstring_style: google
            show_source: true
            show_root_heading: true
            members_order: source
            separate_signature: true
            show_signature_annotations: true
  - autorefs

markdown_extensions:
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.superfences
  - pymdownx.tabbed:
      alternate_style: true
  - admonition
  - pymdownx.details
  - attr_list
  - md_in_html
  - toc:
      permalink: true

nav:
  - Home: index.md
  - Getting Started:
    - Installation: getting-started/installation.md
    - Quick Start: getting-started/quickstart.md
    - Configuration: getting-started/configuration.md
  - User Guide:
    - Decorators: user-guide/decorators.md
    - Exporters: user-guide/exporters.md
    - Processors: user-guide/processors.md
    - Adapters: user-guide/adapters.md
  - API Reference:
    - Core: reference/api/core.md
    - Instrumentation: reference/api/instrumentation.md
    - Exporters: reference/api/exporters.md
  - Integrations:
    - Langfuse: integrations/langfuse.md
    - Datadog: integrations/datadog.md
  - Contributing: contributing.md
```

---

## API Reference Page Example

For auto-generating API docs from docstrings:

```markdown
# Core Module

The core module contains the fundamental data models and runtime for AgentTrace.

## Models

::: agenttrace.core.models
    options:
      show_root_heading: false
      members_order: source

## Runtime

::: agenttrace.core.runtime
    options:
      show_root_heading: false
      members_order: source

## Configuration

::: agenttrace.core.config
    options:
      show_root_heading: false
      members_order: source
```

---

## Resources

- [MkDocs Documentation](https://www.mkdocs.org/)
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
- [mkdocstrings](https://mkdocstrings.github.io/)
- [mike - MkDocs Versioning](https://github.com/jimporter/mike)
