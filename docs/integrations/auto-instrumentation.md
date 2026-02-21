# Auto-Instrumentation

Trace Craft can automatically instrument popular LLM SDKs and agent frameworks **without any code changes** to your application — no decorators, no wrappers, no refactoring. Just initialize Trace Craft before your LLM imports and every call is captured.

**Supported:** OpenAI · Anthropic · LangChain · LlamaIndex

## Installation

```bash
# OpenAI + Anthropic auto-instrumentation
pip install "tracecraft[auto,tui]"

# LangChain auto-instrumentation
pip install "tracecraft[langchain,tui]"

# LlamaIndex auto-instrumentation
pip install "tracecraft[llamaindex,tui]"

# Everything at once
pip install "tracecraft[all]"
```

## Quick Start

Two lines. That's it:

```python
import tracecraft

# Must call init() BEFORE importing LLM SDKs
tracecraft.init(auto_instrument=True, jsonl=True)

# Now use OpenAI, Anthropic, LangChain, or LlamaIndex normally
import openai
client = openai.OpenAI()
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}]
)
# ^ This call is automatically traced — no decorator needed
```

Then explore every trace in the TUI:

```bash
tracecraft tui
```

!!! warning "Initialize Before Importing SDKs"

    `tracecraft.init()` must be called **before** importing OpenAI, Anthropic,
    LangChain, or LlamaIndex. Trace Craft patches the SDK at import time — if
    you import first, the patch won't apply.

    ```python
    # ✅ Correct
    import tracecraft
    tracecraft.init(auto_instrument=True)
    import openai  # patched

    # ❌ Incorrect — OpenAI already imported, patch won't apply
    import openai
    import tracecraft
    tracecraft.init(auto_instrument=True)
    ```

## Supported Frameworks

### OpenAI

Automatically traces:

- Chat completions (sync + async)
- Embeddings
- Streaming responses
- Function calling
- Token usage and cost

```python
import tracecraft
tracecraft.init(auto_instrument=True, jsonl=True)

from openai import OpenAI

client = OpenAI()

# Automatically traced — no decorator needed
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello"}]
)
```

### Anthropic

Automatically traces:

- Messages API (sync + async)
- Streaming
- Tool use
- Token counts and cost

```python
import tracecraft
tracecraft.init(auto_instrument=True, jsonl=True)

from anthropic import Anthropic

client = Anthropic()

# Automatically traced — no decorator needed
message = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}]
)
```

### LangChain

Trace Craft patches LangChain's `CallbackManager` to automatically inject its callback handler into **all** chains, agents, and tools — no explicit `callbacks=[...]` required.

Automatically traces:

- LLM calls (ChatOpenAI, ChatAnthropic, etc.)
- Chain invocations
- Agent runs and tool calls
- Retrieval steps

```python
import tracecraft
tracecraft.init(auto_instrument=True, jsonl=True)

# Import LangChain after init
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

llm = ChatOpenAI(model="gpt-4o-mini")
prompt = ChatPromptTemplate.from_template("Tell me a joke about {topic}")
chain = prompt | llm

# Automatically traced — no callback configuration needed
result = chain.invoke({"topic": "bears"})
```

!!! tip "LangChain Installation"

    ```bash
    pip install "tracecraft[langchain,tui]"
    ```

### LlamaIndex

Trace Craft registers its span handler with LlamaIndex's global instrumentation dispatcher, automatically capturing all query and retrieval operations.

Automatically traces:

- Query engine runs
- Retrieval steps
- LLM calls within index operations
- Embedding generation

```python
import tracecraft
tracecraft.init(auto_instrument=True, jsonl=True)

# Import LlamaIndex after init
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader

documents = SimpleDirectoryReader("data/").load_data()
index = VectorStoreIndex.from_documents(documents)

query_engine = index.as_query_engine()

# Automatically traced — every query and retrieval step captured
response = query_engine.query("What is the main theme?")
```

!!! tip "LlamaIndex Installation"

    ```bash
    pip install "tracecraft[llamaindex,tui]"
    ```

## Configuration

### Via `init()` Parameters

```python
import tracecraft

# Instrument all supported SDKs + stream live to TUI receiver
tracecraft.init(auto_instrument=True, receiver=True, service_name="my-agent")

# Instrument all SDKs + write to file
tracecraft.init(auto_instrument=True, jsonl=True)
```

### Via Config File

Set `auto_instrument` in `.tracecraft/config.yaml` — no code changes required:

```yaml
# .tracecraft/config.yaml
default:
  instrumentation:
    auto_instrument: true          # all SDKs

    # or selectively:
    # auto_instrument:
    #   - openai
    #   - anthropic

environments:
  development:
    instrumentation:
      auto_instrument: true        # full instrumentation in dev

  staging:
    instrumentation:
      auto_instrument:
        - openai
        - anthropic                # selected providers in staging

  production:
    instrumentation:
      auto_instrument: false       # decorators only in production
```

