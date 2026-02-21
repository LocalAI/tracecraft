# Glossary

This glossary defines the key terms used in Trace Craft and the broader LLM observability ecosystem. Terms are organized into four categories and sorted alphabetically within each category.

---

## Trace Craft-Specific Terms

### Adapter

A framework-specific integration that translates the tracing callbacks and lifecycle hooks of an external framework into Trace Craft Steps. Adapters exist for LangChain, LlamaIndex, and PydanticAI. Rather than modifying your framework code, you install the adapter once and Trace Craft automatically captures all relevant operations.

See also: [Integrations](integrations/index.md), [Step](#step)

---

### AgentRun

The top-level container for a complete agent execution. An `AgentRun` holds metadata (run ID, timestamps, status), the initial input and final output, tags, and the full tree of child Steps. Every traced execution produces exactly one `AgentRun`.

`AgentRun` is the Trace Craft equivalent of a **Trace** in OpenTelemetry.

```python
from tracecraft import TraceCraftRuntime

runtime = tracecraft.init()

with runtime.run("user_query") as run:
    # Everything inside creates child Steps on this AgentRun
    result = await agent(user_input)

print(run.run_id)       # Unique identifier
print(run.duration_ms)  # Total execution time
```

See also: [Step](#step), [Trace](#trace)

---

### Auto-Instrumentation

Automatic tracing of third-party SDK calls (such as OpenAI or Anthropic) without modifying your existing code. Trace Craft's auto-instrumentation wraps installed OpenTelemetry instrumentation libraries and patches the SDK at import time, so every API call becomes a traced Step.

```python
import tracecraft

tracecraft.init(auto_instrument=["openai", "anthropic"])

# All subsequent openai.chat.completions.create() calls are now traced
```

See also: [Auto-Instrumentation Guide](integrations/auto-instrumentation.md)

---

### Decorator

A Python function annotation that automatically creates and manages a Step when the decorated function is called. Trace Craft provides four built-in decorators, each corresponding to a semantic operation type:

| Decorator | Step Type | Typical Use |
|---|---|---|
| `@trace_agent` | `AGENT` | Orchestration, coordination |
| `@trace_tool` | `TOOL` | Function calls, utilities |
| `@trace_llm` | `LLM` | LLM API calls |
| `@trace_retrieval` | `RETRIEVAL` | Vector search, RAG |

```python
from tracecraft import trace_agent, trace_tool

@trace_agent(name="research_agent")
async def research(query: str) -> str:
    results = await search(query)
    return summarize(results)

@trace_tool(name="web_search")
async def search(query: str) -> list[str]:
    ...
```

See also: [Decorators Guide](user-guide/decorators.md), [StepType](#steptype)

---

### Exporter

A component that receives a completed `AgentRun` and sends it to a storage or observability backend. Exporters are called after the processing pipeline finishes. Multiple exporters can be active simultaneously.

Built-in exporters:

| Exporter | Destination |
|---|---|
| `ConsoleExporter` | Rich terminal output |
| `JSONLExporter` | Local JSONL file |
| `OTLPExporter` | Any OTLP-compatible backend |
| `MLflowExporter` | MLflow experiment tracking |
| `HTMLExporter` | Self-contained HTML report |

```python
from tracecraft.exporters import ConsoleExporter, JSONLExporter

tracecraft.init(
    exporters=[
        ConsoleExporter(),
        JSONLExporter(filepath="traces/run.jsonl"),
    ]
)
```

See also: [Exporters Guide](user-guide/exporters.md)

---

### OTLPReceiverServer

An HTTP server bundled with Trace Craft that listens for incoming OpenTelemetry traces (sent via the OTLP HTTP protocol) and stores them in a Trace Craft storage backend. This allows any OTel-instrumented application - regardless of language or framework - to send traces to Trace Craft for analysis in the TUI.

```python
from tracecraft.receiver import OTLPReceiverServer
from tracecraft.storage.sqlite import SQLiteTraceStore

store = SQLiteTraceStore("traces/my_traces.db")
server = OTLPReceiverServer(store=store, host="0.0.0.0", port=4318)
server.run()
```

See also: [OpenTelemetry Receiver](integrations/otel-receiver.md), [TUI](#tui)

---

### Processor

A component in the trace processing pipeline that transforms, filters, or enriches an `AgentRun` before it reaches any exporter. Processors run in a configurable order and can modify, redact, or discard traces.

Built-in processors:

| Processor | Purpose |
|---|---|
| `EnrichmentProcessor` | Adds static or dynamic metadata attributes |
| `RedactionProcessor` | Removes or masks PII from inputs and outputs |
| `SamplingProcessor` | Drops a percentage of traces to reduce volume |

```python
from tracecraft.processors.redaction import RedactionProcessor, RedactionMode
from tracecraft.processors.sampling import SamplingProcessor

tracecraft.init(
    processors=[
        RedactionProcessor(mode=RedactionMode.MASK),
        SamplingProcessor(rate=0.1, always_keep_errors=True),
    ]
)
```

See also: [Processors Guide](user-guide/processors.md), [PII Redaction](#pii-redaction), [Sampling](#sampling)

---

### Step

A single traced operation within an `AgentRun`. Steps form a tree: a parent Step can have many child Steps, reflecting the actual call hierarchy of your code. Each Step records its type, name, start time, duration, status, inputs, outputs, and arbitrary attributes.

`Step` is the Trace Craft equivalent of a **Span** in OpenTelemetry.

```python
from tracecraft import step
from tracecraft.core.models import StepType

with step("preprocess", type=StepType.WORKFLOW) as s:
    result = preprocess(data)
    s.attributes["rows"] = len(data)
    s.outputs["result"] = result
```

Key fields:

- `step_id` - Unique identifier
- `name` - Human-readable operation name
- `step_type` - One of the `StepType` enum values
- `duration_ms` - Elapsed time in milliseconds
- `inputs` / `outputs` - Operation data
- `attributes` - Arbitrary key-value metadata
- `children` - Child Steps

See also: [AgentRun](#agentrun), [StepType](#steptype), [Span](#span)

---

### StepType

An enum that categorizes the semantic nature of a Step. Backends and the TUI use `StepType` to display appropriate icons, apply semantic conventions, and enable filtering.

```python
from tracecraft.core.models import StepType

StepType.AGENT      # Agent orchestration or top-level workflow
StepType.LLM        # Language model API call
StepType.TOOL       # Tool or function execution
StepType.RETRIEVAL  # Vector search or document retrieval
StepType.MEMORY     # Memory read or write
StepType.GUARDRAIL  # Safety or validation check
StepType.EVALUATION # LLM output scoring or evaluation
StepType.WORKFLOW   # Sub-workflow or processing step
StepType.ERROR      # Explicit error handling step
```

See also: [Step](#step), [Decorator](#decorator)

---

### TraceCraftConfig

A dataclass that holds all configuration options for a Trace Craft runtime instance. Pass it to `TraceCraftRuntime` directly, or use the convenience parameters on `tracecraft.init()`.

```python
from tracecraft import TraceCraftConfig, TraceCraftRuntime

config = TraceCraftConfig(
    service_name="my-agent",
    console=True,
    jsonl=True,
    jsonl_path="traces/agent.jsonl",
    sampling_rate=0.5,
    redact_pii=True,
)

runtime = TraceCraftRuntime(config=config)
```

See also: [Configuration Guide](user-guide/configuration.md), [TraceCraftRuntime](#tracecraftruntime)

---

### TraceCraftRuntime

The main runtime class that manages the tracing lifecycle: it initializes context, coordinates the processor pipeline, dispatches completed `AgentRun` objects to exporters, and provides the `run()` context manager.

A global singleton instance is created by `tracecraft.init()` and accessible via `tracecraft.get_runtime()`. Multiple independent runtime instances can coexist for multi-tenancy scenarios.

```python
import tracecraft

# Create global singleton
runtime = tracecraft.init(console=True, jsonl=True)

# Or create a named instance
from tracecraft import TraceCraftRuntime, TraceCraftConfig

runtime = TraceCraftRuntime(config=TraceCraftConfig(service_name="my-service"))

with runtime.run("task") as run:
    result = await agent(input)
```

See also: [TraceCraftConfig](#tracecraftconfig), [Multi-Tenancy](user-guide/multi-tenancy.md)

---

### TUI

The Terminal User Interface included with Trace Craft for browsing and analyzing stored traces offline. Built with [Textual](https://textual.textualize.io/), the TUI reads from JSONL or SQLite storage and provides an interactive, keyboard-driven interface for exploring the trace tree, inspecting inputs/outputs, reading LLM prompts and completions, and comparing runs.

```bash
# Launch from a JSONL file
tracecraft tui traces/agent.jsonl

# Launch from a SQLite database
tracecraft tui sqlite://traces/my_traces.db
```

See also: [Terminal UI Guide](user-guide/tui.md), [OTLPReceiverServer](#otlpreceiverserver)

---

## OpenTelemetry Terms

### BatchSpanProcessor

An OpenTelemetry SDK component that queues completed spans in memory and exports them in batches at regular intervals or when the queue reaches a threshold. Preferred over `SimpleSpanProcessor` in production because it reduces the performance impact of exporting on the critical path.

Trace Craft's `setup_exporter()` uses `BatchSpanProcessor` by default (`batch_export=True`).

See also: [SimpleSpanProcessor](#simplespanprocessor), [OpenTelemetry Receiver](integrations/otel-receiver.md)

---

### OTLP

**OpenTelemetry Protocol** - The standard wire protocol for transmitting traces, metrics, and logs between OpenTelemetry-instrumented applications and backends. Comes in two transport variants: HTTP/protobuf (port 4318) and gRPC (port 4317).

Trace Craft's `OTLPExporter` and `OTLPReceiverServer` both use OTLP HTTP.

See also: [Exporters Guide](user-guide/exporters.md), [OTLPReceiverServer](#otlpreceiverserver)

---

### Propagation

The mechanism for passing trace context (trace ID, span ID, sampling flags) across process or network boundaries so that distributed operations can be linked into a single coherent trace. Trace Craft uses the **W3C Trace Context** standard (`traceparent` and `tracestate` HTTP headers) for cross-service propagation, and Python `contextvars` for propagation across async boundaries within a single process.

See also: [W3C Trace Context](#w3c-trace-context), [Trace Context](#trace-context)

---

### Resource

In OpenTelemetry, a `Resource` is the set of immutable attributes that describe the entity producing telemetry - typically the service name, version, and deployment environment. Trace Craft automatically creates a `Resource` from your `TraceCraftConfig.service_name` and related fields.

```python
# Equivalent OTel resource attributes populated by Trace Craft
{
    "service.name": "my-agent",
    "service.version": "1.0.0",
    "deployment.environment": "production",
}
```

---

### Semantic Conventions

Standardized attribute names and values defined by the OpenTelemetry project for common concepts (HTTP requests, database queries, LLM calls, etc.). Using semantic conventions makes traces portable across different backends and analysis tools.

Trace Craft follows the **OTel GenAI Semantic Conventions** and also emits **OpenInference** attributes for maximum backend compatibility.

See also: [OTel GenAI Conventions](#otel-genai-conventions), [OpenInference](#openinference)

---

### SimpleSpanProcessor

An OpenTelemetry SDK component that exports each span immediately and synchronously as it completes. Simple to reason about and useful for debugging, but adds latency to every instrumented operation. Not recommended for production.

Use `batch_export=False` in `setup_exporter()` to switch to `SimpleSpanProcessor`.

See also: [BatchSpanProcessor](#batchspanprocessor)

---

### Span

The fundamental unit of work in OpenTelemetry. A Span represents a single operation with a start time, end time, status, and a set of key-value attributes. Spans are linked by parent-child relationships to form a tree within a Trace.

In Trace Craft terminology, a Span corresponds to a [Step](#step).

See also: [Step](#step), [Trace](#trace), [Trace Context](#trace-context)

---

### Trace

In OpenTelemetry, a Trace is the complete record of a distributed operation: a directed acyclic graph of Spans sharing the same `trace_id`. It represents the full path of a request or task through a system.

In Trace Craft terminology, a Trace corresponds to an [AgentRun](#agentrun).

See also: [AgentRun](#agentrun), [Span](#span)

---

### Trace Context

The metadata that links related Spans together into a Trace: primarily the `trace_id` (shared by all Spans in a Trace), the `span_id` (unique per Span), the `parent_span_id` (links child to parent), and trace flags (sampling decision). Trace Craft manages trace context automatically via Python `contextvars`.

See also: [Propagation](#propagation), [W3C Trace Context](#w3c-trace-context)

---

### TracerProvider

The OpenTelemetry entry point for creating tracers and configuring the export pipeline (processors, exporters, resource). `TraceCraftRuntime` wraps and configures a `TracerProvider` internally; you typically do not need to interact with it directly.

See also: [TraceCraftRuntime](#tracecraftruntime)

---

## LLM Observability Terms

### Completion

The output text generated by an LLM in response to a prompt. Trace Craft captures completions in `Step.outputs` under the key `completion` (or via OTel GenAI convention attributes such as `gen_ai.completion`). For streaming responses, individual chunks are captured in `streaming_chunks`.

See also: [Prompt](#prompt), [Streaming](#streaming), [Token](#token)

---

### Cost Tracking

Calculating the monetary cost of LLM API calls based on token usage and provider-specific pricing tables. Trace Craft records input and output token counts on LLM Steps and can compute estimated cost in USD when the model and provider are known.

```python
# Attributes recorded on an LLM Step
step.attributes["gen_ai.usage.input_tokens"] = 250
step.attributes["gen_ai.usage.output_tokens"] = 80
step.attributes["tracecraft.cost_usd"] = 0.00099
```

See also: [Token Counting](#token-counting), [Token](#token)

---

### Latency

The elapsed wall-clock time for an operation. Trace Craft records `duration_ms` on every Step, making it straightforward to identify slow LLM calls, retrieval bottlenecks, or tool timeouts in the TUI.

See also: [Step](#step)

---

### PII Redaction

The process of removing or masking personally identifiable information (names, email addresses, phone numbers, credit card numbers, etc.) from trace data before it is stored or exported. Trace Craft's `RedactionProcessor` applies configurable regex patterns client-side, so sensitive data never leaves your infrastructure.

```python
from tracecraft.processors.redaction import RedactionProcessor, RedactionMode

processor = RedactionProcessor(
    mode=RedactionMode.MASK,       # Replace with [REDACTED]
    custom_patterns=[r"\b[A-Z]{2}\d{6}\b"],  # Add custom patterns
)
```

See also: [Processor](#processor), [RedactionMode]

---

### Prompt

The input text (or structured messages) sent to an LLM. Trace Craft captures prompts in `Step.inputs` and via OTel GenAI convention attributes such as `gen_ai.prompt`. Prompts are displayed in the TUI's detail panel and can be redacted if they contain PII.

See also: [Completion](#completion), [PII Redaction](#pii-redaction)

---

### RAG

**Retrieval-Augmented Generation** - An architecture that combines a retrieval system (vector database, search engine) with an LLM. The retrieval step fetches relevant documents based on the user's query; those documents are added to the LLM prompt as context, grounding the response in factual information.

Trace Craft traces RAG pipelines end-to-end using `StepType.RETRIEVAL` for the retrieval step and `StepType.LLM` for the generation step.

See also: [StepType](#steptype), `@trace_retrieval` in [Decorators Guide](user-guide/decorators.md)

---

### Sampling

Selectively recording only a fraction of all traces to reduce storage costs and processing overhead while still providing statistical visibility. Trace Craft's `SamplingProcessor` supports rate-based sampling with configurable overrides to always capture errors and slow traces.

```python
from tracecraft.processors.sampling import SamplingProcessor

processor = SamplingProcessor(
    rate=0.1,                  # Record 10% of traces
    always_keep_errors=True,   # Always record failed runs
    always_keep_slow=True,     # Always record slow runs
    slow_threshold_ms=5000,
)
```

See also: [Processor](#processor)

---

### Streaming

Receiving LLM output incrementally as it is generated, token by token, rather than waiting for the complete response. Trace Craft captures streaming responses by accumulating `streaming_chunks` on the LLM Step and recording the final assembled completion.

See also: [Completion](#completion), [Token](#token)

---

### Token

The basic unit of text that LLMs process. Roughly equivalent to a word fragment (a typical English word is 1-2 tokens). Token counts directly determine the cost and throughput of LLM API calls. Trace Craft records `input_tokens` and `output_tokens` on every LLM Step.

See also: [Token Counting](#token-counting), [Cost Tracking](#cost-tracking)

---

### Token Counting

Measuring the number of tokens in a prompt (input tokens) and a completion (output tokens). Token counts are reported by the LLM provider in the API response and are captured automatically by Trace Craft on LLM Steps. They are the basis for [Cost Tracking](#cost-tracking).

See also: [Token](#token), [Cost Tracking](#cost-tracking)

---

## Schema and Standards Terms

### JSONL

**JSON Lines** - A text format where each line is a self-contained, valid JSON object. Trace Craft uses JSONL as its default local storage format: each line represents one serialized `AgentRun`. JSONL is human-readable, easy to stream, and directly parseable with standard tools.

```bash
# Each line is one AgentRun
cat traces/agent.jsonl | python -m json.tool | head -50
```

See also: [Exporters Guide](user-guide/exporters.md)

---

### MLflow

An open-source platform for managing the machine learning lifecycle, including experiment tracking, model registry, and evaluation. Trace Craft can export traces to MLflow as runs, making it possible to correlate agent behavior with ML experiments and model versions.

```python
from tracecraft.exporters import MLflowExporter

tracecraft.init(exporters=[MLflowExporter(tracking_uri="http://localhost:5000")])
```

See also: [Exporters Guide](user-guide/exporters.md)

---

### OpenInference

A trace schema standard developed by Arize AI for LLM and agent tracing. It defines attribute names such as `llm.model_name`, `llm.token_count.prompt`, `input.value`, and `output.value`. Trace Craft emits OpenInference attributes alongside OTel GenAI attributes, making traces compatible with Phoenix and other Arize-ecosystem backends.

See also: [OTel GenAI Conventions](#otel-genai-conventions), [Core Concepts](getting-started/concepts.md#schema-support)

---

### OTel GenAI Conventions

The OpenTelemetry Semantic Conventions for Generative AI: a standardized set of attribute names for LLM operations maintained by the OpenTelemetry project. Key attributes include `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, and `gen_ai.usage.output_tokens`.

```python
# Attributes emitted by Trace Craft on LLM Steps
{
    "gen_ai.system": "openai",
    "gen_ai.request.model": "gpt-4o",
    "gen_ai.response.model": "gpt-4o-2024-08-06",
    "gen_ai.usage.input_tokens": 320,
    "gen_ai.usage.output_tokens": 95,
}
```

See also: [OpenInference](#openinference), [Semantic Conventions](#semantic-conventions)

---

### W3C Trace Context

An HTTP header standard ([W3C Recommendation](https://www.w3.org/TR/trace-context/)) for propagating trace context across service boundaries. It defines two headers: `traceparent` (carries `trace_id`, `span_id`, and sampling flags) and `tracestate` (vendor-specific context). Trace Craft uses W3C Trace Context for cross-service propagation.

See also: [Propagation](#propagation), [Trace Context](#trace-context)

---

## See Also

- [Core Concepts](getting-started/concepts.md) - Conceptual overview of how Trace Craft works
- [API Reference](api/index.md) - Full API documentation
- [User Guide](user-guide/index.md) - Feature documentation and how-to guides
