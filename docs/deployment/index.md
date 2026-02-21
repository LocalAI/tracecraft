# Deployment

Trace Craft is designed to run everywhere - from a developer laptop to high-throughput production
clusters on managed cloud platforms. This section covers how to configure, deploy, and operate
Trace Craft in each environment.

## Deployment Options

<div class="grid cards" markdown>

- :material-cog-outline:{ .lg .middle } __Production Configuration__

    ---

    Baseline settings for production: sampling, PII redaction, async export, health checks,
    and Docker/Compose recipes.

    [:octicons-arrow-right-24: Production Configuration](production.md)

- :simple-amazonaws:{ .lg .middle } __AWS AgentCore__

    ---

    Deploy Trace Craft alongside AWS Bedrock AgentCore. Covers IAM roles, CloudWatch
    integration, and ECS task definitions.

    [:octicons-arrow-right-24: AWS AgentCore](aws-agentcore.md)

- :simple-microsoftazure:{ .lg .middle } __Azure AI Foundry__

    ---

    Integrate with Azure AI Foundry agents. Includes managed identity setup, Azure Monitor
    export, and Container Apps deployment.

    [:octicons-arrow-right-24: Azure AI Foundry](azure-foundry.md)

- :simple-googlecloud:{ .lg .middle } __GCP Vertex Agent__

    ---

    Run Trace Craft with Vertex AI Agent Builder. Covers Workload Identity, Cloud Trace
    export, and Cloud Run deployment.

    [:octicons-arrow-right-24: GCP Vertex Agent](gcp-vertex-agent.md)

- :simple-kubernetes:{ .lg .middle } __Kubernetes__

    ---

    Complete Kubernetes deployment guide: Helm values, ConfigMaps, Secrets, sidecar
    collectors, and HPA configuration.

    [:octicons-arrow-right-24: Kubernetes](kubernetes.md)

- :material-speedometer:{ .lg .middle } __High Throughput__

    ---

    Optimize for millions of traces per day. Covers async batching, aggressive sampling,
    queue tuning, and benchmarks.

    [:octicons-arrow-right-24: High Throughput](high-throughput.md)

</div>

## Choosing a Deployment Model

| Scenario | Recommended Guide |
|----------|------------------|
| First production deployment | [Production Configuration](production.md) |
| Running on AWS Bedrock | [AWS AgentCore](aws-agentcore.md) |
| Running on Azure AI Foundry | [Azure AI Foundry](azure-foundry.md) |
| Running on GCP Vertex AI | [GCP Vertex Agent](gcp-vertex-agent.md) |
| Kubernetes cluster | [Kubernetes](kubernetes.md) |
| Very high trace volume | [High Throughput](high-throughput.md) |

## Quick Start: Production-Ready Config

The following configuration is a safe starting point for any production deployment. Adjust
`sampling_rate` and exporter settings to match your environment.

```python title="app.py"
import os
import tracecraft

tracecraft.init(
    service_name=os.getenv("SERVICE_NAME", "my-agent"),
    environment="production",
    console=False,
    otlp_endpoint=os.getenv("OTLP_ENDPOINT"),
    sampling_rate=float(os.getenv("TRACECRAFT_SAMPLING_RATE", "0.1")),
    always_keep_errors=True,
    enable_pii_redaction=True,
)
```

```bash title=".env.production"
SERVICE_NAME=my-agent
OTLP_ENDPOINT=https://otlp.example.com:4317
TRACECRAFT_SAMPLING_RATE=0.1
```

## Next Steps

Start with [Production Configuration](production.md) for the foundational settings, then move to
the platform-specific guide that matches your infrastructure.
