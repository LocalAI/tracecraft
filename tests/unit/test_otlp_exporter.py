"""
Tests for the OTLP exporter.

TDD approach: These tests are written BEFORE the implementation.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from uuid import uuid4


class TestOTLPExporterInitialization:
    """Tests for OTLP exporter initialization."""

    def test_otlp_exporter_with_endpoint(self) -> None:
        """OTLP exporter should initialize with an endpoint."""
        from agenttrace.exporters.otlp import OTLPExporter

        exporter = OTLPExporter(endpoint="http://localhost:4317")
        assert exporter.endpoint == "http://localhost:4317"

    def test_otlp_exporter_default_protocol_grpc(self) -> None:
        """OTLP exporter should default to gRPC protocol."""
        from agenttrace.exporters.otlp import OTLPExporter

        exporter = OTLPExporter(endpoint="http://localhost:4317")
        assert exporter.protocol == "grpc"

    def test_otlp_exporter_http_protocol(self) -> None:
        """OTLP exporter should support HTTP protocol."""
        from agenttrace.exporters.otlp import OTLPExporter

        exporter = OTLPExporter(endpoint="http://localhost:4318", protocol="http")
        assert exporter.protocol == "http"

    def test_otlp_exporter_with_headers(self) -> None:
        """OTLP exporter should accept custom headers."""
        from agenttrace.exporters.otlp import OTLPExporter

        headers = {"Authorization": "Bearer token123"}
        exporter = OTLPExporter(endpoint="http://localhost:4317", headers=headers)
        assert exporter.headers == headers

    def test_otlp_exporter_with_service_name(self) -> None:
        """OTLP exporter should accept a service name."""
        from agenttrace.exporters.otlp import OTLPExporter

        exporter = OTLPExporter(endpoint="http://localhost:4317", service_name="my-agent")
        assert exporter.service_name == "my-agent"

    def test_otlp_exporter_default_service_name(self) -> None:
        """OTLP exporter should have default service name."""
        from agenttrace.exporters.otlp import OTLPExporter

        exporter = OTLPExporter(endpoint="http://localhost:4317")
        assert exporter.service_name == "agenttrace"

    def test_otlp_exporter_with_timeout(self) -> None:
        """OTLP exporter should accept a timeout."""
        from agenttrace.exporters.otlp import OTLPExporter

        exporter = OTLPExporter(endpoint="http://localhost:4317", timeout_ms=5000)
        assert exporter.timeout_ms == 5000

    def test_otlp_exporter_default_timeout(self) -> None:
        """OTLP exporter should have default timeout."""
        from agenttrace.exporters.otlp import OTLPExporter

        exporter = OTLPExporter(endpoint="http://localhost:4317")
        assert exporter.timeout_ms == 10000


class TestOTLPExporterBaseClass:
    """Tests for OTLP exporter base class compliance."""

    def test_otlp_exporter_is_base_exporter(self) -> None:
        """OTLP exporter should inherit from BaseExporter."""
        from agenttrace.exporters.base import BaseExporter
        from agenttrace.exporters.otlp import OTLPExporter

        exporter = OTLPExporter(endpoint="http://localhost:4317")
        assert isinstance(exporter, BaseExporter)

    def test_otlp_exporter_has_export_method(self) -> None:
        """OTLP exporter should have an export method."""
        from agenttrace.exporters.otlp import OTLPExporter

        exporter = OTLPExporter(endpoint="http://localhost:4317")
        assert hasattr(exporter, "export")
        assert callable(exporter.export)

    def test_otlp_exporter_has_close_method(self) -> None:
        """OTLP exporter should have a close method."""
        from agenttrace.exporters.otlp import OTLPExporter

        exporter = OTLPExporter(endpoint="http://localhost:4317")
        assert hasattr(exporter, "close")
        assert callable(exporter.close)


class TestStepToSpanConversion:
    """Tests for Step to OpenTelemetry Span conversion."""

    def test_step_to_span_basic_conversion(self, sample_timestamp: datetime) -> None:
        """A Step should convert to an OTel span with correct attributes."""
        from agenttrace.core.models import AgentRun, Step, StepType
        from agenttrace.exporters.otlp import OTLPExporter

        run_id = uuid4()
        step = Step(
            trace_id=run_id,
            type=StepType.TOOL,
            name="test_tool",
            start_time=sample_timestamp,
            end_time=sample_timestamp,
            duration_ms=100.0,
        )

        run = AgentRun(id=run_id, name="test_run", start_time=sample_timestamp)
        run.steps = [step]

        exporter = OTLPExporter(endpoint="http://localhost:4317")
        span_data = exporter._step_to_span_data(step, run.id)

        assert span_data["name"] == "test_tool"
        assert "trace_id" in span_data
        assert "span_id" in span_data

    def test_step_to_span_llm_attributes(self, sample_timestamp: datetime) -> None:
        """LLM steps should include GenAI attributes."""
        from agenttrace.core.models import AgentRun, Step, StepType
        from agenttrace.exporters.otlp import OTLPExporter

        run_id = uuid4()
        step = Step(
            trace_id=run_id,
            type=StepType.LLM,
            name="llm_call",
            start_time=sample_timestamp,
            end_time=sample_timestamp,
            model_name="gpt-4",
            model_provider="openai",
            input_tokens=100,
            output_tokens=200,
            cost_usd=0.015,
        )

        run = AgentRun(id=run_id, name="test_run", start_time=sample_timestamp)
        run.steps = [step]

        exporter = OTLPExporter(endpoint="http://localhost:4317")
        span_data = exporter._step_to_span_data(step, run.id)

        # Check GenAI attributes are present
        attrs = span_data.get("attributes", {})
        assert attrs.get("gen_ai.request.model") == "gpt-4"
        assert attrs.get("gen_ai.system") == "openai"
        assert attrs.get("gen_ai.usage.input_tokens") == 100
        assert attrs.get("gen_ai.usage.output_tokens") == 200


class TestSpanHierarchy:
    """Tests for maintaining span hierarchy."""

    def test_parent_child_relationship(self, sample_timestamp: datetime) -> None:
        """Child steps should reference parent span ID."""
        from agenttrace.core.models import AgentRun, Step, StepType
        from agenttrace.exporters.otlp import OTLPExporter

        run_id = uuid4()
        parent_id = uuid4()
        child_id = uuid4()

        child_step = Step(
            id=child_id,
            trace_id=run_id,
            parent_id=parent_id,
            type=StepType.TOOL,
            name="child_tool",
            start_time=sample_timestamp,
        )

        parent_step = Step(
            id=parent_id,
            trace_id=run_id,
            type=StepType.AGENT,
            name="parent_agent",
            start_time=sample_timestamp,
            children=[child_step],
        )

        run = AgentRun(id=run_id, name="test_run", start_time=sample_timestamp)
        run.steps = [parent_step]

        exporter = OTLPExporter(endpoint="http://localhost:4317")
        child_span_data = exporter._step_to_span_data(child_step, run.id)

        # Child should have parent_span_id set
        assert "parent_span_id" in child_span_data

    def test_root_step_no_parent(self, sample_timestamp: datetime) -> None:
        """Root steps should not have a parent span ID."""
        from agenttrace.core.models import AgentRun, Step, StepType
        from agenttrace.exporters.otlp import OTLPExporter

        run_id = uuid4()
        step = Step(
            trace_id=run_id,
            type=StepType.AGENT,
            name="root_agent",
            start_time=sample_timestamp,
        )

        run = AgentRun(id=run_id, name="test_run", start_time=sample_timestamp)
        run.steps = [step]

        exporter = OTLPExporter(endpoint="http://localhost:4317")
        span_data = exporter._step_to_span_data(step, run.id)

        # Root step should have None or empty parent_span_id
        parent_id = span_data.get("parent_span_id")
        assert parent_id is None or parent_id == ""


class TestSchemaDialects:
    """Tests for schema dialect support."""

    def test_default_dialect_is_both(self) -> None:
        """Default schema dialect should include both conventions."""
        from agenttrace.exporters.otlp import OTLPExporter

        exporter = OTLPExporter(endpoint="http://localhost:4317")
        assert exporter.schema_dialect == "both"

    def test_otel_genai_dialect(self, sample_timestamp: datetime) -> None:
        """OTel GenAI dialect should only include GenAI attributes."""
        from agenttrace.core.models import Step, StepType
        from agenttrace.exporters.otlp import OTLPExporter

        run_id = uuid4()
        step = Step(
            trace_id=run_id,
            type=StepType.LLM,
            name="llm_call",
            start_time=sample_timestamp,
            model_name="gpt-4",
            input_tokens=100,
        )

        exporter = OTLPExporter(endpoint="http://localhost:4317", schema_dialect="otel_genai")
        span_data = exporter._step_to_span_data(step, run_id)
        attrs = span_data.get("attributes", {})

        # Should have OTel GenAI attrs
        assert "gen_ai.request.model" in attrs
        # Should not have OpenInference attrs
        assert "llm.model_name" not in attrs

    def test_openinference_dialect(self, sample_timestamp: datetime) -> None:
        """OpenInference dialect should only include OpenInference attributes."""
        from agenttrace.core.models import Step, StepType
        from agenttrace.exporters.otlp import OTLPExporter

        run_id = uuid4()
        step = Step(
            trace_id=run_id,
            type=StepType.LLM,
            name="llm_call",
            start_time=sample_timestamp,
            model_name="gpt-4",
            input_tokens=100,
        )

        exporter = OTLPExporter(endpoint="http://localhost:4317", schema_dialect="openinference")
        span_data = exporter._step_to_span_data(step, run_id)
        attrs = span_data.get("attributes", {})

        # Should have OpenInference attrs
        assert "llm.model_name" in attrs
        # Should not have OTel GenAI attrs (except basic ones)
        assert "gen_ai.usage.input_tokens" not in attrs

    def test_both_dialects(self, sample_timestamp: datetime) -> None:
        """Both dialect should include all attributes."""
        from agenttrace.core.models import Step, StepType
        from agenttrace.exporters.otlp import OTLPExporter

        run_id = uuid4()
        step = Step(
            trace_id=run_id,
            type=StepType.LLM,
            name="llm_call",
            start_time=sample_timestamp,
            model_name="gpt-4",
            input_tokens=100,
        )

        exporter = OTLPExporter(endpoint="http://localhost:4317", schema_dialect="both")
        span_data = exporter._step_to_span_data(step, run_id)
        attrs = span_data.get("attributes", {})

        # Should have both
        assert "gen_ai.request.model" in attrs
        assert "llm.model_name" in attrs


class TestExportExecution:
    """Tests for the export method execution."""

    def test_export_creates_spans_for_all_steps(self, sample_timestamp: datetime) -> None:
        """Export should create spans for all steps in a run."""
        from agenttrace.core.models import AgentRun, Step, StepType
        from agenttrace.exporters.otlp import OTLPExporter

        run_id = uuid4()
        steps = [
            Step(
                trace_id=run_id,
                type=StepType.AGENT,
                name=f"step_{i}",
                start_time=sample_timestamp,
            )
            for i in range(3)
        ]

        run = AgentRun(id=run_id, name="test_run", start_time=sample_timestamp)
        run.steps = steps

        with patch.object(OTLPExporter, "_send_spans") as mock_send:
            exporter = OTLPExporter(endpoint="http://localhost:4317")
            exporter.export(run)

            # Should have called _send_spans with 3 spans
            mock_send.assert_called_once()
            spans = mock_send.call_args[0][0]
            assert len(spans) == 3

    def test_export_handles_nested_steps(self, sample_timestamp: datetime) -> None:
        """Export should flatten nested steps into spans."""
        from agenttrace.core.models import AgentRun, Step, StepType
        from agenttrace.exporters.otlp import OTLPExporter

        run_id = uuid4()
        parent_id = uuid4()

        child = Step(
            trace_id=run_id,
            parent_id=parent_id,
            type=StepType.TOOL,
            name="child",
            start_time=sample_timestamp,
        )

        parent = Step(
            id=parent_id,
            trace_id=run_id,
            type=StepType.AGENT,
            name="parent",
            start_time=sample_timestamp,
            children=[child],
        )

        run = AgentRun(id=run_id, name="test_run", start_time=sample_timestamp)
        run.steps = [parent]

        with patch.object(OTLPExporter, "_send_spans") as mock_send:
            exporter = OTLPExporter(endpoint="http://localhost:4317")
            exporter.export(run)

            # Should have 2 spans (parent + child)
            spans = mock_send.call_args[0][0]
            assert len(spans) == 2


class TestErrorHandling:
    """Tests for error handling in the exporter."""

    def test_export_handles_connection_error_gracefully(self, sample_timestamp: datetime) -> None:
        """Export should handle connection errors gracefully."""
        from agenttrace.core.models import AgentRun, Step, StepType
        from agenttrace.exporters.otlp import OTLPExporter

        run_id = uuid4()
        step = Step(
            trace_id=run_id,
            type=StepType.AGENT,
            name="test_step",
            start_time=sample_timestamp,
        )

        run = AgentRun(id=run_id, name="test_run", start_time=sample_timestamp)
        run.steps = [step]

        with patch.object(
            OTLPExporter, "_send_spans", side_effect=ConnectionError("Failed to connect")
        ):
            exporter = OTLPExporter(endpoint="http://nonexistent:4317")
            # Should not raise - just log the error
            exporter.export(run)  # No exception

    def test_export_handles_empty_run(self, sample_timestamp: datetime) -> None:
        """Export should handle runs with no steps."""
        from agenttrace.core.models import AgentRun
        from agenttrace.exporters.otlp import OTLPExporter

        run = AgentRun(name="empty_run", start_time=sample_timestamp)

        with patch.object(OTLPExporter, "_send_spans") as mock_send:
            exporter = OTLPExporter(endpoint="http://localhost:4317")
            exporter.export(run)

            # Should not call _send_spans for empty run
            mock_send.assert_not_called()


class TestContextManager:
    """Tests for context manager support."""

    def test_exporter_as_context_manager(self) -> None:
        """OTLP exporter should work as a context manager."""
        from agenttrace.exporters.otlp import OTLPExporter

        with OTLPExporter(endpoint="http://localhost:4317") as exporter:
            assert exporter is not None
            assert hasattr(exporter, "export")

    def test_close_called_on_exit(self) -> None:
        """Close should be called when exiting context."""
        from agenttrace.exporters.otlp import OTLPExporter

        with patch.object(OTLPExporter, "close") as mock_close:
            with OTLPExporter(endpoint="http://localhost:4317"):
                pass
            mock_close.assert_called_once()
