# Quick Start

This guide will get you up and running with TraceCraft in 5 minutes.

## Prerequisites

- Python 3.11 or later
- TraceCraft installed (`pip install tracecraft`)

## Step 1: Initialize TraceCraft

The simplest way to start using TraceCraft is with the default configuration:

```python
import tracecraft

# Initialize with defaults (console + JSONL output)
tracecraft.init()
```

This sets up:

- Console output with Rich formatting
- JSONL file output to `traces/tracecraft.jsonl`
- PII redaction enabled
- 100% sampling (all traces captured)

## Step 2: Instrument Your Code

TraceCraft provides decorators for different types of operations:

```python
from tracecraft import trace_agent, trace_tool, trace_llm

@trace_agent(name="research_assistant")
async def research_assistant(query: str) -> str:
    """Main agent that coordinates research tasks."""
    # Search for information
    results = await search_web(query)

    # Generate response using LLM
    response = await generate_summary(results)

    return response

@trace_tool(name="web_search")
async def search_web(query: str) -> list[str]:
    """Search tool that finds relevant information."""
    # Your search implementation
    return ["result1", "result2", "result3"]

@trace_llm(name="summarizer", model="gpt-4", provider="openai")
async def generate_summary(results: list[str]) -> str:
    """LLM call to generate summary."""
    # Your LLM call implementation
    return f"Summary of {len(results)} results"
```

## Step 3: Run Your Application

```python
import asyncio

async def main():
    # This will be automatically traced
    response = await research_assistant("What is TraceCraft?")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
```

## Step 4: View the Traces

TraceCraft automatically outputs traces in two ways:

### Console Output

You'll see beautiful formatted output in your terminal:

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Agent Run: research_assistant                ┃
┃ Duration: 1.23s                              ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

  └─ research_assistant (1.23s)
      ├─ web_search (0.15s)
      │   Output: ["result1", "result2", "result3"]
      └─ summarizer [gpt-4] (1.05s)
          Output: "Summary of 3 results"
```

### JSONL Files

Traces are saved to `traces/tracecraft.jsonl` for later analysis:

```json
{
  "trace_id": "abc123...",
  "span_id": "def456...",
  "name": "research_assistant",
  "start_time": "2024-01-15T10:30:00Z",
  "duration_ms": 1230,
  "attributes": {
    "step.type": "agent",
    "step.name": "research_assistant"
  }
}
```

## Step 5: Explore with Terminal UI (Optional)

If you installed the TUI extra:

```bash
pip install "tracecraft[tui]"
```

You can explore traces interactively:

```bash
tracecraft tui traces/tracecraft.jsonl
```

Use keyboard shortcuts to:

- `↑↓`: Navigate traces
- `Enter`: Expand/collapse details
- `/`: Search traces
- `q`: Quit

## Complete Example

Here's a complete working example:

```python
import asyncio
import tracecraft
from tracecraft import trace_agent, trace_tool, trace_llm

# Initialize TraceCraft
tracecraft.init(
    console=True,
    jsonl=True,
)

@trace_agent(name="research_assistant")
async def research_assistant(query: str) -> str:
    """Main research agent."""
    results = await search_web(query)
    summary = await generate_summary(results, query)
    return summary

@trace_tool(name="web_search")
async def search_web(query: str) -> list[str]:
    """Mock web search."""
    # Simulate search delay
    await asyncio.sleep(0.1)
    return [
        "TraceCraft is a vendor-neutral LLM observability SDK",
        "It supports multiple frameworks like LangChain and LlamaIndex",
        "Built on OpenTelemetry standards",
    ]

@trace_llm(name="summarizer", model="gpt-4o-mini", provider="openai")
async def generate_summary(results: list[str], query: str) -> str:
    """Mock LLM call for summarization."""
    # Simulate LLM latency
    await asyncio.sleep(0.5)
    summary = f"Based on {len(results)} sources about '{query}': " + \
              " ".join(results)
    return summary

async def main():
    print("Starting research assistant...")
    response = await research_assistant("What is TraceCraft?")
    print(f"\nResponse: {response}\n")

if __name__ == "__main__":
    asyncio.run(main())
```

## Framework Integration Examples

### With LangChain

```python
import tracecraft
from tracecraft.adapters.langchain import TraceCraftCallbackHandler
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# Initialize TraceCraft
tracecraft.init()

