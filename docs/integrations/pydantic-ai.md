# PydanticAI Integration

TraceCraft integrates with PydanticAI through the `TraceCraftSpanProcessor`, an OpenTelemetry SpanProcessor that captures PydanticAI/Logfire spans as TraceCraft Steps.

## Installation

```bash
pip install "tracecraft[pydantic-ai]"
```

## Quick Start

```python
import tracecraft
from tracecraft.adapters.pydantic_ai import TraceCraftSpanProcessor
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from datetime import UTC, datetime

# Initialize TraceCraft
tracecraft.init()

# Set up the span processor
processor = TraceCraftSpanProcessor()
provider = TracerProvider()
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

# Create a run and trace PydanticAI execution
run = AgentRun(name="my_run", start_time=datetime.now(UTC))
with run_context(run):
    # Your PydanticAI code here
    agent.run_sync("What is 2+2?")

# run.steps now contains the trace
processor.clear()  # Free memory when done
```

## What Gets Captured

The `TraceCraftSpanProcessor` automatically infers step types from span attributes:

- **LLM calls** - Detected via `gen_ai.system` or `gen_ai.request.model` attributes
- **Tool calls** - Detected via `tool.name` attribute or `tool:` span name prefix
- **Agent spans** - Detected when span name contains "agent"
- **Retrieval spans** - Detected when span name contains "retriev" or "vector"
- **Workflow spans** - Default for other spans

### Token Tracking

For LLM steps, token counts are automatically extracted from:

- `gen_ai.usage.input_tokens`
- `gen_ai.usage.output_tokens`

### Streaming Support

The processor handles streaming events (`gen_ai.content.chunk`) and aggregates streaming chunks for LLM steps.

## Next Steps

- [LangChain Integration](langchain.md)
- [Auto-Instrumentation](auto-instrumentation.md)
- [User Guide](../user-guide/index.md)
