# OpenTelemetry Integration

TraceCraft provides seamless OpenTelemetry (OTel) integration, allowing you to collect traces from any OTel-instrumented application and view them in TraceCraft's powerful TUI.

!!! tip "When to Use This"
    Use the OTel integration when you want to:

    - **Receive traces** from existing OTel-instrumented applications
    - **Use standard instrumentation** libraries (OpenAI, Anthropic, LangChain, etc.)
    - **Send to multiple backends** simultaneously (TraceCraft + DataDog, etc.)
    - **Integrate with existing OTel infrastructure** (collectors, pipelines)

    For simpler use cases, consider [Auto-Instrumentation](auto-instrumentation.md) or [TraceCraft decorators](../user-guide/decorators.md).

---

## Installation

=== "Basic (Receiver Only)"

    ```bash
    pip install "tracecraft[receiver]"
    ```

=== "With OpenAI Instrumentation"

    ```bash
    pip install "tracecraft[receiver]" opentelemetry-instrumentation-openai
    ```

=== "With Multiple SDKs"

    ```bash
    pip install "tracecraft[receiver]" \
        opentelemetry-instrumentation-openai \
        opentelemetry-instrumentation-anthropic
    ```

=== "Full Installation"

    ```bash
    pip install "tracecraft[all]"
    ```

---

## Quick Start

Get up and running in 4 simple steps:

### Step 1: Start the Receiver

=== "Python"

    ```python
    from pathlib import Path
    from tracecraft.receiver import OTLPReceiverServer
    from tracecraft.storage.sqlite import SQLiteTraceStore

    # Create storage
    storage_path = Path("traces/my_traces.db")
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    store = SQLiteTraceStore(storage_path)

    # Create and start receiver
    server = OTLPReceiverServer(
        store=store,
        host="0.0.0.0",
        port=4318,
    )
    server.run()  # Blocking - or use server.start_background() for non-blocking
    ```

=== "CLI"

    ```bash
    # Coming soon
    tracecraft receiver --storage traces/my_traces.db --port 4318
    ```

### Step 2: Configure Your Application

Use `setup_exporter()` to configure OpenTelemetry in just 3 lines:

```python
from tracecraft.otel import setup_exporter

tracer = setup_exporter(
    endpoint="http://localhost:4318",
    service_name="my-agent",
    instrument=["openai"],  # Auto-instrument OpenAI SDK
)
```

### Step 3: Instrument Your Code

```python
import openai

client = openai.OpenAI()

# Create a parent span for your agent
with tracer.start_as_current_span("MyAgent") as span:
    span.set_attribute("tracecraft.step.type", "AGENT")
    span.set_attribute("input.value", '{"query": "Hello!"}')

    # OpenAI calls are automatically traced as child spans
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello!"}]
    )

    span.set_attribute("output.value", f'{{"response": "{response.choices[0].message.content}"}}')
```

### Step 4: View in TUI

```bash
tracecraft ui sqlite://traces/my_traces.db
```

!!! success "That's it!"
    Your traces are now being collected and can be viewed in TraceCraft's terminal UI.

---

## The `setup_exporter()` API

The `setup_exporter()` function replaces 20+ lines of OpenTelemetry boilerplate with a single, intuitive call.

### Before vs After

=== "Before (Manual Setup) - 15 lines"

    ```python
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.openai import OpenAIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create({
        "service.name": "my-agent",
        "service.version": "1.0.0",
    })
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint="http://localhost:4318/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    OpenAIInstrumentor().instrument()
    tracer = trace.get_tracer("my-agent")
    ```

=== "After (With TraceCraft) - 3 lines"

    ```python
    from tracecraft.otel import setup_exporter

    tracer = setup_exporter(
        endpoint="http://localhost:4318",
        service_name="my-agent",
        instrument=["openai"],
    )
    ```

---

## Configuration Reference

### `setup_exporter()` Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `endpoint` | `str \| None` | `http://localhost:4318` | OTLP HTTP endpoint URL. Supports custom schemes. |
| `service_name` | `str \| None` | `"tracecraft-agent"` | Service name shown in traces. |
| `service_version` | `str` | `"1.0.0"` | Service version for trace metadata. |
| `instrument` | `list[str] \| None` | `None` | List of SDKs to auto-instrument. |
| `batch_export` | `bool` | `True` | Use batch processing (recommended for production). |
| `resource_attributes` | `dict[str, str] \| None` | `None` | Additional OTel resource attributes. |
| `tracer_name` | `str` | `"tracecraft"` | Name for the returned tracer instance. |

