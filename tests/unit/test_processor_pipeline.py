"""
Tests for the processor pipeline integration.

TDD approach: These tests verify that processors are properly
wired into the export pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun


class TestBaseProcessor:
    """Tests for the base processor interface."""

    def test_base_processor_is_abstract(self) -> None:
        """BaseProcessor should be abstract and not directly instantiable."""
        from tracecraft.processors.base import BaseProcessor

        with pytest.raises(TypeError):
            BaseProcessor()  # type: ignore

    def test_processor_has_process_method(self) -> None:
        """Processors must implement the process method."""
        from tracecraft.processors.base import BaseProcessor

        assert hasattr(BaseProcessor, "process")

    def test_processor_has_name_property(self) -> None:
        """Processors should have a name property."""
        from tracecraft.processors.base import BaseProcessor

        assert hasattr(BaseProcessor, "name")


class TestRedactionProcessorAdapter:
    """Tests for the redaction processor adapter."""

    def test_redaction_adapter_processes_run(self, sample_run_with_pii) -> None:
        """Redaction adapter should redact PII from run."""
        from tracecraft.processors.base import RedactionProcessorAdapter
        from tracecraft.processors.redaction import RedactionProcessor

        processor = RedactionProcessor()
        adapter = RedactionProcessorAdapter(processor)

        result = adapter.process(sample_run_with_pii)

        assert result is not None
        # Check that email was redacted in step inputs
        step = result.steps[0]
        assert "test@example.com" not in str(step.inputs)
        assert "[REDACTED]" in str(step.inputs)

    def test_redaction_adapter_returns_new_run(self, sample_run_with_pii) -> None:
        """Redaction adapter should return a new run, not mutate original."""
        from tracecraft.processors.base import RedactionProcessorAdapter
        from tracecraft.processors.redaction import RedactionProcessor

        processor = RedactionProcessor()
        adapter = RedactionProcessorAdapter(processor)

        result = adapter.process(sample_run_with_pii)

        # Original should still have PII
        assert "test@example.com" in str(sample_run_with_pii.steps[0].inputs)
        # Result should have redacted PII
        assert "test@example.com" not in str(result.steps[0].inputs)


class TestSamplingProcessorAdapter:
    """Tests for the sampling processor adapter."""

    def test_sampling_adapter_keeps_at_rate_1(self, sample_run) -> None:
        """Sampling adapter should keep runs at 100% rate."""
        from tracecraft.processors.base import SamplingProcessorAdapter
        from tracecraft.processors.sampling import SamplingProcessor

        processor = SamplingProcessor(default_rate=1.0)
        adapter = SamplingProcessorAdapter(processor)

        result = adapter.process(sample_run)

        assert result is not None
        assert result.should_export is True

    def test_sampling_adapter_drops_at_rate_0(self, sample_run) -> None:
        """Sampling adapter should drop runs at 0% rate."""
        from tracecraft.processors.base import SamplingProcessorAdapter
        from tracecraft.processors.sampling import SamplingProcessor

        processor = SamplingProcessor(default_rate=0.0)
        adapter = SamplingProcessorAdapter(processor)

        result = adapter.process(sample_run)

        assert result is None

    def test_sampling_adapter_keeps_error_traces(self, sample_run_with_error) -> None:
        """Sampling adapter should keep error traces even at 0% rate."""
        from tracecraft.processors.base import SamplingProcessorAdapter
        from tracecraft.processors.sampling import SamplingProcessor

        processor = SamplingProcessor(default_rate=0.0, always_keep_errors=True)
        adapter = SamplingProcessorAdapter(processor)

        result = adapter.process(sample_run_with_error)

        assert result is not None
        assert "error" in result.sample_reason.lower()


class TestEnrichmentProcessorAdapter:
    """Tests for the token enrichment processor adapter."""

    def test_enrichment_adapter_adds_token_counts(self, sample_run_with_llm_step) -> None:
        """Enrichment adapter should add token counts to LLM steps."""
        from tracecraft.processors.base import EnrichmentProcessorAdapter
        from tracecraft.processors.enrichment import TokenEnrichmentProcessor

        processor = TokenEnrichmentProcessor()
        adapter = EnrichmentProcessorAdapter(processor)

        # Initially no token counts
        assert sample_run_with_llm_step.steps[0].input_tokens is None

        result = adapter.process(sample_run_with_llm_step)

        assert result is not None
        # Should have estimated token counts now
        step = result.steps[0]
        assert step.input_tokens is not None or step.output_tokens is not None


class TestProcessorPipelineIntegration:
    """Tests for the full processor pipeline in the runtime."""

    def test_runtime_accepts_config(self) -> None:
        """Runtime init should accept a config object."""
        from tracecraft.core.config import TraceCraftConfig
        from tracecraft.core.runtime import TALRuntime

        config = TraceCraftConfig(
            service_name="test-service",
            console_enabled=False,
            jsonl_enabled=False,
        )

        runtime = TALRuntime(
            console=False,
            jsonl=False,
            config=config,
        )

        assert runtime._config is not None
        assert runtime._config.service_name == "test-service"

    def test_runtime_initializes_processors_from_config(self) -> None:
        """Runtime should initialize processors from config."""
        from tracecraft.core.config import RedactionConfig, SamplingConfig, TraceCraftConfig
        from tracecraft.core.runtime import TALRuntime

        config = TraceCraftConfig(
            console_enabled=False,
            jsonl_enabled=False,
            redaction=RedactionConfig(enabled=True),
            sampling=SamplingConfig(rate=0.5),
        )

        runtime = TALRuntime(
            console=False,
            jsonl=False,
            config=config,
        )

        assert len(runtime._processors) > 0

    def test_export_applies_processors(self, sample_run_with_pii) -> None:
        """Export should apply processors before exporting."""
        from tracecraft.core.config import RedactionConfig, TraceCraftConfig
        from tracecraft.core.runtime import TALRuntime

        config = TraceCraftConfig(
            console_enabled=False,
            jsonl_enabled=False,
            redaction=RedactionConfig(enabled=True),
        )

        # Create mock exporter to capture what's exported
        mock_exporter = MagicMock()

        runtime = TALRuntime(
            console=False,
            jsonl=False,
            config=config,
            exporters=[mock_exporter],
        )

        runtime.export(sample_run_with_pii)

        # Check that exported run has redacted content
        mock_exporter.export.assert_called_once()
        exported_run = mock_exporter.export.call_args[0][0]
        assert "test@example.com" not in str(exported_run.steps[0].inputs)

    def test_export_sampling_filters_runs(self, sample_run) -> None:
        """Export should not export runs that are sampled out."""
        from tracecraft.core.config import SamplingConfig, TraceCraftConfig
        from tracecraft.core.runtime import TALRuntime

        config = TraceCraftConfig(
            console_enabled=False,
            jsonl_enabled=False,
            sampling=SamplingConfig(rate=0.0),  # Drop all
        )

        mock_exporter = MagicMock()

        runtime = TALRuntime(
            console=False,
            jsonl=False,
            config=config,
            exporters=[mock_exporter],
        )

        runtime.export(sample_run)

        # Exporter should not be called since run was sampled out
        mock_exporter.export.assert_not_called()

    def test_processor_order_safety_default(self) -> None:
        """Default SAFETY order: enrichment → redaction → sampling."""
        from tracecraft.core.config import (
            ProcessorOrder,
            RedactionConfig,
            SamplingConfig,
            TraceCraftConfig,
        )
        from tracecraft.core.runtime import TALRuntime

        config = TraceCraftConfig(
            console_enabled=False,
            jsonl_enabled=False,
            processor_order=ProcessorOrder.SAFETY,
            redaction=RedactionConfig(enabled=True),
            sampling=SamplingConfig(rate=0.5),  # < 1.0 to include sampling processor
        )

        runtime = TALRuntime(
            console=False,
            jsonl=False,
            config=config,
        )

        # Check processor order
        processor_names = [p.name for p in runtime._processors]

        enrichment_idx = next(
            (i for i, name in enumerate(processor_names) if "Enrichment" in name),
            -1,
        )
        redaction_idx = next(
            (i for i, name in enumerate(processor_names) if "Redaction" in name),
            -1,
        )
        sampling_idx = next(
            (i for i, name in enumerate(processor_names) if "Sampling" in name),
            -1,
        )

        # All should exist
        assert enrichment_idx >= 0
        assert redaction_idx >= 0
        assert sampling_idx >= 0

        # SAFETY order: enrichment < redaction < sampling
        assert enrichment_idx < redaction_idx < sampling_idx

    def test_processor_order_efficiency(self) -> None:
        """EFFICIENCY order: sampling → redaction → enrichment."""
        from tracecraft.core.config import (
            ProcessorOrder,
            RedactionConfig,
            SamplingConfig,
            TraceCraftConfig,
        )
        from tracecraft.core.runtime import TALRuntime

        config = TraceCraftConfig(
            console_enabled=False,
            jsonl_enabled=False,
            processor_order=ProcessorOrder.EFFICIENCY,
            redaction=RedactionConfig(enabled=True),
            sampling=SamplingConfig(rate=0.5),  # < 1.0 to include sampling processor
        )

        runtime = TALRuntime(
            console=False,
            jsonl=False,
            config=config,
        )

        # Check processor order
        processor_names = [p.name for p in runtime._processors]

        sampling_idx = next(
            (i for i, name in enumerate(processor_names) if "Sampling" in name),
            -1,
        )
        redaction_idx = next(
            (i for i, name in enumerate(processor_names) if "Redaction" in name),
            -1,
        )
        enrichment_idx = next(
            (i for i, name in enumerate(processor_names) if "Enrichment" in name),
            -1,
        )

        # All should exist
        assert sampling_idx >= 0
        assert redaction_idx >= 0
        assert enrichment_idx >= 0

        # EFFICIENCY order: sampling < redaction < enrichment
        assert sampling_idx < redaction_idx < enrichment_idx

    def test_processor_order_without_sampling(self) -> None:
        """Should work without sampling processor (rate=1.0, no error/slow options)."""
        from tracecraft.core.config import (
            ProcessorOrder,
            RedactionConfig,
            SamplingConfig,
            TraceCraftConfig,
        )
        from tracecraft.core.runtime import TALRuntime

        config = TraceCraftConfig(
            console_enabled=False,
            jsonl_enabled=False,
            processor_order=ProcessorOrder.SAFETY,
            redaction=RedactionConfig(enabled=True),
            sampling=SamplingConfig(
                rate=1.0,
                always_keep_errors=False,
                always_keep_slow=False,
            ),
        )

        runtime = TALRuntime(
            console=False,
            jsonl=False,
            config=config,
        )

        processor_names = [p.name for p in runtime._processors]

        # Should have enrichment and redaction but no sampling
        assert any("Enrichment" in name for name in processor_names)
        assert any("Redaction" in name for name in processor_names)
        assert not any("Sampling" in name for name in processor_names)


class TestEnvVarConfiguration:
    """Tests for environment variable configuration."""

    def test_env_var_redaction_enabled(self, sample_run_with_pii, monkeypatch) -> None:
        """TRACECRAFT_REDACTION_ENABLED=true should enable redaction."""
        monkeypatch.setenv("TRACECRAFT_REDACTION_ENABLED", "true")

        from tracecraft.core.config import load_config_from_env
        from tracecraft.core.runtime import TALRuntime

        config = load_config_from_env()

        mock_exporter = MagicMock()
        runtime = TALRuntime(
            console=False,
            jsonl=False,
            config=config,
            exporters=[mock_exporter],
        )

        runtime.export(sample_run_with_pii)

        # Should have redacted
        if mock_exporter.export.called:
            exported_run = mock_exporter.export.call_args[0][0]
            assert "test@example.com" not in str(exported_run.steps[0].inputs)

    def test_env_var_sampling_rate(self, sample_run, monkeypatch) -> None:
        """TRACECRAFT_SAMPLING_RATE should control sampling."""
        monkeypatch.setenv("TRACECRAFT_SAMPLING_RATE", "0.0")

        from tracecraft.core.config import load_config_from_env
        from tracecraft.core.runtime import TALRuntime

        config = load_config_from_env()
        assert config.sampling.rate == 0.0

        mock_exporter = MagicMock()
        runtime = TALRuntime(
            console=False,
            jsonl=False,
            config=config,
            exporters=[mock_exporter],
        )

        runtime.export(sample_run)

        # Should not export at 0% rate
        mock_exporter.export.assert_not_called()


# Fixtures for processor tests
@pytest.fixture
def sample_run_with_pii(sample_timestamp) -> AgentRun:
    """Create a run with PII in step inputs."""
    from tracecraft.core.models import AgentRun, Step, StepType

    run_id = uuid4()
    step = Step(
        trace_id=run_id,
        type=StepType.LLM,
        name="llm_with_pii",
        start_time=sample_timestamp,
        inputs={"prompt": "Contact me at test@example.com or call 555-123-4567"},
        outputs={"response": "Email sent to test@example.com"},
    )

    return AgentRun(
        id=run_id,
        name="run_with_pii",
        start_time=sample_timestamp,
        steps=[step],
    )


@pytest.fixture
def sample_run_with_error(sample_timestamp) -> AgentRun:
    """Create a run with an error."""
    from tracecraft.core.models import AgentRun, Step, StepType

    run_id = uuid4()
    step = Step(
        trace_id=run_id,
        type=StepType.LLM,
        name="llm_error",
        start_time=sample_timestamp,
        error="API rate limit exceeded",
        error_type="RateLimitError",
    )

    return AgentRun(
        id=run_id,
        name="run_with_error",
        start_time=sample_timestamp,
        steps=[step],
        error_count=1,
    )


@pytest.fixture
def sample_run_with_llm_step(sample_timestamp) -> AgentRun:
    """Create a run with an LLM step for enrichment testing."""
    from tracecraft.core.models import AgentRun, Step, StepType

    run_id = uuid4()
    step = Step(
        trace_id=run_id,
        type=StepType.LLM,
        name="llm_call",
        start_time=sample_timestamp,
        model_name="gpt-4",
        inputs={"messages": [{"content": "Hello, how are you?"}]},
        outputs={"content": "I'm doing well, thank you for asking!"},
    )

    return AgentRun(
        id=run_id,
        name="run_with_llm",
        start_time=sample_timestamp,
        steps=[step],
    )
