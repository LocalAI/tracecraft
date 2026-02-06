# TraceCraft

**Vendor-neutral LLM observability SDK** - Instrument once, observe anywhere.

TraceCraft is the "LiteLLM for Observability" - a portable Python instrumentation SDK that lets you capture consistent agent/LLM trace semantics and route them to any backend (Langfuse, Datadog, Phoenix, or any OTLP-compatible system).

## Why TraceCraft?

| Feature | TraceCraft | LangSmith | Langfuse | Phoenix |
|---------|------------|-----------|----------|---------|
| **Vendor Lock-in** | None - export anywhere | LangChain ecosystem | Langfuse backend | Arize ecosystem |
| **Framework Support** | LangChain, LlamaIndex, PydanticAI, custom | LangChain only | Multiple | Multiple |
| **Local Development** | Full offline support | Cloud required | Self-host option | Self-host option |
| **OpenTelemetry Native** | Built on OTel | Proprietary | Proprietary | OTel compatible |
| **PII Redaction** | Built-in SDK | Backend only | Backend only | Backend only |
| **Schema Support** | OTel GenAI + OpenInference | Proprietary | Proprietary | OpenInference |
| **Cost** | Free & Open Source | Paid tiers | Paid tiers | Paid tiers |

## Key Features

### Local-First Development

Beautiful console output and HTML reports without any backend setup. Perfect for development and debugging.

```python
import tracecraft

# That's it - you're ready to trace!
tracecraft.init()
```

### Built on OpenTelemetry

Higher-level abstractions on the proven OpenTelemetry foundation. Use standard OTLP exporters to send data anywhere.

### Dual-Dialect Schema Support

Supports both OTel GenAI conventions and OpenInference, making it compatible with multiple backends out of the box.

### Privacy by Default

PII redaction and client-side sampling built into the SDK, not just the backend. Your sensitive data never leaves your infrastructure.

### Framework Agnostic

Works seamlessly with:

- LangChain
- LlamaIndex
- PydanticAI
- Claude SDK
- Custom code

### Multiple Export Targets

Send traces to one or more destinations:

- Console (Rich terminal output)
- JSONL files
- OTLP (Jaeger, Grafana, Datadog, etc.)
- MLflow
- HTML reports
- Custom exporters

## Quick Example

```python
import tracecraft
from tracecraft import trace_agent, trace_tool

# Initialize with defaults (console + JSONL output)
tracecraft.init()

@trace_agent(name="research_agent")
async def research(query: str) -> str:
    """Research agent that searches and synthesizes information."""
    results = await search(query)
    return synthesize(results)

@trace_tool(name="web_search")
async def search(query: str) -> list[str]:
    """Search tool that returns results."""
    # Your search implementation
    return ["result1", "result2"]

def synthesize(results: list[str]) -> str:
    return f"Synthesized {len(results)} results"

# Run your agent
import asyncio
asyncio.run(research("What is TraceCraft?"))
```

## Architecture

```mermaid
graph TB
    App[Your Application]
    App --> SDK[TraceCraft SDK]

    SDK --> Inst[Instrumentation Layer]
    Inst --> Dec[@decorators]
    Inst --> Adapt[Framework Adapters]
    Inst --> Auto[Auto-instrumentation]

    SDK --> Proc[Processing Layer]
    Proc --> Redact[PII Redaction]
    Proc --> Sample[Sampling]
    Proc --> Enrich[Enrichment]

    SDK --> Export[Export Layer]
    Export --> Console[Console]
    Export --> JSONL[JSONL/SQLite]
    Export --> OTLP[OTLP]
    Export --> MLflow[MLflow]

    OTLP --> Langfuse[Langfuse]
    OTLP --> Datadog[Datadog]
    OTLP --> Phoenix[Phoenix]
    OTLP --> Grafana[Grafana]
```

## Installation

=== "Basic"

    ```bash
    pip install tracecraft
    ```

=== "With Framework Support"

    ```bash
    # LangChain
    pip install "tracecraft[langchain]"

    # LlamaIndex
    pip install "tracecraft[llamaindex]"

    # PydanticAI
    pip install "tracecraft[pydantic-ai]"
    ```

=== "With Export Capabilities"

    ```bash
    # OTLP export (Jaeger, Grafana, etc.)
    pip install "tracecraft[otlp]"

    # Terminal UI for trace exploration
    pip install "tracecraft[tui]"

    # All features
    pip install "tracecraft[all]"
    ```

=== "Using uv (recommended)"

    ```bash
    uv add tracecraft

    # Or with extras
    uv add "tracecraft[all]"
    ```

## Next Steps

<div class="grid cards" markdown>

- :material-clock-fast:{ .lg .middle } **Quick Start**

    ---

    Get up and running in 5 minutes

    [:octicons-arrow-right-24: Quick Start](getting-started/quickstart.md)

- :material-book-open-variant:{ .lg .middle } **User Guide**

    ---

    Learn about decorators, configuration, and exporters

    [:octicons-arrow-right-24: User Guide](user-guide/index.md)

- :material-connection:{ .lg .middle } **Integrations**

    ---

    Use with LangChain, LlamaIndex, and more

    [:octicons-arrow-right-24: Integrations](integrations/index.md)

- :material-api:{ .lg .middle } **API Reference**

    ---

    Complete API documentation

    [:octicons-arrow-right-24: API Reference](api/index.md)

</div>

## Framework Support

| Framework | Status | Installation |
|-----------|--------|--------------|
| LangChain | Stable | `tracecraft[langchain]` |
| LlamaIndex | Stable | `tracecraft[llamaindex]` |
| PydanticAI | Stable | `tracecraft[pydantic-ai]` |
| Claude SDK | Beta | `tracecraft[claude-sdk]` |
| Custom Code | Stable | Base package |

## Community & Support

- **GitHub Issues**: [Report bugs and request features](https://github.com/LocalAI/tracecraft/issues)
- **GitHub Discussions**: [Ask questions and share ideas](https://github.com/LocalAI/tracecraft/discussions)
- **Contributing**: See our [Contributing Guide](contributing.md)

## License

TraceCraft is licensed under the Apache-2.0 License. See [LICENSE](https://github.com/LocalAI/tracecraft/blob/main/LICENSE) for details.