Explicit `init()` parameters always take precedence over the config file.

### Selective Instrumentation

Instrument only specific providers by passing a list:

```python
import tracecraft

# Only OpenAI
tracecraft.init(auto_instrument=["openai"], jsonl=True)

# Only Anthropic
tracecraft.init(auto_instrument=["anthropic"], jsonl=True)

# OpenAI + LangChain
tracecraft.init(auto_instrument=["openai", "langchain"], jsonl=True)

# All four
tracecraft.init(auto_instrument=True, jsonl=True)  # same as ["openai", "anthropic", "langchain", "llamaindex"]
```

### Via Environment Variable

```bash
export TRACECRAFT_AUTO_INSTRUMENT=true              # all SDKs
export TRACECRAFT_AUTO_INSTRUMENT=openai,langchain  # selective
```

### Disable Instrumentation

```python
from tracecraft.instrumentation.auto import disable_auto_instrumentation

# Disable all instrumentation
disable_auto_instrumentation()

# Disable specific providers
disable_auto_instrumentation(["openai", "langchain"])
```

## Combining with Manual Tracing

Auto-instrumentation and decorators work together seamlessly. Use decorators for your agent/orchestration logic and let auto-instrumentation handle the LLM calls:

```python
import tracecraft
from tracecraft import trace_agent, trace_tool

tracecraft.init(auto_instrument=True, jsonl=True)

@trace_agent(name="research_agent")
async def research_agent(query: str) -> str:
    # This span: captured by @trace_agent decorator
    docs = await retrieve(query)
    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": query}]
    )
    # ^ This LLM span: captured automatically by auto-instrumentation
    return response.choices[0].message.content

@trace_tool(name="retrieve")
async def retrieve(query: str) -> list[str]:
    # This span: captured by @trace_tool decorator
    return ["doc1", "doc2"]
```

## What Gets Captured

### OpenAI and Anthropic Spans

| Field | Description |
|-------|-------------|
| Model name and provider | e.g., `gpt-4o-mini`, `openai` |
| Prompt and completion | Full messages sent and received |
| Token counts | Input, output, and total tokens |
| Estimated cost | Calculated per call |
| Finish reason | `stop`, `length`, `tool_calls`, etc. |
| Function/tool calls | Full tool call arguments and results |
| Latency | Time-to-first-token and total duration |

### LangChain Spans

| Field | Description |
|-------|-------------|
| Chain type and name | e.g., `LLMChain`, `RetrievalQA` |
| LLM calls | Model, prompts, outputs, token counts |
| Tool calls | Tool name, input, output |
| Agent steps | Full reasoning chain with intermediate steps |

### LlamaIndex Spans

| Field | Description |
|-------|-------------|
| Query text | The input query string |
| Retrieved nodes | Document chunks with relevance scores |
| LLM calls | Prompts constructed from retrieved context |
| Embedding calls | Text and embedding model used |

## Best Practices

### Initialize at Application Startup

```python
# entry_point.py — at the very top, before any LLM imports
import tracecraft

tracecraft.init(
    auto_instrument=True,
    jsonl=True,           # Enable TUI access
    service_name="my-agent-service",
)

# Now import everything else
from my_agent import run_agent
```

### Combine with Decorators for Full Observability

```python
import tracecraft
from tracecraft import trace_agent

tracecraft.init(auto_instrument=True, jsonl=True)

@trace_agent(name="rag_agent")
async def rag_agent(query: str) -> str:
    # Decorator traces the agent span
    # Auto-instrumentation traces every LLM call inside
    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": query}]
    )
    return response.choices[0].message.content
```

## Troubleshooting

### Instrumentation Not Working

Ensure `tracecraft.init()` is called **before** importing SDKs:

```python
# ✅ Correct order
import tracecraft
tracecraft.init(auto_instrument=True)
import openai  # Import after — patched successfully

# ❌ Incorrect order
import openai  # Too early — already imported before patching
tracecraft.init(auto_instrument=True)  # Won't patch already-imported modules
```

### Duplicate Spans

If you're seeing duplicate spans, you might be calling `init()` twice. Trace Craft's
`init()` is idempotent — the second call is a no-op. If you need to re-instrument,
call `disable_auto_instrumentation()` first:

```python
from tracecraft.instrumentation.auto import disable_auto_instrumentation

disable_auto_instrumentation()
tracecraft.init(auto_instrument=True)  # Re-instrument cleanly
```

## Next Steps

- [LangChain Integration](langchain.md)
- [LlamaIndex Integration](llamaindex.md)
- [Decorators](../user-guide/decorators.md)
- [Terminal UI Guide](../user-guide/tui.md)
