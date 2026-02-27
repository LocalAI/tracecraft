# Configuration

TraceCraft can be configured through code, a config file, or environment variables. This guide covers all available configuration options.

## Configuration Precedence

Configuration is applied in this order (later overrides earlier):

1. Default values
2. Environment variables (`TRACECRAFT_*`)
3. `.tracecraft/config.yaml` (project or home directory)
4. Explicit parameters passed to `tracecraft.init()`

Example:

```bash
# Environment variable sets the service name
export TRACECRAFT_SERVICE_NAME=env-service
```

```python
# Explicit param wins — "code-service" is used, not "env-service"
tracecraft.init(service_name="code-service")
```

---

## Config File

The easiest way to configure TraceCraft for a project is a config file at `.tracecraft/config.yaml` in your project root (or `~/.tracecraft/config.yaml` globally). The file is loaded automatically — no code changes required.

### Minimal Config

```yaml
# .tracecraft/config.yaml
env: development

default:
  service_name: my-agent-service

  storage:
    type: jsonl
    jsonl_path: traces/tracecraft.jsonl

  exporters:
    console: true
    jsonl: true
    # Stream traces live to `tracecraft serve --tui`
    receiver: false
    receiver_endpoint: http://localhost:4318

  instrumentation:
    # true, false, or a list like [openai, anthropic]
    auto_instrument: false
```

### Full Config with Environments

```yaml
# .tracecraft/config.yaml
env: development

default:
  service_name: my-agent-service

  storage:
    type: jsonl
    jsonl_path: traces/tracecraft.jsonl

  exporters:
    console: true
    jsonl: true
    otlp: false
    receiver: false
    receiver_endpoint: http://localhost:4318

  instrumentation:
    auto_instrument: false

  processors:
    redaction_enabled: false
    redaction_mode: mask      # mask, hash, or remove
    sampling_enabled: false
    sampling_rate: 1.0
    enrichment_enabled: true

environments:
  # Development: stream live to TUI receiver
  development:
    storage:
      type: sqlite
      sqlite_path: traces/dev.db
    exporters:
      console: true
      receiver: true            # run: tracecraft serve --tui
      receiver_endpoint: http://localhost:4318
    instrumentation:
      auto_instrument: true     # instrument all available SDKs

  # Staging: SQLite + OTLP, selective auto-instrumentation
  staging:
    storage:
      type: sqlite
      sqlite_path: traces/staging.db
    exporters:
      console: false
      jsonl: true
      otlp: true
      otlp_endpoint: ${OTEL_EXPORTER_OTLP_ENDPOINT}
    instrumentation:
      auto_instrument:
        - openai
        - anthropic
    processors:
      redaction_enabled: true
      redaction_mode: mask

  # Production: OTLP only, no local storage, sampled
  production:
    storage:
      type: none
    exporters:
      console: false
      jsonl: false
      otlp: true
      otlp_endpoint: ${OTEL_EXPORTER_OTLP_ENDPOINT}
      otlp_headers:
        Authorization: Bearer ${OTEL_AUTH_TOKEN}
    instrumentation:
      auto_instrument: false    # use decorators in production
    processors:
      redaction_enabled: true
      redaction_mode: hash
      sampling_enabled: true
      sampling_rate: 0.1        # 10% in production

  # Test: no output, no instrumentation
  test:
    storage:
      type: none
    exporters:
      console: false
      jsonl: false
      otlp: false
      receiver: false
    instrumentation:
      auto_instrument: false
```

Set the active environment:

```bash
export TRACECRAFT_ENV=staging     # via env var
```

or in the config file:

```yaml
env: production
```

---

## Quick Start

### Basic Initialization

```python
import tracecraft

# Loads .tracecraft/config.yaml automatically
tracecraft.init()
```

### Common Configurations

```python
# Local development — stream live to TUI receiver
tracecraft.init(
    auto_instrument=True,
    receiver=True,
    service_name="my-agent",
)
```

```bash
tracecraft serve --tui  # start receiver + TUI
```

```python
# Local development — write to file, open TUI separately
tracecraft.init(
    auto_instrument=True,
    jsonl=True,
    service_name="my-agent",
)
```

```bash
tracecraft tui
```

```python
# Production — OTLP export, no local output
tracecraft.init(
    service_name="production-agent",
    console=False,
    jsonl=False,
    exporters=[OTLPExporter(endpoint="https://otlp.example.com")],
)
```

---

## Configuration Options

### Service Identification

```python
tracecraft.init(
    service_name="my-agent-service",  # shown in TUI and OTLP traces
)
```

**Config file:**

```yaml
default:
  service_name: my-agent-service
```

**Environment variable:**

```bash
export TRACECRAFT_SERVICE_NAME=my-service
```

### TUI Receiver Shorthand

Stream traces live to the `tracecraft serve --tui` receiver without any extra setup:

```python
# receiver=True → connect to http://localhost:4318 (default)
tracecraft.init(
    auto_instrument=True,
    receiver=True,
    service_name="my-agent",
)
```

