"""
Tests for model name normalization and fuzzy matching.

Verifies that model pricing lookup works correctly for various
model name formats and variants.
"""

from __future__ import annotations

import pytest

from tracecraft.processors.enrichment import (
    DEFAULT_PRICING,
    ModelPricing,
    TokenEnrichmentProcessor,
    find_best_pricing_match,
    normalize_model_name,
)


class TestNormalizeModelName:
    """Tests for the normalize_model_name function."""

    def test_empty_string_returns_empty(self) -> None:
        """Empty string should return empty string."""
        assert normalize_model_name("") == ""

    def test_lowercase_conversion(self) -> None:
        """Model names should be converted to lowercase."""
        assert normalize_model_name("GPT-4") == "gpt-4"
        assert normalize_model_name("Claude-3-Sonnet") == "claude-3-sonnet"

    def test_strips_whitespace(self) -> None:
        """Whitespace should be stripped."""
        assert normalize_model_name("  gpt-4  ") == "gpt-4"

    def test_strips_provider_prefixes(self) -> None:
        """Provider prefixes should be stripped."""
        assert normalize_model_name("openai/gpt-4") == "gpt-4"
        assert normalize_model_name("anthropic/claude-3-sonnet") == "claude-3-sonnet"
        assert normalize_model_name("google/gemini-pro") == "gemini-pro"
        assert normalize_model_name("azure/gpt-4") == "gpt-4"
        assert normalize_model_name("together/mistral-7b") == "mistral-7b"

    def test_strips_date_suffixes(self) -> None:
        """Date suffixes should be stripped."""
        assert normalize_model_name("gpt-4-0613") == "gpt-4"
        assert normalize_model_name("gpt-4-1106") == "gpt-4"
        assert normalize_model_name("claude-3-sonnet-20240229") == "claude-3-sonnet"
        assert normalize_model_name("gpt-3.5-turbo-0125") == "gpt-3.5-turbo"

    def test_preserves_model_variants(self) -> None:
        """Model variants like -mini, -turbo should be preserved."""
        assert normalize_model_name("gpt-4-turbo") == "gpt-4-turbo"
        assert normalize_model_name("gpt-4o-mini") == "gpt-4o-mini"
        assert normalize_model_name("o1-mini") == "o1-mini"

    def test_handles_mixed_format(self) -> None:
        """Should handle combination of prefix and date suffix."""
        assert normalize_model_name("openai/gpt-4-0613") == "gpt-4"
        assert normalize_model_name("anthropic/claude-3-sonnet-20240229") == "claude-3-sonnet"


class TestFindBestPricingMatch:
    """Tests for the find_best_pricing_match function."""

    @pytest.fixture
    def sample_pricing_map(self) -> dict[str, ModelPricing]:
        """Create a sample pricing map for testing."""
        return {
            "gpt-4": ModelPricing(model="gpt-4", input_cost_per_1k_tokens=0.03),
            "gpt-4o": ModelPricing(model="gpt-4o", input_cost_per_1k_tokens=0.005),
            "gpt-4o-mini": ModelPricing(model="gpt-4o-mini", input_cost_per_1k_tokens=0.00015),
            "claude-3.5-sonnet": ModelPricing(
                model="claude-3.5-sonnet", input_cost_per_1k_tokens=0.003
            ),
        }

    def test_exact_match(self, sample_pricing_map) -> None:
        """Exact match should return correct pricing."""
        result = find_best_pricing_match("gpt-4", sample_pricing_map)
        assert result is not None
        assert result.model == "gpt-4"

    def test_normalized_match(self, sample_pricing_map) -> None:
        """Normalized name should match."""
        result = find_best_pricing_match("GPT-4", sample_pricing_map)
        assert result is not None
        assert result.model == "gpt-4"

    def test_prefix_match(self, sample_pricing_map) -> None:
        """Model with date suffix should match base model."""
        result = find_best_pricing_match("gpt-4-0613", sample_pricing_map)
        assert result is not None
        assert result.model == "gpt-4"

    def test_most_specific_match(self, sample_pricing_map) -> None:
        """Should match most specific model (gpt-4o-mini before gpt-4o)."""
        result = find_best_pricing_match("gpt-4o-mini", sample_pricing_map)
        assert result is not None
        assert result.model == "gpt-4o-mini"

    def test_provider_prefix_stripped(self, sample_pricing_map) -> None:
        """Provider prefix should be stripped for matching."""
        result = find_best_pricing_match("openai/gpt-4", sample_pricing_map)
        assert result is not None
        assert result.model == "gpt-4"

    def test_no_match_returns_none(self, sample_pricing_map) -> None:
        """Unknown model should return None."""
        result = find_best_pricing_match("unknown-model", sample_pricing_map)
        assert result is None

    def test_empty_model_returns_none(self, sample_pricing_map) -> None:
        """Empty model name should return None."""
        result = find_best_pricing_match("", sample_pricing_map)
        assert result is None


