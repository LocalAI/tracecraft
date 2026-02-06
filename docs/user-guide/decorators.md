# Decorators

TraceCraft provides decorators for instrumenting your code with semantic tracing. Each decorator is designed for a specific type of operation.

## Overview

TraceCraft offers four main decorators:

| Decorator | Purpose | Step Type |
|-----------|---------|-----------|
| `@trace_agent` | Agent orchestration and workflows | `AGENT` |
| `@trace_tool` | Tool and utility functions | `TOOL` |
| `@trace_llm` | LLM API calls | `LLM` |
| `@trace_retrieval` | Retrieval operations (RAG, search) | `RETRIEVAL` |

Plus a flexible context manager:

- `step()` - For fine-grained manual instrumentation

## @trace_agent

Use for agent functions that orchestrate workflows or coordinate multiple operations.

### Signature

```python
def trace_agent(
    name: str | None = None,
    exclude_inputs: list[str] | None = None,
    capture_inputs: bool = True,
    runtime: TALRuntime | None = None,
) -> Callable
```

### Parameters

- **name** (str, optional): Name for the step. Defaults to function name.
- **exclude_inputs** (list[str], optional): Parameter names to exclude from capture. Shows as `[EXCLUDED]`.
- **capture_inputs** (bool): If False, no inputs are captured. Default: True.
- **runtime** (TALRuntime, optional): Explicit runtime for multi-tenant scenarios.

### Basic Usage

```python
from tracecraft import trace_agent

@trace_agent(name="customer_support")
async def customer_support(query: str) -> str:
    """Main customer support agent."""
    context = await search_knowledge_base(query)
    response = await generate_response(query, context)
    return response
```

### Excluding Sensitive Inputs

```python
@trace_agent(
    name="authenticated_agent",
    exclude_inputs=["api_key", "password"]
)
async def authenticated_agent(
    user: str,
    api_key: str,
    password: str
) -> dict:
    """Agent that requires authentication."""
    # api_key and password won't be logged
    return await process_authenticated(user, api_key, password)
```

### With Explicit Runtime

```python
from tracecraft import TraceCraftRuntime, TraceCraftConfig

# Create tenant-specific runtime
tenant_runtime = TraceCraftRuntime(
    config=TraceCraftConfig(service_name="tenant-a")
)

@trace_agent(name="tenant_agent", runtime=tenant_runtime)
async def tenant_agent(query: str) -> str:
    """Agent for specific tenant."""
    return await process(query)
```

### Synchronous Functions

Works with both sync and async functions:

```python
@trace_agent(name="sync_agent")
def sync_agent(input: str) -> str:
    """Synchronous agent."""
    return process(input)
```

## @trace_tool

Use for tool or utility functions that perform specific tasks.

### Signature

```python
def trace_tool(
    name: str | None = None,
    exclude_inputs: list[str] | None = None,
    capture_inputs: bool = True,
    runtime: TALRuntime | None = None,
) -> Callable
```

### Parameters

Same as `@trace_agent`.

### Basic Usage

```python
from tracecraft import trace_tool

@trace_tool(name="calculator")
def calculator(expression: str) -> float:
    """Calculate mathematical expression."""
    return eval(expression)

@trace_tool(name="web_scraper")
async def web_scraper(url: str) -> str:
    """Scrape content from a webpage."""
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.text
```

### File Operations

```python
@trace_tool(name="file_reader")
def read_file(filepath: str) -> str:
    """Read file contents."""
    with open(filepath) as f:
        return f.read()

@trace_tool(name="file_writer")
def write_file(filepath: str, content: str) -> None:
    """Write content to file."""
    with open(filepath, 'w') as f:
        f.write(content)
```

### API Calls

```python
@trace_tool(name="weather_api")
async def get_weather(city: str) -> dict:
    """Fetch weather data from API."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.weather.com/v1/{city}"
        )
        return response.json()
```

## @trace_llm

Use for LLM API calls to capture model information, prompts, and completions.

### Signature

```python
def trace_llm(
    name: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    exclude_inputs: list[str] | None = None,
    capture_inputs: bool = True,
    runtime: TALRuntime | None = None,
) -> Callable
```

