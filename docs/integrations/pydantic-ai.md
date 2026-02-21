# PydanticAI Integration

Trace Craft integrates with PydanticAI through the `TraceCraftSpanProcessor`, an OpenTelemetry
`SpanProcessor` that intercepts PydanticAI's Logfire-based spans and converts them to Trace Craft
Steps. You get full traces — LLM calls, tool use, structured output, and retries — with no changes
to your PydanticAI agent code.

## Installation

```bash
pip install "tracecraft[pydantic-ai]"
```

This installs Trace Craft with PydanticAI support, including `opentelemetry-sdk` and
`pydantic-ai>=0.0.14`.

## Quick Start

```python
import tracecraft
from tracecraft.adapters.pydantic_ai import TraceCraftSpanProcessor
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from pydantic_ai import Agent
from datetime import UTC, datetime

# Initialize Trace Craft
tracecraft.init(console=True)

# Wire the span processor into an OTel TracerProvider
processor = TraceCraftSpanProcessor()
provider = TracerProvider()
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

# Create a PydanticAI agent
agent = Agent("openai:gpt-4o-mini", system_prompt="You are a helpful assistant.")

# Wrap execution in a Trace Craft run
run = AgentRun(name="pydantic_ai_demo", start_time=datetime.now(UTC))
with run_context(run):
    result = agent.run_sync("What is the capital of France?")
    print(result.data)

# run.steps now contains LLM and workflow steps
processor.clear()
```

!!! note "TracerProvider must be set before agent calls"
    Set `trace.set_tracer_provider(provider)` before your first `agent.run_sync()` or
    `agent.run()` call. PydanticAI reads the global provider at import time.

## How It Works

### OTel SpanProcessor Approach

PydanticAI emits OpenTelemetry spans for every significant operation. `TraceCraftSpanProcessor`
sits in the OTel pipeline and is notified on `on_start()` (when a span opens) and `on_end()`
(when it closes). For each span it:

1. Extracts the span name and its attributes.
2. Infers a `StepType` from the attribute keys and span name.
3. Creates a `Step` and attaches it to the active `AgentRun` (respecting parent-child hierarchy).
4. On `on_end()`, fills in `end_time`, `duration_ms`, token counts, and any error status.

### Attribute Mapping

| OTel attribute | Maps to |
|---|---|
| `gen_ai.system` | `step.model_provider`, triggers `StepType.LLM` |
| `gen_ai.request.model` | `step.model_name`, triggers `StepType.LLM` |
| `gen_ai.usage.input_tokens` | `step.input_tokens` |
| `gen_ai.usage.output_tokens` | `step.output_tokens` |
| `tool.name` | `step.name`, triggers `StepType.TOOL` |
| span name starts with `"tool:"` | triggers `StepType.TOOL` |
| span name contains `"agent"` | triggers `StepType.AGENT` |
| span name contains `"retriev"` or `"vector"` | triggers `StepType.RETRIEVAL` |
| everything else | `StepType.WORKFLOW` |

### Streaming

Streaming chunks arrive as OTel span events named `gen_ai.content.chunk` or `llm.content.chunk`.
`TraceCraftSpanProcessor.on_event()` captures these, sets `step.is_streaming = True`, and
accumulates the text in `step.streaming_chunks`.

## Basic Examples

### Simple Agent

```python
import tracecraft
from tracecraft.adapters.pydantic_ai import TraceCraftSpanProcessor
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from pydantic_ai import Agent
from datetime import UTC, datetime

tracecraft.init()

processor = TraceCraftSpanProcessor()
provider = TracerProvider()
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

agent = Agent("openai:gpt-4o-mini")

run = AgentRun(name="simple_agent", start_time=datetime.now(UTC))
with run_context(run):
    result = agent.run_sync("Explain what an LLM trace is in two sentences.")
    print(result.data)

processor.clear()
```

### Async Agent

```python
import asyncio
import tracecraft
from tracecraft.adapters.pydantic_ai import TraceCraftSpanProcessor
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from pydantic_ai import Agent
from datetime import UTC, datetime

tracecraft.init()

processor = TraceCraftSpanProcessor()
provider = TracerProvider()
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

agent = Agent("openai:gpt-4o-mini", system_prompt="Answer concisely.")

async def main() -> None:
    run = AgentRun(name="async_agent", start_time=datetime.now(UTC))
    with run_context(run):
        result = await agent.run("List three benefits of LLM observability.")
        print(result.data)
    processor.clear()

asyncio.run(main())
```

## Structured Output

