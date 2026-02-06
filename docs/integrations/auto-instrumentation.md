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
from tracecraft.instrumentation.auto import auto_instrument

# Initialize TraceCraft
tracecraft.init()

# Auto-instrument OpenAI and Anthropic SDKs
auto_instrument()

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

```python
from tracecraft.instrumentation.auto import auto_instrument

# Only OpenAI
auto_instrument(openai=True, anthropic=False)

# Only Anthropic
auto_instrument(openai=False, anthropic=True)
```

### Disable Instrumentation

```python
from tracecraft.instrumentation.auto import uninstrument

# Remove instrumentation
uninstrument()
```

## Combining with Manual Tracing

```python
import tracecraft
from tracecraft import trace_agent
from tracecraft.instrumentation.auto import auto_instrument

tracecraft.init()
auto_instrument()

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
from tracecraft.instrumentation.auto import auto_instrument

tracecraft.init()
auto_instrument()

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
from tracecraft.adapters.langchain import TraceCraftCallbackHandler
from tracecraft.instrumentation.auto import auto_instrument

tracecraft.init()
auto_instrument()

# Both LangChain and direct OpenAI calls are traced
handler = TraceCraftCallbackHandler()
chain.invoke(input, config={"callbacks": [handler]})
```

## Troubleshooting

### Instrumentation Not Working

Ensure auto_instrument is called before importing SDKs:

```python
# Correct order
import tracecraft
from tracecraft.instrumentation.auto import auto_instrument

tracecraft.init()
auto_instrument()

import openai  # Import after instrumentation

# Incorrect order
import openai  # Too early!
auto_instrument()  # Won't work
```

### Duplicate Spans

If you're seeing duplicate spans, you might be instrumenting twice:

```python
# Don't do this
auto_instrument()
auto_instrument()  # Duplicate!

# Do this
from tracecraft.instrumentation.auto import is_instrumented

if not is_instrumented():
    auto_instrument()
```

## Next Steps

- [LangChain Integration](langchain.md)
- [Decorators](../user-guide/decorators.md)
- [User Guide](../user-guide/index.md)
