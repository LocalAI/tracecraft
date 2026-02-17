# Kubernetes Deployment Guide

Deploy TraceCraft-instrumented applications to Kubernetes with OTLP export.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Kubernetes Cluster                       │
│                                                              │
│  ┌─────────────┐      ┌──────────────────┐                  │
│  │   Your App  │─────▶│  OTEL Collector  │                  │
│  │  (TraceCraft│      │   (DaemonSet)    │                  │
│  │   enabled)  │      └────────┬─────────┘                  │
│  └─────────────┘               │                            │
│                                ▼                            │
│                    ┌──────────────────────┐                 │
│                    │      Jaeger          │                 │
│                    │   (Deployment)       │                 │
│                    └──────────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

- Kubernetes cluster (1.24+)
- kubectl configured
- Helm (optional, for OTEL Collector)

## Step 1: Deploy OpenTelemetry Collector

```yaml
# otel-collector.yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: otel-collector
  namespace: observability
spec:
  selector:
    matchLabels:
      app: otel-collector
  template:
    metadata:
      labels:
        app: otel-collector
    spec:
      containers:
      - name: collector
        image: otel/opentelemetry-collector:latest
        ports:
        - containerPort: 4317  # OTLP gRPC
        - containerPort: 4318  # OTLP HTTP
        volumeMounts:
        - name: config
          mountPath: /etc/otelcol
      volumes:
      - name: config
        configMap:
          name: otel-collector-config
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: otel-collector-config
  namespace: observability
data:
  config.yaml: |
    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 0.0.0.0:4317
          http:
            endpoint: 0.0.0.0:4318
    processors:
      batch:
        timeout: 1s
        send_batch_size: 1024
    exporters:
      otlp:
        endpoint: jaeger:4317
        tls:
          insecure: true
    service:
      pipelines:
        traces:
          receivers: [otlp]
          processors: [batch]
          exporters: [otlp]
---
apiVersion: v1
kind: Service
metadata:
  name: otel-collector
  namespace: observability
spec:
  selector:
    app: otel-collector
  ports:
  - name: otlp-grpc
    port: 4317
  - name: otlp-http
    port: 4318
```

## Step 2: Deploy Jaeger

```yaml
# jaeger.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jaeger
  namespace: observability
spec:
  replicas: 1
  selector:
    matchLabels:
      app: jaeger
  template:
    metadata:
      labels:
        app: jaeger
    spec:
      containers:
      - name: jaeger
        image: jaegertracing/all-in-one:latest
        ports:
        - containerPort: 16686  # UI
        - containerPort: 4317   # OTLP gRPC
        env:
        - name: COLLECTOR_OTLP_ENABLED
          value: "true"
---
apiVersion: v1
kind: Service
metadata:
  name: jaeger
  namespace: observability
spec:
  selector:
    app: jaeger
  ports:
  - name: ui
    port: 16686
  - name: otlp
    port: 4317
```

## Step 3: Configure Your Application

```yaml
# your-app.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-llm-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-llm-app
  template:
    metadata:
      labels:
        app: my-llm-app
    spec:
      containers:
      - name: app
        image: my-llm-app:latest
        env:
        - name: TRACECRAFT_OTLP_ENABLED
          value: "true"
        - name: TRACECRAFT_OTLP_ENDPOINT
          value: "otel-collector.observability.svc.cluster.local:4317"
        - name: TRACECRAFT_SERVICE_NAME
          value: "my-llm-app"
        - name: TRACECRAFT_CONSOLE_ENABLED
          value: "false"
        - name: TRACECRAFT_REDACTION_ENABLED
          value: "true"
```

## Step 4: Application Code

```python
# app.py
import os
import tracecraft
from tracecraft.exporters.otlp import OTLPExporter
from tracecraft.exporters.retry import RetryingExporter

# Configure from environment
endpoint = os.environ.get("TRACECRAFT_OTLP_ENDPOINT", "localhost:4317")
service_name = os.environ.get("TRACECRAFT_SERVICE_NAME", "my-app")

# Use retrying exporter for resilience
otlp = OTLPExporter(endpoint=endpoint, service_name=service_name)
retrying_otlp = RetryingExporter(otlp, max_retries=3)

tracecraft.init(
    console=False,
    jsonl=False,
    exporters=[retrying_otlp]
)

# Your application code...
@tracecraft.trace_agent(name="my_agent")
async def process_request(query: str) -> str:
    # ...
    pass
```

## Step 5: Expose Jaeger UI

```bash
kubectl port-forward svc/jaeger -n observability 16686:16686
# Open http://localhost:16686
```

## Production Considerations

### High Availability

```yaml
# OTEL Collector as Deployment with HPA
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: otel-collector
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: otel-collector
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

### Resource Limits

```yaml
resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: 500m
    memory: 512Mi
```

### Persistent Storage (Jaeger)

For production, use Elasticsearch or Cassandra backend for Jaeger instead of all-in-one.

## Troubleshooting

### Check Collector Logs

```bash
kubectl logs -l app=otel-collector -n observability
```

### Verify Connectivity

```bash
kubectl exec -it <your-pod> -- nc -zv otel-collector.observability.svc.cluster.local 4317
```

### Debug Mode

```python
import logging
logging.getLogger("tracecraft").setLevel(logging.DEBUG)
```