### Supported Auto-Instrumentation SDKs

The `instrument` parameter accepts any combination of these SDK names:

| SDK Name | Package Required | What Gets Traced |
|----------|------------------|------------------|
| `"openai"` | `opentelemetry-instrumentation-openai` | Chat completions, embeddings, streaming, function calls |
| `"anthropic"` | `opentelemetry-instrumentation-anthropic` | Messages, streaming, tool use |
| `"langchain"` | `opentelemetry-instrumentation-langchain` | Chains, agents, tools, retrievers |
| `"llamaindex"` | `opentelemetry-instrumentation-llamaindex` | Query engines, indices, retrievers |
| `"cohere"` | `opentelemetry-instrumentation-cohere` | Generate, embed, rerank |
| `"bedrock"` | `opentelemetry-instrumentation-bedrock` | AWS Bedrock model invocations |
| `"vertexai"` | `opentelemetry-instrumentation-vertexai` | Google Vertex AI predictions |
| `"mistral"` | `opentelemetry-instrumentation-mistralai` | Mistral chat completions |
| `"groq"` | `opentelemetry-instrumentation-groq` | Groq chat completions |

!!! warning "Install Instrumentation Packages"
    Each SDK requires its corresponding instrumentation package to be installed:

    ```bash
    pip install opentelemetry-instrumentation-openai
    pip install opentelemetry-instrumentation-anthropic
    ```

    TraceCraft will display a warning if a requested package is missing.

---

## Environment Variables

`setup_exporter()` respects standard OpenTelemetry environment variables, making it easy to configure in different environments:

| TraceCraft Variable | OTel Fallback | Description | Example |
|---------------------|---------------|-------------|---------|
| `TRACECRAFT_ENDPOINT` | `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP endpoint URL | `http://localhost:4318` |
| `TRACECRAFT_SERVICE_NAME` | `OTEL_SERVICE_NAME` | Service name | `my-agent` |

### Example: Environment-Based Configuration

=== "Development (.env)"

    ```bash
    TRACECRAFT_ENDPOINT=http://localhost:4318
    TRACECRAFT_SERVICE_NAME=my-agent-dev
    ```

=== "Production (.env)"

    ```bash
    TRACECRAFT_ENDPOINT=https://otel.mycompany.com:4318
    TRACECRAFT_SERVICE_NAME=my-agent-prod
    ```

=== "Python Code"

    ```python
    from tracecraft.otel import setup_exporter

    # No endpoint/service_name needed - reads from environment
    tracer = setup_exporter(instrument=["openai", "anthropic"])
    ```

---

## Backend URL Schemes

TraceCraft supports custom URL schemes for different observability backends:

| Scheme | Converts To | Default Port | Use Case |
|--------|-------------|--------------|----------|
| `http://` | `http://` | 4318 | Local development, internal collectors |
| `https://` | `https://` | 4318 | Production OTLP endpoints |
| `tracecraft://` | `http://` | 4318 | TraceCraft receiver (alias for http) |
| `datadog://` | `https://` | 4318 | DataDog OTLP intake |
| `azure://` | `https://` | 443 | Azure Application Insights |
| `aws://` | `https://` | 443 | AWS X-Ray |
| `xray://` | `https://` | 443 | AWS X-Ray (alias) |

### Examples

=== "Local TraceCraft"

    ```python
    tracer = setup_exporter(endpoint="tracecraft://localhost:4318")
    ```

=== "DataDog"

    ```python
    tracer = setup_exporter(endpoint="datadog://intake.datadoghq.com")
    ```

=== "Azure"

    ```python
    tracer = setup_exporter(endpoint="azure://dc.applicationinsights.azure.com")
    ```

=== "AWS X-Ray"

    ```python
    tracer = setup_exporter(endpoint="aws://xray.us-east-1.amazonaws.com")
    ```

---

## TraceCraft Span Attributes

To ensure your traces display correctly in TraceCraft's TUI, set these attributes on your spans:

### Step Types

