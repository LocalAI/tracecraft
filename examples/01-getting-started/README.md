# 01 - Getting Started

Learn the fundamentals of TraceCraft in under 30 minutes. These examples require no API keys and run with mocked LLM calls.

## Learning Path

| # | Example | Description | Time |
|---|---------|-------------|------|
| 1 | [01_hello_world.py](01_hello_world.py) | Simplest possible example | 2 min |
| 2 | [02_decorators.py](02_decorators.py) | All decorator types | 5 min |
| 3 | [03_context_managers.py](03_context_managers.py) | Sync and async patterns | 10 min |
| 4 | [04_configuration.py](04_configuration.py) | Configuration options | 10 min |

## Prerequisites

- Python 3.10+
- TraceCraft installed: `pip install tracecraft`

No API keys or external services required.

## Running the Examples

```bash
# From the repository root
cd examples

# Run examples in order
python 01-getting-started/01_hello_world.py
python 01-getting-started/02_decorators.py
python 01-getting-started/03_context_managers.py
python 01-getting-started/04_configuration.py

# Or use the example runner
python run_example.py 01-getting-started/01_hello_world.py
```

## What You'll Learn

### 01_hello_world.py

- Initialize TraceCraft with `tracecraft.init()`
- Use `@trace_llm` decorator
- Group traces with `runtime.run()`
- View traces in console and JSONL

### 02_decorators.py

- **@trace_agent** - Top-level agent orchestration
- **@trace_llm** - LLM/model calls with model info
- **@trace_tool** - External tools and utilities
- **@trace_retrieval** - Vector search and document retrieval
- Nested decorator hierarchy
- Error capture and propagation

### 03_context_managers.py

- Sync context: `with runtime.run("name"):`
- Async context: `async with runtime.run_async("name"):`
- Concurrent operations with `asyncio.gather()`
- Rate-limited concurrency with semaphores
- Error handling in contexts
- Manual run management

### 04_configuration.py

- Default configuration
- Init parameters
- Environment variables (all `TRACECRAFT_*` vars)
- Configuration objects (`TraceCraftConfig`)
- Loading config with overrides
- Environment-specific configuration (dev/staging/prod)

## Key Concepts

### Decorators

```python
from tracecraft.instrumentation.decorators import (
    trace_agent,      # Agent-level orchestration
    trace_llm,        # LLM calls
    trace_tool,       # Tools and utilities
    trace_retrieval,  # Vector search
)

@trace_llm(name="my_llm", model="gpt-4o-mini", provider="openai")
def my_llm_function(prompt: str) -> str:
    return "response"
```

### Context Managers

```python
import tracecraft

runtime = tracecraft.init()

# Sync
with runtime.run("my_run"):
    my_llm_function("hello")

# Async
async with runtime.run_async("my_async_run"):
    await my_async_function()
```

### Configuration

```python
from tracecraft.core.config import TraceCraftConfig, SamplingConfig

config = TraceCraftConfig(
    service_name="my-service",
    sampling=SamplingConfig(rate=0.5),
)
```

Or via environment variables:

```bash
export TRACECRAFT_SERVICE_NAME=my-service
export TRACECRAFT_SAMPLING_RATE=0.5
```

## Output

All examples produce:

1. **Console output** - Rich tree visualization of traces
2. **JSONL file** - `traces/tracecraft.jsonl` (or custom path)

Example console output:

```
AgentRun: my_run
├── Duration: 150ms
├── Cost: $0.0000
├── Tokens: 0
└── Steps:
    └── [LLM] my_llm (gpt-4o-mini) - 0 tokens
```

## Troubleshooting

### "No traces appearing"

- Ensure you're using a context manager or calling `runtime.end_run(run)`
- Check that `TRACECRAFT_CONSOLE_ENABLED` isn't set to `false`

### "ModuleNotFoundError: tracecraft"

```bash
pip install tracecraft
```

### "Permission denied" for traces file

```bash
mkdir -p traces
chmod 755 traces
```

## Next Steps

After completing these examples:

1. **[02-frameworks/](../02-frameworks/)** - Integrate with LangChain, LlamaIndex, etc.
2. **[03-exporters/](../03-exporters/)** - Export to OTLP, HTML, MLflow
3. **[04-production/](../04-production/)** - Production patterns and processors
