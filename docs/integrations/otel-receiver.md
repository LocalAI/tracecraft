# OpenTelemetry Receiver

TraceCraft includes an OTLP receiver that accepts traces from any OpenTelemetry-instrumented application. This enables you to:

- Collect traces from existing OTel-instrumented apps without code changes
- Use industry-standard instrumentation libraries (OpenAI, Anthropic, etc.)
- View traces in TraceCraft's TUI from any OTLP source

## Quick Start

### 1. Start the Receiver

```python
from tracecraft.receiver import OTLPReceiver

receiver = OTLPReceiver(
    storage="sqlite://traces/my_traces.db",
    host="0.0.0.0",
    port=4318,
)
receiver.start()
```

### 2. Configure Your Application

Use `setup_exporter()` to configure OpenTelemetry in 3 lines:

```python
from tracecraft.otel import setup_exporter

tracer = setup_exporter(
    endpoint="http://localhost:4318",
    service_name="my-agent",
    instrument=["openai"],  # Auto-instrument OpenAI SDK
)
```

### 3. Use Your Instrumented SDK

```python
import openai

client = openai.OpenAI()

# Create a parent span for your agent
with tracer.start_as_current_span("MyAgent") as span:
    span.set_attribute("tracecraft.step.type", "AGENT")

    # OpenAI calls are automatically traced as child spans
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello!"}]
    )
```

### 4. View in TUI

```bash
tracecraft ui sqlite://traces/my_traces.db
```

## The `setup_exporter()` API

The `setup_exporter()` function replaces 20+ lines of OpenTelemetry boilerplate with a single call.

### Before (Manual Setup)

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

### After (With TraceCraft)

```python
from tracecraft.otel import setup_exporter

tracer = setup_exporter(
    endpoint="http://localhost:4318",
    service_name="my-agent",
    instrument=["openai"],
)
```

## Configuration Options

### `setup_exporter()` Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `endpoint` | `str` | `http://localhost:4318` | OTLP HTTP endpoint URL |
| `service_name` | `str` | `"tracecraft-agent"` | Service name in traces |
| `service_version` | `str` | `"1.0.0"` | Service version |
| `instrument` | `list[str]` | `None` | SDKs to auto-instrument |
| `batch_export` | `bool` | `True` | Use batch processing |
| `resource_attributes` | `dict` | `None` | Additional attributes |
| `tracer_name` | `str` | `"tracecraft"` | Name for returned tracer |

### Auto-Instrumentation Options

The `instrument` parameter accepts a list of SDK names:

```python
tracer = setup_exporter(
    endpoint="http://localhost:4318",
    service_name="my-agent",
    instrument=[
        "openai",      # OpenAI SDK
        "anthropic",   # Anthropic SDK
        "langchain",   # LangChain
        "llamaindex",  # LlamaIndex
        "cohere",      # Cohere SDK
        "bedrock",     # AWS Bedrock
        "vertexai",    # Google Vertex AI
        "mistral",     # Mistral AI
        "groq",        # Groq
    ],
)
```

!!! note "Required Packages"
    Each SDK requires its corresponding instrumentation package:

    ```bash
    pip install opentelemetry-instrumentation-openai
    pip install opentelemetry-instrumentation-anthropic
    # etc.
    ```

    TraceCraft will warn you if a package is missing.

## Environment Variables

`setup_exporter()` respects standard OpenTelemetry environment variables:

| Variable | Fallback | Description |
|----------|----------|-------------|
| `TRACECRAFT_ENDPOINT` | `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP endpoint URL |
| `TRACECRAFT_SERVICE_NAME` | `OTEL_SERVICE_NAME` | Service name |

```bash
# Set environment variables
export TRACECRAFT_ENDPOINT=http://localhost:4318
export TRACECRAFT_SERVICE_NAME=my-agent

# Then use minimal configuration
from tracecraft.otel import setup_exporter
tracer = setup_exporter(instrument=["openai"])
```

## Backend URL Schemes

TraceCraft supports custom URL schemes for different backends:

| Scheme | Description | Example |
|--------|-------------|---------|
| `http://` | Standard OTLP HTTP | `http://localhost:4318` |
| `https://` | Secure OTLP HTTP | `https://otel.example.com` |
| `tracecraft://` | TraceCraft receiver | `tracecraft://localhost:4318` |
| `datadog://` | DataDog OTLP intake | `datadog://intake.datadoghq.com` |
| `azure://` | Azure App Insights | `azure://appinsights.azure.com` |
| `aws://` | AWS X-Ray | `aws://xray.us-east-1.amazonaws.com` |

```python
# Send to TraceCraft
tracer = setup_exporter(endpoint="tracecraft://localhost:4318")

# Send to DataDog (OTLP)
tracer = setup_exporter(endpoint="datadog://intake.datadoghq.com")
```

