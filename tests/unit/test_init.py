"""
Tests for agenttrace.init() API.

TDD approach: These tests are written BEFORE the implementation.
"""

import tempfile
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path


class TestInit:
    """Tests for the init() function."""

    def test_init_returns_runtime(self):
        """init() should return a runtime instance."""
        import agenttrace

        runtime = agenttrace.init()
        assert runtime is not None
        runtime.shutdown()

    def test_init_enables_console_by_default(self):
        """init() should enable console exporter by default."""
        import agenttrace

        runtime = agenttrace.init()
        assert runtime.has_exporter("console")
        runtime.shutdown()

    def test_init_can_disable_console(self):
        """init() should allow disabling console exporter."""
        import agenttrace

        runtime = agenttrace.init(console=False)
        assert not runtime.has_exporter("console")
        runtime.shutdown()

    def test_init_enables_jsonl_by_default(self):
        """init() should enable JSONL exporter by default."""
        import agenttrace

        runtime = agenttrace.init()
        assert runtime.has_exporter("jsonl")
        runtime.shutdown()

    def test_init_can_disable_jsonl(self):
        """init() should allow disabling JSONL exporter."""
        import agenttrace

        runtime = agenttrace.init(jsonl=False)
        assert not runtime.has_exporter("jsonl")
        runtime.shutdown()

    def test_init_custom_jsonl_path(self):
        """init() should accept custom JSONL file path."""
        import agenttrace

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "custom_traces.jsonl"
            runtime = agenttrace.init(jsonl_path=str(filepath))

            # Trigger export by running a traced function
            from agenttrace.core.models import AgentRun

            run = AgentRun(name="test", start_time=datetime.now(UTC))
            runtime.export(run)

            assert filepath.exists()
            runtime.shutdown()

    def test_init_custom_exporters(self):
        """init() should accept custom exporters list."""
        import agenttrace
        from agenttrace.exporters.base import BaseExporter

        class CustomExporter(BaseExporter):
            def __init__(self):
                self.exported = []

            def export(self, run):
                self.exported.append(run)

        custom = CustomExporter()
        runtime = agenttrace.init(exporters=[custom], console=False, jsonl=False)

        from agenttrace.core.models import AgentRun

        run = AgentRun(name="test", start_time=datetime.now(UTC))
        runtime.export(run)

        assert len(custom.exported) == 1
        runtime.shutdown()

    def test_init_is_idempotent(self):
        """Multiple init() calls should return the same runtime."""
        import agenttrace

        runtime1 = agenttrace.init()
        runtime2 = agenttrace.init()
        assert runtime1 is runtime2
        runtime1.shutdown()


class TestRuntime:
    """Tests for the TALRuntime class."""

    def test_runtime_start_run_creates_run(self):
        """start_run should create and return an AgentRun."""
        import agenttrace

        runtime = agenttrace.init()
        run = runtime.start_run("test_agent")

        assert run is not None
        assert run.name == "test_agent"
        runtime.shutdown()

    def test_runtime_end_run_finalizes_run(self):
        """end_run should finalize and export the run."""
        import agenttrace

        runtime = agenttrace.init(console=False, jsonl=False)
        run = runtime.start_run("test_agent")
        runtime.end_run(run, output={"result": "done"})

        assert run.end_time is not None
        assert run.output == {"result": "done"}
        runtime.shutdown()

    def test_runtime_context_manager(self):
        """Runtime should work as context manager for runs."""
        import agenttrace

        runtime = agenttrace.init(console=False, jsonl=False)

        with runtime.run("managed_run") as run:
            assert run is not None
            assert run.name == "managed_run"

        assert run.end_time is not None
        runtime.shutdown()


class TestPublicAPI:
    """Tests for the public API surface."""

    def test_trace_agent_is_exported(self):
        """trace_agent should be available from the package."""
        from agenttrace import trace_agent

        assert callable(trace_agent)

    def test_trace_tool_is_exported(self):
        """trace_tool should be available from the package."""
        from agenttrace import trace_tool

        assert callable(trace_tool)

    def test_trace_llm_is_exported(self):
        """trace_llm should be available from the package."""
        from agenttrace import trace_llm

        assert callable(trace_llm)

    def test_trace_retrieval_is_exported(self):
        """trace_retrieval should be available from the package."""
        from agenttrace import trace_retrieval

        assert callable(trace_retrieval)

    def test_step_is_exported(self):
        """step context manager should be available from the package."""
        from agenttrace import step

        assert callable(step)

    def test_models_are_exported(self):
        """Core models should be available from the package."""
        from agenttrace import AgentRun, Step, StepType

        assert AgentRun is not None
        assert Step is not None
        assert StepType is not None


class TestIntegration:
    """Integration tests for the full flow."""

    def test_decorated_function_exports_trace(self):
        """Decorated function should produce a trace that gets exported."""
        import agenttrace
        from agenttrace import trace_agent, trace_tool

        output = StringIO()
        runtime = agenttrace.init(console_file=output, jsonl=False)

        @trace_tool(name="inner_tool")
        def inner():
            return "tool result"

        @trace_agent(name="outer_agent")
        def outer():
            return inner()

        with runtime.run("integration_test"):
            outer()

        # Output should contain our trace
        output_str = output.getvalue()
        assert "integration_test" in output_str or len(output_str) > 0

        runtime.shutdown()

    def test_async_decorated_function_exports_trace(self):
        """Async decorated function should produce a trace that gets exported."""
        import asyncio

        import agenttrace
        from agenttrace import trace_agent

        output = StringIO()
        runtime = agenttrace.init(console_file=output, jsonl=False)

        @trace_agent(name="async_agent")
        async def async_func():
            await asyncio.sleep(0.001)
            return "async result"

        async def test():
            with runtime.run("async_test"):
                await async_func()

        asyncio.run(test())

        output_str = output.getvalue()
        assert len(output_str) > 0

        runtime.shutdown()