| Attribute Value | Description | Icon in TUI |
|-----------------|-------------|-------------|
| `AGENT` | Top-level agent or workflow | 🤖 |
| `LLM` | Language model call | 💬 |
| `TOOL` | Tool/function execution | 🔧 |
| `RETRIEVAL` | Document/data retrieval | 📚 |
| `MEMORY` | Memory read/write operations | 🧠 |
| `GUARDRAIL` | Safety/validation checks | 🛡️ |
| `EVALUATION` | LLM output evaluation | 📊 |
| `WORKFLOW` | Sub-workflow or chain | ⚙️ |
| `ERROR` | Error handling | ❌ |

### Essential Attributes

```python
with tracer.start_as_current_span("MyOperation") as span:
    # Required: Set the step type
    span.set_attribute("tracecraft.step.type", "AGENT")

    # Recommended: Set input (JSON string)
    span.set_attribute("input.value", '{"query": "What is AI?"}')

    # ... perform operation ...

    # Recommended: Set output (JSON string)
    span.set_attribute("output.value", '{"answer": "AI is..."}')
```

!!! tip "JSON Format"
    Use JSON strings for `input.value` and `output.value` to enable structured display in the TUI.

---

## Complete Examples

### Example 1: Simple Chat Agent

A basic chat agent with automatic OpenAI tracing.

```python
#!/usr/bin/env python3
"""Simple chat agent with automatic OpenAI tracing."""

from tracecraft.otel import setup_exporter, flush_traces
import openai

# Configure tracing - instrument OpenAI automatically
tracer = setup_exporter(
    endpoint="http://localhost:4318",
    service_name="chat-agent",
    instrument=["openai"],
)

client = openai.OpenAI()


def chat(message: str) -> str:
    """Send a message and get a response."""
    with tracer.start_as_current_span("Chat") as span:
        span.set_attribute("tracecraft.step.type", "AGENT")
        span.set_attribute("input.value", f'{{"message": "{message}"}}')

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Be concise and helpful."},
                {"role": "user", "content": message},
            ],
        )

        result = response.choices[0].message.content or ""
        span.set_attribute("output.value", f'{{"response": "{result}"}}')
        return result


if __name__ == "__main__":
    print(chat("What is the capital of France?"))
    flush_traces()  # Ensure traces are sent before exit
```

### Example 2: Anthropic Agent

Using Anthropic's Claude with automatic tracing.

```python
#!/usr/bin/env python3
"""Anthropic Claude agent with automatic tracing."""

from tracecraft.otel import setup_exporter, flush_traces
import anthropic

# Configure tracing - instrument Anthropic automatically
tracer = setup_exporter(
    endpoint="http://localhost:4318",
    service_name="claude-agent",
    instrument=["anthropic"],
)

client = anthropic.Anthropic()


def ask_claude(question: str) -> str:
    """Ask Claude a question."""
    with tracer.start_as_current_span("AskClaude") as span:
        span.set_attribute("tracecraft.step.type", "AGENT")
        span.set_attribute("input.value", f'{{"question": "{question}"}}')

        message = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1024,
            messages=[{"role": "user", "content": question}],
        )

        result = message.content[0].text
        span.set_attribute("output.value", f'{{"answer": "{result}"}}')
        return result


if __name__ == "__main__":
    print(ask_claude("Explain quantum computing in one sentence."))
    flush_traces()
```

### Example 3: Multi-Turn Conversation

Track a multi-turn conversation with proper trace hierarchy.

```python
#!/usr/bin/env python3
"""Multi-turn conversation with trace hierarchy."""

from tracecraft.otel import setup_exporter, flush_traces
import openai

tracer = setup_exporter(
    endpoint="http://localhost:4318",
    service_name="conversation-agent",
    instrument=["openai"],
)

client = openai.OpenAI()


def conversation() -> str:
    """Run a multi-turn conversation."""
    with tracer.start_as_current_span("Conversation") as span:
        span.set_attribute("tracecraft.step.type", "AGENT")
        span.set_attribute("input.value", '{"task": "Math tutoring session"}')

        messages = [
            {"role": "system", "content": "You are a helpful math tutor. Be brief."},
        ]

        # Turn 1
        messages.append({"role": "user", "content": "What is 2 + 2?"})
        response1 = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )
        answer1 = response1.choices[0].message.content
        messages.append({"role": "assistant", "content": answer1})
        print(f"Turn 1: {answer1}")

        # Turn 2
        messages.append({"role": "user", "content": "Multiply that by 3"})
        response2 = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )
        answer2 = response2.choices[0].message.content
        print(f"Turn 2: {answer2}")

        span.set_attribute("output.value", f'{{"final_answer": "{answer2}"}}')
        return answer2


if __name__ == "__main__":
    conversation()
    flush_traces()
```

