# Remote Trace Sources

Trace Craft's TUI can pull traces that already live in your cloud observability platform — no need to copy data locally. Connect directly to AWS X-Ray, GCP Cloud Trace, Azure Monitor, or DataDog and browse those traces with the same interactive interface you use for locally-stored traces.

!!! info "Read-only connection"
    Remote backends are **read-only**. The TUI fetches and displays traces; it never writes, modifies, or deletes records in your platform. `save()` and `delete()` operations always raise `NotImplementedError`.

---

## Supported Platforms

| Platform | URL Scheme | Extra | Auth |
|----------|-----------|-------|------|
| AWS X-Ray (AgentCore) | `xray://region/service` | `storage-xray` | boto3 credential chain |
| GCP Cloud Trace (Vertex AI) | `cloudtrace://project/service` | `storage-cloudtrace` | ADC (`google.auth.default()`) |
| Azure Monitor (AI Foundry) | `azuremonitor://workspace-id/service` | `storage-azuremonitor` | `DefaultAzureCredential` |
| DataDog APM | `datadog://site/service` | `storage-datadog` | `DD_API_KEY` + `DD_APP_KEY` |

---

## Installation

Install the extras for the platform(s) you use:

```bash
# Individual platforms
pip install "tracecraft[storage-xray]"
pip install "tracecraft[storage-cloudtrace]"
pip install "tracecraft[storage-azuremonitor]"
pip install "tracecraft[storage-datadog]"

# All remote backends at once
pip install "tracecraft[storage-all]"

# Already covered by the cloud bundle
pip install "tracecraft[cloud]"
```

---

## AWS X-Ray

### Quick Start

```bash
# Browse all traces in us-east-1 from the last hour
tracecraft tui xray://us-east-1/

# Filter to a specific service
tracecraft tui xray://us-east-1/my-bedrock-agent
```

### Authentication

Uses the standard **boto3 credential chain** — no credentials are stored in the config file:

1. Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`
2. AWS profile: `~/.aws/credentials` (selected by `AWS_PROFILE`)
3. IAM instance profile / ECS task role / EKS IRSA (in EC2/ECS/EKS environments)
4. AWS SSO

```bash
# Required IAM permissions:
# xray:GetTraceSummaries
# xray:BatchGetTraces
```

### Config File

```yaml
# .tracecraft/config.yaml
default:
  storage:
    type: xray
    xray_region: us-east-1
    xray_service_name: my-bedrock-agent   # optional
    xray_lookback_hours: 1
    xray_cache_ttl_seconds: 60
```

---

## GCP Cloud Trace

### Quick Start

```bash
# Set your project (or use GOOGLE_CLOUD_PROJECT env var)
export GOOGLE_CLOUD_PROJECT=my-gcp-project

# Browse all traces
tracecraft tui cloudtrace://my-gcp-project/

# Filter to a specific service
tracecraft tui cloudtrace://my-gcp-project/my-vertex-agent
```

### Authentication

Uses **Application Default Credentials** (`google.auth.default()`) — no credentials are stored in the config file:

1. Workload Identity (GKE, Cloud Run)
2. `gcloud auth application-default login`
3. `GOOGLE_APPLICATION_CREDENTIALS` env var pointing to a service account key file

```bash
# Required IAM roles:
# roles/cloudtrace.viewer
```

### Config File

```yaml
# .tracecraft/config.yaml
default:
  storage:
    type: cloudtrace
    cloudtrace_project_id: my-gcp-project   # or set GOOGLE_CLOUD_PROJECT
    cloudtrace_service_name: my-agent       # optional
    cloudtrace_lookback_hours: 1
    cloudtrace_cache_ttl_seconds: 60
```

---

## Azure Monitor (Application Insights)

### Quick Start

```bash
# Set your workspace ID
export AZURE_MONITOR_WORKSPACE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

tracecraft tui azuremonitor://xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/

# Filter to a service (cloud_RoleName)
tracecraft tui azuremonitor://xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/my-ai-foundry-agent
```

### Authentication

Uses **`DefaultAzureCredential`** — no credentials are stored in the config file:

1. Managed Identity (Azure VMs, App Service, AKS)
2. `az login` (Azure CLI)
3. Environment variables: `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`
4. VS Code Azure extension / Interactive browser

```bash
# Required Azure RBAC role:
# Log Analytics Reader
```

!!! warning "Workspace ID vs Connection String"
    The `workspace_id` is the **Log Analytics Workspace ID** (a GUID), not the Application Insights connection string or instrumentation key. Find it in the Azure Portal under your Log Analytics workspace → Overview → Workspace ID.

### Config File

```yaml
# .tracecraft/config.yaml
default:
  storage:
    type: azuremonitor
    # Set AZURE_MONITOR_WORKSPACE_ID env var instead of hardcoding here
    azuremonitor_workspace_id: null
    azuremonitor_service_name: my-agent     # optional (cloud_RoleName)
    azuremonitor_lookback_hours: 1
    azuremonitor_cache_ttl_seconds: 60
