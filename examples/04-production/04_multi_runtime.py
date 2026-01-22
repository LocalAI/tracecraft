#!/usr/bin/env python3
"""
Multi-Runtime Example

Demonstrates using multiple runtime instances for:
- Multi-tenant applications
- Different configurations per tenant/use case
- Runtime isolation
- Decorator with explicit runtime parameter
- Runtime factory pattern

Run: python examples/04-production/04_multi_runtime.py
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

from agenttrace import AgentTraceRuntime, trace_agent
from agenttrace.core.config import AgentTraceConfig, RedactionConfig, SamplingConfig
from agenttrace.core.context import get_current_runtime

# =============================================================================
# Demo 1: Creating Multiple Runtime Instances
# =============================================================================


def demo_multiple_runtimes():
    """Demonstrate creating multiple runtime instances."""
    print("\n" + "=" * 60)
    print("Demo 1: Creating Multiple Runtime Instances")
    print("=" * 60)

    # Tenant A configuration - high compliance
    config_a = AgentTraceConfig(
        service_name="tenant-a-service",
        redaction=RedactionConfig(enabled=True),  # Strict privacy
        sampling=SamplingConfig(rate=1.0),  # Keep all traces
        console_enabled=False,
        jsonl_enabled=False,
    )

    # Tenant B configuration - performance focused
    config_b = AgentTraceConfig(
        service_name="tenant-b-service",
        redaction=RedactionConfig(enabled=False),  # No redaction for internal use
        sampling=SamplingConfig(rate=0.1),  # Sample 10%
        console_enabled=False,
        jsonl_enabled=False,
    )

    runtime_a = AgentTraceRuntime(console=False, jsonl=False, config=config_a)
    runtime_b = AgentTraceRuntime(console=False, jsonl=False, config=config_b)

    print("\nRuntime A (High Compliance):")
    print(f"  Service: {runtime_a._config.service_name}")
    print(f"  Redaction: {runtime_a._config.redaction.enabled}")
    print(f"  Sampling: {runtime_a._config.sampling.rate * 100}%")

    print("\nRuntime B (Performance Focused):")
    print(f"  Service: {runtime_b._config.service_name}")
    print(f"  Redaction: {runtime_b._config.redaction.enabled}")
    print(f"  Sampling: {runtime_b._config.sampling.rate * 100}%")


# =============================================================================
# Demo 2: Runtime Context Scoping
# =============================================================================


def demo_runtime_context_scoping():
    """Demonstrate using trace_context() for runtime scoping."""
    print("\n" + "=" * 60)
    print("Demo 2: Runtime Context Scoping")
    print("=" * 60)

    # Create two runtimes
    runtime_a = AgentTraceRuntime(console=False, jsonl=False)
    runtime_b = AgentTraceRuntime(console=False, jsonl=False)

    print("\n--- Using trace_context() ---")

    # Before any context
    print(f"Outside context: current_runtime = {get_current_runtime()}")

    # Using runtime A
    with runtime_a.trace_context():
        current = get_current_runtime()
        print(f"Inside runtime_a context: is runtime_a = {current is runtime_a}")

        # Nested context with runtime B
        with runtime_b.trace_context():
            current = get_current_runtime()
            print(f"Inside nested runtime_b context: is runtime_b = {current is runtime_b}")

        # Back to runtime A
        current = get_current_runtime()
        print(f"Back to runtime_a context: is runtime_a = {current is runtime_a}")

    # Outside again
    print(f"Outside context again: current_runtime = {get_current_runtime()}")


# =============================================================================
# Demo 3: Decorator with Explicit Runtime
# =============================================================================


def demo_decorator_with_runtime():
    """Demonstrate using decorators with explicit runtime parameter."""
    print("\n" + "=" * 60)
    print("Demo 3: Decorator with Explicit Runtime")
    print("=" * 60)

    # Create tenant-specific runtimes
    tenant_a_runtime = AgentTraceRuntime(console=True, jsonl=False)
    tenant_b_runtime = AgentTraceRuntime(console=True, jsonl=False)

    # Define agents bound to specific runtimes
    @trace_agent(name="tenant_a_agent", runtime=tenant_a_runtime)
    def tenant_a_process(data: str) -> str:
        """Agent bound to tenant A runtime."""
        return f"Processed by A: {data}"

    @trace_agent(name="tenant_b_agent", runtime=tenant_b_runtime)
    def tenant_b_process(data: str) -> str:
        """Agent bound to tenant B runtime."""
        return f"Processed by B: {data}"

    print("\n--- Executing tenant-specific agents ---")
    print("(Each agent uses its bound runtime)")

    # Execute agents - each uses its own runtime
    with tenant_a_runtime.trace_context():
        with tenant_a_runtime.run("tenant_a_session"):
            result_a = tenant_a_process("Hello from A")
            print(f"Result A: {result_a}")

    with tenant_b_runtime.trace_context():
        with tenant_b_runtime.run("tenant_b_session"):
            result_b = tenant_b_process("Hello from B")
            print(f"Result B: {result_b}")


# =============================================================================
# Demo 4: Runtime Factory Pattern
# =============================================================================


def demo_runtime_factory():
    """Demonstrate the runtime factory pattern for multi-tenancy."""
    print("\n" + "=" * 60)
    print("Demo 4: Runtime Factory Pattern")
    print("=" * 60)

    # Runtime factory with caching
    class RuntimeFactory:
        """Factory for creating and caching tenant-specific runtimes."""

        def __init__(self):
            self._runtimes: dict[str, AgentTraceRuntime] = {}

        def get_runtime(self, tenant_id: str) -> AgentTraceRuntime:
            """Get or create runtime for tenant."""
            if tenant_id not in self._runtimes:
                # Create tenant-specific configuration
                config = AgentTraceConfig(
                    service_name=f"service-{tenant_id}",
                    redaction=RedactionConfig(enabled=True),
                    console_enabled=False,
                    jsonl_enabled=False,
                )

                self._runtimes[tenant_id] = AgentTraceRuntime(
                    console=False,
                    jsonl=False,
                    config=config,
                )
                print(f"  Created runtime for tenant: {tenant_id}")

            return self._runtimes[tenant_id]

        def list_tenants(self) -> list[str]:
            """List all tenant IDs with active runtimes."""
            return list(self._runtimes.keys())

    # Use the factory
    factory = RuntimeFactory()

    print("\n--- Getting runtimes for tenants ---")
    runtime_1 = factory.get_runtime("acme-corp")
    runtime_2 = factory.get_runtime("widget-co")
    runtime_1_again = factory.get_runtime("acme-corp")  # Should reuse

    print(f"\nActive tenants: {factory.list_tenants()}")
    print(f"Runtime reuse works: {runtime_1 is runtime_1_again}")


# =============================================================================
# Demo 5: Runtime Isolation Verification
# =============================================================================


def demo_runtime_isolation():
    """Verify that runtimes are properly isolated."""
    print("\n" + "=" * 60)
    print("Demo 5: Runtime Isolation Verification")
    print("=" * 60)

    # Create runtimes with mock exporters to track exports
    exports_a: list[Any] = []
    exports_b: list[Any] = []

    exporter_a = MagicMock()
    exporter_a.export.side_effect = lambda run: exports_a.append(run)

    exporter_b = MagicMock()
    exporter_b.export.side_effect = lambda run: exports_b.append(run)

    runtime_a = AgentTraceRuntime(
        console=False,
        jsonl=False,
        exporters=[exporter_a],
    )

    runtime_b = AgentTraceRuntime(
        console=False,
        jsonl=False,
        exporters=[exporter_b],
    )

    print("\n--- Processing requests in different runtimes ---")

    # Process in runtime A
    with runtime_a.trace_context():
        with runtime_a.run("request_from_tenant_a") as run_a:
            pass

    # Process in runtime B
    with runtime_b.trace_context():
        with runtime_b.run("request_from_tenant_b") as run_b:
            pass

    print(f"\nExports to Runtime A: {len(exports_a)} runs")
    print(f"  Run names: {[r.name for r in exports_a]}")

    print(f"\nExports to Runtime B: {len(exports_b)} runs")
    print(f"  Run names: {[r.name for r in exports_b]}")

    # Verify isolation
    assert len(exports_a) == 1
    assert len(exports_b) == 1
    assert exports_a[0].name == "request_from_tenant_a"
    assert exports_b[0].name == "request_from_tenant_b"
    print("\nIsolation verified! Each runtime only sees its own runs.")


# =============================================================================
# Demo 6: Concurrent Async Runtime Isolation
# =============================================================================


def demo_async_isolation():
    """Demonstrate runtime isolation in concurrent async code."""
    print("\n" + "=" * 60)
    print("Demo 6: Concurrent Async Runtime Isolation")
    print("=" * 60)

    runtime_a = AgentTraceRuntime(console=False, jsonl=False)
    runtime_b = AgentTraceRuntime(console=False, jsonl=False)

    async def process_tenant_a() -> AgentTraceRuntime | None:
        """Process request for tenant A."""
        with runtime_a.trace_context():
            await asyncio.sleep(0.01)  # Simulate async work
            return get_current_runtime()

    async def process_tenant_b() -> AgentTraceRuntime | None:
        """Process request for tenant B."""
        with runtime_b.trace_context():
            await asyncio.sleep(0.01)  # Simulate async work
            return get_current_runtime()

    async def run_concurrent():
        """Run both tenant processes concurrently."""
        results = await asyncio.gather(
            process_tenant_a(),
            process_tenant_b(),
        )
        return results

    print("\n--- Running concurrent tenant requests ---")
    result_a, result_b = asyncio.run(run_concurrent())

    print(f"Tenant A saw its runtime: {result_a is runtime_a}")
    print(f"Tenant B saw its runtime: {result_b is runtime_b}")

    assert result_a is runtime_a
    assert result_b is runtime_b
    print("\nAsync isolation verified! Each task sees its own runtime.")


# =============================================================================
# Demo 7: Real-World Multi-Tenant Service
# =============================================================================


def demo_real_world_service():
    """Demonstrate a real-world multi-tenant service pattern."""
    print("\n" + "=" * 60)
    print("Demo 7: Real-World Multi-Tenant Service Pattern")
    print("=" * 60)

    # Simulate incoming requests with tenant context
    class TenantContext:
        """Context for a tenant request."""

        def __init__(self, tenant_id: str, user_id: str):
            self.tenant_id = tenant_id
            self.user_id = user_id

    # Runtime factory with different configs per tenant tier
    tenant_configs = {
        "enterprise": AgentTraceConfig(
            service_name="enterprise-service",
            redaction=RedactionConfig(enabled=True),
            sampling=SamplingConfig(rate=1.0),  # Keep all
            console_enabled=False,
            jsonl_enabled=False,
        ),
        "standard": AgentTraceConfig(
            service_name="standard-service",
            redaction=RedactionConfig(enabled=True),
            sampling=SamplingConfig(rate=0.5),  # Keep 50%
            console_enabled=False,
            jsonl_enabled=False,
        ),
        "free": AgentTraceConfig(
            service_name="free-service",
            redaction=RedactionConfig(enabled=True),
            sampling=SamplingConfig(rate=0.1),  # Keep 10%
            console_enabled=False,
            jsonl_enabled=False,
        ),
    }

    tenant_tiers = {
        "acme-corp": "enterprise",
        "startup-inc": "standard",
        "hobby-user": "free",
    }

    runtimes: dict[str, AgentTraceRuntime] = {}

    def get_tenant_runtime(tenant_id: str) -> AgentTraceRuntime:
        """Get runtime for tenant based on their tier."""
        if tenant_id not in runtimes:
            tier = tenant_tiers.get(tenant_id, "free")
            config = tenant_configs[tier]
            runtimes[tenant_id] = AgentTraceRuntime(console=False, jsonl=False, config=config)
        return runtimes[tenant_id]

    def process_request(ctx: TenantContext, query: str) -> str:
        """Process a request with tenant-specific tracing."""
        runtime = get_tenant_runtime(ctx.tenant_id)

        @trace_agent(name="request_handler")
        def handle(query: str) -> str:
            return f"Response to: {query}"

        with runtime.trace_context():
            with runtime.run(f"request_{ctx.user_id}") as run:
                return handle(query)

    print("\n--- Processing requests from different tenants ---")

    # Enterprise tenant (100% sampled)
    ctx_enterprise = TenantContext("acme-corp", "user-001")
    result = process_request(ctx_enterprise, "Enterprise query")
    tier = tenant_tiers["acme-corp"]
    rate = tenant_configs[tier].sampling.rate
    print(f"Enterprise tenant ({rate * 100}% sampling): {result}")

    # Standard tenant (50% sampled)
    ctx_standard = TenantContext("startup-inc", "user-002")
    result = process_request(ctx_standard, "Standard query")
    tier = tenant_tiers["startup-inc"]
    rate = tenant_configs[tier].sampling.rate
    print(f"Standard tenant ({rate * 100}% sampling): {result}")

    # Free tenant (10% sampled)
    ctx_free = TenantContext("hobby-user", "user-003")
    result = process_request(ctx_free, "Free tier query")
    tier = tenant_tiers["hobby-user"]
    rate = tenant_configs[tier].sampling.rate
    print(f"Free tenant ({rate * 100}% sampling): {result}")


# =============================================================================
# Main
# =============================================================================


def main():
    """Run all multi-runtime demos."""
    print("\n" + "#" * 60)
    print("# AgentTrace Multi-Runtime Examples")
    print("#" * 60)

    demo_multiple_runtimes()
    demo_runtime_context_scoping()
    demo_decorator_with_runtime()
    demo_runtime_factory()
    demo_runtime_isolation()
    demo_async_isolation()
    demo_real_world_service()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
