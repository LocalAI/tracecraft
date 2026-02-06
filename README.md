# TraceCraft

[![CI](https://github.com/LocalAI/tracecraft/actions/workflows/ci.yml/badge.svg)](https://github.com/LocalAI/tracecraft/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/LocalAI/tracecraft/branch/main/graph/badge.svg)](https://codecov.io/gh/LocalAI/tracecraft)
[![PyPI version](https://badge.fury.io/py/tracecraft.svg)](https://badge.fury.io/py/tracecraft)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

> **Vendor-neutral LLM observability SDK** - Instrument once, observe anywhere.

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

## Features

- **Local-First DX**: Beautiful console output + HTML reports without any backend setup
- **Built on OTel, Not Replacing It**: Higher-level abstractions on a proven foundation
- **Dual-Dialect Schema**: Supports both OTel GenAI and OpenInference conventions
- **Governance Built-In**: PII redaction + client-side sampling in the SDK
- **Framework Agnostic**: Works with LangChain, LlamaIndex, PydanticAI, or custom code
- **Multiple Export Targets**: Console, JSONL, OTLP, MLflow, HTML reports

## Installation

```bash
pip install tracecraft
```

Or with uv (recommended):

```bash
uv add tracecraft
```

### Optional Dependencies

Install with specific framework support:

```bash
# LangChain integration
pip install "tracecraft[langchain]"

# LlamaIndex integration
pip install "tracecraft[llamaindex]"

# PydanticAI integration
pip install "tracecraft[pydantic-ai]"

# OTLP export (for Jaeger, Grafana, etc.)
pip install "tracecraft[otlp]"

# Terminal UI for trace exploration
pip install "tracecraft[tui]"

# All features
pip install "tracecraft[all]"
```

## Quick Start

### Basic Usage (5 minutes)

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
def search(query: str) -> list[str]:
    """Search tool that returns results."""
    # Your search implementation
    return ["result1", "result2"]

def synthesize(results: list[str]) -> str:
    return f"Synthesized {len(results)} results"

# Run your agent
import asyncio
asyncio.run(research("What is TraceCraft?"))
```

### With LangChain

```python
import tracecraft
from tracecraft.adapters import LangChainAdapter
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# Initialize TraceCraft
tracecraft.init()

# Wrap your LangChain components
llm = ChatOpenAI(model="gpt-4")
adapter = LangChainAdapter()

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    ("user", "{input}")
])

chain = prompt | llm

# Use with automatic tracing
with adapter.trace():
    response = chain.invoke({"input": "Hello!"})
```

### With Custom Export

```python
import tracecraft
from tracecraft.exporters import OTLPExporter, JSONLExporter

# Export to multiple backends
tracecraft.init(
    exporters=[
        OTLPExporter(endpoint="http://localhost:4317"),  # Jaeger, Grafana, etc.
        JSONLExporter(filepath="traces.jsonl"),           # Local file
    ],
    service_name="my-agent-service"
)
```

### Terminal UI

Explore your traces interactively:

```bash
# View traces from JSONL file
tracecraft tui traces.jsonl

# View traces from SQLite database
tracecraft tui traces.db
```

## Framework Support

| Framework | Status | Installation |
|-----------|--------|--------------|
| LangChain | Stable | `tracecraft[langchain]` |
| LlamaIndex | Stable | `tracecraft[llamaindex]` |
| PydanticAI | Stable | `tracecraft[pydantic-ai]` |
| Claude SDK | Beta | `tracecraft[claude-sdk]` |
| Custom Code | Stable | Base package |

## Architecture

```
                    Your Application
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│                    TraceCraft SDK                    │
├─────────────────────────────────────────────────────┤
│  Instrumentation Layer                              │
│  ├── @trace_agent, @trace_tool decorators           │
│  ├── Framework adapters (LangChain, LlamaIndex)     │
│  └── Auto-instrumentation (OpenAI, Anthropic)       │
├─────────────────────────────────────────────────────┤
│  Processing Layer                                   │
│  ├── PII Redaction                                  │
│  ├── Sampling                                       │
│  └── Enrichment                                     │
├─────────────────────────────────────────────────────┤
│  Export Layer                                       │
│  ├── Console (Rich)                                 │
│  ├── JSONL / SQLite                                 │
│  ├── OTLP (Jaeger, Grafana, Datadog)               │
│  └── MLflow                                         │
└─────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
      Langfuse        Datadog         Phoenix
```

## Configuration

TraceCraft can be configured via environment variables or code:

```python
import tracecraft

tracecraft.init(
    service_name="my-service",           # Service name for traces
    environment="production",            # Environment tag
    sampling_rate=0.1,                   # Sample 10% of traces
    enable_pii_redaction=True,           # Redact PII automatically
    console_output=True,                 # Pretty print to console
)
```

Environment variables:

```bash
export TRACECRAFT_SERVICE_NAME=my-service
export TRACECRAFT_ENVIRONMENT=production
export TRACECRAFT_SAMPLING_RATE=0.1
export TRACECRAFT_OTLP_ENDPOINT=http://localhost:4317
```

## Examples

See the [examples/](examples/) directory for more comprehensive examples:

- Basic tracing with decorators
- LangChain integration
- LlamaIndex integration
- Multi-agent workflows
- Custom processors and exporters
- Production deployment patterns

## Documentation

- [Full Documentation](https://tracecraft.dev)
- [API Reference](https://tracecraft.dev/api)
- [Migration Guides](docs/migration/)
- [Deployment Guides](docs/deployment/)

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Quick Development Setup

```bash
# Clone the repository
git clone https://github.com/LocalAI/tracecraft.git
cd tracecraft

# Install with development dependencies
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install

# Run tests
uv run pytest
```

## Security

For security concerns, please see [SECURITY.md](SECURITY.md).

## License

Apache-2.0 - See [LICENSE](LICENSE) for details.

---

Made with care by the TraceCraft Contributors
