# TraceCraft

[![CI](https://github.com/LocalAI/tracecraft/actions/workflows/ci.yml/badge.svg)](https://github.com/LocalAI/tracecraft/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/LocalAI/tracecraft/branch/main/graph/badge.svg)](https://codecov.io/gh/LocalAI/tracecraft)
[![PyPI version](https://badge.fury.io/py/tracecraft.svg)](https://badge.fury.io/py/tracecraft)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

> **Vendor-neutral LLM observability — instrument once, observe anywhere.**
>
> [!WARNING]
> This project is under active development. APIs may change between releases and it is not yet production-ready. Use with that in mind.

TraceCraft is a Python observability SDK with a built-in **Terminal UI (TUI)** that lets you visually explore, debug, and analyze agent traces right in your terminal — no browser, no cloud dashboard, no waiting.

---

## The fastest path: zero code changes

If your app already uses OpenAI, Anthropic, LangChain, LlamaIndex, or any OpenTelemetry-compatible framework, TraceCraft can observe it **without touching a single line of application code**.

**Step 1 — Install and set one environment variable:**

```bash
pip install "tracecraft[receiver,tui]"

export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

**Step 2 — Start the receiver and TUI together:**

```bash
tracecraft serve --tui
```

**Step 3 — Run your existing app unchanged:**

```bash
python your_app.py
```

Traces from any OTLP-compatible framework (OpenLLMetry, LangChain, LlamaIndex, DSPy, or any standard OpenTelemetry SDK) stream live into the TUI the moment they arrive. No `init()` call. No decorators. No code changes.

---

![TraceCraft TUI - Main View](docs/assets/screenshots/tui-main-view.svg)

*All your agent runs at a glance — name, duration, token usage, and status.*

![TraceCraft TUI - Waterfall and Detail View](docs/assets/screenshots/tui-waterfall-view.svg)

*Hierarchical waterfall view with timing bars. See exactly where your agent spends its time. Navigate to any LLM step and press `i` for the prompt, `o` for the response, or `a` for attributes.*

---

## Path 2 — Config file + one line

When you want a persistent local setup — custom service name, JSONL export, PII redaction — drop a config file into your project and add one line to your app:

**`.tracecraft/config.yaml`:**

```yaml
# .tracecraft/config.yaml
default:
  exporters:
    receiver: true         # stream to tracecraft serve --tui
  instrumentation:
    auto_instrument: true  # patches OpenAI, Anthropic, LangChain, LlamaIndex
```

**Your app:**

```python
import tracecraft

tracecraft.init()  # reads .tracecraft/config.yaml automatically
```

**Then start the TUI:**

```bash
tracecraft serve --tui
```

Or, if you prefer to write traces to a file and open the TUI separately:

```bash
tracecraft tui
```

> **Note:** Call `tracecraft.init()` **before** importing any LLM SDK. TraceCraft patches SDKs at import time — importing first means the patch won't apply.

---

## SDK decorators

For fine-grained control — custom span names, explicit inputs/outputs, structured step hierarchies — TraceCraft provides `@trace_agent`, `@trace_tool`, `@trace_llm`, and `@trace_retrieval` decorators, plus a `step()` context manager for inline instrumentation. See the [SDK Guide](https://tracecraft.io/getting-started/quickstart/) for details.

---

## TUI Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `↑` / `↓` | Navigate traces |
| `Enter` | Expand trace — shows waterfall |
| `i` | View input/prompt |
| `o` | View output/response |
| `a` | View attributes and metadata |
| `/` | Filter traces |
| `Tab` | Cycle view modes |
| `m` + `C` | Mark and compare two traces |
| `p` | Open playground |
| `q` | Quit |

---

## Why TraceCraft?

| Feature | TraceCraft | LangSmith | Langfuse | Phoenix |
|---------|------------|-----------|----------|---------|
| **Terminal UI** | **Yes — built-in** | No | No | No |
| **Zero-Code Instrumentation** | Yes | No | No | No |
| **Vendor Lock-in** | None | LangChain | Langfuse | Arize |
| **Local Development** | Full offline | Cloud required | Self-host | Self-host |
| **OpenTelemetry Native** | Built on OTel | Proprietary | Proprietary | OTel compatible |
| **PII Redaction** | SDK-level | Backend only | Backend only | Backend only |
| **Cost** | Free & Open Source | Paid tiers | Paid tiers | Paid tiers |

---

## Features

- **Built-in Terminal UI**: Explore, filter, compare, and debug traces without leaving your terminal
- **Local-First**: All traces stay on your machine — the TUI is fully offline
- **Zero-Code OTLP Receiver**: Set one env var, run `tracecraft serve --tui`, observe any OTLP app
- **Auto-Instrumentation**: Two lines capture all OpenAI, Anthropic, LangChain, and LlamaIndex calls automatically
- **Decorators**: `@trace_agent`, `@trace_tool`, `@trace_llm`, `@trace_retrieval` for custom tracing
- **Dual-Dialect Schema**: OTel GenAI and OpenInference conventions
- **PII Redaction**: Client-side redaction before data ever leaves your app
- **Export Anywhere**: Console, JSONL, SQLite, OTLP, MLflow, HTML reports

---

## Installation

```bash
# OTLP receiver + TUI (zero code changes path)
pip install "tracecraft[receiver,tui]"

# TUI + auto-instrumentation
pip install "tracecraft[auto,tui]"

# With specific frameworks
pip install "tracecraft[langchain,tui]"
pip install "tracecraft[llamaindex,tui]"

# All features
pip install "tracecraft[all]"
```

Or with uv:

```bash
uv add "tracecraft[auto,tui]"
```

---

## Framework Support

| Framework | Status | Installation |
|-----------|--------|--------------|
| OpenAI | Stable (auto) | `tracecraft[auto]` |
| Anthropic | Stable (auto) | `tracecraft[auto]` |
| LangChain | Beta | `tracecraft[langchain]` |
| LlamaIndex | Beta | `tracecraft[llamaindex]` |
| PydanticAI | Beta | `tracecraft[pydantic-ai]` |
| Claude SDK | Beta | `tracecraft[claude-sdk]` |
| Custom Code | Stable | Base package |

---

## Configuration

```python
import tracecraft

tracecraft.init(
    service_name="my-agent-service",
    jsonl=True,              # Enable JSONL output for the TUI
    console=True,            # Pretty-print to console
    auto_instrument=True,    # Auto-capture OpenAI/Anthropic calls
    enable_pii_redaction=True,
    sampling_rate=1.0,
)
```

Environment variables:

```bash
export TRACECRAFT_SERVICE_NAME=my-service
export TRACECRAFT_ENVIRONMENT=production
export TRACECRAFT_SAMPLING_RATE=0.1
export TRACECRAFT_OTLP_ENDPOINT=http://localhost:4317
```

---

## Export to Any Backend

```python
from tracecraft.exporters import OTLPExporter

tracecraft.init(
    jsonl=True,  # Keep local TUI access
    exporters=[
        OTLPExporter(endpoint="http://localhost:4317"),  # Jaeger, Grafana, etc.
    ],
)
```

Supported backends: Langfuse, Datadog, Phoenix (Arize), Jaeger, Grafana Tempo, Honeycomb, any OTLP system.

---

## Documentation

- [Full Documentation](https://tracecraft.io)
- [Terminal UI Guide](https://tracecraft.io/user-guide/tui/)
- [API Reference](https://tracecraft.io/api)
- [Migration Guides](docs/migration/)
- [Deployment Guides](docs/deployment/)

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
git clone https://github.com/LocalAI/tracecraft.git
cd tracecraft
uv sync --all-extras
uv run pre-commit install
uv run pytest
```

---

## Security

See [SECURITY.md](SECURITY.md) for security concerns.

## License

Apache-2.0 — See [LICENSE](LICENSE) for details.

---

Made with care by the TraceCraft Contributors
