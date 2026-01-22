"""
Tests for multiple runtime instances and context scoping.

Verifies that:
- Multiple runtime instances can be created with different configs
- Trace context is properly isolated between runtimes
- Decorators work with explicit runtime parameter
- trace_context() properly scopes runtime selection
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from agenttrace.core.config import AgentTraceConfig, RedactionConfig
from agenttrace.core.context import (
    get_current_runtime,
    runtime_context,
)
from agenttrace.core.runtime import TALRuntime
from agenttrace.instrumentation.decorators import trace_agent, trace_llm, trace_tool


class TestMultipleRuntimeInstances:
    """Tests for creating and managing multiple runtime instances."""

    def test_create_multiple_runtimes(self) -> None:
        """Can create multiple runtime instances with different configs."""
        config_a = AgentTraceConfig(
            service_name="service-a",
            console_enabled=False,
            jsonl_enabled=False,
        )
        config_b = AgentTraceConfig(
            service_name="service-b",
            console_enabled=False,
            jsonl_enabled=False,
        )

        runtime_a = TALRuntime(console=False, jsonl=False, config=config_a)
        runtime_b = TALRuntime(console=False, jsonl=False, config=config_b)

        assert runtime_a is not runtime_b
        assert runtime_a._config.service_name == "service-a"
        assert runtime_b._config.service_name == "service-b"

    def test_runtimes_have_independent_configs(self) -> None:
        """Runtime instances maintain independent configurations."""
        config_a = AgentTraceConfig(
            service_name="tenant-a",
            console_enabled=False,
            jsonl_enabled=False,
            redaction=RedactionConfig(enabled=True),
        )
        config_b = AgentTraceConfig(
            service_name="tenant-b",
            console_enabled=False,
            jsonl_enabled=False,
            redaction=RedactionConfig(enabled=False),
        )

        runtime_a = TALRuntime(console=False, jsonl=False, config=config_a)
        runtime_b = TALRuntime(console=False, jsonl=False, config=config_b)

        # Verify configs are independent
        assert runtime_a._config.redaction.enabled is True
        assert runtime_b._config.redaction.enabled is False

    def test_runtime_has_trace_context_method(self) -> None:
        """Runtime instances have trace_context() method."""
        runtime = TALRuntime(console=False, jsonl=False)
        assert hasattr(runtime, "trace_context")
        assert callable(runtime.trace_context)


class TestTraceContextScoping:
    """Tests for trace_context() context manager scoping."""

    def test_trace_context_sets_current_runtime(self) -> None:
        """trace_context() sets the runtime in context."""
        runtime = TALRuntime(console=False, jsonl=False)

        # Before entering context
        assert get_current_runtime() is None

        with runtime.trace_context():
            # Inside context
            assert get_current_runtime() is runtime

        # After exiting context
        assert get_current_runtime() is None

    def test_trace_context_restores_previous_runtime(self) -> None:
        """trace_context() restores previous runtime on exit."""
        runtime_a = TALRuntime(console=False, jsonl=False)
        runtime_b = TALRuntime(console=False, jsonl=False)

        with runtime_a.trace_context():
            assert get_current_runtime() is runtime_a

            with runtime_b.trace_context():
                assert get_current_runtime() is runtime_b

            # Back to runtime_a
            assert get_current_runtime() is runtime_a

        # Back to none
        assert get_current_runtime() is None

    def test_standalone_runtime_context_function(self) -> None:
        """runtime_context() function works independently."""
        runtime = TALRuntime(console=False, jsonl=False)

        with runtime_context(runtime):
            assert get_current_runtime() is runtime

        assert get_current_runtime() is None


class TestRuntimeIsolation:
    """Tests for trace isolation between runtimes."""

    def test_runs_are_isolated_between_runtimes(self) -> None:
        """Runs from different runtimes don't leak into each other."""
        mock_exporter_a = MagicMock()
        mock_exporter_b = MagicMock()

        config_a = AgentTraceConfig(
            service_name="service-a",
            console_enabled=False,
            jsonl_enabled=False,
        )
        config_b = AgentTraceConfig(
            service_name="service-b",
            console_enabled=False,
            jsonl_enabled=False,
        )

        runtime_a = TALRuntime(
            console=False,
            jsonl=False,
            config=config_a,
            exporters=[mock_exporter_a],
        )
        runtime_b = TALRuntime(
            console=False,
            jsonl=False,
            config=config_b,
            exporters=[mock_exporter_b],
        )

        # Start runs in each runtime using context manager
        with runtime_a.trace_context():
            with runtime_a.run("run_a") as run_a:
                pass  # Run completes on exit

        with runtime_b.trace_context():
            with runtime_b.run("run_b") as run_b:
                pass  # Run completes on exit

        # Each exporter should only see its own runs
        assert mock_exporter_a.export.call_count == 1
        assert mock_exporter_b.export.call_count == 1

        exported_a = mock_exporter_a.export.call_args[0][0]
        exported_b = mock_exporter_b.export.call_args[0][0]

        assert exported_a.name == "run_a"
        assert exported_b.name == "run_b"

    def test_concurrent_runtimes_stay_isolated(self) -> None:
        """Concurrent contexts with different runtimes stay isolated."""
        runtime_a = TALRuntime(console=False, jsonl=False)
        runtime_b = TALRuntime(console=False, jsonl=False)

        async def check_runtime_a() -> TALRuntime | None:
            with runtime_a.trace_context():
                await asyncio.sleep(0.01)  # Simulate async work
                return get_current_runtime()

        async def check_runtime_b() -> TALRuntime | None:
            with runtime_b.trace_context():
                await asyncio.sleep(0.01)  # Simulate async work
                return get_current_runtime()

        async def run_concurrent() -> tuple[TALRuntime | None, TALRuntime | None]:
            results = await asyncio.gather(
                check_runtime_a(),
                check_runtime_b(),
            )
            return results[0], results[1]

        result_a, result_b = asyncio.run(run_concurrent())

        # Each task should see its own runtime
        assert result_a is runtime_a
        assert result_b is runtime_b


