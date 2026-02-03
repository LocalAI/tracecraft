# 02 - Framework Integrations

Learn how to integrate TraceCraft with popular LLM frameworks. Each framework has its own integration approach tailored to its architecture.

## Framework Overview

| Framework | Adapter | Integration Style |
|-----------|---------|-------------------|
| [LangChain](langchain/) | `TraceCraftCallbackHandler` | Callback-based |
| [LangGraph](langgraph/) | `TraceCraftCallbackHandler` | Same as LangChain |
| [LlamaIndex](llamaindex/) | `TraceCraftSpanHandler` | Callback manager |
| [PydanticAI](pydantic_ai/) | `TraceCraftSpanProcessor` | OpenTelemetry span processor |
| [OpenAI](openai/) | Decorators | Manual decoration |

## Prerequisites

All examples in this section require:

- An OpenAI API key: `export OPENAI_API_KEY=sk-...`
- Framework-specific dependencies (see below)

## Framework Dependencies

```bash
# LangChain
pip install langchain-openai langchain-community

# LangGraph (uses same callback as LangChain)
pip install langgraph langchain-openai

# LlamaIndex
pip install llama-index-core llama-index-llms-openai

# PydanticAI
pip install pydantic-ai

# OpenAI (direct)
pip install openai
```

## Quick Comparison

### LangChain

```python
from tracecraft.adapters.langchain import TraceCraftCallbackHandler

handler = TraceCraftCallbackHandler()
chain.invoke(input, config={"callbacks": [handler]})
```

### LangGraph

```python
from tracecraft.adapters.langchain import TraceCraftCallbackHandler

handler = TraceCraftCallbackHandler()
# LangGraph uses the same callback system as LangChain
graph.invoke(state, config={"callbacks": [handler]})
```

### LlamaIndex

```python
from tracecraft.adapters.llamaindex import TraceCraftSpanHandler
from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager

handler = TraceCraftSpanHandler()
Settings.callback_manager = CallbackManager(handlers=[handler])
```

### PydanticAI

```python
from tracecraft.adapters.pydantic_ai import TraceCraftSpanProcessor

processor = TraceCraftSpanProcessor()
# PydanticAI uses OpenTelemetry internally; the processor intercepts spans
```

### OpenAI Direct

```python
from tracecraft.instrumentation.decorators import trace_llm

@trace_llm(name="chat", model="gpt-4o-mini", provider="openai")
def chat(prompt: str) -> str:
    client = openai.OpenAI()
    response = client.chat.completions.create(...)
    return response.choices[0].message.content
```

## Example Files

### LangChain (`langchain/`)

| Example | Description |
|---------|-------------|
| `01_simple_chain.py` | Basic LCEL chain with prompts and LLM |
| `02_tools_and_agents.py` | Tool binding and agent execution |
| `03_rag_pipeline.py` | RAG with retrieval and generation |
| `04_streaming.py` | Streaming response handling |

### LangGraph (`langgraph/`)

| Example | Description |
|---------|-------------|
| `01_simple_graph.py` | Basic state graph with LLM nodes |
| `02_multi_node_graph.py` | Conditional routing and sequential pipelines |
| `03_react_agent.py` | ReAct agents with tool execution |

### LlamaIndex (`llamaindex/`)

| Example | Description |
|---------|-------------|
| `01_basic_query.py` | Completion, chat, RAG, and streaming |
| `02_rag_with_retrieval.py` | Advanced RAG patterns |
| `03_agents.py` | LlamaIndex agent workflows |

### PydanticAI (`pydantic_ai/`)

| Example | Description |
|---------|-------------|
| `01_basic_agent.py` | Simple agent, structured output, tools |
| `02_tool_use.py` | Advanced tool patterns |

### OpenAI (`openai/`)

| Example | Description |
|---------|-------------|
| `01_direct_api.py` | Direct API calls with tracing |
| `02_function_calling.py` | Function calling patterns |
| `03_streaming.py` | Token-level streaming |

## What Gets Traced

Each framework adapter captures:

| Framework | LLM Calls | Tools | Retrieval | Tokens | Cost |
|-----------|-----------|-------|-----------|--------|------|
| LangChain | Yes | Yes | Yes | Yes | Via enrichment |
| LangGraph | Yes | Yes | Yes | Yes | Via enrichment |
| LlamaIndex | Yes | Yes | Yes | Yes | Via enrichment |
| PydanticAI | Yes | Yes | N/A | Yes | Via enrichment |
| OpenAI | Manual | Manual | Manual | Manual | Manual |

## Troubleshooting

### "No traces appearing"

- Ensure the callback handler is passed to the invocation
- Check that you're within a `run_context()`
- Verify the handler is initialized before the call

### "Missing token counts"

- Token counts come from the LLM response
- Use the `TokenEnrichmentProcessor` for cost calculation

### "Handler not clearing"

- Call `handler.clear()` after `runtime.end_run()`
- This is important when reusing handlers

## Next Steps

After mastering framework integrations:

- [03-exporters/](../03-exporters/) - Export traces to various backends
- [04-production/](../04-production/) - Production patterns and processors