```python
# receiver=<url> → custom receiver address
tracecraft.init(
    receiver="http://remote-host:4318",
    service_name="my-agent",
)
```

**Config file:**

```yaml
default:
  exporters:
    receiver: true
    receiver_endpoint: http://localhost:4318  # optional, this is the default
```

**Start the receiver:**

```bash
tracecraft serve --tui
```

### Auto-Instrumentation

Automatically capture all LLM calls without decorators:

```python
# Instrument all supported SDKs (OpenAI, Anthropic, LangChain, LlamaIndex)
tracecraft.init(auto_instrument=True)

# Instrument specific SDKs only
tracecraft.init(auto_instrument=["openai", "langchain"])
```

**Config file:**

```yaml
default:
  instrumentation:
    auto_instrument: true           # all SDKs

    # or selectively:
    # auto_instrument:
    #   - openai
    #   - anthropic
```

**Environment variable:**

```bash
export TRACECRAFT_AUTO_INSTRUMENT=true
export TRACECRAFT_AUTO_INSTRUMENT=openai,langchain  # selective
```

!!! warning "Initialize Before Importing SDKs"

    `tracecraft.init()` must be called **before** importing OpenAI, Anthropic,
    LangChain, or LlamaIndex. TraceCraft patches at import time — importing first
    means the patch won't apply.

### Console Output

```python
tracecraft.init(
    console=True,           # Enable console output (default: True)
    console_verbose=False,  # Show all attributes
)
```

**Config file:**

```yaml
default:
  exporters:
    console: true
```

**Environment variable:**

```bash
export TRACECRAFT_CONSOLE_ENABLED=true
```

### JSONL File Export

```python
tracecraft.init(
    jsonl=True,                    # Enable JSONL export
    jsonl_path="./my-traces/",     # Output path
)
```

**Config file:**

```yaml
default:
  exporters:
    jsonl: true
  storage:
    type: jsonl
    jsonl_path: traces/tracecraft.jsonl
```

**Environment variable:**

```bash
export TRACECRAFT_JSONL_ENABLED=true
export TRACECRAFT_JSONL_PATH=./my-traces/
```

### OTLP Export

```python
tracecraft.init(
    otlp_endpoint="http://localhost:4317",
    otlp_insecure=True,
    otlp_headers={"Authorization": "Bearer token"},
)
```

**Config file:**

```yaml
default:
  exporters:
    otlp: true
    otlp_endpoint: ${OTEL_EXPORTER_OTLP_ENDPOINT}
    otlp_headers:
      Authorization: Bearer ${OTEL_AUTH_TOKEN}
```

**Environment variables:**

```bash
export TRACECRAFT_OTLP_ENDPOINT=http://localhost:4317
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer token
```

### Sampling

```python
tracecraft.init(
    sampling_rate=0.1,           # Sample 10% of traces
    always_keep_errors=True,     # Always keep error traces
    always_keep_slow=True,       # Always keep slow traces
    slow_threshold_ms=5000,      # >5s is slow
)
```

**Config file:**

```yaml
default:
  processors:
    sampling_enabled: true
    sampling_rate: 0.1
```

**Environment variables:**

```bash
export TRACECRAFT_SAMPLING_RATE=0.1
export TRACECRAFT_ALWAYS_KEEP_ERRORS=true
```

### PII Redaction

```python
from tracecraft.core.config import RedactionConfig, RedactionMode

tracecraft.init(
    enable_pii_redaction=True,
    redaction_mode=RedactionMode.MASK,  # or REMOVE, HASH
    redaction_patterns=[
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",  # Emails
        r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
    ]
)
```

**Config file:**

```yaml
default:
  processors:
    redaction_enabled: true
    redaction_mode: mask   # mask, hash, or remove
```

**Environment variables:**

```bash
export TRACECRAFT_REDACTION_ENABLED=true
export TRACECRAFT_REDACTION_MODE=mask
```

### Processor Order

Control the order of the processing pipeline:

```python
from tracecraft.core.config import ProcessorOrder

tracecraft.init(
    processor_order=ProcessorOrder.SAFETY,  # or EFFICIENCY
)
```

- **SAFETY** (default): Enrich → Redact → Sample. Better for compliance.
- **EFFICIENCY**: Sample → Redact → Enrich. Better for high throughput.

### Max Step Depth

Limit trace hierarchy depth:

```python
tracecraft.init(
    max_step_depth=100,  # Maximum nesting level
)
```

---

## Custom Exporters

Create and use custom exporters:

```python
from tracecraft.exporters import BaseExporter, ConsoleExporter, JSONLExporter

# Use multiple exporters alongside built-in ones
tracecraft.init(
    exporters=[
        ConsoleExporter(),
        JSONLExporter(filepath="traces.jsonl"),
        MyCustomExporter(),
    ]
)
```

## Custom Processors

Add custom processors:

