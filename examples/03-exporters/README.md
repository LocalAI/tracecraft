# 03 - Exporters

Learn how to export traces to various destinations including OTLP collectors, HTML reports, and MLflow.

## Exporter Overview

| Exporter | Output | Use Case |
|----------|--------|----------|
| Console | Terminal | Development and debugging |
| JSONL | File | Log aggregation, offline analysis |
| OTLP | Network | Distributed tracing (Jaeger, Tempo) |
| HTML | File | Sharing, documentation |
| MLflow | Server | ML experiment tracking |

## Examples

| # | Example | Description | External Deps |
|---|---------|-------------|---------------|
| 1 | `01_console_jsonl.py` | Default exporters | None |
| 2 | `02_otlp_jaeger.py` | OTLP to Jaeger | Jaeger (Docker) |
| 3 | `03_otlp_tempo.py` | OTLP to Grafana Tempo | Tempo (Docker) |
| 4 | `04_html_reports.py` | Interactive HTML reports | None |
| 5 | `05_mlflow.py` | MLflow experiment tracking | MLflow server |
| 6 | `06_custom_exporter.py` | Building custom exporters | None |

## Console and JSONL (Built-in)

Enabled by default. No extra setup required.

```python
import agenttrace

runtime = agenttrace.init(
    console=True,       # Rich tree in terminal
    jsonl=True,         # JSONL file
    jsonl_path="traces/my_traces.jsonl",
)
```

### Disable via environment

```bash
export AGENTTRACE_CONSOLE_ENABLED=false
export AGENTTRACE_JSONL_ENABLED=false
```

## OTLP Export

Export traces to any OpenTelemetry-compatible backend.

### Setup Jaeger

```bash
docker run -d --name jaeger \
    -p 4317:4317 \
    -p 16686:16686 \
    jaegertracing/all-in-one:latest
```

### Use in code

```python
from agenttrace.exporters.otlp import OTLPExporter

otlp = OTLPExporter(
    endpoint="http://localhost:4317",
    service_name="my-service",
)

runtime = agenttrace.init(exporters=[otlp])
```

### Via environment

```bash
export AGENTTRACE_OTLP_ENABLED=true
export AGENTTRACE_OTLP_ENDPOINT=http://localhost:4317
```

## HTML Reports

Generate self-contained HTML files for sharing.

```python
from agenttrace.exporters.html import HTMLExporter

html_exporter = HTMLExporter(filepath="report.html")
html_exporter.export(run)
```

Features:

- Self-contained (no external dependencies)
- Interactive trace tree
- Timing visualization
- Shareable via email or hosting

## MLflow Integration

Track traces alongside ML experiments.

```python
from agenttrace.exporters.mlflow import MLflowExporter

mlflow_exporter = MLflowExporter(
    experiment_name="my-agent-experiment",
    tracking_uri="http://localhost:5000",
)

runtime = agenttrace.init(exporters=[mlflow_exporter])
```

### Start MLflow

```bash
mlflow server --host 0.0.0.0 --port 5000
```

## Custom Exporters

Create your own exporter by inheriting from `BaseExporter`:

```python
from agenttrace.exporters.base import BaseExporter
from agenttrace.core.models import AgentRun

class MyExporter(BaseExporter):
    def export(self, run: AgentRun) -> None:
        # Convert run to your format
        # Send to your backend
        pass

    def close(self) -> None:
        # Cleanup resources
        pass
```

## Multiple Exporters

Use multiple exporters simultaneously:

```python
from agenttrace.exporters.otlp import OTLPExporter
from agenttrace.exporters.html import HTMLExporter

runtime = agenttrace.init(
    console=True,
    jsonl=True,
    exporters=[
        OTLPExporter(endpoint="http://localhost:4317"),
        HTMLExporter(filepath="traces.html"),
    ],
)
```

## Exporter Comparison

| Feature | Console | JSONL | OTLP | HTML | MLflow |
|---------|---------|-------|------|------|--------|
| Real-time | Yes | No | Yes | No | No |
| Shareable | No | Yes | Via UI | Yes | Via UI |
| Search | No | CLI tools | Yes | No | Yes |
| Visualization | Tree | Raw | Jaeger/Tempo | Yes | Yes |
| Offline | N/A | Yes | No | Yes | No |

## Troubleshooting

### OTLP: "Connection refused"

- Ensure collector is running: `docker ps`
- Check endpoint port (4317 for gRPC, 4318 for HTTP)
- Verify network connectivity

### HTML: "Permission denied"

- Check write permissions for output directory
- Use absolute path if needed

### MLflow: "Experiment not found"

- The experiment is created automatically
- Ensure MLflow server is accessible
- Check tracking URI configuration

## Next Steps

- [04-production/](../04-production/) - Production patterns (async, resilience)
- [05-alerting/](../05-alerting/) - Set up monitoring and alerts
