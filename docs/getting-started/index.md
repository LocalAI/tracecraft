# Getting Started with TraceCraft

Welcome to TraceCraft! This guide will help you get started with instrumenting your LLM applications for observability.

## What is TraceCraft?

TraceCraft is a vendor-neutral observability SDK for LLM applications. It provides:

- **Unified Instrumentation**: Single API that works across different frameworks
- **Flexible Export**: Send traces to multiple backends simultaneously
- **Privacy First**: Built-in PII redaction and sampling
- **Local Development**: Works offline with beautiful console output
- **OpenTelemetry Native**: Built on industry-standard OTel

## Learning Path

Follow this learning path to master TraceCraft:

### 1. Installation

Start by installing TraceCraft with the features you need.

[:octicons-arrow-right-24: Installation Guide](installation.md)

### 2. Quick Start

Build your first instrumented application in 5 minutes.

[:octicons-arrow-right-24: Quick Start](quickstart.md)

### 3. Core Concepts

Understand the key concepts behind TraceCraft.

[:octicons-arrow-right-24: Core Concepts](concepts.md)

## Quick Example

Here's a minimal example to get a taste of TraceCraft:

```python
import tracecraft
from tracecraft import trace_agent, trace_tool

# Initialize TraceCraft
tracecraft.init()

@trace_agent(name="assistant")
async def assistant(message: str) -> str:
    """Main assistant that coordinates tasks."""
    context = await search(message)
    return f"Found: {context}"

@trace_tool(name="search")
async def search(query: str) -> list[str]:
    """Search for relevant information."""
    return ["result1", "result2"]

# Use your traced functions
import asyncio
asyncio.run(assistant("Hello!"))
```

That's it! TraceCraft will automatically:

- Capture the function hierarchy
- Record inputs and outputs
- Measure timing
- Export to console and JSONL file

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

### Framework Integration

Native support for popular frameworks:

```python
# LangChain
from tracecraft.adapters.langchain import TraceCraftCallbackHandler
handler = TraceCraftCallbackHandler()
chain.invoke(input, config={"callbacks": [handler]})

# LlamaIndex
from tracecraft.adapters.llamaindex import TraceCraftSpanHandler
import llama_index.core
llama_index.core.global_handler = TraceCraftSpanHandler()
```

## Common Use Cases

### Local Development

Perfect for debugging and development without any external services:

```python
tracecraft.init(
    console=True,      # Pretty print to terminal
    jsonl=True,        # Save to local file
)
```

### Production Monitoring

Send traces to your observability platform:

```python
tracecraft.init(
    service_name="production-agent",
    otlp_endpoint="https://otlp.example.com",
    sampling_rate=0.1,  # Sample 10% of traces
    enable_pii_redaction=True
)
```

### Multi-Backend

Send traces to multiple destinations:

```python
from tracecraft.exporters import OTLPExporter, JSONLExporter

tracecraft.init(
    exporters=[
        OTLPExporter(endpoint="http://jaeger:4317"),
        OTLPExporter(endpoint="http://tempo:4317"),
        JSONLExporter(filepath="traces.jsonl"),
    ]
)
```

## Next Steps

Ready to dive deeper? Start with the installation guide:

[:octicons-arrow-right-24: Install TraceCraft](installation.md){ .md-button .md-button--primary }
