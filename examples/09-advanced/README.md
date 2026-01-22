# 09 - Advanced Patterns

> **Status: In Progress** - 1 of 8 planned examples available.
> Run `05_multi_agent.py` to see multi-agent collaboration patterns.

Advanced AgentTrace patterns for specialized use cases.

## Overview

| # | Example | Description | Status |
|---|---------|-------------|--------|
| 1 | `01_streaming_traces.py` | Token-level streaming with timing | Planned |
| 2 | `02_memory_tracking.py` | Agent memory with StepType.MEMORY | Planned |
| 3 | `03_guardrails.py` | Guardrails AI integration | Planned |
| 4 | `04_ab_testing.py` | Prompt A/B testing with traces | Planned |
| 5 | `05_multi_agent.py` | Multi-agent collaboration patterns | **Available** |
| 6 | `06_tui_workflow.py` | Using the terminal UI | Planned |
| 7 | `07_playground.py` | Trace replay and prompt iteration | Planned |
| 8 | `08_cloud_providers.py` | AWS/Azure/GCP helper usage | Planned |

## Streaming Traces

Capture token-level timing for streaming responses:

```python
from agenttrace.instrumentation.streaming import trace_llm_stream

@trace_llm_stream(name="streaming_llm")
async def stream_response(prompt: str):
    async for token in llm.stream(prompt):
        yield token
    # Trace includes:
    # - Time to first token
    # - Token timings
    # - Total token count
    # - Aggregated output
```

### Metrics Captured

- `time_to_first_token_ms` - Latency to first token
- `tokens_per_second` - Throughput
- `total_tokens` - Complete count
- `token_timings` - Per-token timestamps (optional)

## Memory Tracking

Track agent memory operations:

```python
from agenttrace.instrumentation.decorators import trace_memory

@trace_memory(name="conversation_memory")
def store_message(session_id: str, message: str) -> None:
    """Store a message in conversation memory."""
    memory_store.add(session_id, message)

@trace_memory(name="conversation_memory")
def retrieve_context(session_id: str) -> list[str]:
    """Retrieve conversation context."""
    return memory_store.get_recent(session_id, limit=10)
```

## Guardrails Integration

Trace guardrail validations:

```python
from agenttrace.adapters.guardrails import trace_guardrail

@trace_guardrail(name="toxicity_filter")
def check_toxicity(text: str) -> bool:
    """Check for toxic content."""
    return toxicity_model.predict(text) < 0.5

@trace_guardrail(name="pii_filter")
def check_pii(text: str) -> tuple[bool, str]:
    """Check and optionally redact PII."""
    if contains_pii(text):
        return False, redact_pii(text)
    return True, text
```

## A/B Testing

Track prompt variants for analysis:

```python
@trace_llm(name="chat", metadata={"variant": "A"})
def chat_variant_a(prompt: str) -> str:
    return llm.chat(system_prompt_a, prompt)

@trace_llm(name="chat", metadata={"variant": "B"})
def chat_variant_b(prompt: str) -> str:
    return llm.chat(system_prompt_b, prompt)

# Analysis
traces_a = filter(lambda t: t.metadata.get("variant") == "A", traces)
traces_b = filter(lambda t: t.metadata.get("variant") == "B", traces)

# Compare metrics
avg_latency_a = mean(t.duration_ms for t in traces_a)
avg_latency_b = mean(t.duration_ms for t in traces_b)
```

## Multi-Agent Patterns

Coordinate multiple agents:

```python
@trace_agent(name="coordinator")
async def coordinator(task: str) -> str:
    # Plan the approach
    plan = await planner_agent(task)

    # Execute in parallel where possible
    results = await asyncio.gather(
        researcher_agent(plan.research_topic),
        analyst_agent(plan.analysis_topic),
    )

    # Synthesize
    return await synthesizer_agent(results)
```

### Agent Communication

```python
@trace_agent(name="sender")
def send_message(agent_id: str, message: str) -> None:
    """Send message to another agent."""
    message_queue.put(agent_id, message)

@trace_agent(name="receiver")
def receive_messages() -> list[str]:
    """Receive pending messages."""
    return message_queue.get_all(self.agent_id)
```

## TUI Workflow

Use the terminal UI for debugging:

```python
from agenttrace.tui import launch_tui

# Launch TUI with trace file
launch_tui("traces/agenttrace.jsonl")

# Or with live streaming
launch_tui(runtime=runtime, live=True)
```

### TUI Features

- Interactive trace tree navigation
- Real-time trace streaming
- Search and filtering
- Step detail inspection
- Cost and timing analysis

## Trace Replay (Playground)

Replay and modify traces:

```python
from agenttrace.playground import TracePlayground

playground = TracePlayground("traces/agenttrace.jsonl")

# Load a specific trace
trace = playground.load_trace(trace_id="abc123")

# Modify and replay
modified = trace.with_step_input(
    step_id="step_1",
    new_input="Modified prompt",
)
result = await playground.replay(modified)
```

### Use Cases

- Debugging failed traces
- Iterating on prompts
- Testing edge cases
- Creating golden datasets

## Cloud Provider Helpers

Use cloud-specific utilities:

```python
from agenttrace.contrib.aws import (
    get_bedrock_trace_config,
    trace_sagemaker_endpoint,
)

from agenttrace.contrib.azure import (
    get_azure_openai_trace_config,
)

from agenttrace.contrib.gcp import (
    get_vertex_ai_trace_config,
)
```

### AWS Bedrock Example

```python
config = get_bedrock_trace_config(
    model_id="anthropic.claude-3-sonnet-20240229-v1:0",
    region="us-east-1",
)

@trace_llm(**config)
def call_bedrock(prompt: str) -> str:
    # Call Bedrock API
    pass
```

## Multi-Tenant Isolation

Isolate traces by tenant:

```python
from agenttrace.core.context import tenant_context

with tenant_context("tenant_abc"):
    # All traces tagged with tenant_id="tenant_abc"
    result = await process_request(request)

# Filter traces by tenant
tenant_traces = filter(
    lambda t: t.metadata.get("tenant_id") == "tenant_abc",
    all_traces,
)
```

## Custom Step Types

Define custom step types:

```python
from agenttrace.core.models import StepType
from agenttrace.instrumentation.decorators import trace_custom

# Register custom type
StepType.register("VALIDATION", emoji="✅")

@trace_custom(step_type="VALIDATION", name="schema_validator")
def validate_schema(data: dict) -> bool:
    """Validate data against schema."""
    return schema.is_valid(data)
```

## Performance Profiling

Profile trace performance:

```python
from agenttrace.profiling import profile_trace

with profile_trace() as profiler:
    result = await my_agent(input)

print(profiler.summary())
# Total duration: 1234ms
# LLM calls: 3 (890ms, 72%)
# Tool calls: 5 (234ms, 19%)
# Overhead: 110ms (9%)
```

## Next Steps

This section covers the most advanced patterns. For more:

- Check the [API Reference](../../docs/api/)
- Read the [Architecture Guide](../../docs/architecture.md)
- Join the [Community Discord](#)
