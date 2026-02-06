# API Reference

Complete API reference for TraceCraft.

## Module: tracecraft

Main entry point with convenience functions and re-exports.

### Functions

#### `init(**kwargs) -> TALRuntime`

Initialize the global TraceCraft runtime.

```python
import tracecraft

# Simple initialization
tracecraft.init()

# With configuration
tracecraft.init(
    service_name="my-service",
    console_enabled=True,
    jsonl_enabled=True,
)
```

#### `get_runtime() -> TALRuntime | None`

Get the global runtime instance.

```python
runtime = tracecraft.get_runtime()
if runtime:
    print(f"Service: {runtime.config.service_name}")
```

### Decorators

#### `@trace_agent(name=None, exclude_inputs=None, capture_inputs=True, runtime=None)`

Trace an agent function execution.

**Parameters:**

- `name: str | None` - Step name (defaults to function name)
- `exclude_inputs: list[str] | None` - Parameter names to exclude from capture
- `capture_inputs: bool` - If False, no inputs are captured
- `runtime: TALRuntime | None` - Explicit runtime for multi-tenant scenarios

**Example:**

```python
@tracecraft.trace_agent(name="research_agent")
async def research(query: str) -> str:
    return await process(query)

# Exclude sensitive parameters
@tracecraft.trace_agent(exclude_inputs=["api_key"])
def auth_agent(user: str, api_key: str) -> bool:
    return authenticate(user, api_key)
```

#### `@trace_tool(name=None, exclude_inputs=None, capture_inputs=True, runtime=None)`

Trace a tool function execution.

**Parameters:** Same as `@trace_agent`

**Example:**

```python
@tracecraft.trace_tool(name="web_search")
def search(query: str) -> list[str]:
    return fetch_results(query)
```

#### `@trace_llm(name=None, model=None, provider=None, exclude_inputs=None, capture_inputs=True, runtime=None)`

Trace an LLM function call with model metadata.

**Parameters:**

- `name: str | None` - Step name (defaults to function name)
- `model: str | None` - Model name (e.g., "gpt-4", "claude-3-opus")
- `provider: str | None` - Model provider (e.g., "openai", "anthropic")
- `exclude_inputs: list[str] | None` - Parameter names to exclude
- `capture_inputs: bool` - If False, no inputs are captured
- `runtime: TALRuntime | None` - Explicit runtime

**Example:**

```python
@tracecraft.trace_llm(model="gpt-4", provider="openai")
def call_llm(prompt: str) -> str:
    return client.chat.completions.create(...)
```

#### `@trace_retrieval(name=None, exclude_inputs=None, capture_inputs=True, runtime=None)`

Trace a retrieval/search function.

**Parameters:** Same as `@trace_agent`

**Example:**

```python
@tracecraft.trace_retrieval(name="vector_search")
def search_docs(query: str) -> list[Document]:
    return vector_store.search(query)
```

#### `@trace_llm_stream(name=None, model=None, provider=None, exclude_inputs=None, capture_inputs=True, runtime=None)`

Trace streaming LLM calls that yield tokens.

**Example:**

```python
@tracecraft.trace_llm_stream(model="gpt-4o", provider="openai")
async def stream_chat(prompt: str) -> AsyncGenerator[str, None]:
    async for chunk in client.chat.completions.create(..., stream=True):
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
```

### Context Managers

#### `step(name, type=StepType.WORKFLOW) -> Generator[Step, None, None]`

Create a traced step using a context manager.

**Parameters:**

- `name: str` - Step name
- `type: StepType` - Step type (default: WORKFLOW)

**Example:**

```python
from tracecraft import step
from tracecraft.core.models import StepType

with step("data_processing", type=StepType.WORKFLOW) as s:
    result = process_data()
    s.attributes["count"] = 100
    s.outputs["result"] = result
```

---

## Module: tracecraft.core.models

Data models for traces and steps.

### Classes

#### `AgentRun`

Represents a complete agent execution trace.

```python
@dataclass
class AgentRun:
    id: UUID
    name: str
    start_time: datetime
    end_time: datetime | None
    status: str  # "running", "completed", "error"
    steps: list[Step]
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    metadata: dict[str, Any]
    tags: list[str]
    error: str | None
```

#### `Step`

Represents a single step within a trace.

```python
@dataclass
class Step:
    id: UUID
    trace_id: UUID
    parent_id: UUID | None
    type: StepType
    name: str
    start_time: datetime
    end_time: datetime | None
    duration_ms: float | None
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    attributes: dict[str, Any]
    children: list[Step]
    error: str | None
    error_type: str | None
    model_name: str | None
    model_provider: str | None
```

