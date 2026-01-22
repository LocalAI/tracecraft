# 04 - Production Patterns

> **Status: Coming Soon** - This section is planned but examples are not yet implemented.
> See [01-getting-started/04_configuration.py](../01-getting-started/04_configuration.py) for basic configuration.

Learn production-ready patterns for deploying AgentTrace in high-throughput environments.

## Overview

This section covers four key areas:

1. **Configuration** - Environment variables and config objects
2. **Processors** - PII redaction, sampling, cost enrichment
3. **Resilience** - Retry, buffering, rate limiting
4. **Async Pipeline** - Non-blocking exports for high throughput

## Subsections

| Subsection | Description | Examples |
|------------|-------------|----------|
| [configuration/](configuration/) | Config management | 3 |
| [processors/](processors/) | Data processing | 4 |
| [resilience/](resilience/) | Fault tolerance | 3 |
| [async_pipeline/](async_pipeline/) | High throughput | 3 |

## Configuration (`configuration/`)

| Example | Description |
|---------|-------------|
| `01_env_variables.py` | All AGENTTRACE_* environment variables |
| `02_config_object.py` | Programmatic configuration |
| `03_dynamic_config.py` | Runtime configuration changes |

### Key Environment Variables

```bash
AGENTTRACE_SERVICE_NAME=my-service
AGENTTRACE_SAMPLING_RATE=0.5
AGENTTRACE_REDACTION_ENABLED=true
AGENTTRACE_OTLP_ENABLED=true
AGENTTRACE_OTLP_ENDPOINT=http://collector:4317
```

## Processors (`processors/`)

Processors transform traces before export.

| Example | Description |
|---------|-------------|
| `01_pii_redaction.py` | Redact API keys, emails, SSNs |
| `02_sampling.py` | Tail-based sampling with error preservation |
| `03_cost_enrichment.py` | Token counting and cost calculation |
| `04_custom_processor.py` | Building custom processors |

### PII Redaction Example

```python
from agenttrace.processors.redaction import RedactionProcessor

processor = RedactionProcessor(
    patterns=["sk-[a-zA-Z0-9]+", r"\b[\w.-]+@[\w.-]+\.\w+\b"],
    mode="mask",  # or "hash", "remove"
)

runtime = agenttrace.init(processors=[processor])
```

### Sampling Example

```python
from agenttrace.processors.sampling import SamplingProcessor

processor = SamplingProcessor(
    rate=0.1,  # Sample 10%
    always_keep_errors=True,
    always_keep_slow=True,
    slow_threshold_ms=5000,
)
```

## Resilience (`resilience/`)

Handle failures gracefully in production.

| Example | Description |
|---------|-------------|
| `01_retry_exporter.py` | Exponential backoff retry |
| `02_buffering.py` | Memory-bounded buffering |
| `03_rate_limiting.py` | Token bucket rate limiting |

### Retry Example

```python
from agenttrace.exporters.retry import RetryingExporter

resilient = RetryingExporter(
    exporter=otlp_exporter,
    max_retries=3,
    backoff_factor=2.0,
)
```

## Async Pipeline (`async_pipeline/`)

Non-blocking exports for high-throughput scenarios.

| Example | Description |
|---------|-------------|
| `01_async_exporter.py` | Background thread export |
| `02_batch_exporter.py` | Batched async exports |
| `03_high_throughput.py` | 10k+ traces/second patterns |

### Async Export Example

```python
from agenttrace.exporters.async_pipeline import AsyncExporter

async_exporter = AsyncExporter(
    exporter=otlp_exporter,
    queue_size=1000,
    num_workers=2,
)
```

### Batch Export Example

```python
from agenttrace.exporters.async_pipeline import AsyncBatchExporter

batch_exporter = AsyncBatchExporter(
    exporter=otlp_exporter,
    batch_size=50,
    flush_interval_seconds=5.0,
)
```

## Production Checklist

- [ ] Enable PII redaction (`AGENTTRACE_REDACTION_ENABLED=true`)
- [ ] Configure sampling rate (`AGENTTRACE_SAMPLING_RATE=0.1`)
- [ ] Use async/batch exporters for high throughput
- [ ] Set up retry for OTLP export
- [ ] Configure appropriate queue sizes
- [ ] Monitor exporter health metrics

## Performance Guidelines

| Throughput | Recommended Config |
|------------|-------------------|
| < 100/sec | Default (sync export) |
| 100-1000/sec | AsyncExporter with 2 workers |
| 1000-10000/sec | AsyncBatchExporter (batch_size=50) |
| > 10000/sec | Multiple batch exporters with sharding |

## Next Steps

- [05-alerting/](../05-alerting/) - Set up monitoring and alerts
- [06-evaluation/](../06-evaluation/) - Integrate evaluation frameworks