### Pydantic Models as Output

PydanticAI validates agent responses against a Pydantic model. Trace Craft captures the LLM call
and the validation result:

```python
from pydantic import BaseModel
from pydantic_ai import Agent
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from datetime import UTC, datetime

class MovieReview(BaseModel):
    title: str
    rating: float
    summary: str
    recommended: bool

agent = Agent(
    "openai:gpt-4o-mini",
    result_type=MovieReview,
    system_prompt="You are a movie critic. Return structured reviews.",
)

run = AgentRun(name="structured_output", start_time=datetime.now(UTC))
with run_context(run):
    result = agent.run_sync("Review the movie Inception.")
    review = result.data
    print(f"Title: {review.title}")
    print(f"Rating: {review.rating}/10")
    print(f"Recommended: {review.recommended}")
```

### Nested Models

```python
from pydantic import BaseModel
from pydantic_ai import Agent
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from datetime import UTC, datetime

class Address(BaseModel):
    street: str
    city: str
    country: str

class Company(BaseModel):
    name: str
    founded: int
    headquarters: Address
    products: list[str]

agent = Agent(
    "openai:gpt-4o-mini",
    result_type=Company,
    system_prompt="Return structured company information.",
)

run = AgentRun(name="nested_structured_output", start_time=datetime.now(UTC))
with run_context(run):
    result = agent.run_sync("Tell me about Anthropic.")
    company = result.data
    print(f"{company.name} founded in {company.founded}")
    print(f"HQ: {company.headquarters.city}, {company.headquarters.country}")
    print(f"Products: {', '.join(company.products)}")
```

## Tool Use

### Basic Tools with @tool

```python
from pydantic_ai import Agent, tool
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from datetime import UTC, datetime

agent = Agent("openai:gpt-4o-mini", system_prompt="Use tools to answer questions.")

@agent.tool_plain
def get_current_temperature(city: str) -> str:
    """Return the current temperature for a city."""
    # Stub: replace with a real weather API call
    temperatures = {"london": "15C", "new york": "22C", "tokyo": "28C"}
    return temperatures.get(city.lower(), "20C")

run = AgentRun(name="tool_use", start_time=datetime.now(UTC))
with run_context(run):
    result = agent.run_sync("What is the temperature in London and Tokyo?")
    print(result.data)
```

Tool calls appear as `StepType.TOOL` steps nested under the agent's `StepType.LLM` step.

### Multiple Tools

```python
from pydantic_ai import Agent
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from datetime import UTC, datetime

agent = Agent("openai:gpt-4o-mini")

@agent.tool_plain
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b

@agent.tool_plain
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b

@agent.tool_plain
def lookup_fact(topic: str) -> str:
    """Look up a fact about a topic."""
    facts = {
        "python": "Python was created by Guido van Rossum in 1991.",
        "tracecraft": "Trace Craft is a vendor-neutral LLM observability SDK.",
    }
    return facts.get(topic.lower(), f"No fact found for '{topic}'.")

run = AgentRun(name="multi_tool", start_time=datetime.now(UTC))
with run_context(run):
    result = agent.run_sync(
        "What is 12 plus 7? What is 6 times 9? Tell me a fact about Python."
    )
    print(result.data)
```

### Async Tools

```python
import asyncio
from pydantic_ai import Agent
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from datetime import UTC, datetime

agent = Agent("openai:gpt-4o-mini")

@agent.tool_plain
async def fetch_user_data(user_id: str) -> dict[str, str]:
    """Fetch user profile from the database."""
    # Simulated async database call
    await asyncio.sleep(0.01)
    return {"id": user_id, "name": "Alice", "role": "admin"}

@agent.tool_plain
async def send_notification(user_id: str, message: str) -> str:
    """Send a notification to a user."""
    await asyncio.sleep(0.01)
    return f"Notification sent to {user_id}: {message}"

async def main() -> None:
    run = AgentRun(name="async_tools", start_time=datetime.now(UTC))
    with run_context(run):
        result = await agent.run(
            "Fetch data for user 'u-123' and send them a welcome notification."
        )
        print(result.data)

asyncio.run(main())
```

### Multi-Step Tool Chains

