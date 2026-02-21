# Azure AI Foundry Deployment Guide

Deploy Trace Craft-instrumented applications to Azure with AI Foundry observability.

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                        Azure Cloud                           │
│                                                              │
│  ┌─────────────────┐      ┌──────────────────────────────┐  │
│  │   Your Agent    │─────▶│    Application Insights       │  │
│  │  (Trace Craft    │      │   (AI Foundry Observability)  │  │
│  │   enabled)      │      └──────────────────────────────┘  │
│  └─────────────────┘                     │                  │
│                                          ▼                  │
│                          ┌──────────────────────────────┐   │
│                          │    Azure AI Foundry Portal    │   │
│                          │   (Trace Visualization)       │   │
│                          └──────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

- Azure subscription
- Application Insights resource
- Python 3.11+

## Quick Start

### 1. Get Connection String

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your Application Insights resource
3. Click **Overview** > **Connection String**
4. Copy the connection string

### 2. Install Trace Craft

```bash
pip install tracecraft[azure-foundry]
```

### 3. Configure Exporter

```python
import tracecraft
from tracecraft.contrib.azure import create_foundry_exporter

# Create exporter with AI Foundry features
exporter = create_foundry_exporter(
    # Get from Azure Portal (or set APPLICATIONINSIGHTS_CONNECTION_STRING env var)
    connection_string="InstrumentationKey=...;IngestionEndpoint=https://...",

    # Service name appears in Azure traces
    service_name="my-agent-service",

    # Enable content recording (prompts/responses)
    # WARNING: Only enable in dev or when data policies allow
    enable_content_recording=False,

    # Agent metadata
    agent_name="research-agent",
    agent_id="agent-001",
    agent_description="Researches topics and synthesizes information",
)

# Initialize Trace Craft
tracecraft.init(
    exporters=[exporter],
    console=False,  # Disable console in production
    jsonl=False,    # Disable local JSONL
)
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Azure connection string | Yes |
| `TRACECRAFT_AZURE_FOUNDRY_ENABLED` | Enable Azure export | No |
| `TRACECRAFT_AZURE_CONTENT_RECORDING` | Record prompts/responses | No |
| `TRACECRAFT_AZURE_AGENT_NAME` | Agent name for traces | No |
| `TRACECRAFT_AZURE_AGENT_ID` | Agent ID for traces | No |

## Azure Functions Deployment

```python
# function_app.py
import azure.functions as func
import tracecraft
from tracecraft.contrib.azure import configure_for_azure_functions

# Configure at function app startup
exporter = configure_for_azure_functions(service_name="my-function")
tracecraft.init(exporters=[exporter], console=False, jsonl=False)

app = func.FunctionApp()

@app.function_name("ProcessAgent")
@app.route(route="agent")
def process_agent(req: func.HttpRequest) -> func.HttpResponse:
    # Your traced agent code here
    pass
```

## Azure Kubernetes Service (AKS)

### 1. Store Connection String as Secret

```yaml
# azure-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: azure-appinsights
  namespace: default
type: Opaque
stringData:
  connection-string: "InstrumentationKey=...;IngestionEndpoint=..."
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
        - name: APPLICATIONINSIGHTS_CONNECTION_STRING
          valueFrom:
            secretKeyRef:
              name: azure-appinsights
              key: connection-string
        - name: TRACECRAFT_AZURE_AGENT_NAME
          value: "aks-research-agent"
```

### 3. Application Code

```python
from tracecraft.contrib.azure import configure_for_aks

exporter = configure_for_aks(service_name="my-aks-agent")
tracecraft.init(exporters=[exporter])
```

## OTel GenAI Semantic Conventions

Trace Craft exports traces following OTel GenAI semantic conventions:

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
| `gen_ai.request.model` | Model name (e.g., "gpt-4") |
| `gen_ai.system` | Provider (e.g., "openai") |
| `gen_ai.usage.input_tokens` | Input token count |
| `gen_ai.usage.output_tokens` | Output token count |

### Content Recording

When enabled, also includes:

| Attribute | Description |
|-----------|-------------|
| `gen_ai.request.messages` | Prompt content (JSON) |
| `gen_ai.response.messages` | Response content (JSON) |

## Viewing Traces

1. Go to Azure Portal > Application Insights
2. Click **Transaction Search**
3. Filter by:
   - Service name
   - Operation name
   - Time range
4. Click a trace to see the full call tree

## LangChain Integration

Use `AzureAITracerAdapter` for LangChain compatibility:

```python
from tracecraft.contrib.azure import AzureAITracerAdapter

adapter = AzureAITracerAdapter(
    enable_content_recording=True,
    agent_name="langchain-agent",
)

# Use as LangChain callback
chain.invoke({"input": "..."}, config={"callbacks": [adapter]})
```

## Best Practices

1. **Never enable content recording in production** unless your data handling policies explicitly allow it
2. **Use environment variables** for connection strings (never hardcode)
3. **Set meaningful agent names** to make traces discoverable
4. **Use session IDs** for multi-turn conversation correlation
5. **Monitor costs** - Application Insights ingestion has costs

## Troubleshooting

### Traces Not Appearing

1. Verify connection string is correct
2. Check network connectivity to Azure
3. Ensure Application Insights resource is in correct region
4. Wait 2-5 minutes for traces to appear

### Missing Attributes

1. Verify OTel GenAI attributes are enabled
2. Check that agent_name/agent_id are set
3. Ensure content_recording is enabled if you need prompts

## References

- [Azure AI Foundry Tracing](https://learn.microsoft.com/en-us/azure/ai-foundry/observability/concepts/trace-agent-concept)
- [Azure AI Foundry OpenTelemetry](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/azure-ai-foundry-advancing-opentelemetry-and-delivering-unified-multi-agent-obse/4456039)
- [OTel GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