# Create LangChain components
llm = ChatOpenAI(model="gpt-4o-mini")
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    ("user", "{input}")
])
chain = prompt | llm

# Use TraceCraft callback handler
handler = TraceCraftCallbackHandler()
response = chain.invoke(
    {"input": "Hello!"},
    config={"callbacks": [handler]}
)
```

### With LlamaIndex

```python
import tracecraft
from tracecraft.adapters.llamaindex import TraceCraftSpanHandler
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader

# Initialize TraceCraft
tracecraft.init()

# Set global handler
import llama_index.core
llama_index.core.global_handler = TraceCraftSpanHandler()

# Use LlamaIndex normally - tracing is automatic
documents = SimpleDirectoryReader("data").load_data()
index = VectorStoreIndex.from_documents(documents)
query_engine = index.as_query_engine()
response = query_engine.query("What is TraceCraft?")
```

## Configuration Options

Customize TraceCraft initialization:

```python
from tracecraft import TraceCraftConfig

# Use init() for common settings
tracecraft.init(
    console=True,
    jsonl=True,
    jsonl_path="./traces/",
    redaction_enabled=True,
    sampling_rate=0.1,  # Sample 10% of traces
)

# Or use TraceCraftConfig for full control
config = TraceCraftConfig(
    service_name="my-app",
    tags=["version:1.0.0", "team:ai"],
)
tracecraft.init(config=config)
```

## Next Steps

Now that you have TraceCraft running, explore:

<div class="grid cards" markdown>

- :material-book-open:{ .lg .middle } __User Guide__

    Learn about decorators, configuration, and advanced features

    [:octicons-arrow-right-24: User Guide](../user-guide/index.md)

- :material-connection:{ .lg .middle } __Integrations__

    Deep dive into framework integrations

    [:octicons-arrow-right-24: Integrations](../integrations/index.md)

- :material-export:{ .lg .middle } __Exporters__

    Send traces to different backends

    [:octicons-arrow-right-24: Exporters](../user-guide/exporters.md)

- :material-shield-check:{ .lg .middle } __Processors__

    Learn about PII redaction and sampling

    [:octicons-arrow-right-24: Processors](../user-guide/processors.md)

</div>

## Common Patterns

### Context Managers

For more control, use context managers:

```python
from tracecraft import step
from tracecraft.core.models import StepType

async def process_request(request):
    with step("validation", type=StepType.WORKFLOW) as s:
        validated = validate(request)
        s.attributes["valid"] = True

    with step("processing", type=StepType.WORKFLOW) as s:
        result = await process(validated)
        s.outputs["result"] = result

    return result
```

### Multi-Tenant Applications

Use separate runtimes for different tenants:

```python
from tracecraft import TraceCraftRuntime, TraceCraftConfig

# Create tenant-specific runtimes
tenant_a = TraceCraftRuntime(
    config=TraceCraftConfig(service_name="tenant-a")
)
tenant_b = TraceCraftRuntime(
    config=TraceCraftConfig(service_name="tenant-b")
)

# Use with context manager
with tenant_a.trace_context():
    process_tenant_a_request()
```

### Error Handling

TraceCraft automatically captures errors:

```python
@trace_agent(name="agent")
async def agent(input: str) -> str:
    try:
        return await risky_operation(input)
    except Exception as e:
        # Error is automatically captured in the trace
        raise
```

## Troubleshooting

### No Console Output

Ensure console output is enabled:

```python
tracecraft.init(console=True)
```

### JSONL File Not Created

Check the path:

```python
tracecraft.init(jsonl=True, jsonl_path="./my-traces/")
```

The directory will be created if it doesn't exist.

### Traces Not Appearing

Make sure you're calling traced functions within a run context:

```python
runtime = tracecraft.init()

with runtime.run("my_run"):
    # Your traced functions here
    result = my_traced_function()
```

Or use automatic run creation:

```python
@trace_agent(name="agent")
async def agent(input: str):
    # Automatically creates a run
    ...
```

## Questions?

- Check the [User Guide](../user-guide/index.md) for more details
- See [API Reference](../api/index.md) for complete documentation
- Visit [GitHub Discussions](https://github.com/LocalAI/tracecraft/discussions) for help