```python
from pydantic_ai import Agent
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from datetime import UTC, datetime

agent = Agent(
    "openai:gpt-4o-mini",
    system_prompt="You are a research assistant. Use tools step by step.",
)

@agent.tool_plain
def search_papers(topic: str) -> list[str]:
    """Search for academic papers on a topic."""
    return [
        f"Paper A: {topic} fundamentals (2023)",
        f"Paper B: Advanced {topic} techniques (2024)",
    ]

@agent.tool_plain
def summarize_paper(title: str) -> str:
    """Summarize an academic paper given its title."""
    return f"Summary of '{title}': This paper explores key concepts and presents novel findings."

@agent.tool_plain
def format_bibliography(titles: list[str]) -> str:
    """Format a list of paper titles as a bibliography."""
    return "\n".join(f"[{i+1}] {title}" for i, title in enumerate(titles))

run = AgentRun(name="research_chain", start_time=datetime.now(UTC))
with run_context(run):
    result = agent.run_sync(
        "Find papers about RAG, summarize the first one, and format a bibliography."
    )
    print(result.data)

# Inspect the full tool chain in the trace
for step in run.steps:
    print(f"{step.type.value}: {step.name} ({step.duration_ms:.0f}ms)")
```

## Dependency Injection

### RunContext Dependencies

PydanticAI uses `RunContext` to inject dependencies into tools. Trace Craft traces the tool
calls transparently regardless of the dependency type:

```python
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from datetime import UTC, datetime

@dataclass
class DatabaseDeps:
    connection_string: str
    max_retries: int = 3

agent: Agent[DatabaseDeps, str] = Agent(
    "openai:gpt-4o-mini",
    system_prompt="Use the database to answer questions.",
)

@agent.tool
async def query_database(ctx: RunContext[DatabaseDeps], sql: str) -> str:
    """Execute a SQL query against the database."""
    # ctx.deps.connection_string is available for the real implementation
    return f"Result from DB ({ctx.deps.connection_string}): 42 rows"

deps = DatabaseDeps(connection_string="postgresql://localhost/mydb")

run = AgentRun(name="deps_injection", start_time=datetime.now(UTC))
with run_context(run):
    result = agent.run_sync("How many users signed up last week?", deps=deps)
    print(result.data)
```

### System Dependencies

```python
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from datetime import UTC, datetime

@dataclass
class AppDeps:
    user_id: str
    session_id: str
    feature_flags: dict[str, bool]

agent: Agent[AppDeps, str] = Agent("openai:gpt-4o-mini")

@agent.tool
def check_feature_flag(ctx: RunContext[AppDeps], flag_name: str) -> bool:
    """Check whether a feature flag is enabled."""
    return ctx.deps.feature_flags.get(flag_name, False)

@agent.tool
def get_user_tier(ctx: RunContext[AppDeps]) -> str:
    """Get the subscription tier for the current user."""
    # Stub: use ctx.deps.user_id to look up tier
    return "pro"

deps = AppDeps(
    user_id="user-456",
    session_id="sess-789",
    feature_flags={"beta_rag": True, "streaming": False},
)

run = AgentRun(name="system_deps", start_time=datetime.now(UTC))
with run_context(run):
    result = agent.run_sync(
        "Is the beta_rag feature enabled? What tier am I on?",
        deps=deps,
    )
    print(result.data)
```

## Retry Handling

### Automatic Retries

PydanticAI automatically retries failed tool calls and LLM requests. Trace Craft captures each
attempt as a separate step, so you can see exactly where failures occurred:

```python
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelRetry
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from datetime import UTC, datetime

attempt_count = 0

agent = Agent("openai:gpt-4o-mini", retries=3)

@agent.tool_plain
def flaky_service(query: str) -> str:
    """A tool that fails on the first two attempts."""
    global attempt_count
    attempt_count += 1
    if attempt_count < 3:
        raise ModelRetry(f"Service unavailable, attempt {attempt_count}")
    return f"Success on attempt {attempt_count}: {query}"

run = AgentRun(name="retry_demo", start_time=datetime.now(UTC))
with run_context(run):
    result = agent.run_sync("Call the flaky service with query 'hello'.")
    print(result.data)

# Failed attempts appear as ERROR steps in the trace
error_steps = [s for s in run.steps if s.error]
print(f"Failed attempts: {len(error_steps)}")
```

### Model Fallback

```python
from pydantic_ai import Agent
from pydantic_ai.models.fallback import FallbackModel
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from datetime import UTC, datetime

# Try GPT-4o-mini first, fall back to GPT-3.5-turbo
fallback_model = FallbackModel("openai:gpt-4o-mini", "openai:gpt-3.5-turbo")
agent = Agent(fallback_model, system_prompt="Answer concisely.")

run = AgentRun(name="fallback_model", start_time=datetime.now(UTC))
with run_context(run):
    result = agent.run_sync("What is the speed of light?")
    print(result.data)

# Each model attempt appears as a separate LLM step
llm_steps = [s for s in run.steps if s.type.value == "llm"]
for step in llm_steps:
    print(f"Model used: {step.model_name}")
```

