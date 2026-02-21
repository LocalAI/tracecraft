# Integrations

Trace Craft integrates with popular LLM frameworks and cloud platforms.

!!! success "No custom integration code required"

    Point any OTLP-instrumented app at Trace Craft and you're done:

    ```bash
    tracecraft serve --tui
    OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 python your_app.py
    ```

    Works with OpenLLMetry, LangChain, LlamaIndex, DSPy, PydanticAI, and any standard
    OpenTelemetry SDK — no Trace Craft-specific code needed.

## Framework Integrations

<div class="grid cards" markdown>

- :simple-python:{ .lg .middle } __LangChain__

    ---

    Automatic tracing for LangChain chains, agents, and tools

    [:octicons-arrow-right-24: LangChain Integration](langchain.md)

- :simple-llamaindex:{ .lg .middle } __LlamaIndex__

    ---

    Seamless integration with LlamaIndex query engines and agents

    [:octicons-arrow-right-24: LlamaIndex Integration](llamaindex.md)

- :simple-pydantic:{ .lg .middle } __PydanticAI__

    ---

    Native support for PydanticAI agents and tools

    [:octicons-arrow-right-24: PydanticAI Integration](pydantic-ai.md)

- :simple-anthropic:{ .lg .middle } __Claude SDK__

    ---

    Wrapper for Claude Agent SDK with automatic tracing

    [:octicons-arrow-right-24: Claude SDK Integration](claude-sdk.md)

</div>

## Auto-Instrumentation

<div class="grid cards" markdown>

- :material-auto-fix:{ .lg .middle } __Auto-Instrumentation__

    ---

    Automatic tracing for OpenAI and Anthropic SDKs

    [:octicons-arrow-right-24: Auto-Instrumentation](auto-instrumentation.md)

- :simple-opentelemetry:{ .lg .middle } __OpenTelemetry Receiver__

    ---

    Receive traces from any OTLP source with simple setup

    [:octicons-arrow-right-24: OpenTelemetry Receiver](otel-receiver.md)

</div>

## Cloud Platforms

<div class="grid cards" markdown>

- :simple-amazonaws:{ .lg .middle } __Cloud Platforms__

    ---

    AWS AgentCore, Azure AI Foundry, GCP Vertex Agent Builder

    [:octicons-arrow-right-24: Cloud Platforms](cloud-platforms.md)

</div>

## Quick Reference

### LangChain

The simplest path requires no Trace Craft-specific code — just set the OTLP endpoint:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 python your_langchain_app.py
```

Or use auto-instrumentation with one line:

```python
import tracecraft
tracecraft.init(auto_instrument=True)   # patches LangChain automatically
```

For richer span context using the native adapter, see [LangChain Integration](langchain.md).

### LlamaIndex

Set the OTLP endpoint if LlamaIndex is already emitting OTel traces:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 python your_llamaindex_app.py
```

Or enable auto-instrumentation:

```python
import tracecraft
tracecraft.init(auto_instrument=True)   # patches LlamaIndex automatically
```

For the native span handler, see [LlamaIndex Integration](llamaindex.md).

### PydanticAI

Set the OTLP endpoint for any PydanticAI app already emitting OTel traces:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 python your_pydanticai_app.py
```

Or use auto-instrumentation:

```python
import tracecraft
tracecraft.init(auto_instrument=True)
```

For the native span processor, see [PydanticAI Integration](pydantic-ai.md).

### Claude SDK

Set the OTLP endpoint for Claude SDK apps already emitting OTel traces:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 python your_claude_app.py
```

Or use auto-instrumentation:

```python
import tracecraft
tracecraft.init(auto_instrument=True)
```

For the full adapter with tool-level tracing, see [Claude SDK Integration](claude-sdk.md).

## Choosing an Integration

| Framework | Use When | Installation |
|-----------|----------|--------------|
| LangChain | Building with LCEL chains | `tracecraft[langchain]` |
| LlamaIndex | Using query engines or RAG | `tracecraft[llamaindex]` |
| PydanticAI | Type-safe agent development | `tracecraft[pydantic-ai]` |
| Claude SDK | Claude-powered agents | `tracecraft[claude-sdk]` |
| Auto | Using OpenAI/Anthropic directly | `tracecraft[auto]` |
| OTel Receiver | Receiving OTLP traces | `tracecraft[receiver]` |
| Custom | Rolling your own | Base package |

## Next Steps

Explore integration guides:

1. [LangChain Integration](langchain.md)
2. [LlamaIndex Integration](llamaindex.md)
3. [PydanticAI Integration](pydantic-ai.md)
4. [Claude SDK Integration](claude-sdk.md)
5. [Auto-Instrumentation](auto-instrumentation.md)
6. [OpenTelemetry Receiver](otel-receiver.md)
7. [Cloud Platforms](cloud-platforms.md)