class TestDecoratorWithExplicitRuntime:
    """Tests for decorators with explicit runtime parameter."""

    def test_trace_agent_with_runtime_param(self) -> None:
        """@trace_agent with runtime parameter uses specified runtime."""
        mock_exporter = MagicMock()
        config = AgentTraceConfig(
            service_name="test-service",
            console_enabled=False,
            jsonl_enabled=False,
        )
        runtime = TALRuntime(
            console=False,
            jsonl=False,
            config=config,
            exporters=[mock_exporter],
        )

        @trace_agent(name="my_agent", runtime=runtime)
        def my_agent(x: int) -> int:
            return x * 2

        # Run with runtime context
        with runtime.trace_context():
            with runtime.run("test_run") as run:
                result = my_agent(5)

        assert result == 10

    def test_trace_tool_with_runtime_param(self) -> None:
        """@trace_tool with runtime parameter uses specified runtime."""
        runtime = TALRuntime(console=False, jsonl=False)

        @trace_tool(name="my_tool", runtime=runtime)
        def my_tool(query: str) -> str:
            return f"result: {query}"

        with runtime.trace_context():
            with runtime.run("test_run") as run:
                result = my_tool("test")

        assert result == "result: test"

    def test_trace_llm_with_runtime_param(self) -> None:
        """@trace_llm with runtime parameter uses specified runtime."""
        runtime = TALRuntime(console=False, jsonl=False)

        @trace_llm(name="my_llm", model="gpt-4", runtime=runtime)
        def my_llm(prompt: str) -> str:
            return f"response to: {prompt}"

        with runtime.trace_context():
            with runtime.run("test_run") as run:
                result = my_llm("hello")

        assert result == "response to: hello"

    @pytest.mark.asyncio
    async def test_async_decorator_with_runtime_param(self) -> None:
        """Async decorators work with runtime parameter."""
        runtime = TALRuntime(console=False, jsonl=False)

        @trace_agent(name="async_agent", runtime=runtime)
        async def async_agent(x: int) -> int:
            await asyncio.sleep(0.001)
            return x * 2

        with runtime.trace_context():
            with runtime.run("test_run") as run:
                result = await async_agent(10)

        assert result == 20