### Parameters

- **name** (str, optional): Name for the step.
- **model** (str, optional): Model identifier (e.g., "gpt-4", "claude-3-opus").
- **provider** (str, optional): Provider name (e.g., "openai", "anthropic").
- **exclude_inputs** (list[str], optional): Parameter names to exclude.
- **capture_inputs** (bool): Capture inputs. Default: True.
- **runtime** (TALRuntime, optional): Explicit runtime.

### Basic Usage

```python
from tracecraft import trace_llm
import openai

@trace_llm(
    name="chat_completion",
    model="gpt-4o-mini",
    provider="openai"
)
async def chat(prompt: str) -> str:
    """Call OpenAI GPT-4."""
    response = await openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content
```

### Different Providers

```python
# OpenAI
@trace_llm(name="gpt4", model="gpt-4", provider="openai")
async def call_gpt4(prompt: str) -> str:
    ...

# Anthropic
@trace_llm(name="claude", model="claude-3-opus", provider="anthropic")
async def call_claude(prompt: str) -> str:
    ...

# Local model
@trace_llm(name="llama", model="llama-2-7b", provider="ollama")
async def call_llama(prompt: str) -> str:
    ...
```

### With System Messages

```python
@trace_llm(model="gpt-4", provider="openai")
async def chat_with_system(
    system: str,
    user: str
) -> str:
    """Chat with system message."""
    response = await openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]
    )
    return response.choices[0].message.content
```

### Streaming Responses

```python
@trace_llm(model="gpt-4", provider="openai")
async def stream_chat(prompt: str) -> str:
    """Stream LLM response."""
    full_response = ""
    stream = await openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            full_response += chunk.choices[0].delta.content
    return full_response
```

## @trace_retrieval

Use for retrieval operations like vector search, RAG, or database queries.

### Signature

```python
def trace_retrieval(
    name: str | None = None,
    exclude_inputs: list[str] | None = None,
    capture_inputs: bool = True,
    runtime: TALRuntime | None = None,
) -> Callable
```

### Parameters

Same as `@trace_agent`.

### Vector Search

```python
from tracecraft import trace_retrieval

@trace_retrieval(name="vector_search")
async def vector_search(
    query: str,
    top_k: int = 5
) -> list[dict]:
    """Search vector database."""
    embedding = await embed(query)
    results = await vector_db.search(
        embedding,
        limit=top_k
    )
    return results
```

### Database Query

```python
@trace_retrieval(name="db_lookup")
async def lookup_customer(customer_id: str) -> dict:
    """Look up customer in database."""
    async with db.connection() as conn:
        result = await conn.fetchone(
            "SELECT * FROM customers WHERE id = ?",
            customer_id
        )
        return result
```

### RAG Retrieval

```python
@trace_retrieval(name="rag_retrieval")
async def retrieve_context(
    query: str,
    top_k: int = 3
) -> list[str]:
    """Retrieve relevant documents for RAG."""
    # Get embeddings
    query_embedding = await embed(query)

    # Search vector store
    results = await vector_store.similarity_search(
        query_embedding,
        k=top_k
    )

    # Extract text
    documents = [r.page_content for r in results]
    return documents
```

## step() Context Manager

For fine-grained manual instrumentation, use the `step()` context manager.

### Signature

```python
@contextmanager
def step(
    name: str,
    type: StepType = StepType.WORKFLOW,
    inputs: dict[str, Any] | None = None,
    model_name: str | None = None,
    model_provider: str | None = None,
) -> Generator[Step, None, None]
```

### Parameters

- **name** (str): Step name.
- **type** (StepType): Step type. Default: `WORKFLOW`.
- **inputs** (dict, optional): Input data.
- **model_name** (str, optional): Model name for LLM steps.
- **model_provider** (str, optional): Provider for LLM steps.

### Basic Usage

```python
from tracecraft import step
from tracecraft.core.models import StepType

async def process_data(data: list):
    # Preprocessing step
    with step("preprocessing", type=StepType.WORKFLOW) as s:
        cleaned = clean_data(data)
        s.attributes["rows_cleaned"] = len(cleaned)
        s.outputs["cleaned_data"] = cleaned

    # Processing step
    with step("processing", type=StepType.WORKFLOW) as s:
        result = await process(cleaned)
        s.outputs["result"] = result

    return result
```

