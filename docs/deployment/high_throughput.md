# High Throughput Deployment Guide

Configure TraceCraft for high-volume production environments.

## Overview

This guide covers optimizations for applications processing thousands of LLM requests per minute.

## Key Optimizations

### 1. Use Buffering Exporter

Buffer traces before sending to reduce network overhead:

```python
from tracecraft.exporters.otlp import OTLPExporter
from tracecraft.exporters.retry import BufferingExporter, RetryingExporter
from tracecraft.exporters.rate_limited import RateLimitedExporter

# Base OTLP exporter
otlp = OTLPExporter(
    endpoint="otel-collector:4317",
    service_name="my-app",
    timeout_ms=5000  # Short timeout for high throughput
)

# Add buffering (batch 100 traces before sending)
buffered = BufferingExporter(otlp, buffer_size=100)

# Add retry for resilience
retrying = RetryingExporter(
    buffered,
    max_retries=2,
    base_delay_ms=50,
    max_delay_ms=1000
)

# Add rate limiting to prevent overwhelming collector
rate_limited = RateLimitedExporter(
    retrying,
    rate=1000.0,  # 1000 exports/second max
    burst=100,
    blocking=False  # Drop instead of block
)

tracecraft.init(exporters=[rate_limited])
```

### 2. Configure Sampling

For very high traffic, sample traces:

```python
from tracecraft.core.config import TraceCraftConfig, SamplingConfig

config = TraceCraftConfig(
    sampling=SamplingConfig(
        rate=0.1,  # Sample 10% of traces
        always_sample_errors=True  # But always sample errors
    )
)

tracecraft.init(config=config)
```

### 3. Async Context Propagation

Use async helpers for concurrent operations:

```python
from tracecraft.contrib import gather_with_context, create_task_with_context

async def process_batch(queries: list[str]) -> list[str]:
    # All tasks maintain trace context
    tasks = [
        create_task_with_context(process_single(q))
        for q in queries
    ]
    return await gather_with_context(*tasks)
```

### 4. Disable Console Output

Console output adds latency:

```python
tracecraft.init(
    console=False,  # Disable console
    jsonl=False,    # Disable local file
    exporters=[otlp_exporter]  # Only OTLP
)
```

### 5. Minimize Captured Data

Reduce payload size:

```python
from tracecraft.core.config import TraceCraftConfig

config = TraceCraftConfig(
    # Truncate large inputs/outputs
    max_input_length=1000,
    max_output_length=1000,
    # Don't capture full prompts in production
    capture_prompts=False
)
```

## Architecture for Scale

```
┌─────────────────────────────────────────────────────────────────┐
│                    Application Tier                              │
│                                                                  │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │  Pod 1  │  │  Pod 2  │  │  Pod 3  │  │  Pod N  │            │
│  │(sampled)│  │(sampled)│  │(sampled)│  │(sampled)│            │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘            │
│       └────────────┼────────────┼────────────┘                  │
│                    ▼                                             │
│            ┌──────────────┐                                      │
│            │   Headless   │                                      │
│            │   Service    │                                      │
│            └──────┬───────┘                                      │
└───────────────────┼─────────────────────────────────────────────┘
                    ▼
┌───────────────────────────────────────────────────────────────────┐
│                   Collector Tier (HPA Enabled)                    │
│                                                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │
│  │  Collector  │  │  Collector  │  │  Collector  │               │
│  │  (batching) │  │  (batching) │  │  (batching) │               │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │
│         └────────────────┼────────────────┘                       │
│                          ▼                                        │
│                  ┌──────────────┐                                 │
│                  │    Kafka     │                                 │
│                  │   (buffer)   │                                 │
│                  └──────┬───────┘                                 │
│                         ▼                                         │
│                 ┌──────────────┐                                  │
│                 │   Backend    │                                  │
│                 │(Elasticsearch│                                  │
│                 │   /Jaeger)   │                                  │
│                 └──────────────┘                                  │
└───────────────────────────────────────────────────────────────────┘
```

## OTEL Collector Configuration

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
        max_recv_msg_size_mib: 16

processors:
  batch:
    timeout: 1s
    send_batch_size: 10000
    send_batch_max_size: 20000

  memory_limiter:
    check_interval: 1s
    limit_mib: 4000
    spike_limit_mib: 500

  probabilistic_sampler:
    sampling_percentage: 10

exporters:
  kafka:
    brokers:
      - kafka:9092
    topic: traces
    encoding: otlp_proto

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch, probabilistic_sampler]
      exporters: [kafka]
```

## Benchmarks

Tested on 8-core, 32GB RAM, Kubernetes cluster:

| Configuration | Throughput | Latency (p99) | Drop Rate |
|---------------|------------|---------------|-----------|
| Baseline (no tracing) | 10,000 req/s | 50ms | 0% |
| TraceCraft (console) | 8,500 req/s | 65ms | 0% |
| TraceCraft (OTLP) | 9,200 req/s | 55ms | 0% |
| TraceCraft (buffered) | 9,800 req/s | 52ms | 0% |
| TraceCraft (sampled 10%) | 9,900 req/s | 51ms | 0% |

## Monitoring the Tracing System

### Metrics to Watch

```python
# Access exporter stats
from tracecraft.exporters.rate_limited import RateLimitedExporter

rate_limited = RateLimitedExporter(...)

# Check dropped count
print(f"Dropped traces: {rate_limited.dropped_count}")
```

### Prometheus Metrics

Configure OTEL Collector to expose metrics:

```yaml
extensions:
  zpages:
    endpoint: 0.0.0.0:55679

service:
  extensions: [zpages]
```

## Troubleshooting

### High Memory Usage

- Reduce buffer size
- Enable aggressive sampling
- Check for memory leaks in custom processors

### Dropped Traces

- Increase rate limit
- Scale collector horizontally
- Use Kafka as buffer

### High Latency

- Disable console output
- Use async exports
- Reduce captured data size
