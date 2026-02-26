# Migrating from Langfuse to TraceCraft

This guide helps you migrate from Langfuse to TraceCraft for LLM observability.

## Key Differences

| Feature | Langfuse | TraceCraft |
|---------|----------|------------|
| Architecture | Cloud + self-host | Local-first |
| UI | Web dashboard | HTML reports + OTLP backends |
| Decorators | `@observe()` | `@trace_agent`, `@trace_llm` |
| Context | Global state | Explicit run context |

## Migration Steps

### 1. Install TraceCraft

```bash
pip install tracecraft
# or
uv add tracecraft
```

### 2. Replace Langfuse Decorators

**Before (Langfuse):**

```python
from langfuse.decorators import observe, langfuse_context

@observe()
def my_agent(query: str) -> str:
    langfuse_context.update_current_observation(
        metadata={"user_id": "123"}
    )
    return process(query)
```

**After (TraceCraft):**

```python
import tracecraft

@tracecraft.trace_agent(name="my_agent")
def my_agent(query: str) -> str:
    # Metadata captured automatically from function args
    return process(query)
```

### 3. Replace Manual Tracing

**Before (Langfuse):**

```python
from langfuse import Langfuse

langfuse = Langfuse()

trace = langfuse.trace(name="my-trace")
span = trace.span(name="llm-call")
span.end(output=result)
trace.update(output=final_result)
```

**After (TraceCraft):**

```python
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun, Step, StepType
from datetime import UTC, datetime

run = AgentRun(name="my-trace", start_time=datetime.now(UTC))

with run_context(run):
    step = Step(
        trace_id=run.id,
        type=StepType.LLM,
        name="llm-call",
        start_time=datetime.now(UTC)
    )
    # ... do work ...
    step.outputs = {"result": result}
    step.end_time = datetime.now(UTC)
    run.steps.append(step)

run.output = {"final": final_result}
```

### 4. Replace LangChain Integration

**Before (Langfuse):**

```python
from langfuse.callback import CallbackHandler

handler = CallbackHandler()
chain.invoke(input, config={"callbacks": [handler]})
```

**After (TraceCraft):**

```python
from tracecraft.adapters.langchain import TraceCraftCallbackHandler

handler = TraceCraftCallbackHandler()
chain.invoke(input, config={"callbacks": [handler]})
```

### 5. Configure Export

**Before (Langfuse):**

```python
os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-..."
os.environ["LANGFUSE_SECRET_KEY"] = "sk-..."
os.environ["LANGFUSE_HOST"] = "https://cloud.langfuse.com"
```

**After (TraceCraft):**

```python
import tracecraft
from tracecraft.exporters.otlp import OTLPExporter

# For local development
tracecraft.init(console=True, jsonl=True)

# For production (Jaeger, Honeycomb, etc.)
tracecraft.init(exporters=[
    OTLPExporter(endpoint="http://collector:4317")
])
```

## Feature Mapping

| Langfuse Feature | TraceCraft Equivalent |
|------------------|----------------------|
| `@observe()` | `@trace_agent`, `@trace_llm`, `@trace_tool` |
| `langfuse.trace()` | `AgentRun` + `run_context` |
| `trace.span()` | `Step` objects |
| Generations | `StepType.LLM` steps |
| Scores | Custom attributes |
| Datasets | Export to JSONL |
| Dashboard | HTML reports + Jaeger/Grafana |

## Benefits of Migration

1. **Simpler architecture**: No external services required
2. **Standard protocols**: OTLP for any observability backend
3. **Better privacy**: No data leaves your infrastructure
4. **Unified tracing**: Same traces in dev and production
5. **Framework support**: LangChain, LlamaIndex, PydanticAI
