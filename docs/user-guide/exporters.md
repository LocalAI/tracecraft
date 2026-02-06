# Exporters

Exporters send trace data to different backends. TraceCraft supports multiple exporters simultaneously.

## Available Exporters

| Exporter | Purpose | Installation |
|----------|---------|--------------|
| ConsoleExporter | Rich terminal output | Built-in |
| JSONLExporter | Local file storage | Built-in |
| OTLPExporter | OpenTelemetry Protocol | `tracecraft[otlp]` |
| MLflowExporter | MLflow tracking | `tracecraft[mlflow]` |
| HTMLExporter | HTML reports | Built-in |

## Console Exporter

Beautiful terminal output with Rich formatting.

```python
from tracecraft.exporters import ConsoleExporter

tracecraft.init(
    exporters=[ConsoleExporter(verbose=True)]
)
```

**Options:**

- `verbose` (bool): Show all span attributes. Default: False.

## JSONL Exporter

Write traces to newline-delimited JSON files.

```python
from tracecraft.exporters import JSONLExporter

tracecraft.init(
    exporters=[
        JSONLExporter(
            filepath="traces/app.jsonl",
            append=True,
        )
    ]
)
```

**Options:**

- `filepath` (str | Path): Output file path
- `append` (bool): Append to existing file. Default: True.

## OTLP Exporter

Export to any OTLP-compatible backend (Jaeger, Grafana Tempo, Datadog, etc.).

```python
from tracecraft.exporters import OTLPExporter

tracecraft.init(
    exporters=[
        OTLPExporter(
            endpoint="http://localhost:4317",
            insecure=True,
            headers={"Authorization": "Bearer token"},
        )
    ]
)
```

**Options:**

- `endpoint` (str): OTLP gRPC endpoint
- `insecure` (bool): Disable TLS. Default: True for localhost.
- `headers` (dict): Custom HTTP headers

**Supported Backends:**

- Jaeger
- Grafana Tempo
- Datadog
- Honeycomb
- New Relic
- Any OTLP-compatible system

## MLflow Exporter

Export traces to MLflow for experiment tracking.

```python
from tracecraft.exporters.mlflow import MLflowExporter

tracecraft.init(
    exporters=[
        MLflowExporter(
            tracking_uri="http://localhost:5000",
            experiment_name="my-agent",
        )
    ]
)
```

**Options:**

- `tracking_uri` (str): MLflow tracking server URL
- `experiment_name` (str): MLflow experiment name

## HTML Exporter

Generate standalone HTML reports.

```python
from tracecraft.exporters import HTMLExporter

tracecraft.init(
    exporters=[
        HTMLExporter(
            output_dir="reports/",
            include_source=True,
        )
    ]
)
```

**Options:**

- `output_dir` (str | Path): Report output directory
- `include_source` (bool): Include source code snippets. Default: True.

## Using Multiple Exporters

Send traces to multiple destinations:

```python
from tracecraft.exporters import (
    ConsoleExporter,
    JSONLExporter,
    OTLPExporter,
)

tracecraft.init(
    exporters=[
        ConsoleExporter(),  # Development
        JSONLExporter(filepath="traces.jsonl"),  # Local storage
        OTLPExporter(endpoint="http://jaeger:4317"),  # Observability platform
    ]
)
```

## Async Exporters

For high-throughput scenarios, use async exporters:

```python
from tracecraft.exporters import AsyncBatchExporter, OTLPExporter

# Wrap exporter in async batch processor
async_exporter = AsyncBatchExporter(
    exporter=OTLPExporter(endpoint="http://localhost:4317"),
    batch_size=100,
    flush_interval_ms=5000,
)

tracecraft.init(exporters=[async_exporter])
```

## Retry and Rate Limiting

Wrap exporters for reliability:

```python
from tracecraft.exporters import RetryingExporter, RateLimitedExporter, OTLPExporter

# Add retry logic
reliable_exporter = RetryingExporter(
    exporter=OTLPExporter(endpoint="http://localhost:4317"),
    max_retries=3,
    backoff_factor=2.0,
)

# Add rate limiting
rate_limited = RateLimitedExporter(
    exporter=reliable_exporter,
    max_requests_per_second=10,
)

tracecraft.init(exporters=[rate_limited])
```

## Custom Exporters

Create your own exporter:

```python
from tracecraft.exporters import BaseExporter
from tracecraft.core.models import AgentRun

class MyCustomExporter(BaseExporter):
    def export(self, run: AgentRun) -> None:
        """Export trace to custom backend."""
        # Your export logic here
        print(f"Exporting run: {run.name}")
        # Send to your backend
        self.send_to_backend(run)

    def send_to_backend(self, run: AgentRun) -> None:
        # Implementation
        pass

# Use it
tracecraft.init(exporters=[MyCustomExporter()])
```

## Environment-Based Configuration

Different exporters per environment:

```python
import os

env = os.getenv("ENV", "dev")

if env == "production":
    exporters = [
        OTLPExporter(endpoint=os.getenv("OTLP_ENDPOINT")),
        JSONLExporter(filepath="/var/log/traces/prod.jsonl"),
    ]
elif env == "staging":
    exporters = [
        OTLPExporter(endpoint=os.getenv("OTLP_ENDPOINT")),
        ConsoleExporter(verbose=True),
    ]
else:  # development
    exporters = [
        ConsoleExporter(verbose=True),
        JSONLExporter(filepath="traces/dev.jsonl"),
    ]

tracecraft.init(exporters=exporters)
```

## Best Practices

### 1. Use Console for Development

```python
# Development
tracecraft.init(
    exporters=[ConsoleExporter(verbose=True)]
)
```

### 2. Use JSONL for Debugging

```python
# Keep local copy for debugging
tracecraft.init(
    exporters=[
        OTLPExporter(endpoint="http://prod:4317"),
        JSONLExporter(filepath="backup.jsonl"),  # Local backup
    ]
)
```

### 3. Disable Console in Production

```python
# Production - no console output
tracecraft.init(
    exporters=[
        OTLPExporter(endpoint=os.getenv("OTLP_ENDPOINT"))
    ]
)
```

### 4. Use Async for High Volume

```python
from tracecraft.exporters import AsyncBatchExporter

# High-throughput production
tracecraft.init(
    exporters=[
        AsyncBatchExporter(
            exporter=OTLPExporter(...),
            batch_size=500,
            flush_interval_ms=1000,
        )
    ]
)
```

## Next Steps

- [Processors](processors.md) - Process traces before export
- [Configuration](configuration.md) - Configure exporters
- [Deployment](../deployment/production.md) - Production deployment