### Adding Attributes

```python
with step("api_call", type=StepType.TOOL) as s:
    response = await make_api_call()
    s.attributes["status_code"] = response.status_code
    s.attributes["response_time_ms"] = response.elapsed.total_seconds() * 1000
    s.outputs["data"] = response.json()
```

### Manual LLM Tracing

```python
with step(
    name="gpt4_call",
    type=StepType.LLM,
    model_name="gpt-4",
    model_provider="openai"
) as s:
    s.inputs["prompt"] = prompt
    response = await openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    s.outputs["completion"] = response.choices[0].message.content
    s.attributes["tokens_used"] = response.usage.total_tokens
```

### Error Handling

```python
with step("risky_operation") as s:
    try:
        result = perform_risky_operation()
        s.outputs["result"] = result
    except Exception as e:
        s.attributes["error"] = str(e)
        s.attributes["error_type"] = type(e).__name__
        raise
```

## Common Patterns

### Nested Decorators

```python
@trace_agent(name="coordinator")
async def coordinator(task: str):
    """Coordinates multiple tools."""
    # Tool calls are nested under agent
    data = await fetch_data(task)
    result = await process_data(data)
    return result

@trace_tool(name="fetch_data")
async def fetch_data(task: str):
    ...

@trace_tool(name="process_data")
async def process_data(data):
    ...
```

### RAG Pipeline

```python
@trace_agent(name="rag_agent")
async def rag_agent(query: str) -> str:
    """Complete RAG pipeline."""
    # Retrieval step
    docs = await retrieve_docs(query)

    # LLM step
    response = await generate(query, docs)

    return response

@trace_retrieval(name="retrieve_docs")
async def retrieve_docs(query: str) -> list[str]:
    ...

@trace_llm(model="gpt-4", provider="openai")
async def generate(query: str, context: list[str]) -> str:
    ...
```

### Multi-Agent System

```python
@trace_agent(name="orchestrator")
async def orchestrator(task: str):
    """Orchestrates multiple specialized agents."""
    results = await asyncio.gather(
        research_agent(task),
        analysis_agent(task),
        synthesis_agent(task),
    )
    return combine(results)

@trace_agent(name="research")
async def research_agent(task: str):
    ...

@trace_agent(name="analysis")
async def analysis_agent(task: str):
    ...

@trace_agent(name="synthesis")
async def synthesis_agent(task: str):
    ...
```

### Disabling Input Capture

For large inputs, disable capture:

```python
@trace_agent(name="document_processor", capture_inputs=False)
async def process_large_document(document: str) -> str:
    """Process large document without logging it."""
    return await process(document)
```

## Best Practices

### 1. Choose the Right Decorator

Match decorator to operation type:

```python
# Agent orchestration
@trace_agent(name="coordinator")

# Utility functions
@trace_tool(name="calculator")

# LLM calls
@trace_llm(model="gpt-4")

# Retrieval operations
@trace_retrieval(name="search")
```

### 2. Use Descriptive Names

```python
# Good
@trace_agent(name="customer_support_coordinator")
@trace_tool(name="stripe_payment_processor")

# Not good
@trace_agent(name="agent1")
@trace_tool(name="tool")
```

### 3. Exclude Sensitive Data

```python
@trace_agent(
    name="auth_handler",
    exclude_inputs=["password", "api_key", "secret"]
)
```

### 4. Add Model Information

```python
@trace_llm(
    name="classification",
    model="gpt-4o-mini",  # Specific model
    provider="openai"     # Provider
)
```

### 5. Document Your Functions

```python
@trace_agent(name="agent")
async def agent(query: str) -> str:
    """
    Process user query and return response.

    Args:
        query: User's natural language query

    Returns:
        Generated response
    """
    ...
```

## Next Steps

- [Configuration](configuration.md) - Configure TraceCraft behavior
- [Exporters](exporters.md) - Send traces to different backends
- [Processors](processors.md) - Process and transform traces
- [API Reference](../api/decorators.md) - Complete decorator API
