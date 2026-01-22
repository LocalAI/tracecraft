# GCP Vertex AI Agent Builder Deployment Guide

Deploy AgentTrace-instrumented applications to GCP with Cloud Trace and Vertex AI Agent Builder observability.

## Architecture

```text
+-------------------------------------------------------------+
|                        GCP Cloud                             |
|                                                              |
|  +------------------+      +------------------------------+  |
|  |   Your Agent     |----->|    Cloud Trace               |  |
|  |  (AgentTrace     |      |   (OTel/Cloud Trace API)     |  |
|  |   enabled)       |      +------------------------------+  |
|  +------------------+                     |                  |
|                                           v                  |
|                           +------------------------------+   |
|                           |   Vertex AI Agent Builder    |   |
|                           |   (Trace Visualization)      |   |
|                           +------------------------------+   |
+-------------------------------------------------------------+
```

## Prerequisites

- GCP project with Cloud Trace API enabled
- Application Default Credentials configured
- Python 3.11+

## Quick Start

### 1. Enable Cloud Trace API

```bash
# Enable Cloud Trace API
gcloud services enable cloudtrace.googleapis.com --project=YOUR_PROJECT_ID
```

### 2. Install AgentTrace

```bash
pip install agenttrace[gcp-vertex-agent]
```

### 3. Configure Exporter

```python
import agenttrace
from agenttrace.contrib.gcp import create_vertex_agent_exporter

# Create exporter with Vertex AI Agent Builder features
exporter = create_vertex_agent_exporter(
    # GCP project ID (or set GOOGLE_CLOUD_PROJECT env var)
    project_id="your-project-id",

    # Service name appears in Cloud Trace
    service_name="my-agent-service",

    # Session ID for multi-turn conversation tracking
    session_id="session-12345",

    # Enable content recording (prompts/responses)
    # WARNING: Only enable in dev or when data policies allow
    enable_content_recording=False,

    # Agent metadata
    agent_name="research-agent",
    agent_id="agent-001",
    agent_description="Researches topics and synthesizes information",

    # For Reasoning Engine integration
    reasoning_engine_id="re-001",
)

# Initialize AgentTrace
agenttrace.init(
    exporters=[exporter],
    console=False,  # Disable console in production
    jsonl=False,    # Disable local JSONL
)
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_CLOUD_PROJECT` | GCP project ID | Yes |
| `AGENTTRACE_GCP_VERTEX_ENABLED` | Enable Vertex export | No |
| `AGENTTRACE_GCP_SESSION_ID` | Session ID for multi-turn | No |
| `AGENTTRACE_GCP_AGENT_NAME` | Agent name for traces | No |
| `AGENTTRACE_GCP_AGENT_ID` | Agent ID for traces | No |
| `AGENTTRACE_GCP_CONTENT_RECORDING` | Record prompts/responses | No |
| `AGENTTRACE_GCP_REASONING_ENGINE_ID` | Reasoning Engine ID | No |

## Cloud Functions Deployment

```python
# main.py
import functions_framework
import agenttrace
from agenttrace.contrib.gcp import configure_for_vertex_agent_builder

# Configure at function startup
exporter = configure_for_vertex_agent_builder(service_name="my-function")
agenttrace.init(exporters=[exporter], console=False, jsonl=False)

@functions_framework.http
def process_agent(request):
    # Your traced agent code here
    pass
```

## Cloud Run Deployment

### 1. Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["python", "main.py"]
```

### 2. Deploy with Service Account

```bash
# Create service account with Cloud Trace permissions
gcloud iam service-accounts create agent-tracer \
    --display-name="Agent Tracer"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:agent-tracer@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/cloudtrace.agent"

# Deploy Cloud Run service
gcloud run deploy my-agent \
    --source . \
    --service-account=agent-tracer@YOUR_PROJECT_ID.iam.gserviceaccount.com \
    --set-env-vars=GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID \
    --set-env-vars=AGENTTRACE_GCP_AGENT_NAME=my-agent
```

### 3. Application Code

```python
from agenttrace.contrib.gcp import configure_for_vertex_agent_builder

exporter = configure_for_vertex_agent_builder(service_name="my-cloudrun-agent")
agenttrace.init(exporters=[exporter])
```

## Google Kubernetes Engine (GKE)

### 1. Create Secret for Service Account

```yaml
# gcp-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: gcp-credentials
  namespace: default
type: Opaque
data:
  key.json: <base64-encoded-service-account-key>
```

### 2. Deploy Application

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-agent
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: agent
        image: my-agent:latest
        env:
        - name: GOOGLE_CLOUD_PROJECT
          value: "your-project-id"
        - name: GOOGLE_APPLICATION_CREDENTIALS
          value: "/var/secrets/google/key.json"
        - name: AGENTTRACE_GCP_AGENT_NAME
          value: "gke-research-agent"
        volumeMounts:
        - name: gcp-credentials
          mountPath: /var/secrets/google
          readOnly: true
      volumes:
      - name: gcp-credentials
        secret:
          secretName: gcp-credentials
```

### 3. Using Workload Identity (Recommended)