### Example 4: RAG Pipeline

A retrieval-augmented generation pipeline with traced retrieval and generation.

```python
#!/usr/bin/env python3
"""RAG pipeline with traced retrieval and generation."""

import json
from tracecraft.otel import setup_exporter, flush_traces
import openai

tracer = setup_exporter(
    endpoint="http://localhost:4318",
    service_name="rag-agent",
    instrument=["openai"],
)

client = openai.OpenAI()

# Simulated document store
DOCUMENTS = {
    "doc1": "Python was created by Guido van Rossum in 1991.",
    "doc2": "JavaScript was created by Brendan Eich in 1995.",
    "doc3": "Rust was created by Mozilla and first released in 2010.",
}


def retrieve_documents(query: str) -> list[str]:
    """Simulate document retrieval."""
    with tracer.start_as_current_span("Retrieve") as span:
        span.set_attribute("tracecraft.step.type", "RETRIEVAL")
        span.set_attribute("input.value", f'{{"query": "{query}"}}')

        # Simple keyword matching (in reality, use embeddings)
        results = []
        query_lower = query.lower()
        for doc_id, content in DOCUMENTS.items():
            if any(word in content.lower() for word in query_lower.split()):
                results.append(content)

        span.set_attribute("output.value", json.dumps({"documents": results}))
        return results


def generate_answer(query: str, context: list[str]) -> str:
    """Generate an answer using retrieved context."""
    context_text = "\n".join(context)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": f"Answer based on this context:\n{context_text}",
            },
            {"role": "user", "content": query},
        ],
    )
    return response.choices[0].message.content or ""


def rag_query(query: str) -> str:
    """Execute a RAG query."""
    with tracer.start_as_current_span("RAGPipeline") as span:
        span.set_attribute("tracecraft.step.type", "AGENT")
        span.set_attribute("input.value", f'{{"query": "{query}"}}')

        # Retrieve relevant documents
        documents = retrieve_documents(query)

        if not documents:
            result = "No relevant documents found."
        else:
            # Generate answer from context
            result = generate_answer(query, documents)

        span.set_attribute("output.value", f'{{"answer": "{result}"}}')
        return result


if __name__ == "__main__":
    answer = rag_query("When was Python created?")
    print(f"Answer: {answer}")
    flush_traces()
```

### Example 5: Tool-Using Agent

An agent that uses function calling with properly traced tool execution.

```python
#!/usr/bin/env python3
"""Agent with function calling and traced tool execution."""

import json
from tracecraft.otel import setup_exporter, flush_traces
import openai

tracer = setup_exporter(
    endpoint="http://localhost:4318",
    service_name="tool-agent",
    instrument=["openai"],
)

client = openai.OpenAI()


def get_weather(location: str) -> dict:
    """Get weather for a location (simulated)."""
    with tracer.start_as_current_span("get_weather") as span:
        span.set_attribute("tracecraft.step.type", "TOOL")
        span.set_attribute("tool.name", "get_weather")
        span.set_attribute("tool.parameters", json.dumps({"location": location}))

        # Simulated weather data
        result = {
            "location": location,
            "temperature": 22,
            "conditions": "Sunny",
            "humidity": 45,
        }

        span.set_attribute("output.value", json.dumps(result))
        return result


def get_time(timezone: str) -> dict:
    """Get current time for a timezone (simulated)."""
    with tracer.start_as_current_span("get_time") as span:
        span.set_attribute("tracecraft.step.type", "TOOL")
        span.set_attribute("tool.name", "get_time")
        span.set_attribute("tool.parameters", json.dumps({"timezone": timezone}))

        result = {"timezone": timezone, "time": "14:30", "date": "2024-01-15"}

        span.set_attribute("output.value", json.dumps(result))
        return result


# Tool definitions for OpenAI
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"},
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get current time for a timezone",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {"type": "string", "description": "Timezone name"},
                },
                "required": ["timezone"],
            },
        },
    },
]

# Tool function mapping
TOOL_FUNCTIONS = {
    "get_weather": get_weather,
    "get_time": get_time,
}


def agent(query: str) -> str:
    """Run the tool-using agent."""
    with tracer.start_as_current_span("ToolAgent") as span:
        span.set_attribute("tracecraft.step.type", "AGENT")
        span.set_attribute("input.value", f'{{"query": "{query}"}}')

        messages = [{"role": "user", "content": query}]

        # First call - model may request tools
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOLS,
        )

        message = response.choices[0].message

        # Handle tool calls
        while message.tool_calls:
            messages.append(message)

            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)

                # Execute the tool
                tool_func = TOOL_FUNCTIONS[func_name]
                result = tool_func(**func_args)

                # Add tool result to messages
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result),
                    }
                )

            # Get next response
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=TOOLS,
            )
            message = response.choices[0].message

        answer = message.content or ""
        span.set_attribute("output.value", f'{{"answer": "{answer}"}}')
        return answer


if __name__ == "__main__":
    result = agent("What's the weather in Tokyo and what time is it there?")
    print(f"Result: {result}")
    flush_traces()
```

