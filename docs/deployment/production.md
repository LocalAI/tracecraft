# Production Deployment

Best practices for deploying Trace Craft in production environments.

## Production Configuration

### Minimal Overhead

```python
import os
import tracecraft

tracecraft.init(
    service_name=os.getenv("SERVICE_NAME", "my-service"),
    environment="production",

    # Disable console in production
    console=False,

    # Use OTLP for observability platform
    otlp_endpoint=os.getenv("OTLP_ENDPOINT"),

    # Sample to reduce volume
    sampling_rate=0.1,  # 10% of traces

    # Always capture errors and slow traces
    always_keep_errors=True,
    always_keep_slow=True,
    slow_threshold_ms=5000,

    # Enable PII redaction
    enable_pii_redaction=True,

    # Production tags
    tags=[
        f"version:{os.getenv('APP_VERSION', 'unknown')}",
        f"region:{os.getenv('AWS_REGION', 'unknown')}",
    ],
)
```

### Environment Variables

```bash
# .env.production
SERVICE_NAME=my-agent-service
OTLP_ENDPOINT=https://otlp.example.com:4317
TRACECRAFT_SAMPLING_RATE=0.1
TRACECRAFT_REDACTION_ENABLED=true
APP_VERSION=1.0.0
```

## High-Throughput Setup

For high-volume production:

```python
from tracecraft.exporters import AsyncBatchExporter, OTLPExporter
from tracecraft.core.config import ProcessorOrder

tracecraft.init(
    # Use efficiency mode - sample first
    processor_order=ProcessorOrder.EFFICIENCY,

    # Aggressive sampling
    sampling_rate=0.01,  # 1% of traces

    # Async batch export
    exporters=[
        AsyncBatchExporter(
            exporter=OTLPExporter(
                endpoint=os.getenv("OTLP_ENDPOINT")
            ),
            batch_size=1000,
            flush_interval_ms=5000,
        )
    ],

    # Disable console
    console=False,
)
```

## Monitoring

### Health Checks

```python
from tracecraft import get_runtime

def health_check():
    runtime = get_runtime()
    return {
        "status": "healthy",
        "config": {
            "service_name": runtime.config.service_name,
            "sampling_rate": runtime.config.sampling_rate,
        }
    }
```

### Metrics

Track Trace Craft metrics:

```python
from tracecraft import get_runtime

runtime = get_runtime()

# Get runtime stats
stats = {
    "traces_exported": runtime.traces_exported,
    "traces_dropped": runtime.traces_dropped,
    "export_errors": runtime.export_errors,
}
```

## Error Handling

### Graceful Degradation

```python
try:
    tracecraft.init(
        otlp_endpoint=os.getenv("OTLP_ENDPOINT"),
    )
except Exception as e:
    # Fallback to local JSONL
    logger.error(f"Failed to initialize OTLP: {e}")
    tracecraft.init(
        console=False,
        jsonl=True,
        jsonl_path="/var/log/traces/",
    )
```

### Retry Logic

```python
from tracecraft.exporters import RetryingExporter, OTLPExporter

exporter = RetryingExporter(
    exporter=OTLPExporter(endpoint=os.getenv("OTLP_ENDPOINT")),
    max_retries=3,
    backoff_factor=2.0,
)

tracecraft.init(exporters=[exporter])
```

## Security

### TLS/SSL

```python
tracecraft.init(
    otlp_endpoint="https://otlp.example.com:4317",
    otlp_insecure=False,  # Enable TLS
    otlp_headers={
        "Authorization": f"Bearer {os.getenv('OTLP_TOKEN')}"
    }
)
```

### PII Redaction

```python
from tracecraft.core.config import RedactionConfig, RedactionMode

tracecraft.init(
    enable_pii_redaction=True,
    redaction_mode=RedactionMode.MASK,
    redaction_patterns=[
        (r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[EMAIL]"),
        (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]"),
        (r"\b\d{16}\b", "[CC]"),
    ]
)
```

## Resource Limits

### Memory Management

```python
from tracecraft.exporters import AsyncBatchExporter

# Limit batch size to control memory
exporter = AsyncBatchExporter(
    exporter=OTLPExporter(...),
    batch_size=100,  # Smaller batches
    max_queue_size=1000,  # Limit queue
)
```

### CPU Usage

```python
# Reduce sampling to lower CPU usage
tracecraft.init(
    sampling_rate=0.01,  # 1% sampling
    processor_order=ProcessorOrder.EFFICIENCY,
)
```

## Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV TRACECRAFT_SERVICE_NAME=my-service
ENV TRACECRAFT_SAMPLING_RATE=0.1

CMD ["python", "main.py"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  app:
    build: .
    environment:
      - TRACECRAFT_SERVICE_NAME=my-service
      - OTLP_ENDPOINT=http://jaeger:4317
      - TRACECRAFT_SAMPLING_RATE=0.1
    depends_on:
      - jaeger

  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "4317:4317"  # OTLP gRPC
      - "16686:16686"  # UI
```

## Kubernetes Deployment

See [Kubernetes Deployment](kubernetes.md) for complete guide.

## Performance Benchmarks

Typical overhead:

| Configuration | Overhead | Throughput |
|--------------|----------|------------|
| 100% sampling, console + OTLP | ~5-10% | 1K traces/s |
| 10% sampling, OTLP only | ~1-2% | 10K traces/s |
| 1% sampling, async batch | <1% | 50K+ traces/s |

## Best Practices

### 1. Use Sampling

```python
# Don't trace everything in production
tracecraft.init(sampling_rate=0.1)
```

### 2. Disable Console Output

```python
# No console in production
tracecraft.init(console=False)
```

### 3. Use Async Exporters

```python
# Better performance
from tracecraft.exporters import AsyncBatchExporter
```

### 4. Monitor Export Errors

```python
runtime = get_runtime()
if runtime.export_errors > 100:
    alert("High export error rate")
```

### 5. Set Resource Limits

```python
# Prevent memory issues
exporter = AsyncBatchExporter(
    batch_size=100,
    max_queue_size=1000,
)
```

## Troubleshooting

### High Memory Usage

Reduce batch size or sampling rate:

```python
tracecraft.init(
    sampling_rate=0.01,  # Lower sampling
    exporters=[
        AsyncBatchExporter(
            batch_size=50,  # Smaller batches
            ...
        )
    ]
)
```

### Export Failures

Add retry logic and fallback:

```python
from tracecraft.exporters import RetryingExporter, JSONLExporter

primary = RetryingExporter(
    exporter=OTLPExporter(...),
    max_retries=3,
)

fallback = JSONLExporter(filepath="/var/log/traces/")

tracecraft.init(exporters=[primary, fallback])
```

## Next Steps

- [Kubernetes Deployment](kubernetes.md)
- [High Throughput](high-throughput.md)
- [Cloud Platforms](../integrations/cloud-platforms.md)