class TestMultiTenantScenario:
    """Tests for multi-tenant usage patterns."""

    def test_tenant_specific_processing(self) -> None:
        """Different tenants can have different processor configurations."""
        # Tenant A: Redaction enabled
        config_a = AgentTraceConfig(
            service_name="tenant-a",
            console_enabled=False,
            jsonl_enabled=False,
            redaction=RedactionConfig(enabled=True),
        )

        # Tenant B: Redaction disabled
        config_b = AgentTraceConfig(
            service_name="tenant-b",
            console_enabled=False,
            jsonl_enabled=False,
            redaction=RedactionConfig(enabled=False),
        )

        runtime_a = TALRuntime(console=False, jsonl=False, config=config_a)
        runtime_b = TALRuntime(console=False, jsonl=False, config=config_b)

        # Verify configurations
        assert runtime_a._config.redaction.enabled is True
        assert runtime_b._config.redaction.enabled is False

        # Both runtimes work independently
        with runtime_a.trace_context():
            with runtime_a.run("tenant_a_run") as run_a:
                pass

        with runtime_b.trace_context():
            with runtime_b.run("tenant_b_run") as run_b:
                pass

    def test_runtime_factory_pattern(self) -> None:
        """Factory pattern for creating tenant-specific runtimes."""
        tenant_runtimes: dict[str, TALRuntime] = {}

        def get_runtime_for_tenant(tenant_id: str) -> TALRuntime:
            if tenant_id not in tenant_runtimes:
                config = AgentTraceConfig(
                    service_name=f"tenant-{tenant_id}",
                    console_enabled=False,
                    jsonl_enabled=False,
                )
                tenant_runtimes[tenant_id] = TALRuntime(
                    console=False,
                    jsonl=False,
                    config=config,
                )
            return tenant_runtimes[tenant_id]

        # Create runtimes for different tenants
        runtime_1 = get_runtime_for_tenant("001")
        runtime_2 = get_runtime_for_tenant("002")
        runtime_1_again = get_runtime_for_tenant("001")

        # Same tenant gets same runtime
        assert runtime_1 is runtime_1_again
        # Different tenants get different runtimes
        assert runtime_1 is not runtime_2

        # Configs are correct
        assert runtime_1._config.service_name == "tenant-001"
        assert runtime_2._config.service_name == "tenant-002"


class TestAsyncContextHelpers:
    """Tests for async context helpers with runtime context."""

    @pytest.mark.asyncio
    async def test_gather_with_context_preserves_runtime(self) -> None:
        """gather_with_context preserves runtime in all tasks."""
        from agenttrace.contrib.async_helpers import gather_with_context

        runtime = TALRuntime(console=False, jsonl=False)
        results = []

        async def task1() -> str:
            results.append(("task1", get_current_runtime()))
            return "result1"

        async def task2() -> str:
            results.append(("task2", get_current_runtime()))
            return "result2"

        with runtime.trace_context():
            await gather_with_context(task1(), task2())

        # Both tasks should have seen the runtime
        assert len(results) == 2
        for name, captured_runtime in results:
            assert captured_runtime is runtime, f"{name} didn't see runtime"

    @pytest.mark.asyncio
    async def test_capture_restore_context_with_runtime(self) -> None:
        """capture_context() and restore_context() work with runtime."""
        from agenttrace.contrib.async_helpers import capture_context, restore_context

        runtime = TALRuntime(console=False, jsonl=False)

        with runtime.trace_context():
            ctx = capture_context()

        # Outside context
        assert get_current_runtime() is None

        # Restore context
        with restore_context(ctx):
            assert get_current_runtime() is runtime

        # Outside again
        assert get_current_runtime() is None


class TestMaxStepDepthConfiguration:
    """Tests for configurable max step depth."""

    def test_default_max_step_depth(self) -> None:
        """Default max_step_depth is 100."""
        config = AgentTraceConfig(
            console_enabled=False,
            jsonl_enabled=False,
        )
        assert config.max_step_depth == 100

    def test_custom_max_step_depth(self) -> None:
        """Can configure custom max_step_depth."""
        config = AgentTraceConfig(
            console_enabled=False,
            jsonl_enabled=False,
            max_step_depth=50,
        )
        assert config.max_step_depth == 50

    def test_unlimited_max_step_depth(self) -> None:
        """Can set max_step_depth to None for unlimited."""
        config = AgentTraceConfig(
            console_enabled=False,
            jsonl_enabled=False,
            max_step_depth=None,
        )
        assert config.max_step_depth is None

    def test_runtime_uses_config_max_step_depth(self) -> None:
        """Runtime uses max_step_depth from config."""
        config = AgentTraceConfig(
            console_enabled=False,
            jsonl_enabled=False,
            max_step_depth=25,
        )
        runtime = TALRuntime(console=False, jsonl=False, config=config)

        assert runtime._config.max_step_depth == 25