### Example 6: Async Agent

An async agent using `asyncio` with proper tracing.

```python
#!/usr/bin/env python3
"""Async agent with concurrent operations."""

import asyncio
import json
from tracecraft.otel import setup_exporter, flush_traces
import openai

tracer = setup_exporter(
    endpoint="http://localhost:4318",
    service_name="async-agent",
    instrument=["openai"],
)

client = openai.AsyncOpenAI()


async def analyze_topic(topic: str) -> dict:
    """Analyze a single topic."""
    with tracer.start_as_current_span(f"Analyze_{topic}") as span:
        span.set_attribute("tracecraft.step.type", "LLM")
        span.set_attribute("input.value", f'{{"topic": "{topic}"}}')

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": f"Summarize {topic} in one sentence."}
            ],
        )

        result = response.choices[0].message.content or ""
        span.set_attribute("output.value", f'{{"summary": "{result}"}}')
        return {"topic": topic, "summary": result}


async def research_agent(topics: list[str]) -> list[dict]:
    """Research multiple topics concurrently."""
    with tracer.start_as_current_span("ResearchAgent") as span:
        span.set_attribute("tracecraft.step.type", "AGENT")
        span.set_attribute("input.value", json.dumps({"topics": topics}))

        # Analyze all topics concurrently
        tasks = [analyze_topic(topic) for topic in topics]
        results = await asyncio.gather(*tasks)

        span.set_attribute("output.value", json.dumps({"results": results}))
        return results


async def main():
    topics = ["quantum computing", "machine learning", "blockchain"]
    results = await research_agent(topics)

    for r in results:
        print(f"{r['topic']}: {r['summary']}")

    flush_traces()


if __name__ == "__main__":
    asyncio.run(main())
```

### Example 7: Error Handling

Proper error handling and tracing for failed operations.

```python
#!/usr/bin/env python3
"""Error handling with proper trace attributes."""

import json
import traceback
from tracecraft.otel import setup_exporter, flush_traces
from opentelemetry.trace import Status, StatusCode
import openai

tracer = setup_exporter(
    endpoint="http://localhost:4318",
    service_name="error-handling-agent",
    instrument=["openai"],
)

client = openai.OpenAI()


def risky_operation(should_fail: bool) -> str:
    """An operation that might fail."""
    with tracer.start_as_current_span("RiskyOperation") as span:
        span.set_attribute("tracecraft.step.type", "TOOL")
        span.set_attribute("input.value", json.dumps({"should_fail": should_fail}))

        try:
            if should_fail:
                raise ValueError("Simulated failure!")

            result = "Operation succeeded"
            span.set_attribute("output.value", f'{{"result": "{result}"}}')
            return result

        except Exception as e:
            # Record the error in the span
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.set_attribute("error.type", type(e).__name__)
            span.set_attribute("error.message", str(e))
            span.set_attribute("error.stacktrace", traceback.format_exc())
            span.record_exception(e)
            raise


def robust_agent(query: str) -> str:
    """Agent with error handling."""
    with tracer.start_as_current_span("RobustAgent") as span:
        span.set_attribute("tracecraft.step.type", "AGENT")
        span.set_attribute("input.value", f'{{"query": "{query}"}}')

        try:
            # Try the risky operation
            result = risky_operation(should_fail=True)
            span.set_attribute("output.value", f'{{"result": "{result}"}}')
            return result

        except Exception as e:
            # Handle the error gracefully
            span.set_status(Status(StatusCode.ERROR, str(e)))

            # Fallback response
            fallback = f"Operation failed: {e}. Using fallback."
            span.set_attribute("output.value", f'{{"fallback": "{fallback}"}}')
            return fallback


if __name__ == "__main__":
    result = robust_agent("Do something risky")
    print(f"Result: {result}")
    flush_traces()
```

