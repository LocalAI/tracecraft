# Migrating from LangSmith to Trace Craft

This guide helps you migrate from LangSmith to Trace Craft for LLM observability.

## Key Differences

| Feature | LangSmith | Trace Craft |
|---------|-----------|------------|
| Vendor Lock-in | LangChain ecosystem | Vendor-neutral |
| Export Formats | Proprietary | OTLP, JSONL, HTML |
| Local-first | Cloud-required | Works offline |
| Pricing | Per-trace pricing | Self-hosted, free |

## Migration Steps

### 1. Install Trace Craft

```bash
pip install tracecraft
# or
uv add tracecraft
```

### 2. Replace LangSmith Tracing

**Before (LangSmith):**

```python
import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "ls_..."

from langchain_openai import ChatOpenAI
llm = ChatOpenAI()
```

**After (Trace Craft):**

```python
import tracecraft
from tracecraft.adapters.langchain import TraceCraftCallbackHandler

# Initialize Trace Craft
tracecraft.init(console=True, jsonl=True)

# Use the callback handler
handler = TraceCraftCallbackHandler()
llm = ChatOpenAI()

# Pass handler to invoke
result = llm.invoke("Hello", config={"callbacks": [handler]})
```

### 3. Update Chain Invocations

**Before:**

```python
chain = prompt | llm | parser
result = chain.invoke({"query": "test"})
```

**After:**

```python
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from datetime import UTC, datetime

handler = TraceCraftCallbackHandler()
run = AgentRun(name="my_chain", start_time=datetime.now(UTC))

with run_context(run):
    result = chain.invoke(
        {"query": "test"},
        config={"callbacks": [handler]}
    )
```

### 4. Export to OTLP (Optional)

If you want to send traces to Jaeger, Honeycomb, or other OTLP backends:

```python
from tracecraft.exporters.otlp import OTLPExporter

otlp = OTLPExporter(
    endpoint="http://localhost:4317",
    service_name="my-app"
)

tracecraft.init(exporters=[otlp])
```

## Feature Mapping

| LangSmith Feature | Trace Craft Equivalent |
|-------------------|----------------------|
| `@traceable` decorator | `@tracecraft.trace_agent` |
| Run trees | Nested Steps with parent_id |
| LangSmith Hub | N/A (use your own prompts) |
| Feedback collection | Custom attributes |
| Dataset creation | Export to JSONL |

## Benefits of Migration

1. **No vendor lock-in**: Export to any OTLP-compatible backend
2. **Local development**: Full tracing without internet
3. **Cost savings**: No per-trace charges
4. **Privacy**: Your data stays on your infrastructure
5. **Framework agnostic**: Works with LangChain, LlamaIndex, PydanticAI
