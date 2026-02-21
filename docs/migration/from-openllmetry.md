# Migrating from OpenLLMetry to Trace Craft

This guide helps you migrate from OpenLLMetry (Traceloop) to Trace Craft.

## Key Differences

| Feature | OpenLLMetry | Trace Craft |
|---------|-------------|------------|
| Focus | Auto-instrumentation | Explicit + auto |
| Protocol | OpenTelemetry native | OTLP export + local |
| Configuration | Environment vars | Python API |
| Decorators | `@workflow`, `@task` | `@trace_agent`, `@trace_llm` |

## Migration Steps

### 1. Install Trace Craft

```bash
pip install tracecraft
# or
uv add tracecraft
```

### 2. Replace Initialization

**Before (OpenLLMetry):**

```python
from traceloop.sdk import Traceloop

Traceloop.init(
    app_name="my-app",
    api_endpoint="https://api.traceloop.com"
)
```

**After (Trace Craft):**

```python
import tracecraft
from tracecraft.exporters.otlp import OTLPExporter

tracecraft.init(
    console=True,
    exporters=[
        OTLPExporter(
            endpoint="http://localhost:4317",
            service_name="my-app"
        )
    ]
)
```

### 3. Replace Decorators

**Before (OpenLLMetry):**

```python
from traceloop.sdk.decorators import workflow, task, agent

@workflow(name="research")
def research_workflow(query: str):
    return search_and_summarize(query)

@task(name="search")
def search(query: str):
    return results

@agent(name="summarizer")
def summarize(docs: list):
    return summary
```

**After (Trace Craft):**

```python
import tracecraft

@tracecraft.trace_agent(name="research")
def research_workflow(query: str):
    return search_and_summarize(query)

@tracecraft.trace_tool(name="search")
def search(query: str):
    return results

@tracecraft.trace_agent(name="summarizer")
def summarize(docs: list):
    return summary
```

### 4. Replace Association Context

**Before (OpenLLMetry):**

```python
from traceloop.sdk import Traceloop

with Traceloop.set_association_properties({
    "user_id": "123",
    "session_id": "abc"
}):
    result = my_function()
```

**After (Trace Craft):**

```python
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from datetime import UTC, datetime

run = AgentRun(
    name="my_workflow",
    start_time=datetime.now(UTC),
    metadata={"user_id": "123", "session_id": "abc"}
)

with run_context(run):
    result = my_function()
```

### 5. Replace Prompt Management

**Before (OpenLLMetry):**

```python
from traceloop.sdk import Traceloop

Traceloop.set_prompt(
    name="summarize",
    version="v1",
    template="Summarize: {text}"
)
```

**After (Trace Craft):**

```python
# Trace Craft doesn't manage prompts - use your preferred solution
# Prompts are captured in LLM step inputs automatically
```

## Feature Mapping

| OpenLLMetry Feature | Trace Craft Equivalent |
|---------------------|----------------------|
| `@workflow` | `@trace_agent` |
| `@task` | `@trace_tool` |
| `@agent` | `@trace_agent` |
| Association properties | `AgentRun.metadata` |
| Auto-instrumentation | Framework adapters |
| Prompt registry | N/A (bring your own) |
| Traceloop Dashboard | Jaeger + Grafana |

## Keeping OpenTelemetry Native

If you want to stay with pure OpenTelemetry but need Trace Craft features:

```python
from tracecraft.exporters.otlp import OTLPExporter

# Trace Craft converts its traces to OTLP spans
otlp = OTLPExporter(
    endpoint="http://otel-collector:4317",
    protocol="grpc"
)

tracecraft.init(exporters=[otlp])

# Your existing OTEL collector config works unchanged
```

## Benefits of Migration

1. **Unified tracing**: Same traces work locally and in production
2. **Better debugging**: HTML reports for local development
3. **Framework support**: Native adapters for LangChain, LlamaIndex
4. **Explicit control**: Know exactly what's being traced
5. **Local-first**: No external dependencies during development