---

## Utility Functions

### `flush_traces()`

Force flush all pending traces. **Always call before application exit.**

```python
from tracecraft.otel import flush_traces

# Flush with default 30-second timeout
flush_traces()

# Flush with custom timeout (in milliseconds)
success = flush_traces(timeout_millis=5000)
if not success:
    print("Warning: Flush timed out")
```

!!! warning "Don't Forget to Flush"
    If you don't call `flush_traces()` before your application exits, pending traces may be lost.

### `shutdown()`

Clean up the TracerProvider and release resources.

```python
from tracecraft.otel import shutdown

# At application shutdown
shutdown()
```

### `get_tracer()`

Get a tracer after initial setup. Useful for multi-module applications.

```python
# In your main module
from tracecraft.otel import setup_exporter

setup_exporter(service_name="my-app", instrument=["openai"])

# In another module
from tracecraft.otel import get_tracer

tracer = get_tracer("my-module")

with tracer.start_as_current_span("operation"):
    # ...
```

---

## Production Considerations

### Batch Export Settings

By default, `setup_exporter()` uses `BatchSpanProcessor` which batches spans before export. For high-throughput applications:

```python
tracer = setup_exporter(
    endpoint="http://localhost:4318",
    service_name="high-throughput-agent",
    batch_export=True,  # Default, recommended for production
)
```

For debugging or low-latency requirements, use `SimpleSpanProcessor`:

```python
tracer = setup_exporter(
    endpoint="http://localhost:4318",
    service_name="debug-agent",
    batch_export=False,  # Immediate export, useful for debugging
)
```

### Resource Attributes

Add deployment-specific attributes:

```python
tracer = setup_exporter(
    endpoint="http://localhost:4318",
    service_name="my-agent",
    service_version="2.1.0",
    resource_attributes={
        "deployment.environment": "production",
        "service.instance.id": "agent-pod-abc123",
        "cloud.provider": "aws",
        "cloud.region": "us-east-1",
    },
)
```

### Graceful Shutdown

For long-running applications, handle shutdown properly:

```python
import signal
import sys
from tracecraft.otel import setup_exporter, flush_traces, shutdown

tracer = setup_exporter(...)


def graceful_shutdown(signum, frame):
    print("Shutting down...")
    flush_traces(timeout_millis=10000)
    shutdown()
    sys.exit(0)


signal.signal(signal.SIGTERM, graceful_shutdown)
signal.signal(signal.SIGINT, graceful_shutdown)
```

---

## Troubleshooting

### Traces Not Appearing

??? question "Is the receiver running?"
    Verify the receiver is healthy:

    ```bash
    curl http://localhost:4318/health
    # Should return: {"status": "healthy"}
    ```

??? question "Did you flush before exit?"
    Always call `flush_traces()` before your application exits:

    ```python
    from tracecraft.otel import flush_traces

    # Before exiting
    flush_traces()
    ```

??? question "Is the endpoint correct?"
    Verify your endpoint URL matches the receiver configuration:

    ```python
    # Check endpoint
    tracer = setup_exporter(
        endpoint="http://localhost:4318",  # Must match receiver
        # ...
    )
    ```

### Empty Input/Output in TUI

??? question "Are you setting TraceCraft attributes?"
    Ensure you set the required attributes on parent spans:

    ```python
    with tracer.start_as_current_span("MyAgent") as span:
        # Required
        span.set_attribute("tracecraft.step.type", "AGENT")

        # Recommended (use JSON strings)
        span.set_attribute("input.value", '{"query": "..."}')
        span.set_attribute("output.value", '{"result": "..."}')
    ```

### Auto-Instrumentation Not Working