```

---

## DataDog APM

### Quick Start

```bash
# Set credentials via env vars (never in config files)
export DD_API_KEY=your_api_key
export DD_APP_KEY=your_application_key

# US1 site (default)
tracecraft tui datadog://us1/my-service

# EU site
tracecraft tui datadog://eu1/my-service
```

### Authentication

Requires **two environment variables** set at shell level:

| Variable | Description |
|----------|-------------|
| `DD_API_KEY` | DataDog API key (from Organization Settings → API Keys) |
| `DD_APP_KEY` | DataDog Application key (from Organization Settings → Application Keys) |

!!! danger "Never put DataDog credentials in config files"
    `DD_API_KEY` and `DD_APP_KEY` must be set as environment variables. Trace Craft validates at startup that both are present and raises `ValueError` with a clear error message if either is missing.

### Supported Sites

| Site Key | API Host |
|----------|----------|
| `us1` (default) | `api.datadoghq.com` |
| `us3` | `api.us3.datadoghq.com` |
| `us5` | `api.us5.datadoghq.com` |
| `eu1` | `api.datadoghq.eu` |
| `ap1` | `api.ap1.datadoghq.com` |

### Config File

```yaml
# .tracecraft/config.yaml
default:
  storage:
    type: datadog
    datadog_site: us1
    datadog_service: my-service   # optional
    datadog_lookback_hours: 1
    datadog_cache_ttl_seconds: 60
# Secrets: set DD_API_KEY and DD_APP_KEY as environment variables
```

---

## Caching and Rate Limiting

All remote backends use an in-memory TTL cache (default: **60 seconds**) to prevent excessive API calls when the TUI polls for new traces.

- The TUI polls every ~1 second; without caching this would hammer platform APIs
- Cache is per-store instance; it resets when the TUI process restarts
- Press **R** in the TUI to force a cache refresh (calls `invalidate_cache()`)
- Tune `*_cache_ttl_seconds` in the config file to balance freshness vs. API cost

---

## Data Mapping

### What Gets Populated

Remote backends map platform-specific spans to Trace Craft's canonical `AgentRun` and `Step` models. The accuracy of LLM-specific fields depends on whether your instrumentation wrote them:

| Field | Populated When |
|-------|---------------|
| `model_name` | `gen_ai.request.model` span attribute/annotation present |
| `input_tokens` | `gen_ai.usage.input_tokens` present |
| `output_tokens` | `gen_ai.usage.output_tokens` present |
| `cost_usd` | Not populated by remote backends |
| `cloud_provider` | Always set (`"aws"`, `"gcp"`, `"azure"`, `"datadog"`) |
| `cloud_trace_id` | Always set to the platform's native trace ID |

!!! tip "Best field coverage"
    If your agents are instrumented with Trace Craft's own decorators or the OpenTelemetry GenAI semantic conventions, all LLM fields will be populated when viewing traces from any platform.

### Step Type Inference

When reading from remote platforms, step types are inferred from span metadata:

| Platform | Signal | Mapped To |
|----------|--------|-----------|
| X-Ray | `namespace: "aws"` or HTTP subsegment | `TOOL` |
| X-Ray | `gen_ai.*` annotation | `LLM` |
| Cloud Trace | `span_kind: CLIENT/PRODUCER` | `TOOL` |
| Cloud Trace | `gen_ai.system` attribute | `LLM` |
| Azure Monitor | `AppDependencies` table | `TOOL` |
| Azure Monitor | `AppExceptions` table | `ERROR` |
| DataDog | `type: "web"`, `"db"` | `TOOL` |
| DataDog | `type: "llm"` | `LLM` |

---

## Troubleshooting

### Missing Optional Dependency

```
ImportError: boto3 is required for XRayTraceStore.
Install with: pip install tracecraft[storage-xray]
```

Install the required extra and retry.

### Authentication Error

**AWS:** Run `aws sts get-caller-identity` to verify credentials are configured.

**GCP:** Run `gcloud auth application-default print-access-token` to verify ADC.

**Azure:** Run `az account show` to verify CLI login. For managed identity issues, check that the correct role (`Log Analytics Reader`) is assigned.

**DataDog:** Verify `DD_API_KEY` and `DD_APP_KEY` are exported in your shell, not just set in `.env` files.

### No Traces Returned

- Increase `*_lookback_hours` — traces may be older than 1 hour
- Verify the service name matches exactly (case-sensitive)
- Check platform-specific sampling: if only 10% of traces are sampled, you may see an empty window during low traffic

### Slow TUI Response

Increase `*_cache_ttl_seconds` to reduce API call frequency:

```yaml
storage:
  type: xray
  xray_cache_ttl_seconds: 300  # 5 minutes
```
