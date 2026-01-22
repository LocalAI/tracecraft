# OpenAI Direct Integration Examples

Trace direct OpenAI API calls using AgentTrace decorators.

## Prerequisites

```bash
pip install openai
export OPENAI_API_KEY=sk-...
```

## Integration Pattern

For direct OpenAI API usage, use the `@trace_llm`, `@trace_tool`, and `@trace_agent` decorators.

```python
from agenttrace.instrumentation.decorators import trace_llm, trace_tool, trace_agent
from agenttrace.core.context import run_context
from agenttrace.core.models import AgentRun
import openai

@trace_llm(name="chat", model="gpt-4o-mini", provider="openai")
def chat(prompt: str) -> str:
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content

run = AgentRun(name="my_chat", start_time=datetime.now(UTC))

with run_context(run):
    result = chat("Hello!")

runtime.end_run(run)
```

## Examples

| File | Description |
|------|-------------|
| `01_direct_api.py` | Basic chat completions with tracing |
| `02_function_calling.py` | Function calling (tool use) patterns |
| `03_streaming.py` | Token-level streaming responses |

## What Gets Traced

- **LLM calls**: Model, messages, response, tokens (manual)
- **Tool execution**: Tool name, inputs, outputs
- **Agent loops**: Multi-turn conversations with tools
- **Streaming**: Flag indicating streaming mode

## Key Patterns

### Basic Chat

```python
@trace_llm(name="chat", model="gpt-4o-mini", provider="openai")
def chat(prompt: str) -> str:
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content
```

### Function Calling

```python
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"},
                },
                "required": ["city"],
            },
        },
    },
]

@trace_tool(name="get_weather")
def get_weather(city: str) -> str:
    return f"72F, Sunny in {city}"

@trace_llm(name="with_tools", model="gpt-4o-mini", provider="openai")
def call_with_tools(messages: list) -> dict:
    client = openai.OpenAI()
    return client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
    )
```

### Streaming

```python
@trace_llm(name="stream", model="gpt-4o-mini", provider="openai")
def stream_chat(prompt: str) -> str:
    client = openai.OpenAI()
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )

    chunks = []
    for chunk in stream:
        if chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            chunks.append(content)
            print(content, end="", flush=True)

    return "".join(chunks)
```

### Async Streaming

```python
async def async_stream(prompt: str) -> str:
    client = openai.AsyncOpenAI()
    stream = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )

    chunks = []
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            chunks.append(chunk.choices[0].delta.content)

    return "".join(chunks)
```

## Notes

- Decorators require explicit model and provider parameters
- Token counts must be extracted manually from responses
- For frameworks like LangChain, use their native adapters instead
- Use `@trace_agent` to wrap multi-step agent loops