## Complete Examples

### Simple Chat Agent

```python
#!/usr/bin/env python3
"""Simple chat agent with automatic OpenAI tracing."""

from tracecraft.otel import setup_exporter, flush_traces
import openai

# Configure tracing
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
                {"role": "system", "content": "Be concise."},
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

### Multi-Turn Conversation

```python
"""Multi-turn conversation with trace hierarchy."""

from tracecraft.otel import setup_exporter, flush_traces
import openai

tracer = setup_exporter(
    endpoint="http://localhost:4318",
    service_name="conversation-agent",
    instrument=["openai"],
)

client = openai.OpenAI()

def conversation():
    """Run a multi-turn conversation."""
    with tracer.start_as_current_span("Conversation") as span:
        span.set_attribute("tracecraft.step.type", "AGENT")

        messages = [
            {"role": "system", "content": "You are a helpful math tutor."},
        ]

        # Turn 1
        messages.append({"role": "user", "content": "What is 2 + 2?"})
        response1 = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )
        answer1 = response1.choices[0].message.content
        messages.append({"role": "assistant", "content": answer1})

        # Turn 2
        messages.append({"role": "user", "content": "Multiply that by 3"})
        response2 = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )
        answer2 = response2.choices[0].message.content

        span.set_attribute("output.value", f'{{"final_answer": "{answer2}"}}')
        return answer2

if __name__ == "__main__":
    print(conversation())
    flush_traces()
```

### Tool-Using Agent

```python
"""Agent that uses function calling with traced tool execution."""

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
    """Simulate getting weather data."""
    # Create a child span for the tool execution
    with tracer.start_as_current_span("get_weather") as span:
        span.set_attribute("tracecraft.step.type", "TOOL")
        span.set_attribute("tool.name", "get_weather")
        span.set_attribute("tool.parameters", json.dumps({"location": location}))

        result = {"temperature": 22, "conditions": "Sunny", "location": location}
        span.set_attribute("output.value", json.dumps(result))
        return result

def weather_agent(query: str) -> str:
    """Answer weather questions using tools."""
    with tracer.start_as_current_span("WeatherAgent") as span:
        span.set_attribute("tracecraft.step.type", "AGENT")
        span.set_attribute("input.value", f'{{"query": "{query}"}}')

        tools = [{
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
        }]

        # First call - model may request tool
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": query}],
            tools=tools,
        )

        message = response.choices[0].message
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            args = json.loads(tool_call.function.arguments)

            # Execute tool
            result = get_weather(args["location"])

            # Second call with tool result
            response2 = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "user", "content": query},
                    message,
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result),
                    },
                ],
            )
            answer = response2.choices[0].message.content
        else:
            answer = message.content

        span.set_attribute("output.value", f'{{"answer": "{answer}"}}')
        return answer or ""

if __name__ == "__main__":
    print(weather_agent("What's the weather in Tokyo?"))
    flush_traces()
```

## Utility Functions

### `flush_traces()`

Force flush all pending traces before application shutdown:

```python
from tracecraft.otel import flush_traces

# Before exiting
flush_traces(timeout_millis=5000)
```

### `shutdown()`

Clean up the TracerProvider:

```python
from tracecraft.otel import shutdown

# At application shutdown
shutdown()
```

### `get_tracer()`

Get a tracer after setup:

```python
from tracecraft.otel import setup_exporter, get_tracer

setup_exporter(service_name="my-app")

# Later, in another module
tracer = get_tracer("my-module")
```

## API Reference

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

## Troubleshooting

### Traces Not Appearing

1. **Check receiver is running**: Verify the receiver is healthy:

   ```bash
   curl http://localhost:4318/health
   ```

2. **Flush before exit**: Ensure you call `flush_traces()` before your application exits.

3. **Check endpoint URL**: Verify the endpoint matches your receiver configuration.

### Empty Input/Output in TUI

Ensure you set TraceCraft-specific attributes on parent spans:

```python
with tracer.start_as_current_span("MyAgent") as span:
    span.set_attribute("tracecraft.step.type", "AGENT")
    span.set_attribute("input.value", '{"query": "..."}')
    # ... do work ...
    span.set_attribute("output.value", '{"result": "..."}')
```

### Missing Instrumentation

If auto-instrumentation isn't working:

1. **Install the package**:

   ```bash
   pip install opentelemetry-instrumentation-openai
   ```

2. **Instrument before importing SDK**:

   ```python
   from tracecraft.otel import setup_exporter

   # Setup FIRST
   tracer = setup_exporter(instrument=["openai"])

   # Then import
   import openai
   ```

## Next Steps

- [Terminal UI](../user-guide/tui.md)
- [Auto-Instrumentation](auto-instrumentation.md)
- [Exporters](../user-guide/exporters.md)
