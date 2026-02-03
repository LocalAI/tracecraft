"""
End-to-end tests for the full TraceCraft pipeline.

Tests the complete flow from run creation through processing to export.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tracecraft.core.config import RedactionConfig, SamplingConfig, TraceCraftConfig
from tracecraft.core.models import Step, StepType
from tracecraft.core.runtime import TALRuntime


class TestFullPipelineE2E:
    """End-to-end tests for the complete trace pipeline."""

    def test_basic_run_to_export(self, tmp_path: Path) -> None:
        """Basic run should export to JSONL file."""
        jsonl_path = tmp_path / "traces.jsonl"

        runtime = TALRuntime(
            console=False,
            jsonl=True,
            jsonl_path=jsonl_path,
        )

        run = runtime.start_run(name="test_run", input={"query": "hello"})
        runtime.end_run(run, output={"response": "world"})

        # Verify JSONL was written
        assert jsonl_path.exists()
        with open(jsonl_path) as f:
            lines = f.readlines()
            assert len(lines) == 1
            data = json.loads(lines[0])
            assert data["name"] == "test_run"

    def test_run_with_steps_export(self, tmp_path: Path) -> None:
        """Run with steps should export all steps."""
        jsonl_path = tmp_path / "traces.jsonl"

        runtime = TALRuntime(
            console=False,
            jsonl=True,
            jsonl_path=jsonl_path,
        )

        run = runtime.start_run(name="agent_run")

        # Add LLM step
        llm_step = Step(
            trace_id=run.id,
            type=StepType.LLM,
            name="chat_completion",
            start_time=datetime.now(UTC),
            model_name="gpt-4",
            inputs={"prompt": "What is 2+2?"},
            outputs={"text": "4"},
            input_tokens=10,
            output_tokens=1,
        )
        llm_step.end_time = datetime.now(UTC)
        run.steps.append(llm_step)

        # Add tool step
        tool_step = Step(
            trace_id=run.id,
            type=StepType.TOOL,
            name="calculator",
            start_time=datetime.now(UTC),
            inputs={"expression": "2+2"},
            outputs={"result": "4"},
        )
        tool_step.end_time = datetime.now(UTC)
        run.steps.append(tool_step)

        runtime.end_run(run)

        # Verify export
        with open(jsonl_path) as f:
            data = json.loads(f.read())
            assert len(data["steps"]) == 2
            assert data["steps"][0]["type"] == "llm"
            assert data["steps"][1]["type"] == "tool"

    def test_pipeline_with_redaction(self, tmp_path: Path) -> None:
        """Pipeline should apply redaction before export."""
        jsonl_path = tmp_path / "traces.jsonl"

        config = TraceCraftConfig(
            console_enabled=False,
            jsonl_enabled=True,
            jsonl_path=str(jsonl_path),
            redaction=RedactionConfig(enabled=True),
        )

        runtime = TALRuntime(
            console=False,
            jsonl=True,
            jsonl_path=jsonl_path,
            config=config,
        )

        run = runtime.start_run(name="run_with_pii")

        # Add step with PII
        step = Step(
            trace_id=run.id,
            type=StepType.LLM,
            name="chat",
            start_time=datetime.now(UTC),
            inputs={"prompt": "Email me at test@example.com"},
        )
        step.end_time = datetime.now(UTC)
        run.steps.append(step)

        runtime.end_run(run)

        # Verify email was redacted
        with open(jsonl_path) as f:
            data = json.loads(f.read())
            prompt = data["steps"][0]["inputs"]["prompt"]
            assert "test@example.com" not in prompt
            assert "[REDACTED]" in prompt

    def test_pipeline_with_sampling(self, tmp_path: Path) -> None:
        """Pipeline should respect sampling rate."""
        jsonl_path = tmp_path / "traces.jsonl"

        config = TraceCraftConfig(
            console_enabled=False,
            jsonl_enabled=True,
            jsonl_path=str(jsonl_path),
            sampling=SamplingConfig(rate=0.0),  # 0% sampling
        )

        runtime = TALRuntime(
            console=False,
            jsonl=True,
            jsonl_path=jsonl_path,
            config=config,
        )

        # Create and end 10 runs
        for i in range(10):
            run = runtime.start_run(name=f"run_{i}")
            runtime.end_run(run)

        # With 0% sampling, nothing should be exported
        if jsonl_path.exists():
            with open(jsonl_path) as f:
                lines = f.readlines()
                assert len(lines) == 0


class TestContextManagerE2E:
    """E2E tests for context manager usage."""

    def test_sync_context_manager(self, tmp_path: Path) -> None:
        """Sync context manager should work end-to-end."""
        jsonl_path = tmp_path / "traces.jsonl"

        runtime = TALRuntime(
            console=False,
            jsonl=True,
            jsonl_path=jsonl_path,
        )

        with runtime.run("test_run", input={"x": 1}) as run:
            # Add a step
            step = Step(
                trace_id=run.id,
                type=StepType.LLM,
                name="llm_call",
                start_time=datetime.now(UTC),
            )
            step.end_time = datetime.now(UTC)
            run.steps.append(step)

        # Verify export
        assert jsonl_path.exists()
        with open(jsonl_path) as f:
            data = json.loads(f.read())
            assert data["name"] == "test_run"
            assert len(data["steps"]) == 1

    @pytest.mark.asyncio
    async def test_async_context_manager(self, tmp_path: Path) -> None:
        """Async context manager should work end-to-end."""
        jsonl_path = tmp_path / "traces.jsonl"

        runtime = TALRuntime(
            console=False,
            jsonl=True,
            jsonl_path=jsonl_path,
        )

        async with runtime.run_async("async_run") as run:
            step = Step(
                trace_id=run.id,
                type=StepType.TOOL,
                name="async_tool",
                start_time=datetime.now(UTC),
            )
            step.end_time = datetime.now(UTC)
            run.steps.append(step)

        # Verify export
        with open(jsonl_path) as f:
            data = json.loads(f.read())
            assert data["name"] == "async_run"


class TestExporterChainE2E:
    """E2E tests for multiple exporters."""

    def test_multiple_exporters(self, tmp_path: Path) -> None:
        """Multiple exporters should all receive the run."""
        jsonl_path = tmp_path / "traces.jsonl"

        mock_exporter1 = MagicMock()
        mock_exporter2 = MagicMock()

        runtime = TALRuntime(
            console=False,
            jsonl=True,
            jsonl_path=jsonl_path,
            exporters=[mock_exporter1, mock_exporter2],
        )

        run = runtime.start_run(name="multi_export_run")
        runtime.end_run(run)

        # All exporters should have been called
        mock_exporter1.export.assert_called_once()
        mock_exporter2.export.assert_called_once()

        # JSONL should also have been written
        assert jsonl_path.exists()


class TestRetryBufferE2E:
    """E2E tests for retry and buffering."""

    def test_buffering_exporter(self, tmp_path: Path) -> None:  # noqa: ARG002
        """Buffering exporter should batch exports."""
        from tracecraft.exporters.retry import BufferingExporter

        mock_exporter = MagicMock()
        buffering = BufferingExporter(exporter=mock_exporter, buffer_size=3)

        runtime = TALRuntime(
            console=False,
            jsonl=False,
            exporters=[buffering],
        )

        # Create 2 runs - should not flush yet
        for i in range(2):
            run = runtime.start_run(name=f"run_{i}")
            runtime.end_run(run)

        assert mock_exporter.export.call_count == 0

        # Third run should trigger flush
        run = runtime.start_run(name="run_2")
        runtime.end_run(run)

        assert mock_exporter.export.call_count == 3

    def test_rate_limited_exporter(self) -> None:
        """Rate limited exporter should respect limits."""
        from tracecraft.exporters.rate_limited import RateLimitedExporter

        mock_exporter = MagicMock()
        rate_limited = RateLimitedExporter(
            exporter=mock_exporter,
            rate=1000.0,  # High rate for testing
            burst=100,
            blocking=False,
        )

        runtime = TALRuntime(
            console=False,
            jsonl=False,
            exporters=[rate_limited],
        )

        # Quick burst should succeed
        for i in range(50):
            run = runtime.start_run(name=f"run_{i}")
            runtime.end_run(run)

        # Most should have been exported
        assert mock_exporter.export.call_count >= 50
