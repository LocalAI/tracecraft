# Auto-Instrumentation

TraceCraft can automatically instrument popular LLM SDKs without code changes.

## Installation

```bash
pip install "tracecraft[auto]"
```

This installs:

- `opentelemetry-instrumentation-openai`
- `opentelemetry-instrumentation-anthropic`

## Quick Start

```python
import tracecraft

# Initialize TraceCraft with auto-instrumentation enabled
tracecraft.init(auto_instrument=True)

# Now use OpenAI/Anthropic normally - tracing is automatic!
import openai
client = openai.OpenAI()
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

## Supported SDKs

### OpenAI

Automatically traces:

- Chat completions
- Embeddings
- Streaming responses
- Function calling
- Token usage

```python
from openai import OpenAI

client = OpenAI()

# Automatically traced
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello"}]
)
```

### Anthropic

Automatically traces:

- Messages API
- Streaming
- Tool use
- Token counts

```python
from anthropic import Anthropic

client = Anthropic()

# Automatically traced
message = client.messages.create(
    model="claude-3-opus-20240229",
    messages=[{"role": "user", "content": "Hello"}]
)
```

## Configuration

### Selective Instrumentation

Pass a list of provider names to instrument only specific SDKs:

```python
import tracecraft

# Only OpenAI (pick one of these options)
tracecraft.init(auto_instrument=["openai"])

# Only Anthropic
# tracecraft.init(auto_instrument=["anthropic"])

# Multiple: OpenAI + LangChain + LlamaIndex
# tracecraft.init(auto_instrument=["openai", "langchain", "llamaindex"])
```

### Disable Instrumentation

```python
from tracecraft.instrumentation.auto import disable_auto_instrumentation

# Remove all instrumentation
disable_auto_instrumentation()

# Remove specific providers
disable_auto_instrumentation(["openai"])
```

## Combining with Manual Tracing

```python
import tracecraft
from tracecraft import trace_agent

tracecraft.init(auto_instrument=True)

@trace_agent(name="agent")
async def my_agent(query: str):
    # Manual trace for agent
    # Auto trace for OpenAI call inside
    response = await openai_client.chat.completions.create(...)
    return response
```

## What Gets Captured

### OpenAI Spans

- Model name and provider
- Prompt and completion
- Token counts (input, output, total)
- Finish reason
- Function calls (if any)
- Latency

### Anthropic Spans

- Model name
- Messages (system, user, assistant)
- Token counts
- Stop reason
- Tool use
- Latency

## Best Practices

### 1. Initialize Early

```python
# At application startup
import tracecraft

tracecraft.init(auto_instrument=True)

# Now use SDKs anywhere in your app
```

### 2. Combine with Decorators

```python
@trace_agent(name="rag_agent")
async def rag_agent(query: str):
    # This span captured by decorator
    docs = await retrieve(query)

    # This span captured by auto-instrumentation
    response = await openai_client.chat.completions.create(...)

    return response
```

### 3. Use with Framework Adapters

```python
# LangChain + Auto-instrumentation
import tracecraft
from tracecraft.adapters.langchain import TraceCraftCallbackHandler

tracecraft.init(auto_instrument=True)

# Both LangChain and direct OpenAI calls are traced
handler = TraceCraftCallbackHandler()
chain.invoke(input, config={"callbacks": [handler]})
```

## Troubleshooting

### Instrumentation Not Working

Ensure `tracecraft.init()` is called before importing SDKs:

```python
# Correct order
import tracecraft

tracecraft.init(auto_instrument=True)

import openai  # Import after instrumentation

# Incorrect order
import openai  # Too early!
tracecraft.init(auto_instrument=True)  # Won't patch already-imported modules
```

### Duplicate Spans

If you're seeing duplicate spans, you might be calling `init()` twice. TraceCraft's
`init()` is idempotent - the second call is a no-op, so this is safe to ignore.
If you need to re-instrument after a restart, call `disable_auto_instrumentation()`
first:

```python
from tracecraft.instrumentation.auto import disable_auto_instrumentation

disable_auto_instrumentation()
tracecraft.init(auto_instrument=True)  # Re-instrument cleanly
```

## Next Steps

- [LangChain Integration](langchain.md)
- [Decorators](../user-guide/decorators.md)
- [User Guide](../user-guide/index.md)
