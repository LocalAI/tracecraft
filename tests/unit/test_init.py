"""
Tests for tracecraft.init() API.

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
        import tracecraft

        runtime = tracecraft.init()
        assert runtime is not None
        runtime.shutdown()

    def test_init_enables_console_by_default(self):
        """init() should enable console exporter by default."""
        import tracecraft

        runtime = tracecraft.init()
        assert runtime.has_exporter("console")
        runtime.shutdown()

    def test_init_can_disable_console(self):
        """init() should allow disabling console exporter."""
        import tracecraft

        runtime = tracecraft.init(console=False)
        assert not runtime.has_exporter("console")
        runtime.shutdown()

    def test_init_enables_jsonl_when_requested(self):
        """init() should enable JSONL exporter when explicitly requested."""
        import tracecraft

        # Use jsonl=True to explicitly enable JSONL exporter
        runtime = tracecraft.init(jsonl=True)
        assert runtime.has_exporter("jsonl")
        runtime.shutdown()

    def test_init_can_disable_jsonl(self):
        """init() should allow disabling JSONL exporter."""
        import tracecraft

        runtime = tracecraft.init(jsonl=False)
        assert not runtime.has_exporter("jsonl")
        runtime.shutdown()

    def test_init_custom_jsonl_path(self):
        """init() should accept custom JSONL file path."""
        import tracecraft

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "custom_traces.jsonl"
            # Explicitly enable JSONL and disable storage to test JSONL exporter
            runtime = tracecraft.init(jsonl=True, jsonl_path=str(filepath), storage="none")

            # Trigger export by running a traced function
            from tracecraft.core.models import AgentRun

            run = AgentRun(name="test", start_time=datetime.now(UTC))
            runtime.export(run)

            assert filepath.exists()
            runtime.shutdown()

    def test_init_custom_exporters(self):
        """init() should accept custom exporters list."""
        import tracecraft
        from tracecraft.exporters.base import BaseExporter

        class CustomExporter(BaseExporter):
            def __init__(self):
                self.exported = []

            def export(self, run):
                self.exported.append(run)

        custom = CustomExporter()
        # Disable storage to prevent config-based SQLite from interfering
        runtime = tracecraft.init(exporters=[custom], console=False, jsonl=False, storage="none")

        from tracecraft.core.models import AgentRun

        run = AgentRun(name="test", start_time=datetime.now(UTC))
        runtime.export(run)

        assert len(custom.exported) == 1
        runtime.shutdown()

    def test_init_is_idempotent(self):
        """Multiple init() calls should return the same runtime."""
        import tracecraft

        runtime1 = tracecraft.init()
        runtime2 = tracecraft.init()
        assert runtime1 is runtime2
        runtime1.shutdown()

    def test_init_receiver_true_adds_otlp_exporter(self):
        """receiver=True should add an OTLPExporter to the runtime."""
        from unittest.mock import patch

        import tracecraft
        from tracecraft.exporters.otlp import OTLPExporter

        with patch.object(OTLPExporter, "__init__", return_value=None) as mock_init:
            # Patch close so shutdown doesn't fail on the uninitialized mock
            with patch.object(OTLPExporter, "close", return_value=None):
                runtime = tracecraft.init(
                    receiver=True,
                    console=False,
                    jsonl=False,
                    storage="none",
                )
                mock_init.assert_called_once()
                call_kwargs = mock_init.call_args
                assert call_kwargs.kwargs["endpoint"] == "http://localhost:4318"
                assert call_kwargs.kwargs["protocol"] == "http"
                runtime.shutdown()

    def test_init_receiver_custom_url(self):
        """receiver=<url> should use the provided URL."""
        from unittest.mock import patch

        import tracecraft
        from tracecraft.exporters.otlp import OTLPExporter

        with patch.object(OTLPExporter, "__init__", return_value=None) as mock_init:
            with patch.object(OTLPExporter, "close", return_value=None):
                runtime = tracecraft.init(
                    receiver="http://remote-host:4318",
                    console=False,
                    jsonl=False,
                    storage="none",
                )
                call_kwargs = mock_init.call_args
                assert call_kwargs.kwargs["endpoint"] == "http://remote-host:4318"
                runtime.shutdown()

    def test_init_receiver_with_service_name(self):
        """service_name should be forwarded to the receiver exporter."""
        from unittest.mock import patch

        import tracecraft
        from tracecraft.exporters.otlp import OTLPExporter

        with patch.object(OTLPExporter, "__init__", return_value=None) as mock_init:
            with patch.object(OTLPExporter, "close", return_value=None):
                runtime = tracecraft.init(
                    receiver=True,
                    service_name="my-agent-service",
                    console=False,
                    jsonl=False,
                    storage="none",
                )
                call_kwargs = mock_init.call_args
                assert call_kwargs.kwargs["service_name"] == "my-agent-service"
                runtime.shutdown()

    def test_init_receiver_from_config(self):
        """receiver and service_name set via .tracecraft/config.yaml are honoured."""
        from unittest.mock import patch

        import tracecraft
        from tracecraft.core.env_config import (
            EnvironmentSettings,
            ExporterConfig,
            TraceCraftEnvConfig,
        )
        from tracecraft.exporters.otlp import OTLPExporter

        config = TraceCraftEnvConfig(
            default=EnvironmentSettings(
                service_name="config-agent",
                exporters=ExporterConfig(
                    console=False,
                    jsonl=False,
                    receiver=True,
                    receiver_endpoint="http://config-host:4318",
                ),
            )
        )

        with patch("tracecraft.core.env_config.load_config", return_value=config):
            with patch.object(OTLPExporter, "__init__", return_value=None) as mock_init:
                with patch.object(OTLPExporter, "close", return_value=None):
                    runtime = tracecraft.init(storage="none")
                    call_kwargs = mock_init.call_args
                    assert call_kwargs.kwargs["endpoint"] == "http://config-host:4318"
                    assert call_kwargs.kwargs["service_name"] == "config-agent"
                    runtime.shutdown()

    def test_init_auto_instrument_from_config(self):
        """auto_instrument set in config is honoured when not passed to init()."""
        from unittest.mock import patch

        import tracecraft
        from tracecraft.core.env_config import (
            EnvironmentSettings,
            ExporterConfig,
            InstrumentationConfig,
            TraceCraftEnvConfig,
        )

        config = TraceCraftEnvConfig(
            default=EnvironmentSettings(
                exporters=ExporterConfig(console=False, jsonl=False),
                instrumentation=InstrumentationConfig(auto_instrument=["openai"]),
            )
        )

        with patch("tracecraft.core.env_config.load_config", return_value=config):
            with patch("tracecraft.core.runtime._handle_auto_instrumentation") as mock_handle:
                runtime = tracecraft.init(storage="none")
                # auto_instrument was None (not passed), config value should flow through
                call_args = mock_handle.call_args
                assert call_args.kwargs["config_auto_instrument"] == ["openai"]
                runtime.shutdown()

    def test_init_explicit_param_overrides_config(self):
        """Explicit init() params take precedence over config file values."""
        from unittest.mock import patch

        import tracecraft
        from tracecraft.core.env_config import (
            EnvironmentSettings,
            ExporterConfig,
            TraceCraftEnvConfig,
        )
        from tracecraft.exporters.otlp import OTLPExporter

        # Config says receiver=True with one endpoint
        config = TraceCraftEnvConfig(
            default=EnvironmentSettings(
                service_name="config-name",
                exporters=ExporterConfig(
                    console=False,
                    jsonl=False,
                    receiver=True,
                    receiver_endpoint="http://config-host:4318",
                ),
            )
        )

        with patch("tracecraft.core.env_config.load_config", return_value=config):
            with patch.object(OTLPExporter, "__init__", return_value=None) as mock_init:
                with patch.object(OTLPExporter, "close", return_value=None):
                    # Explicit params override config
                    runtime = tracecraft.init(
                        receiver="http://override-host:4318",
                        service_name="override-name",
                        storage="none",
                    )
                    call_kwargs = mock_init.call_args
                    assert call_kwargs.kwargs["endpoint"] == "http://override-host:4318"
                    assert call_kwargs.kwargs["service_name"] == "override-name"
                    runtime.shutdown()

    def test_init_receiver_combined_with_custom_exporters(self):
        """receiver= and exporters= should both be active."""
        from unittest.mock import patch

        import tracecraft
        from tracecraft.exporters.base import BaseExporter
        from tracecraft.exporters.otlp import OTLPExporter

        class CustomExporter(BaseExporter):
            def export(self, run):
                pass

        custom = CustomExporter()

        with patch.object(OTLPExporter, "__init__", return_value=None):
            with patch.object(OTLPExporter, "close", return_value=None):
                runtime = tracecraft.init(
                    receiver=True,
                    exporters=[custom],
                    console=False,
                    jsonl=False,
                    storage="none",
                )
                # Both the custom exporter and the receiver exporter should be present
                assert custom in runtime._custom_exporters
                assert any(isinstance(e, OTLPExporter) for e in runtime._custom_exporters)
                runtime.shutdown()


class TestRuntime:
    """Tests for the TALRuntime class."""

    def test_runtime_start_run_creates_run(self):
        """start_run should create and return an AgentRun."""
        import tracecraft

        runtime = tracecraft.init()
        run = runtime.start_run("test_agent")

        assert run is not None
        assert run.name == "test_agent"
        runtime.shutdown()

    def test_runtime_end_run_finalizes_run(self):
        """end_run should finalize and export the run."""
        import tracecraft

        runtime = tracecraft.init(console=False, jsonl=False)
        run = runtime.start_run("test_agent")
        runtime.end_run(run, output={"result": "done"})

        assert run.end_time is not None
        assert run.output == {"result": "done"}
        runtime.shutdown()

    def test_runtime_context_manager(self):
        """Runtime should work as context manager for runs."""
        import tracecraft

        runtime = tracecraft.init(console=False, jsonl=False)

        with runtime.run("managed_run") as run:
            assert run is not None
            assert run.name == "managed_run"

        assert run.end_time is not None
        runtime.shutdown()


class TestPublicAPI:
    """Tests for the public API surface."""

    def test_trace_agent_is_exported(self):
        """trace_agent should be available from the package."""
        from tracecraft import trace_agent

        assert callable(trace_agent)

    def test_trace_tool_is_exported(self):
        """trace_tool should be available from the package."""
        from tracecraft import trace_tool

        assert callable(trace_tool)

    def test_trace_llm_is_exported(self):
        """trace_llm should be available from the package."""
        from tracecraft import trace_llm

        assert callable(trace_llm)

    def test_trace_retrieval_is_exported(self):
        """trace_retrieval should be available from the package."""
        from tracecraft import trace_retrieval

        assert callable(trace_retrieval)

    def test_step_is_exported(self):
        """step context manager should be available from the package."""
        from tracecraft import step

        assert callable(step)

    def test_models_are_exported(self):
        """Core models should be available from the package."""
        from tracecraft import AgentRun, Step, StepType

        assert AgentRun is not None
        assert Step is not None
        assert StepType is not None


class TestIntegration:
    """Integration tests for the full flow."""

    def test_decorated_function_exports_trace(self):
        """Decorated function should produce a trace that gets exported."""
        import tracecraft
        from tracecraft import trace_agent, trace_tool

        output = StringIO()
        runtime = tracecraft.init(console_file=output, jsonl=False)

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

        import tracecraft
        from tracecraft import trace_agent

        output = StringIO()
        runtime = tracecraft.init(console_file=output, jsonl=False)

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


class TestExampleDataCreation:
    """Tests for example data creation during initialization."""

    def test_create_example_data_creates_project(self):
        """_create_example_data should create an Example Project."""
        from tracecraft.core.init import _create_example_data
        from tracecraft.storage.sqlite import SQLiteTraceStore

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = SQLiteTraceStore(db_path)
            store.close()

            _create_example_data(db_path)

            store = SQLiteTraceStore(db_path)
            projects = store.list_projects()
            store.close()

            project_names = [p["name"] for p in projects]
            assert "Example Project" in project_names

    def test_create_example_data_creates_traces(self):
        """_create_example_data should create example traces."""
        from tracecraft.core.init import _create_example_data
        from tracecraft.storage.sqlite import SQLiteTraceStore

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = SQLiteTraceStore(db_path)
            store.close()

            _create_example_data(db_path)

            store = SQLiteTraceStore(db_path)
            traces = store.list_all(limit=50)
            store.close()

            # Should have 5 example traces
            assert len(traces) >= 5

    def test_initialize_creates_example_data_by_default(self):
        """initialize() with create_sample_project=True should create example data."""
        from tracecraft.core.init import InitLocation, initialize
        from tracecraft.storage.sqlite import SQLiteTraceStore

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)

            result = initialize(
                InitLocation.LOCAL,
                base_path=base_path,
                create_sample_project=True,
            )

            assert result.success
            assert result.database_path.exists()

            store = SQLiteTraceStore(result.database_path)
            projects = store.list_projects()
            traces = store.list_all(limit=50)
            store.close()

            # Should have Example Project
            project_names = [p["name"] for p in projects]
            assert "Example Project" in project_names

            # Should have traces
            assert len(traces) >= 5
