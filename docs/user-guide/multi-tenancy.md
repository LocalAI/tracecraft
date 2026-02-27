# Multi-Tenancy

Handle multiple tenants with separate configurations using TraceCraft runtimes.

## Overview

TraceCraft supports multi-tenancy through isolated runtimes, each with its own configuration.

## Basic Multi-Tenancy

```python
from tracecraft import TraceCraftRuntime, TraceCraftConfig

# Create tenant-specific runtimes
tenant_a_runtime = TraceCraftRuntime(
    config=TraceCraftConfig(
        service_name="tenant-a",
        sampling_rate=1.0,
    )
)

tenant_b_runtime = TraceCraftRuntime(
    config=TraceCraftConfig(
        service_name="tenant-b",
        sampling_rate=0.1,
    )
)

# Use with context managers
with tenant_a_runtime.trace_context():
    process_tenant_a_request()

with tenant_b_runtime.trace_context():
    process_tenant_b_request()
```

## Decorator-Based

```python
@trace_agent(name="agent", runtime=tenant_a_runtime)
async def tenant_a_agent(input: str):
    return await process(input)

@trace_agent(name="agent", runtime=tenant_b_runtime)
async def tenant_b_agent(input: str):
    return await process(input)
```

## Dynamic Runtime Selection

```python
def get_runtime_for_tenant(tenant_id: str) -> TraceCraftRuntime:
    if tenant_id not in tenant_runtimes:
        tenant_runtimes[tenant_id] = TraceCraftRuntime(
            config=get_config_for_tenant(tenant_id)
        )
    return tenant_runtimes[tenant_id]

# Use it
runtime = get_runtime_for_tenant(request.tenant_id)
with runtime.trace_context():
    handle_request(request)
```

## Per-Tenant Configuration

```python
def get_config_for_tenant(tenant_id: str) -> TraceCraftConfig:
    tenant = load_tenant(tenant_id)
    return TraceCraftConfig(
        service_name=f"tenant-{tenant_id}",
        sampling_rate=tenant.sampling_rate,
        otlp_endpoint=tenant.otlp_endpoint,
        enable_pii_redaction=tenant.pii_redaction,
        tags=[f"tenant:{tenant_id}", f"tier:{tenant.tier}"],
    )
```

## Best Practices

1. Cache runtimes per tenant
2. Use tenant ID in service name
3. Configure per-tenant sampling
4. Isolate tenant data
5. Add tenant tags

## Next Steps

- [Configuration](configuration.md) - Configuration options
- [Deployment](../deployment/production.md) - Production patterns
