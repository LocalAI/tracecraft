# OTLP Receiver Examples

Receive live traces from any OpenTelemetry-instrumented application.

## Quick Start

### Option 1: Using the CLI (Recommended)

```bash
# Start receiver with TUI in one command
tracecraft serve --tui

# Or just the receiver (headless)
tracecraft receive
```

### Option 2: Using the Examples

**Terminal 1 - Start the receiver:**

```bash
uv run python examples/06-receiver/01_receiver_demo.py
```

**Terminal 2 - Send traces:**

```bash
# Simple HTTP sender (no extra deps)
uv run python examples/06-receiver/02_send_traces.py

# Or using OpenTelemetry SDK
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
uv run python examples/06-receiver/03_otel_sdk_example.py
```

**View the traces:**

```bash
tracecraft ui sqlite://traces/receiver_demo.db
```

## Examples

| File | Description |
|------|-------------|
| `01_receiver_demo.py` | Start OTLP receiver server |
| `02_send_traces.py` | Send simulated traces (various patterns, no API keys) |
| `03_otel_sdk_example.py` | Send traces using standard OpenTelemetry SDK |
| `04_real_openai_traces.py` | **Real OpenAI calls** with OTel instrumentation |
| `05_real_anthropic_traces.py` | **Real Anthropic/Claude calls** with OTel instrumentation |

## Real API Examples

For testing with actual LLM calls:

```bash
# OpenAI (requires OPENAI_API_KEY)
pip install openai opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http opentelemetry-instrumentation-openai
export OPENAI_API_KEY="your-key-here"
uv run python examples/06-receiver/04_real_openai_traces.py

# Anthropic (requires ANTHROPIC_API_KEY)
pip install anthropic opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
export ANTHROPIC_API_KEY="your-key-here"
uv run python examples/06-receiver/05_real_anthropic_traces.py
```

## Integration with Real Applications

Configure your OpenTelemetry-instrumented application to send traces to TraceCraft:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_EXPORTER_OTLP_PROTOCOL=http/json

# Run your application
python my_agent.py
```

## Supported Schema Dialects

The receiver auto-detects and supports both:

- **OTel GenAI** (`gen_ai.*` attributes)
- **OpenInference** (`llm.*`, `tool.*` attributes)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/traces` | POST | Receive OTLP traces (JSON or protobuf) |
| `/health` | GET | Health check |
