# 07 - Distributed Tracing

> **Status: Coming Soon** - This section is planned but examples are not yet implemented.
> See [03-exporters/02_otlp_jaeger.py](../03-exporters/02_otlp_jaeger.py) for OTLP export basics.

Trace requests across multiple services in distributed systems.

## Overview

This section covers:

- **W3C Trace Context** - Standard propagation format
- **Microservices** - Multi-service tracing example
- **Context Propagation** - Handling async operations

## Examples

| # | Example | Description |
|---|---------|-------------|
| 1 | `01_w3c_propagation.py` | W3C trace context headers |
| 2 | `02_microservices/` | Complete multi-service example |
| 3 | `03_context_propagation.py` | asyncio.gather, thread pools |

## W3C Trace Context

Inject and extract trace context using the W3C standard:

```python
from agenttrace.propagation import W3CTraceContextPropagator

propagator = W3CTraceContextPropagator()

# Inject into outgoing request
headers = {}
propagator.inject(headers, run)
# headers = {"traceparent": "00-abc123...-def456...-01"}

# Extract from incoming request
context = propagator.extract(incoming_headers)
# context = TraceContext(trace_id="abc123...", parent_id="def456...")
```

## Microservices Example

The `02_microservices/` directory contains a complete example:

```
02_microservices/
├── docker-compose.yml      # All services + Jaeger
├── gateway/               # FastAPI gateway
│   ├── main.py
│   ├── Dockerfile
│   └── requirements.txt
├── agent_service/         # Agent processing
│   ├── main.py
│   ├── Dockerfile
│   └── requirements.txt
├── retrieval_service/     # Vector search
│   ├── main.py
│   ├── Dockerfile
│   └── requirements.txt
└── README.md
```

### Run the Example

```bash
cd examples/07-distributed/02_microservices
docker compose up -d
```

### Request Flow

```
User Request
    ↓
Gateway (injects traceparent)
    ↓
Agent Service (extracts traceparent, calls retrieval)
    ↓
Retrieval Service (extracts traceparent, returns results)
    ↓
Response (with trace_id for debugging)
```

### View Traces

Open Jaeger at <http://localhost:16686> to see the full distributed trace.

## Context Propagation

Handle context across async boundaries:

```python
from agenttrace.contrib.async_helpers import gather_with_context

# Preserve trace context across concurrent tasks
results = await gather_with_context(
    fetch_data_1(),
    fetch_data_2(),
    fetch_data_3(),
)
# All three tasks share the same trace context
```

### Thread Pool Executor

```python
from agenttrace.contrib.async_helpers import run_in_executor_with_context

# Run in thread pool while preserving context
result = await run_in_executor_with_context(
    executor=thread_pool,
    fn=cpu_intensive_task,
    args=(data,),
)
```

## HTTP Client Integration

Automatically inject trace context:

```python
import httpx
from agenttrace.propagation import inject_trace_headers

async def call_service(url: str, data: dict) -> dict:
    headers = {}
    inject_trace_headers(headers)  # Adds traceparent

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=data, headers=headers)
        return response.json()
```

## FastAPI Integration

Extract trace context in FastAPI:

```python
from fastapi import FastAPI, Request
from agenttrace.propagation import extract_trace_context

app = FastAPI()

@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    context = extract_trace_context(dict(request.headers))

    if context:
        # Continue existing trace
        with runtime.run("request", parent_context=context):
            return await call_next(request)
    else:
        # Start new trace
        with runtime.run("request"):
            return await call_next(request)
```

## Best Practices

1. **Always propagate context** - Even if a service doesn't use AgentTrace
2. **Use standard headers** - `traceparent` and `tracestate`
3. **Include trace ID in responses** - Helps debugging
4. **Set service name** - Each service should have a unique name

## Troubleshooting

### "Traces not connected"

- Verify traceparent header is being passed
- Check that both services use the same trace ID format
- Ensure context is extracted before starting new trace

### "Missing parent spans"

- The parent service may not be exporting to the same backend
- Check service names in Jaeger/Tempo

## Next Steps

- [08-real-world/](../08-real-world/) - Complete applications with distributed tracing
- [03-exporters/](../03-exporters/) - OTLP export configuration
