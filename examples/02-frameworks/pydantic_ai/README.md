# PydanticAI Integration Examples

Trace PydanticAI agents using the `TraceCraftSpanProcessor`.

## Prerequisites

```bash
pip install pydantic-ai
export OPENAI_API_KEY=sk-...
```

## Integration Pattern

PydanticAI uses OpenTelemetry internally. The `TraceCraftSpanProcessor` intercepts spans and converts them to TraceCraft format.

```python
from tracecraft.adapters.pydantic_ai import TraceCraftSpanProcessor
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from pydantic_ai import Agent

processor = TraceCraftSpanProcessor()

agent = Agent(
    "openai:gpt-4o-mini",
    system_prompt="You are a helpful assistant.",
)

run = AgentRun(name="my_agent", start_time=datetime.now(UTC))

with run_context(run):
    result = agent.run_sync("Your prompt")

runtime.end_run(run)
processor.clear()
```

## Examples

| File | Description |
|------|-------------|
| `01_basic_agent.py` | Simple agent, structured output, basic tools |
| `02_tool_use.py` | Advanced tool patterns with multiple tools |

## What Gets Traced

- **Agent execution**: Start, end, result
- **LLM calls**: Model, messages, response
- **Tool invocations**: Tool name, inputs, outputs
- **Structured output**: Pydantic model validation

## Key Patterns

### Basic Agent

```python
from pydantic_ai import Agent

agent = Agent(
    "openai:gpt-4o-mini",
    system_prompt="You are a helpful assistant.",
)

result = agent.run_sync("What is 2 + 2?")
print(result.output)
```

### Structured Output

```python
from pydantic import BaseModel
from pydantic_ai import Agent

class Response(BaseModel):
    answer: str
    confidence: float

agent = Agent(
    "openai:gpt-4o-mini",
    output_type=Response,
)

result = agent.run_sync("What is the capital of France?")
print(result.output.answer)  # Paris
print(result.output.confidence)  # 0.99
```

### Tools with `@tool_plain`

```python
from pydantic_ai import Agent

agent = Agent("openai:gpt-4o-mini")

@agent.tool_plain
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"72F, Sunny in {city}"

@agent.tool_plain
def calculator(expression: str) -> str:
    """Evaluate a math expression."""
    return str(eval(expression))

result = agent.run_sync("What's the weather in Paris?")
```

### Async Execution

```python
import asyncio

async def main():
    result = await agent.run("Your prompt")
    print(result.output)

asyncio.run(main())
```

## Notes

- PydanticAI uses OpenTelemetry, so spans are automatically captured
- Always call `processor.clear()` after `runtime.end_run()`
- Use `agent.run_sync()` for synchronous execution
- Use `agent.run()` (with `await`) for async execution