#### `StepType`

Enumeration of step types.

```python
class StepType(str, Enum):
    AGENT = "agent"
    TOOL = "tool"
    LLM = "llm"
    RETRIEVAL = "retrieval"
    WORKFLOW = "workflow"
    EMBEDDING = "embedding"
    RERANK = "rerank"
    GUARDRAIL = "guardrail"
```

---

## Module: tracecraft.core.runtime

Runtime management for TraceCraft.

### Classes

#### `TALRuntime` (alias: `TraceCraftRuntime`)

The main runtime class that manages tracing infrastructure.

**Constructor:**

```python
TALRuntime(config: TraceCraftConfig | None = None)
```

**Methods:**

- `start_run(name, inputs=None, tags=None) -> AgentRun` - Start a new trace
- `end_run(run, outputs=None, error=None)` - End a trace
- `trace_context() -> ContextManager` - Context manager for scoped runtime selection
- `shutdown()` - Clean up resources

**Example:**

```python
from tracecraft import TraceCraftRuntime, TraceCraftConfig

runtime = TraceCraftRuntime(
    config=TraceCraftConfig(service_name="my-service")
)

# Use as context manager
with runtime.trace_context():
    run = runtime.start_run("my_agent", inputs={"query": "hello"})
    # ... do work ...
    runtime.end_run(run, outputs={"result": "world"})
```

---

## Module: tracecraft.core.config

Configuration classes.

### Classes

See [Configuration Reference](../user/configuration.md) for detailed documentation.

- `TraceCraftConfig` - Main configuration
- `RedactionConfig` - PII redaction settings
- `SamplingConfig` - Trace sampling settings
- `ExporterConfig` - Exporter settings
- `AzureFoundryConfig` - Azure AI Foundry settings
- `AWSAgentCoreConfig` - AWS AgentCore settings
- `GCPVertexAgentConfig` - GCP Vertex Agent settings

### Functions

#### `load_config_from_env() -> TraceCraftConfig`

Load configuration from environment variables.

#### `load_config(**kwargs) -> TraceCraftConfig`

Load configuration from environment variables with overrides.

---

## Module: tracecraft.adapters

Framework adapters for automatic instrumentation.

### LangChain Adapter

```python
from tracecraft.adapters.langchain import TraceCraftCallbackHandler

handler = TraceCraftCallbackHandler()
chain.invoke(input, config={"callbacks": [handler]})
```

### LlamaIndex Adapter

```python
from tracecraft.adapters.llamaindex import TraceCraftSpanHandler

import llama_index.core
llama_index.core.global_handler = TraceCraftSpanHandler()
```

### Claude SDK Adapter

```python
from tracecraft import ClaudeTraceCraftr

traced_agent = ClaudeTraceCraftr(agent)
result = await traced_agent.run(prompt)
```

### Pydantic AI Adapter

```python
from tracecraft.adapters.pydantic_ai import TraceCraftInstrumentor

instrumentor = TraceCraftInstrumentor()
instrumentor.instrument()
```

---

## Module: tracecraft.exporters

Trace exporters for different backends.

### Available Exporters

- `ConsoleExporter` - Human-readable console output
- `JSONLExporter` - JSON Lines file format
- `OTLPExporter` - OpenTelemetry Protocol
- `MLflowExporter` - MLflow tracking
- `HTMLExporter` - HTML report generation

### Example: Custom Exporter

```python
from tracecraft.exporters.base import BaseExporter
from tracecraft.core.models import AgentRun

class CustomExporter(BaseExporter):
    def export(self, run: AgentRun) -> None:
        # Custom export logic
        pass

    def shutdown(self) -> None:
        # Cleanup
        pass
```

---

## Module: tracecraft.processors

Trace processors for data transformation.

### Available Processors

- `RedactionProcessor` - PII redaction
- `SamplingProcessor` - Trace sampling
- `EnrichmentProcessor` - Metadata enrichment

### Configuration

Processor order can be configured via `ProcessorOrder`:

```python
from tracecraft.core.config import TraceCraftConfig, ProcessorOrder

config = TraceCraftConfig(
    processor_order=ProcessorOrder.SAFETY  # Enrich -> Redact -> Sample
    # or
    processor_order=ProcessorOrder.EFFICIENCY  # Sample -> Redact -> Enrich
)
```