??? question "Did you install the instrumentation package?"
    Each SDK needs its corresponding package:

    ```bash
    pip install opentelemetry-instrumentation-openai
    pip install opentelemetry-instrumentation-anthropic
    ```

??? question "Did you instrument before importing the SDK?"
    The instrumentation must happen before you import the SDK:

    ```python
    # CORRECT ORDER
    from tracecraft.otel import setup_exporter
    tracer = setup_exporter(instrument=["openai"])  # First!

    import openai  # Then import

    # WRONG ORDER
    import openai  # Too early!
    from tracecraft.otel import setup_exporter
    tracer = setup_exporter(instrument=["openai"])  # Won't work
    ```

### Duplicate Spans

??? question "Are you instrumenting multiple times?"
    Avoid calling `setup_exporter()` multiple times:

    ```python
    # Do this once at startup
    tracer = setup_exporter(instrument=["openai"])

    # Don't do this
    tracer1 = setup_exporter(instrument=["openai"])
    tracer2 = setup_exporter(instrument=["openai"])  # Duplicate!
    ```

---

## Advanced Usage

### Dynamic Instrumentation

For advanced scenarios, you can dynamically instrument or uninstrument SDKs:

```python
from tracecraft.otel import instrument_sdk, uninstrument_sdk, get_available_instrumentors

# See what SDKs are available
print(get_available_instrumentors())
# ['openai', 'anthropic', 'langchain', 'llamaindex', ...]

# Instrument a specific SDK
success = instrument_sdk("openai")
if success:
    print("OpenAI instrumented!")

# Later, remove instrumentation (useful for testing)
uninstrument_sdk("openai")
```

### Parsing Backend URLs

Use `parse_endpoint` to understand how URLs are interpreted:

```python
from tracecraft.otel import parse_endpoint

# Parse a TraceCraft URL
config = parse_endpoint("tracecraft://myhost:4318/custom/path")
print(f"Scheme: {config.scheme}")          # tracecraft
print(f"Host: {config.host}")              # myhost
print(f"Port: {config.port}")              # 4318
print(f"Path: {config.path}")              # /custom/path
print(f"Endpoint URL: {config.endpoint_url}")  # http://myhost:4318/custom/path
print(f"Backend Type: {config.backend_type}")  # tracecraft
```

---

## API Reference

### Core Functions

::: tracecraft.otel.setup_exporter
    options:
      show_root_heading: true
      show_source: false

::: tracecraft.otel.flush_traces
    options:
      show_root_heading: true
      show_source: false

::: tracecraft.otel.shutdown
    options:
      show_root_heading: true
      show_source: false

::: tracecraft.otel.get_tracer
    options:
      show_root_heading: true
      show_source: false

### Instrumentation Functions

::: tracecraft.otel.instrument_sdk
    options:
      show_root_heading: true
      show_source: false

::: tracecraft.otel.instrument_sdks
    options:
      show_root_heading: true
      show_source: false

::: tracecraft.otel.uninstrument_sdk
    options:
      show_root_heading: true
      show_source: false

::: tracecraft.otel.get_available_instrumentors
    options:
      show_root_heading: true
      show_source: false

### Configuration Types

::: tracecraft.otel.parse_endpoint
    options:
      show_root_heading: true
      show_source: false

::: tracecraft.otel.get_service_name
    options:
      show_root_heading: true
      show_source: false

::: tracecraft.otel.BackendConfig
    options:
      show_root_heading: true
      show_source: false

---

## Next Steps

<div class="grid cards" markdown>

- :material-console:{ .lg .middle } **Terminal UI**

    ---

    Learn to navigate and analyze traces in the TUI

    [:octicons-arrow-right-24: Terminal UI Guide](../user-guide/tui.md)

- :material-auto-fix:{ .lg .middle } **Auto-Instrumentation**

    ---

    Alternative approach using TraceCraft's native instrumentation

    [:octicons-arrow-right-24: Auto-Instrumentation](auto-instrumentation.md)

- :material-code-tags:{ .lg .middle } **Decorators**

    ---

    Use decorators for manual tracing

    [:octicons-arrow-right-24: Decorators Guide](../user-guide/decorators.md)

- :material-export:{ .lg .middle } **Exporters**

    ---

    Configure different export backends

    [:octicons-arrow-right-24: Exporters Guide](../user-guide/exporters.md)

</div>
