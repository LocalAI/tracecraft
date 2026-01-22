# 08 - Real-World Applications

> **Status: Coming Soon** - This section is planned but examples are not yet implemented.
> See [09-advanced/05_multi_agent.py](../09-advanced/05_multi_agent.py) for multi-agent patterns.

Complete, production-realistic applications demonstrating AgentTrace integration.

## Overview

Each application is a full implementation you can run, learn from, and adapt:

| Application | Description | Key Features |
|-------------|-------------|--------------|
| [rag_chatbot/](rag_chatbot/) | RAG-based chatbot | Retrieval, generation, guardrails |
| [research_agent/](research_agent/) | Multi-tool research | Planning, tools, synthesis |
| [code_assistant/](code_assistant/) | Code generation | Code tools, execution, testing |
| [customer_support/](customer_support/) | Support bot | Multi-tenant, escalation, memory |

## RAG Chatbot

A complete RAG chatbot with full observability:

```
rag_chatbot/
├── main.py           # FastAPI application
├── retriever.py      # Vector search with @trace_retrieval
├── generator.py      # LLM generation with @trace_llm
├── config.py         # Configuration management
├── requirements.txt
├── docker-compose.yml  # App + Jaeger
└── README.md
```

### Features Demonstrated

- Document ingestion with tracing
- Vector search with `@trace_retrieval`
- LLM generation with `@trace_llm`
- Streaming responses
- Guardrails for output validation
- PII redaction
- Cost tracking
- Quality metrics integration

### Architecture

```
User Query
    ↓
┌─────────────────────────────────┐
│         AgentTrace Run          │
├─────────────────────────────────┤
│  ┌─────────────┐                │
│  │  Retriever  │ @trace_retrieval
│  └─────────────┘                │
│         ↓                       │
│  ┌─────────────┐                │
│  │ Reranker    │ @trace_tool   │
│  └─────────────┘                │
│         ↓                       │
│  ┌─────────────┐                │
│  │ Generator   │ @trace_llm    │
│  └─────────────┘                │
│         ↓                       │
│  ┌─────────────┐                │
│  │ Guardrails  │ @trace_tool   │
│  └─────────────┘                │
└─────────────────────────────────┘
    ↓
Response (with trace_id)
```

## Research Agent

Multi-step research agent with tool use:

```
research_agent/
├── main.py           # Agent orchestration
├── tools.py          # Web search, database, calculator
├── planner.py        # Task decomposition LLM
├── requirements.txt
└── README.md
```

### Features Demonstrated

- Multi-step planning
- Multiple tool types
- State management between steps
- Error recovery
- Synthesis from multiple sources

## Code Assistant

Code generation with execution and testing:

```
code_assistant/
├── main.py           # Main agent loop
├── code_tools.py     # Code search, file ops, execution
├── requirements.txt
└── README.md
```

### Features Demonstrated

- Code search and reading
- Code generation LLM
- Sandboxed code execution
- Test running and iteration
- Error analysis and fixing

## Customer Support

Production-grade support bot:

```
customer_support/
├── main.py           # FastAPI application
├── guardrails.py     # Content moderation
├── memory.py         # Conversation state
├── requirements.txt
└── README.md
```

### Features Demonstrated

- Intent classification
- FAQ retrieval
- Escalation logic with alerting
- **PII redaction** (live demo)
- Multi-tenant isolation
- Conversation memory
- Guardrails for harmful content
- Slack alerting on escalations

## Running the Applications

Each application includes:

1. `requirements.txt` - Dependencies
2. `README.md` - Setup and usage instructions
3. `docker-compose.yml` - Container setup (where applicable)

### Example: RAG Chatbot

```bash
cd examples/08-real-world/rag_chatbot

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY=sk-...

# Start the application
python main.py

# View traces
open http://localhost:16686  # Jaeger UI
```

## Common Patterns

### 1. Trace ID in Responses

All applications return trace IDs for debugging:

```json
{"answer": "...", "trace_id": "abc123..."}
```

### 2. Error Handling

Errors are captured in traces:

```python
@trace_agent(name="main_agent")
async def process(request):
    try:
        return await do_work(request)
    except Exception as e:
        # Error is automatically captured
        raise
```

### 3. Multi-Tenant Isolation

```python
with runtime.run(f"tenant_{tenant_id}"):
    # All traces tagged with tenant
    pass
```

### 4. Health Checks

```python
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "trace_exporter": runtime.exporter_healthy(),
    }
```

## Customization

Use these applications as starting points:

1. Replace mock components with real implementations
2. Add your specific tools and prompts
3. Adjust quality thresholds and alerting rules
4. Configure for your infrastructure

## Next Steps

- [09-advanced/](../09-advanced/) - Advanced patterns and edge cases
- [04-production/](../04-production/) - Production deployment patterns
