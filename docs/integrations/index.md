# Integrations

TraceCraft integrates with popular LLM frameworks and cloud platforms. This section covers all available integrations.

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

```python
from tracecraft.adapters.langchain import TraceCraftCallbackHandler

handler = TraceCraftCallbackHandler()
chain.invoke(input, config={"callbacks": [handler]})
```

### LlamaIndex

```python
from tracecraft.adapters.llamaindex import TraceCraftSpanHandler

import llama_index.core
llama_index.core.global_handler = TraceCraftSpanHandler()
```

### PydanticAI

```python
from tracecraft.adapters.pydantic_ai import TraceCraftSpanProcessor
from opentelemetry.sdk.trace import TracerProvider

processor = TraceCraftSpanProcessor()
provider = TracerProvider()
provider.add_span_processor(processor)
```

### Claude SDK

```python
from tracecraft.adapters.claude_sdk import ClaudeTraceCraftr

tracer = ClaudeTraceCraftr(runtime=runtime)
options = tracer.get_options(allowed_tools=["Read", "Grep"])
```

### Auto-Instrumentation

```python
from tracecraft.instrumentation.auto import auto_instrument

# Automatically instrument OpenAI and Anthropic SDKs
auto_instrument()
```

## Choosing an Integration

| Framework | Use When | Installation |
|-----------|----------|--------------|
| LangChain | Building with LCEL chains | `tracecraft[langchain]` |
| LlamaIndex | Using query engines or RAG | `tracecraft[llamaindex]` |
| PydanticAI | Type-safe agent development | `tracecraft[pydantic-ai]` |
| Claude SDK | Claude-powered agents | `tracecraft[claude-sdk]` |
| Auto | Using OpenAI/Anthropic directly | `tracecraft[auto]` |
| Custom | Rolling your own | Base package |

## Next Steps

Explore integration guides:

1. [LangChain Integration](langchain.md)
2. [LlamaIndex Integration](llamaindex.md)
3. [PydanticAI Integration](pydantic-ai.md)
4. [Claude SDK Integration](claude-sdk.md)
5. [Auto-Instrumentation](auto-instrumentation.md)
6. [Cloud Platforms](cloud-platforms.md)
