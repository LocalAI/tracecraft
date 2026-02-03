# TraceCraft Examples

Comprehensive examples demonstrating all TraceCraft features, from basic usage to production-ready patterns.

## Quick Start (5 minutes)

```bash
# Install TraceCraft
pip install tracecraft

# Run the simplest example (no API key needed)
python examples/01-getting-started/01_hello_world.py

# View your trace
cat traces/tracecraft.jsonl
```

## Examples by Category

| Category | Description | Available | Status |
|----------|-------------|-----------|--------|
| [01-getting-started](01-getting-started/) | Onboarding tutorials (no API key needed) | 4 | Complete |
| [02-frameworks](02-frameworks/) | LangChain, LlamaIndex, PydanticAI, OpenAI | 4 | Core complete |
| [03-exporters](03-exporters/) | OTLP, Tempo, HTML reports | 4 | Core complete |
| [04-production](04-production/) | Config, processors, resilience | 0 | Planned |
| [05-alerting](05-alerting/) | Slack, PagerDuty, quality monitoring | 0 | Planned |
| [06-evaluation](06-evaluation/) | DeepEval, RAGAS, MLflow | 0 | Planned |
| [07-distributed](07-distributed/) | W3C propagation, microservices | 0 | Planned |
| [08-real-world](08-real-world/) | Complete applications | 0 | Planned |
| [09-advanced](09-advanced/) | Multi-agent, streaming, memory | 1 | In progress |

**Current: 13 examples | Planned: 55+ examples covering 100% of TraceCraft features**

## Running Examples

### Using the Example Runner

```bash
# List all examples
python examples/run_example.py --list

# Run a specific example
python examples/run_example.py 01-getting-started/01_hello_world.py

# Check dependencies for an example
python examples/run_example.py --check 02-frameworks/langchain/01_simple_chain.py

# Run with verbose output
python examples/run_example.py -v 01-getting-started/02_decorators.py

# Filter by category
python examples/run_example.py --list --category 04-production
```

### Direct Execution

```bash
cd examples
python 01-getting-started/01_hello_world.py
```

## Learning Path

### Beginner (Start Here)

1. **[01-getting-started/](01-getting-started/)** - Learn decorators, context managers, and configuration
2. **[03-exporters/01_console_jsonl.py](03-exporters/01_console_jsonl.py)** - Understand default exporters

### Intermediate

3. **[02-frameworks/](02-frameworks/)** - Integrate with your preferred LLM framework
4. **[03-exporters/](03-exporters/)** - Export to OTLP, Tempo, HTML
5. **[09-advanced/05_multi_agent.py](09-advanced/05_multi_agent.py)** - Multi-agent collaboration patterns

### Coming Soon

The following categories are planned:

- **[04-production/](04-production/)** - Production patterns (PII redaction, sampling, resilience)
- **[05-alerting/](05-alerting/)** - Monitoring and alerting (Slack, PagerDuty)
- **[06-evaluation/](06-evaluation/)** - Evaluation frameworks (DeepEval, RAGAS)
- **[07-distributed/](07-distributed/)** - Distributed tracing across services
- **[08-real-world/](08-real-world/)** - Complete production applications
- More **[09-advanced/](09-advanced/)** examples (streaming, memory, A/B testing)

## Dependencies

### Core (No Extra Install)

These examples work with just `pip install tracecraft`:

- All of `01-getting-started/`
- `03-exporters/01_console_jsonl.py`
- `03-exporters/04_html_reports.py`
- All of `04-production/`

### Framework Dependencies

```bash
# LangChain examples
pip install langchain-openai langchain-community

# LlamaIndex examples
pip install llama-index-core llama-index-llms-openai

# PydanticAI examples
pip install pydantic-ai

# OpenAI direct examples
pip install openai
```

### Evaluation Dependencies

```bash
# DeepEval examples
pip install deepeval

# RAGAS examples
pip install ragas datasets

# MLflow examples
pip install mlflow
```

### External Services

Some examples require external services:

| Service | Examples | Setup |
|---------|----------|-------|
| Jaeger | `03-exporters/02_otlp_jaeger.py` | `docker run -d -p 4317:4317 -p 16686:16686 jaegertracing/all-in-one` |
| Grafana Tempo | `03-exporters/03_otlp_tempo.py` | See example docstring |

## Environment Variables

TraceCraft can be configured entirely via environment variables:

