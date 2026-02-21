# Cloud Platform Integrations

Trace Craft integrates with major cloud AI platforms.

## Supported Platforms

| Platform | Status | Installation |
|----------|--------|--------------|
| AWS AgentCore | Stable | `tracecraft[aws-agentcore]` |
| Azure AI Foundry | Stable | `tracecraft[azure-foundry]` |
| GCP Vertex Agent Builder | Stable | `tracecraft[gcp-vertex-agent]` |
| All Platforms | - | `tracecraft[cloud]` |

## AWS AgentCore

Integration with AWS Bedrock AgentCore.

### Installation

```bash
pip install "tracecraft[aws-agentcore]"
```

### Configuration

```python
from tracecraft.core.config import TraceCraftConfig, AWSAgentCoreConfig

config = TraceCraftConfig(
    aws_agentcore=AWSAgentCoreConfig(
        enabled=True,
        use_xray_propagation=True,
        session_id="conversation-123",
    )
)

tracecraft.init(config=config)
```

### Environment Variables

```bash
export TRACECRAFT_AWS_AGENTCORE_ENABLED=true
export TRACECRAFT_AWS_XRAY_PROPAGATION=true
export TRACECRAFT_AWS_SESSION_ID=conversation-123
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317  # ADOT collector
```

### Features

- X-Ray trace propagation
- Session tracking
- CloudWatch Logs integration
- ADOT collector support

See [AWS AgentCore Deployment](../deployment/aws-agentcore.md) for details.

## Azure AI Foundry

Integration with Azure AI Foundry (Project Geneva).

### Installation

```bash
pip install "tracecraft[azure-foundry]"
```

### Configuration

```python
from tracecraft.core.config import TraceCraftConfig, AzureFoundryConfig

config = TraceCraftConfig(
    azure_foundry=AzureFoundryConfig(
        enabled=True,
        connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"],
        enable_content_recording=True,
        agent_name="customer-support",
        agent_id="agent-v1",
    )
)

tracecraft.init(config=config)
```

### Environment Variables

```bash
export TRACECRAFT_AZURE_FOUNDRY_ENABLED=true
export APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=..."
export TRACECRAFT_AZURE_CONTENT_RECORDING=true
export TRACECRAFT_AZURE_AGENT_NAME=customer-support
```

### Features

- Application Insights integration
- Agent metadata tracking
- Content recording (prompts/responses)
- Azure Monitor compatibility

See [Azure AI Foundry Deployment](../deployment/azure-foundry.md) for details.

## GCP Vertex Agent Builder

Integration with Google Cloud Vertex AI Agent Builder.

### Installation

```bash
pip install "tracecraft[gcp-vertex-agent]"
```

### Configuration

```python
from tracecraft.core.config import TraceCraftConfig, GCPVertexAgentConfig

config = TraceCraftConfig(
    gcp_vertex_agent=GCPVertexAgentConfig(
        enabled=True,
        project_id="my-project",
        session_id="session-123",
        agent_name="support-agent",
        enable_content_recording=True,
    )
)

tracecraft.init(config=config)
```

### Environment Variables

```bash
export TRACECRAFT_GCP_VERTEX_ENABLED=true
export GOOGLE_CLOUD_PROJECT=my-project
export TRACECRAFT_GCP_SESSION_ID=session-123
export TRACECRAFT_GCP_AGENT_NAME=support-agent
```

### Features

- Cloud Trace integration
- Agent session tracking
- Content recording
- Vertex AI compatibility

See [GCP Vertex Agent Deployment](../deployment/gcp-vertex-agent.md) for details.

## Multi-Cloud

Use Trace Craft with multiple cloud platforms:

```python
config = TraceCraftConfig(
    # AWS
    aws_agentcore=AWSAgentCoreConfig(enabled=True),

    # Azure
    azure_foundry=AzureFoundryConfig(
        enabled=True,
        connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"],
    ),

    # GCP
    gcp_vertex_agent=GCPVertexAgentConfig(
        enabled=True,
        project_id=os.environ["GOOGLE_CLOUD_PROJECT"],
    ),
)

tracecraft.init(config=config)
```

## Next Steps

- [AWS AgentCore Deployment](../deployment/aws-agentcore.md)
- [Azure AI Foundry Deployment](../deployment/azure-foundry.md)
- [GCP Vertex Agent Deployment](../deployment/gcp-vertex-agent.md)
- [Configuration](../user-guide/configuration.md)