class TestTokenEnrichmentProcessorPricing:
    """Tests for TokenEnrichmentProcessor pricing lookup."""

    def test_get_pricing_exact_match(self) -> None:
        """get_pricing should find exact model matches."""
        processor = TokenEnrichmentProcessor()

        pricing = processor.get_pricing("gpt-4")
        assert pricing is not None
        assert pricing.model == "gpt-4"

    def test_get_pricing_with_date_suffix(self) -> None:
        """get_pricing should match models with date suffixes."""
        processor = TokenEnrichmentProcessor()

        pricing = processor.get_pricing("gpt-4-0613")
        assert pricing is not None
        assert pricing.model == "gpt-4"

    def test_get_pricing_with_provider_prefix(self) -> None:
        """get_pricing should match models with provider prefixes."""
        processor = TokenEnrichmentProcessor()

        pricing = processor.get_pricing("openai/gpt-4o")
        assert pricing is not None
        assert pricing.model == "gpt-4o"

    def test_get_pricing_claude_variants(self) -> None:
        """get_pricing should match Claude model variants."""
        processor = TokenEnrichmentProcessor()

        # Test various Claude formats
        for model_name in [
            "claude-3.5-sonnet",
            "claude-3.5-sonnet-20240229",
            "anthropic/claude-3.5-sonnet",
        ]:
            pricing = processor.get_pricing(model_name)
            assert pricing is not None, f"Failed for {model_name}"
            assert "claude" in pricing.model.lower()

    def test_get_pricing_all_default_models(self) -> None:
        """All default models should be findable."""
        processor = TokenEnrichmentProcessor()

        for pricing in DEFAULT_PRICING:
            result = processor.get_pricing(pricing.model)
            assert result is not None, f"Failed to find {pricing.model}"
            assert result.model == pricing.model

    def test_custom_pricing_overrides_default(self) -> None:
        """Custom pricing should override default pricing."""
        custom = ModelPricing(
            model="gpt-4",
            input_cost_per_1k_tokens=0.99,  # Custom price
            output_cost_per_1k_tokens=0.99,
        )
        processor = TokenEnrichmentProcessor(pricing_data=[custom])

        pricing = processor.get_pricing("gpt-4")
        assert pricing is not None
        assert pricing.input_cost_per_1k_tokens == 0.99

    def test_new_models_have_pricing(self) -> None:
        """All newly added models should have pricing data."""
        processor = TokenEnrichmentProcessor()

        new_models = [
            "gpt-4o-mini",
            "o1",
            "o1-mini",
            "o1-preview",
            "claude-3.5-sonnet",
            "claude-3.5-haiku",
            "claude-opus-4",
            "claude-sonnet-4",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-2.0-flash",
            "mistral-large",
            "mistral-medium",
            "mistral-small",
        ]

        for model in new_models:
            pricing = processor.get_pricing(model)
            assert pricing is not None, f"Missing pricing for {model}"
            assert pricing.get_input_cost_per_token() > 0


class TestClaudeModelVariations:
    """Tests for Claude model name variations matching."""

    def test_claude_dash_vs_dot_naming(self) -> None:
        """Claude 3.5 should match whether written with dot or dash."""
        processor = TokenEnrichmentProcessor()

        # Both formats should find the same pricing
        dot_pricing = processor.get_pricing("claude-3.5-sonnet")
        dash_pricing = processor.get_pricing("claude-3-5-sonnet")

        assert dot_pricing is not None
        assert dash_pricing is not None
        # Both should map to the same model
        assert dot_pricing.model == dash_pricing.model

    def test_claude_4_naming(self) -> None:
        """Claude 4 models should match both naming formats."""
        processor = TokenEnrichmentProcessor()

        # claude-opus-4 format
        opus_4 = processor.get_pricing("claude-opus-4")
        assert opus_4 is not None

        # claude-4-opus format should also match
        opus_4_alt = processor.get_pricing("claude-4-opus")
        assert opus_4_alt is not None
