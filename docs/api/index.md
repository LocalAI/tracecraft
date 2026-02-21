# API Reference

Complete API documentation for Trace Craft.

## Modules

<div class="grid cards" markdown>

- :material-code-braces:{ .lg .middle } __Core__

    ---

    Core models, runtime, and configuration

    [:octicons-arrow-right-24: Core API](core.md)

- :material-code-tags:{ .lg .middle } __Decorators__

    ---

    Instrumentation decorators and context managers

    [:octicons-arrow-right-24: Decorators API](decorators.md)

- :material-export:{ .lg .middle } __Exporters__

    ---

    Export traces to different backends

    [:octicons-arrow-right-24: Exporters API](exporters.md)

- :material-shield-check:{ .lg .middle } __Processors__

    ---

    Data processing and transformation

    [:octicons-arrow-right-24: Processors API](processors.md)

- :material-connection:{ .lg .middle } __Adapters__

    ---

    Framework integration adapters

    [:octicons-arrow-right-24: Adapters API](adapters.md)

- :material-cog:{ .lg .middle } __Configuration__

    ---

    Configuration classes and options

    [:octicons-arrow-right-24: Configuration API](configuration.md)

</div>

## Quick Reference

### Core Classes

```python
from tracecraft import (
    TraceCraftRuntime,
    TraceCraftConfig,
    AgentRun,
    Step,
    StepType,
)

# Create runtime
runtime = TraceCraftRuntime(config=TraceCraftConfig())

# Create run
with runtime.run("my_run"):
    # Your code here
    pass
```

### Decorators

```python
from tracecraft import (
    trace_agent,
    trace_tool,
    trace_llm,
    trace_retrieval,
    step,
)

@trace_agent(name="agent")
async def agent(input: str) -> str:
    pass

@trace_tool(name="tool")
def tool(input: str) -> str:
    pass

@trace_llm(name="llm", model="gpt-4", provider="openai")
async def llm(prompt: str) -> str:
    pass

@trace_retrieval(name="retrieval")
async def retrieval(query: str) -> list[str]:
    pass
```

### Exporters

```python
from tracecraft.exporters import (
    ConsoleExporter,
    JSONLExporter,
    OTLPExporter,
    MLflowExporter,
    HTMLExporter,
)

# Use with init
tracecraft.init(
    exporters=[
        ConsoleExporter(),
        JSONLExporter(filepath="traces.jsonl"),
        OTLPExporter(endpoint="http://localhost:4317"),
    ]
)
```

### Processors

```python
from tracecraft.processors.redaction import RedactionProcessor, RedactionMode
from tracecraft.processors.sampling import SamplingProcessor
from tracecraft.processors.enrichment import EnrichmentProcessor

# PII redaction
redaction = RedactionProcessor(mode=RedactionMode.MASK)

# Sampling
sampling = SamplingProcessor(rate=0.1)

# Enrichment
enrichment = EnrichmentProcessor(
    static_attributes={"version": "1.0.0"}
)
```

### Adapters

```python
# LangChain
from tracecraft.adapters.langchain import TraceCraftCallbackHandler
handler = TraceCraftCallbackHandler()

# LlamaIndex
from tracecraft.adapters.llamaindex import TraceCraftSpanHandler
handler = TraceCraftSpanHandler()

# PydanticAI
from tracecraft.adapters.pydantic_ai import TraceCraftSpanProcessor
processor = TraceCraftSpanProcessor()

# Claude SDK
from tracecraft.adapters.claude_sdk import ClaudeTraceCraftr
tracer = ClaudeTraceCraftr(runtime=runtime)
```

## Auto-Generated Documentation

The following pages contain auto-generated API documentation from source code docstrings:

- [Core](core.md) - Core functionality
- [Decorators](decorators.md) - Instrumentation decorators
- [Exporters](exporters.md) - Export backends
- [Processors](processors.md) - Data processors
- [Adapters](adapters.md) - Framework adapters
- [Configuration](configuration.md) - Configuration classes

## Type Hints

Trace Craft is fully typed. Import types for static analysis:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tracecraft.core.runtime import TALRuntime
    from tracecraft.core.models import AgentRun, Step
    from tracecraft.core.config import TraceCraftConfig
```

## Next Steps

Explore specific API modules:

1. [Core API](core.md)
2. [Decorators API](decorators.md)
3. [Exporters API](exporters.md)
4. [Processors API](processors.md)
5. [Adapters API](adapters.md)
6. [Configuration API](configuration.md)
