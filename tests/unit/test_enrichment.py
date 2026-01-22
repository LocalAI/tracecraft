"""
Tests for the token enrichment processor.

Tests token counting and cost calculation functionality.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from agenttrace.core.models import Step, StepType
from agenttrace.processors.enrichment import (
    ModelPricing,
    TokenEnrichmentProcessor,
    count_tokens,
    estimate_cost,
)


class TestCountTokens:
    """Tests for token counting function."""

    def test_count_tokens_simple_text(self) -> None:
        """Should count tokens in simple text."""
        text = "Hello, world!"
        count = count_tokens(text)
        assert count > 0
        assert isinstance(count, int)

    def test_count_tokens_empty_string(self) -> None:
        """Should return 0 for empty string."""
        assert count_tokens("") == 0

    def test_count_tokens_longer_text(self) -> None:
        """Should count tokens in longer text."""
        text = "The quick brown fox jumps over the lazy dog. " * 10
        count = count_tokens(text)
        assert count > 50  # Should be many tokens

    def test_count_tokens_with_model(self) -> None:
        """Should accept model parameter for tiktoken."""
        text = "Hello, world!"
        count = count_tokens(text, model="gpt-4")
        assert count > 0

    def test_fallback_counting(self) -> None:
        """Should use fallback when tiktoken not available for model."""
        text = "Hello, world!"
        # Use an unknown model to trigger fallback
        count = count_tokens(text, model="unknown-model-xyz")
        assert count > 0
        # Fallback is approximately len(text) / 4
        assert count == len(text) // 4 or count > 0

    def test_fallback_counting_approximation(self) -> None:
        """Fallback counting should approximate len/4."""
        text = "a" * 100
        count = count_tokens(text, model="unknown-model")
        # Fallback divides by 4
        assert count == 25


class TestModelPricing:
    """Tests for ModelPricing dataclass."""

    def test_pricing_with_rates(self) -> None:
        """Should store per-token pricing."""
        pricing = ModelPricing(
            model="gpt-4",
            input_cost_per_token=0.00003,
            output_cost_per_token=0.00006,
        )
        assert pricing.model == "gpt-4"
        assert pricing.input_cost_per_token == 0.00003
        assert pricing.output_cost_per_token == 0.00006

    def test_pricing_with_1k_rates(self) -> None:
        """Should support per-1K token pricing."""
        pricing = ModelPricing(
            model="gpt-3.5-turbo",
            input_cost_per_1k_tokens=0.0005,
            output_cost_per_1k_tokens=0.0015,
        )
        assert pricing.input_cost_per_1k_tokens == 0.0005
        assert pricing.output_cost_per_1k_tokens == 0.0015


class TestEstimateCost:
    """Tests for cost estimation function."""

    def test_estimate_cost_with_per_token_pricing(self) -> None:
        """Should calculate cost using per-token rates."""
        pricing = ModelPricing(
            model="gpt-4",
            input_cost_per_token=0.00003,
            output_cost_per_token=0.00006,
        )
        cost = estimate_cost(
            input_tokens=1000,
            output_tokens=500,
            pricing=pricing,
        )
        expected = (1000 * 0.00003) + (500 * 0.00006)
        assert cost == pytest.approx(expected)

    def test_estimate_cost_with_1k_pricing(self) -> None:
        """Should calculate cost using per-1K rates."""
        pricing = ModelPricing(
            model="gpt-3.5-turbo",
            input_cost_per_1k_tokens=0.0005,
            output_cost_per_1k_tokens=0.0015,
        )
        cost = estimate_cost(
            input_tokens=1000,
            output_tokens=500,
            pricing=pricing,
        )
        expected = (1000 / 1000 * 0.0005) + (500 / 1000 * 0.0015)
        assert cost == pytest.approx(expected)

    def test_estimate_cost_zero_tokens(self) -> None:
        """Should return 0 for zero tokens."""
        pricing = ModelPricing(
            model="gpt-4",
            input_cost_per_token=0.00003,
            output_cost_per_token=0.00006,
        )
        cost = estimate_cost(input_tokens=0, output_tokens=0, pricing=pricing)
        assert cost == 0.0

    def test_estimate_cost_input_only(self) -> None:
        """Should handle input-only cost."""
        pricing = ModelPricing(
            model="gpt-4",
            input_cost_per_token=0.00003,
            output_cost_per_token=0.00006,
        )
        cost = estimate_cost(input_tokens=1000, output_tokens=0, pricing=pricing)
        assert cost == pytest.approx(0.03)


class TestTokenEnrichmentProcessor:
    """Tests for TokenEnrichmentProcessor."""

    @pytest.fixture
    def sample_step(self) -> Step:
        """Create a sample LLM step."""
        return Step(
            trace_id=uuid4(),
            type=StepType.LLM,
            name="chat_completion",
            start_time=datetime.now(UTC),
            model_name="gpt-4",
            inputs={"prompt": "Hello, how are you?"},
            outputs={"result": "I'm doing well, thank you for asking!"},
        )

    @pytest.fixture
    def processor_with_pricing(self) -> TokenEnrichmentProcessor:
        """Create processor with GPT-4 pricing."""
        pricing = ModelPricing(
            model="gpt-4",
            input_cost_per_token=0.00003,
            output_cost_per_token=0.00006,
        )
        return TokenEnrichmentProcessor(pricing_data=[pricing])

    def test_enrich_step_counts_tokens(
        self,
        sample_step: Step,
        processor_with_pricing: TokenEnrichmentProcessor,
    ) -> None:
        """Should count and add tokens to step."""
        processor_with_pricing.enrich_step(sample_step)
        assert sample_step.input_tokens is not None
        assert sample_step.input_tokens > 0
        assert sample_step.output_tokens is not None
        assert sample_step.output_tokens > 0

    def test_enrich_step_calculates_cost(
        self,
        sample_step: Step,
        processor_with_pricing: TokenEnrichmentProcessor,
    ) -> None:
        """Should calculate cost for step."""
        processor_with_pricing.enrich_step(sample_step)
        assert sample_step.cost_usd is not None
        assert sample_step.cost_usd > 0

    def test_enrich_step_skips_non_llm(
        self,
        processor_with_pricing: TokenEnrichmentProcessor,
    ) -> None:
        """Should skip non-LLM steps."""
        tool_step = Step(
            trace_id=uuid4(),
            type=StepType.TOOL,
            name="search",
            start_time=datetime.now(UTC),
            inputs={"query": "test"},
        )
        processor_with_pricing.enrich_step(tool_step)
        assert tool_step.input_tokens is None
        assert tool_step.cost_usd is None

    def test_enrich_step_without_pricing(
        self,
        sample_step: Step,
    ) -> None:
        """Should count tokens even without pricing data."""
        # Disable default pricing so no cost is calculated
        processor = TokenEnrichmentProcessor(use_default_pricing=False)
        processor.enrich_step(sample_step)
        assert sample_step.input_tokens is not None
        assert sample_step.input_tokens > 0
        # No cost calculated without pricing
        assert sample_step.cost_usd is None

    def test_enrich_step_preserves_existing_tokens(
        self,
        sample_step: Step,
        processor_with_pricing: TokenEnrichmentProcessor,
    ) -> None:
        """Should not overwrite existing token counts."""
        sample_step.input_tokens = 100
        sample_step.output_tokens = 50
        processor_with_pricing.enrich_step(sample_step)
        assert sample_step.input_tokens == 100
        assert sample_step.output_tokens == 50

    def test_enrich_step_handles_missing_inputs(
        self,
        processor_with_pricing: TokenEnrichmentProcessor,
    ) -> None:
        """Should handle steps with missing inputs/outputs."""
        step = Step(
            trace_id=uuid4(),
            type=StepType.LLM,
            name="completion",
            start_time=datetime.now(UTC),
            model_name="gpt-4",
        )
        # Should not raise
        processor_with_pricing.enrich_step(step)
        assert step.input_tokens == 0 or step.input_tokens is None

    def test_enrich_step_with_string_input(
        self,
        processor_with_pricing: TokenEnrichmentProcessor,
    ) -> None:
        """Should handle string input in inputs dict."""
        step = Step(
            trace_id=uuid4(),
            type=StepType.LLM,
            name="completion",
            start_time=datetime.now(UTC),
            model_name="gpt-4",
            inputs={"messages": "Hello world"},
        )
        processor_with_pricing.enrich_step(step)
        assert step.input_tokens is not None
        assert step.input_tokens > 0


class TestTokenEnrichmentProcessorBulkOperations:
    """Tests for bulk enrichment operations."""

    def test_enrich_multiple_steps(self) -> None:
        """Should enrich multiple steps."""
        trace_id = uuid4()
        steps = [
            Step(
                trace_id=trace_id,
                type=StepType.LLM,
                name=f"step_{i}",
                start_time=datetime.now(UTC),
                inputs={"prompt": f"Message {i}"},
                outputs={"result": f"Response {i}"},
            )
            for i in range(3)
        ]
        processor = TokenEnrichmentProcessor()
        for step in steps:
            processor.enrich_step(step)

        for step in steps:
            assert step.input_tokens is not None
            assert step.output_tokens is not None


class TestDefaultPricing:
    """Tests for default pricing data."""

    def test_default_pricing_includes_common_models(self) -> None:
        """Should include pricing for common models."""
        processor = TokenEnrichmentProcessor(use_default_pricing=True)
        # Check that common models are available
        assert processor.get_pricing("gpt-4") is not None
        assert processor.get_pricing("gpt-3.5-turbo") is not None
        assert processor.get_pricing("claude-3-opus") is not None

    def test_get_pricing_unknown_model(self) -> None:
        """Should return None for unknown models."""
        processor = TokenEnrichmentProcessor()
        assert processor.get_pricing("unknown-model-xyz") is None

    def test_custom_pricing_overrides_default(self) -> None:
        """Custom pricing should override defaults."""
        custom_pricing = ModelPricing(
            model="gpt-4",
            input_cost_per_token=0.001,  # Much higher than default
            output_cost_per_token=0.002,
        )
        processor = TokenEnrichmentProcessor(
            pricing_data=[custom_pricing],
            use_default_pricing=True,
        )
        pricing = processor.get_pricing("gpt-4")
        assert pricing is not None
        assert pricing.input_cost_per_token == 0.001
