# TraceCraft TAL

**Vendor-neutral LLM observability SDK** - Instrument once, observe anywhere.

TraceCraft is the "LiteLLM for Observability" - a portable Python instrumentation SDK that lets you capture consistent agent/LLM trace semantics and route them to any backend (Langfuse, Datadog, Phoenix, or any OTLP-compatible system).

## Features

- **Local-First DX**: Beautiful console output + HTML reports without any backend setup
- **Built on OTel, Not Replacing It**: Higher-level abstractions on a proven foundation
- **Dual-Dialect Schema**: Supports both OTel GenAI and OpenInference conventions
- **Governance Built-In**: PII redaction + client-side sampling in the SDK
- **Framework Agnostic**: Works with LangChain, LlamaIndex, PydanticAI, or custom code

## Installation

```bash
pip install tracecraft
```

Or with uv:

```bash
uv add tracecraft
```

## Quick Start

```python
import tracecraft
from tracecraft import trace_agent, trace_tool

# Initialize with defaults (console + JSONL output)
tracecraft.init()

@trace_agent(name="research_agent")
async def research(query: str) -> str:
    results = await search(query)
    return synthesize(results)

@trace_tool(name="web_search")
def search(query: str) -> list[str]:
    return ["result1", "result2"]
```

## Documentation

See [Documentation](https://tracecraft.dev) for full details.

## License

Apache-2.0