## Streaming

### Text Output Streaming

```python
import asyncio
from pydantic_ai import Agent
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from datetime import UTC, datetime

agent = Agent("openai:gpt-4o-mini")

async def main() -> None:
    run = AgentRun(name="streaming_text", start_time=datetime.now(UTC))
    with run_context(run):
        async with agent.run_stream("Write a haiku about observability.") as response:
            async for chunk in response.stream_text():
                print(chunk, end="", flush=True)
        print()

asyncio.run(main())
```

Trace Craft marks the LLM step with `is_streaming = True` and accumulates text in
`step.streaming_chunks`.

### Structured Output Streaming

```python
import asyncio
from pydantic import BaseModel
from pydantic_ai import Agent
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from datetime import UTC, datetime

class StoryOutline(BaseModel):
    title: str
    protagonist: str
    setting: str
    conflict: str

agent = Agent("openai:gpt-4o-mini", result_type=StoryOutline)

async def main() -> None:
    run = AgentRun(name="streaming_structured", start_time=datetime.now(UTC))
    with run_context(run):
        async with agent.run_stream("Create a story outline about a robot detective.") as response:
            # Stream the validated result as it builds up
            async for partial in response.stream():
                pass  # Process incremental Pydantic model
            outline = response.data
            print(f"Title: {outline.title}")
            print(f"Protagonist: {outline.protagonist}")

asyncio.run(main())
```

## Multiple Model Support

### OpenAI

```python
from pydantic_ai import Agent
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from datetime import UTC, datetime

agent = Agent("openai:gpt-4o", system_prompt="You are an expert analyst.")

run = AgentRun(name="openai_agent", start_time=datetime.now(UTC))
with run_context(run):
    result = agent.run_sync("Analyze the current state of LLM observability tooling.")
    print(result.data)
```

### Anthropic

```python
from pydantic_ai import Agent
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from datetime import UTC, datetime

agent = Agent("anthropic:claude-3-5-sonnet-latest", system_prompt="Think step by step.")

run = AgentRun(name="anthropic_agent", start_time=datetime.now(UTC))
with run_context(run):
    result = agent.run_sync("What are the tradeoffs of sampling in LLM tracing?")
    print(result.data)
```

### Model Switching

You can run the same agent logic against different models and compare results in Trace Craft:

```python
from pydantic_ai import Agent
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from datetime import UTC, datetime

MODELS = ["openai:gpt-4o-mini", "anthropic:claude-3-haiku-latest"]
PROMPT = "Summarize the CAP theorem in one paragraph."

for model_id in MODELS:
    agent = Agent(model_id)
    run = AgentRun(name=f"model_comparison_{model_id}", start_time=datetime.now(UTC))
    with run_context(run):
        result = agent.run_sync(PROMPT)
        print(f"\n--- {model_id} ---")
        print(result.data)
```

## Advanced Usage

### Per-Run Configuration

Attach custom metadata to a run before entering the context:

```python
import tracecraft
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from datetime import UTC, datetime

run = AgentRun(name="customer_support_session", start_time=datetime.now(UTC))
run.attributes["user_id"] = "cust-9001"
run.attributes["session_id"] = "sess-abc123"
run.attributes["tier"] = "enterprise"

with run_context(run):
    result = agent.run_sync("How do I export traces to S3?")
    print(result.data)

# Explicit export when not using runtime.run()
tracecraft.get_runtime().end_run(run)
```

### Custom System Prompts

```python
from pydantic_ai import Agent
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from datetime import UTC, datetime

def build_system_prompt(user_tier: str, locale: str) -> str:
    return (
        f"You are a helpful assistant for {user_tier} customers. "
        f"Respond in {locale}. Be concise and precise."
    )

agent = Agent("openai:gpt-4o-mini")

run = AgentRun(name="custom_prompt", start_time=datetime.now(UTC))
with run_context(run):
    result = agent.run_sync(
        "What is Trace Craft?",
        system_prompt=build_system_prompt(user_tier="pro", locale="English"),
    )
    print(result.data)
```

### Caching Responses