```bash
# Core Settings
export TRACECRAFT_ENABLED=true              # Enable/disable tracing
export TRACECRAFT_SERVICE_NAME=my-service   # Service name for traces
export TRACECRAFT_CONSOLE=true              # Console output (rich tree)
export TRACECRAFT_JSONL=true                # JSONL file output
export TRACECRAFT_JSONL_PATH=traces/        # JSONL output directory

# OTLP Export
export TRACECRAFT_OTLP_ENABLED=true
export TRACECRAFT_OTLP_ENDPOINT=http://localhost:4317
export TRACECRAFT_OTLP_PROTOCOL=grpc        # grpc or http

# Processors
export TRACECRAFT_REDACTION_ENABLED=true    # PII redaction
export TRACECRAFT_SAMPLING_RATE=1.0         # Sampling rate (0.0-1.0)

# API Keys (for framework examples)
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
```

## Sample Output

### Console Output (Rich Tree)

```
AgentRun: research_assistant
├── Duration: 2,450ms
├── Cost: $0.0234
├── Tokens: 1,847
└── Steps:
    ├── [LLM] plan_research (gpt-4o-mini) - 523 tokens, $0.0012
    ├── [TOOL] web_search - 0 tokens, $0.0000
    ├── [RETRIEVAL] vector_search - 5 chunks
    └── [LLM] synthesize (gpt-4o-mini) - 1,324 tokens, $0.0222
```

### JSONL Output

```json
{"name": "research_assistant", "trace_id": "abc123", "duration_ms": 2450, "total_cost_usd": 0.0234, ...}
```

### Jaeger UI

![Jaeger trace visualization](docs/images/jaeger_trace.png)

### HTML Report

![HTML report screenshot](docs/images/html_report.png)

## Troubleshooting

### "No traces appearing"

- Ensure `runtime.export()` is called (automatic with context managers)
- Check `TRACECRAFT_ENABLED` is not set to `false`
- Verify you're within a `run_context()` or using `@trace_*` decorators

### "ModuleNotFoundError"

- Install framework dependencies (see Dependencies section)
- For evaluation: `pip install tracecraft[evaluation]`
- For all extras: `pip install tracecraft[all]`

### "Connection refused" (OTLP)

- Ensure collector is running: `docker ps`
- Verify endpoint matches: `TRACECRAFT_OTLP_ENDPOINT`
- Check ports: 4317 (gRPC) or 4318 (HTTP)

### "Empty traces.jsonl"

- Traces are written on run completion
- Use context manager: `with runtime.run("name"):` for automatic export
- Call `runtime.export(run)` explicitly if manual

## Contributing Examples

New examples should follow this template:

```python
#!/usr/bin/env python3
"""[Title] - [One-line description]

[2-3 sentence description of what this example demonstrates]

Prerequisites:
    - [Required knowledge]
    - [Required installations]

Environment Variables:
    - [Required env vars]

External Services:
    - [Required services]

Usage:
    python examples/[path]/[filename].py

Expected Output:
    [Description of expected output]
"""

from __future__ import annotations

import os
import sys


def check_prerequisites() -> bool:
    """Verify all prerequisites are met."""
    # Check for required packages, API keys, services
    return True


def main() -> None:
    """Run the example."""
    print("=" * 60)
    print("[Example Title]")
    print("=" * 60)

    # ... example code ...

    print("\n" + "=" * 60)
    print("Example complete! Check traces/ for output.")
    print("=" * 60)


if __name__ == "__main__":
    if not check_prerequisites():
        sys.exit(1)
    main()
```

## Legacy Examples

The original flat examples have been reorganized:

| Old Location | New Location |
|--------------|--------------|
| `basic_usage.py` | `01-getting-started/02_decorators.py` |
| `openai_direct.py` | `02-frameworks/openai/01_direct_api.py` |
| `langchain_example.py` | `02-frameworks/langchain/01_simple_chain.py` |
| `llamaindex_example.py` | `02-frameworks/llamaindex/01_basic_query.py` |
| `pydantic_ai_example.py` | `02-frameworks/pydantic_ai/01_basic_agent.py` |
| `otlp_export.py` | `03-exporters/02_otlp_jaeger.py` |
| `html_report.py` | `03-exporters/04_html_reports.py` |
| `multi_agent.py` | `09-advanced/05_multi_agent.py` |
| `async_patterns.py` | `01-getting-started/03_context_managers.py` |

## Links

- [TraceCraft Documentation](https://github.com/your-org/agent-trace)
- [API Reference](https://github.com/your-org/agent-trace/docs/api)
- [GitHub Issues](https://github.com/your-org/agent-trace/issues)
