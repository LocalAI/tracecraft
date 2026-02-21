# Getting Started with Trace Craft

Welcome to Trace Craft! This guide will help you get started with instrumenting your LLM applications for observability.

## What is Trace Craft?

Trace Craft is a vendor-neutral observability SDK for LLM applications. It provides:

- **Unified Instrumentation**: Single API that works across different frameworks
- **Flexible Export**: Send traces to multiple backends simultaneously
- **Privacy First**: Built-in PII redaction and sampling
- **Local Development**: Works offline with beautiful console output
- **OpenTelemetry Native**: Built on industry-standard OTel

## Learning Path

Follow this learning path to master Trace Craft:

### 1. Installation

Start by installing Trace Craft with the features you need.

[:octicons-arrow-right-24: Installation Guide](installation.md)

### 2. Quick Start

Build your first instrumented application in 5 minutes.

[:octicons-arrow-right-24: Quick Start](quickstart.md)

### 3. Core Concepts

Understand the key concepts behind Trace Craft.

[:octicons-arrow-right-24: Core Concepts](concepts.md)

## Quick Example

The fastest way to get traces into the TUI requires **zero code changes** to your existing application:

```bash
# Terminal 1 — start the receiver + TUI
pip install "tracecraft[receiver,tui]"
tracecraft serve --tui

# Terminal 2 — run your existing app, unchanged
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
python your_app.py
```

Any OTLP-instrumented app (OpenLLMetry, LangChain, LlamaIndex, DSPy, or standard OTel SDK) sends traces directly to the TUI — no code changes needed.

**Prefer a config file?** Create `.tracecraft/config.yaml` and add one line to your app:

```yaml
# .tracecraft/config.yaml
default:
  exporters:
    receiver: true
  instrumentation:
    auto_instrument: true
```

```python
import tracecraft
tracecraft.init()   # reads from .tracecraft/config.yaml
```

```bash
tracecraft serve --tui && python your_app.py
```

Auto-instrumentation and decorators add rich structured spans — [→ SDK Guide](../user-guide/index.md)

## Key Features at a Glance

### Decorators

Simple decorators for different trace types:

```python
@trace_agent(name="agent")      # For agent/workflow functions
@trace_tool(name="tool")        # For tool/utility functions
@trace_llm(model="gpt-4")       # For LLM calls
@trace_retrieval(name="rag")    # For retrieval operations
```

### Configuration

Flexible configuration via code or environment variables:

```python
tracecraft.init(
    service_name="my-app",
    console=True,
    jsonl=True,
    otlp_endpoint="http://localhost:4317"
)
```

### Terminal UI

Explore your traces with the interactive terminal UI:

```bash
tracecraft tui
```

## Next Steps

Ready to dive deeper? Start with the installation guide:

[:octicons-arrow-right-24: Install Trace Craft](installation.md){ .md-button .md-button--primary }