```python
from pydantic_ai import Agent
from pydantic_ai.cache import FileCache
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from datetime import UTC, datetime
from pathlib import Path

agent = Agent("openai:gpt-4o-mini", cache=FileCache(Path(".cache/pydantic_ai")))

run = AgentRun(name="cached_agent", start_time=datetime.now(UTC))
with run_context(run):
    # First call hits the model; subsequent identical calls use the cache
    result = agent.run_sync("What is the Pythagorean theorem?")
    print(result.data)
```

## Best Practices

### 1. Set the TracerProvider Once at Startup

```python
# app.py — module-level initialization
import tracecraft
from tracecraft.adapters.pydantic_ai import TraceCraftSpanProcessor
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

tracecraft.init(service_name="my-pydantic-ai-app")

processor = TraceCraftSpanProcessor()
provider = TracerProvider()
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
```

Changing the global `TracerProvider` after agents are created can cause spans to be lost.

### 2. Always Use run_context

Every agent call must be wrapped in a `run_context` (or `runtime.run()`). Without an active
`AgentRun`, the processor receives spans but has nowhere to attach them:

```python
runtime = tracecraft.get_runtime()

with runtime.run("agent_session"):
    result = agent.run_sync(user_prompt)
```

### 3. Call clear() After Each Session

`TraceCraftSpanProcessor` tracks in-flight spans internally. Calling `processor.clear()` after
a completed session prevents memory from accumulating across many requests:

```python
try:
    with run_context(run):
        result = agent.run_sync(prompt)
finally:
    processor.clear()
```

### 4. Use Descriptive Run Names

Run names appear in the Trace Craft TUI and JSONL exports. Choose names that identify the
workflow, user, and session for easy filtering:

```python
run = AgentRun(
    name=f"support_{user_id}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}",
    start_time=datetime.now(UTC),
)
```

### 5. Handle Tool Errors Explicitly

When a tool raises an exception that is not `ModelRetry`, PydanticAI propagates it to the caller.
Trace Craft captures the error in the span, but you should still handle it at the application level:

```python
from pydantic_ai.exceptions import UnexpectedModelBehavior

with run_context(run):
    try:
        result = agent.run_sync(prompt)
    except UnexpectedModelBehavior as exc:
        # The failed LLM step is already in run.steps with step.error set
        logger.error("Unexpected model behavior: %s", exc)
```

## Troubleshooting

### Spans Not Captured

**Symptom:** `run.steps` is empty after calling `agent.run_sync()`.

**Cause:** The `TracerProvider` was not set before the agent was created, or no `AgentRun` was
active.

**Fix:** Set the provider at module level and wrap calls in `run_context`:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from tracecraft.adapters.pydantic_ai import TraceCraftSpanProcessor

processor = TraceCraftSpanProcessor()
provider = TracerProvider()
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)  # Must happen before any agent.run_sync()
```

### Missing Token Counts

**Symptom:** `step.input_tokens` and `step.output_tokens` are `None` for LLM steps.

**Cause:** The model or provider does not emit `gen_ai.usage.*` span attributes.

**Fix:** Verify that PydanticAI's OTel instrumentation is active. Check the span attributes by
adding a debug processor:

```python
from opentelemetry.sdk.trace import SpanProcessor

class DebugProcessor(SpanProcessor):
    def on_end(self, span):
        print(dict(span.attributes or {}))

provider.add_span_processor(DebugProcessor())
```

Look for `gen_ai.usage.input_tokens` and `gen_ai.usage.output_tokens` in the output.

### Tool Spans Missing

**Symptom:** Tool steps are absent from `run.steps` even though tools were called.

**Cause:** PydanticAI emits tool spans with a `tool:` prefix in the span name or with a
`tool.name` attribute. If the span name format differs in your version, the type inference
may fall back to `WORKFLOW`.

**Fix:** Check which span names PydanticAI emits with the debug processor above. If the names
differ, tool steps still appear as `WORKFLOW` steps — search by `step.name` instead of
`step.type`.

### Memory Issues in Long-Running Services

**Symptom:** Memory grows steadily in a server handling many requests.

**Cause:** `processor.clear()` is not called after each request, leaving completed span references
in the processor's internal dictionaries.

**Fix:** Use `try/finally` to ensure `clear()` is always called:

```python
async def handle_request(prompt: str) -> str:
    run = AgentRun(name="request", start_time=datetime.now(UTC))
    try:
        with run_context(run):
            result = await agent.run(prompt)
            return result.data
    finally:
        processor.clear()
```

## Next Steps

- [LlamaIndex Integration](llamaindex.md)
- [LangChain Integration](langchain.md)
- [Auto-Instrumentation](auto-instrumentation.md)
- [User Guide](../user-guide/index.md)