```yaml
# service-account.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: agent-sa
  annotations:
    iam.gke.io/gcp-service-account: agent-tracer@YOUR_PROJECT_ID.iam.gserviceaccount.com
---
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-agent
spec:
  template:
    spec:
      serviceAccountName: agent-sa
      containers:
      - name: agent
        image: my-agent:latest
        env:
        - name: GOOGLE_CLOUD_PROJECT
          value: "your-project-id"
```

## Cloud Trace Context Propagation

Propagate trace context to downstream services:

```python
from agenttrace.contrib.gcp import inject_cloudtrace_context, extract_cloudtrace_context
from agenttrace import get_current_run
import requests

# Inject context into outgoing request
headers = {}
inject_cloudtrace_context(headers, get_current_run(), session_id="session-123")
response = requests.post(downstream_url, headers=headers, json=payload)

# Extract context from incoming request (in downstream service)
result = extract_cloudtrace_context(request.headers)
if result:
    trace_id, span_id, sampled, session_id = result
    # Continue the trace
```

## Cloud Trace Header Format

The X-Cloud-Trace-Context header format:

```text
X-Cloud-Trace-Context: TRACE_ID/SPAN_ID;o=OPTIONS
```

- `TRACE_ID`: 32 hex characters
- `SPAN_ID`: Decimal number (converted to 16 hex chars internally)
- `OPTIONS`: 0 (not sampled) or 1 (sampled)

Example:

```text
X-Cloud-Trace-Context: 105445aa7843bc8bf206b12000100000/12345678901234567;o=1
```

AgentTrace also supports W3C Trace Context (`traceparent` header) which GCP natively understands.

## Session Tracking for Multi-Turn

Use session IDs to correlate multi-turn conversations:

```python
from agenttrace.core.models import AgentRun

# Create run with session ID
run = AgentRun(
    name="conversation",
    start_time=datetime.now(UTC),
    session_id="user-session-abc123",  # Links all turns
)

# Each turn in the conversation uses the same session_id
# Traces will be correlated in Cloud Trace
```

## OTel GenAI Semantic Conventions

AgentTrace exports traces following OTel GenAI semantic conventions:

### Agent Spans

| Attribute | Description |
|-----------|-------------|
| `gen_ai.agent.name` | Human-readable agent name |
| `gen_ai.agent.id` | Unique agent identifier |
| `gen_ai.agent.description` | Agent description |
| `gen_ai.operation.name` | "invoke_agent" |

### LLM Spans

| Attribute | Description |
|-----------|-------------|
| `gen_ai.request.model` | Model name (e.g., "gemini-1.5-pro") |
| `gen_ai.system` | Provider (e.g., "google") |
| `gen_ai.usage.input_tokens` | Input token count |
| `gen_ai.usage.output_tokens` | Output token count |

### Content Recording

When enabled, also includes:

| Attribute | Description |
|-----------|-------------|
| `gen_ai.request.messages` | Prompt content (JSON) |
| `gen_ai.response.messages` | Response content (JSON) |

## Reasoning Engine Integration

For Vertex AI Reasoning Engine:

```python
exporter = create_vertex_agent_exporter(
    project_id="your-project-id",
    reasoning_engine_id="projects/123/locations/us-central1/reasoningEngines/456",
    agent_name="reasoning-agent",
)
```

## LangChain Integration

Use `VertexAITracerAdapter` for LangChain compatibility:

```python
from agenttrace.contrib.gcp import VertexAITracerAdapter

adapter = VertexAITracerAdapter(
    project_id="your-project-id",
    enable_content_recording=True,
    agent_name="langchain-agent",
)

# Use as LangChain callback
chain.invoke({"input": "..."}, config={"callbacks": [adapter]})
```

## Viewing Traces

1. Go to GCP Console > Cloud Trace
2. Click **Trace List**
3. Filter by:
   - Service name
   - Time range
   - Latency
4. Click a trace to see the call tree and timeline

## Best Practices

1. **Never enable content recording in production** unless your data handling policies explicitly allow it
2. **Use Workload Identity** instead of service account keys in GKE
3. **Set meaningful agent names** to make traces discoverable
4. **Use session IDs** for multi-turn conversation correlation
5. **Monitor Cloud Trace quotas** - free tier has limits

## Troubleshooting

### Traces Not Appearing

1. Verify Cloud Trace API is enabled
2. Check service account has `roles/cloudtrace.agent` role
3. Verify Application Default Credentials are configured
4. Wait 1-2 minutes for traces to appear

### Missing Attributes

1. Verify OTel GenAI attributes are enabled
2. Check that agent_name/agent_id are set
3. Ensure content_recording is enabled if you need prompts

### Authentication Errors

```bash
# Verify ADC is configured
gcloud auth application-default print-access-token

# Re-authenticate if needed
gcloud auth application-default login
```

### IAM Permissions

Required IAM roles:

- `roles/cloudtrace.agent` - Write traces
- `roles/cloudtrace.user` - Read traces (for viewing)

## References

- [Google Cloud Trace Documentation](https://cloud.google.com/trace/docs)
- [Vertex AI Agent Builder](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-builder/overview)
- [OTel GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [Cloud Trace Header Format](https://cloud.google.com/trace/docs/setup#force-trace)
