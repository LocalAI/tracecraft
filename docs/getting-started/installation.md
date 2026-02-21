# Installation

This guide covers all the ways to install Trace Craft and its optional dependencies.

## Requirements

- Python 3.11 or later
- pip or uv package manager

## Basic Installation

=== "pip"

    ```bash
    pip install tracecraft
    ```

=== "uv (recommended)"

    ```bash
    uv add tracecraft
    ```

=== "Poetry"

    ```bash
    poetry add tracecraft
    ```

This installs the core Trace Craft SDK with:

- OpenTelemetry API and SDK
- Rich console output
- Pydantic models
- Basic exporters (Console, JSONL)

## Optional Dependencies

Trace Craft uses optional dependencies for different features. Install only what you need:

### Framework Integrations

=== "LangChain"

    ```bash
    pip install "tracecraft[langchain]"
    ```

    Adds LangChain callback handler for automatic tracing of:
    - Chains and LCEL pipelines
    - Agents and tools
    - LLM calls
    - Retrievers

=== "LlamaIndex"

    ```bash
    pip install "tracecraft[llamaindex]"
    ```

    Adds LlamaIndex span handler for automatic tracing of:
    - Query engines
    - Chat engines
    - Agents
    - Retrievers

=== "PydanticAI"

    ```bash
    pip install "tracecraft[pydantic-ai]"
    ```

    Adds PydanticAI integration for:
    - Agent runs
    - Tool calls
    - Model invocations

=== "Claude SDK"

    ```bash
    pip install "tracecraft[claude-sdk]"
    ```

    Adds Claude Agent SDK wrapper for tracing Claude-powered agents.

### Export Targets

=== "OTLP"

    ```bash
    pip install "tracecraft[otlp]"
    ```

    Enables OTLP export to:
    - Jaeger
    - Grafana Tempo
    - Datadog
    - Honeycomb
    - Any OTLP-compatible backend

=== "MLflow"

    ```bash
    pip install "tracecraft[mlflow]"
    ```

    Enables MLflow export for:
    - Experiment tracking
    - Model registry integration
    - Metrics and artifacts

=== "Terminal UI"

    ```bash
    pip install "tracecraft[tui]"
    ```

    Adds interactive terminal UI for exploring traces:
    - Browse trace hierarchy
    - Filter and search
    - View detailed span information
    - Export to different formats

### Auto-Instrumentation

```bash
pip install "tracecraft[auto]"
```

Automatically instruments popular LLM SDKs:

- OpenAI SDK (via opentelemetry-instrumentation-openai)
- Anthropic SDK (via opentelemetry-instrumentation-anthropic)

No code changes required - just import and initialize!

### Cloud Platform Integrations

=== "AWS AgentCore"

    ```bash
    pip install "tracecraft[aws-agentcore]"
    ```

    For AWS Bedrock AgentCore integration with X-Ray propagation.

=== "Azure AI Foundry"

    ```bash
    pip install "tracecraft[azure-foundry]"
    ```

    For Azure AI Foundry (Project Geneva) integration.

=== "GCP Vertex Agent"

    ```bash
    pip install "tracecraft[gcp-vertex-agent]"
    ```

    For GCP Vertex AI Agent Builder integration.

=== "All Cloud Platforms"

    ```bash
    pip install "tracecraft[cloud]"
    ```

### Convenience Bundles

Trace Craft provides convenience bundles for common use cases:

=== "All Features"

    ```bash
    pip install "tracecraft[all]"
    ```

    Includes everything:
    - All framework integrations
    - All exporters
    - Auto-instrumentation
    - Terminal UI
    - Cloud platform support

=== "Production"

    ```bash
    pip install "tracecraft[production]"
    ```

    Essentials for production:
    - OTLP export
    - Alerting capabilities

=== "Development"

    ```bash
    pip install "tracecraft[dev]"
    ```

    Development tools:
    - pytest
    - pytest-asyncio
    - pytest-cov
    - ruff (linter)
    - mypy (type checker)
    - pre-commit hooks

## Verification

Verify your installation:

```python
import tracecraft

print(f"Trace Craft version: {tracecraft.__version__}")

# Test basic functionality
tracecraft.init()
print("Trace Craft initialized successfully!")
```

## Development Installation

For contributing to Trace Craft:

```bash
# Clone the repository
git clone https://github.com/LocalAI/tracecraft.git
cd tracecraft

# Install with all extras using uv (recommended)
uv sync --all-extras

# Or using pip
pip install -e ".[all,dev]"

# Install pre-commit hooks
uv run pre-commit install

# Run tests
uv run pytest
```

## Upgrading

To upgrade to the latest version:

=== "pip"

    ```bash
    pip install --upgrade tracecraft
    ```

=== "uv"

    ```bash
    uv pip install --upgrade tracecraft
    ```

=== "Poetry"

    ```bash
    poetry update tracecraft
    ```

## Troubleshooting

### Import Errors

If you see import errors for optional dependencies:

```python
ModuleNotFoundError: No module named 'langchain_core'
```

Install the required extra:

```bash
pip install "tracecraft[langchain]"
```

### Version Conflicts

If you encounter version conflicts with OpenTelemetry packages, ensure you're using compatible versions:

```bash
pip install --upgrade opentelemetry-api opentelemetry-sdk
```

Trace Craft requires:

- opentelemetry-api >= 1.20
- opentelemetry-sdk >= 1.20

### Platform-Specific Issues

#### macOS Apple Silicon

Some dependencies may require Rosetta 2 or native builds:

```bash
# Install Rosetta 2 if needed
softwareupdate --install-rosetta

# Or use native builds
pip install --no-binary :all: tracecraft
```

#### Windows

On Windows, you may need to install Visual C++ build tools for some dependencies:

Download from: <https://visualstudio.microsoft.com/visual-cpp-build-tools/>

## Next Steps

Now that Trace Craft is installed, follow the quick start guide:

[:octicons-arrow-right-24: Quick Start Guide](quickstart.md){ .md-button .md-button--primary }