```python
from tracecraft.processors.base import BaseProcessor
from tracecraft.core.models import AgentRun

class MyCustomProcessor(BaseProcessor):
    def process(self, run: AgentRun) -> AgentRun | None:
        run.metadata["custom_field"] = "value"
        return run

from tracecraft import TraceCraftRuntime, TraceCraftConfig

config = TraceCraftConfig(...)
runtime = TraceCraftRuntime(config=config)
runtime.add_processor(MyCustomProcessor())
```

---

## Cloud Platform Configurations

### AWS AgentCore

```python
from tracecraft.core.config import AWSAgentCoreConfig

tracecraft.init(
    aws_agentcore=AWSAgentCoreConfig(
        enabled=True,
        use_xray_propagation=True,
        session_id="conversation-123",
    )
)
```

**Environment variables:**

```bash
export TRACECRAFT_AWS_AGENTCORE_ENABLED=true
export TRACECRAFT_AWS_XRAY_PROPAGATION=true
export TRACECRAFT_AWS_SESSION_ID=conversation-123
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317  # ADOT collector
```

### Azure AI Foundry

```python
from tracecraft.core.config import AzureFoundryConfig

tracecraft.init(
    azure_foundry=AzureFoundryConfig(
        enabled=True,
        connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"],
        enable_content_recording=True,
        agent_name="customer-support",
        agent_id="agent-v1",
    )
)
```

**Environment variables:**

```bash
export TRACECRAFT_AZURE_FOUNDRY_ENABLED=true
export APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...
```

### GCP Vertex Agent

```python
from tracecraft.core.config import GCPVertexAgentConfig

tracecraft.init(
    gcp_vertex_agent=GCPVertexAgentConfig(
        enabled=True,
        project_id="my-project",
        session_id="session-123",
        agent_name="support-agent",
        enable_content_recording=True,
    )
)
```

---

## Remote Storage Backends (TUI Read-Only)

The TUI can pull traces from cloud observability platforms without copying data locally. These backends are **read-only** — they never write to the platform.

### StorageConfig Type Values

| `type` | Description | Required Extra |
|--------|-------------|---------------|
| `jsonl` | JSONL file (default) | built-in |
| `sqlite` | SQLite database | built-in |
| `mlflow` | MLflow tracking server | `tracecraft[mlflow]` |
| `none` | No local storage | built-in |
| `xray` | AWS X-Ray (read-only) | `tracecraft[storage-xray]` |
| `cloudtrace` | GCP Cloud Trace (read-only) | `tracecraft[storage-cloudtrace]` |
| `azuremonitor` | Azure Monitor (read-only) | `tracecraft[storage-azuremonitor]` |
| `datadog` | DataDog APM (read-only) | `tracecraft[storage-datadog]` |

### X-Ray Config

```yaml
default:
  storage:
    type: xray
    xray_region: us-east-1
    xray_service_name: my-bedrock-agent   # optional, None = all services
    xray_lookback_hours: 1
    xray_cache_ttl_seconds: 60
# Auth: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_PROFILE / instance profile
```

### Cloud Trace Config

```yaml
default:
  storage:
    type: cloudtrace
    cloudtrace_project_id: my-gcp-project   # or set GOOGLE_CLOUD_PROJECT
    cloudtrace_service_name: my-agent       # optional
    cloudtrace_lookback_hours: 1
    cloudtrace_cache_ttl_seconds: 60
# Auth: GOOGLE_APPLICATION_CREDENTIALS / gcloud ADC / Workload Identity
```

### Azure Monitor Config

```yaml
default:
  storage:
    type: azuremonitor
    # Never hardcode workspace_id — use AZURE_MONITOR_WORKSPACE_ID env var
    azuremonitor_workspace_id: null
    azuremonitor_service_name: my-agent     # optional (cloud_RoleName)
    azuremonitor_lookback_hours: 1
    azuremonitor_cache_ttl_seconds: 60
# Auth: DefaultAzureCredential (managed identity → az login → env vars)
```

### DataDog Config

```yaml
default:
  storage:
    type: datadog
    datadog_site: us1                       # us1, us3, us5, eu1, ap1
    datadog_service: my-service             # optional
    datadog_lookback_hours: 1
    datadog_cache_ttl_seconds: 60
# Secrets: DD_API_KEY and DD_APP_KEY must be set as env vars — never in config
```

For full details on authentication, CLI usage, and troubleshooting, see the [Remote Trace Sources](remote-trace-sources.md) guide.

---

## Next Steps

- [Terminal UI Guide](tui.md) — Explore traces in the TUI
- [Remote Trace Sources](remote-trace-sources.md) — Pull from X-Ray, Cloud Trace, Azure Monitor, DataDog
- [Auto-Instrumentation](../integrations/auto-instrumentation.md) — Zero-code LLM tracing
- [Exporters](exporters.md) — Export to any backend
- [Processors](processors.md) — Configure data processing
- [Deployment](../deployment/production.md) — Production deployment patterns
