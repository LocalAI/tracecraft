"""
Token counting and cost enrichment processor.

Provides token counting using tiktoken (with fallback) and
cost calculation based on model pricing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from types import ModuleType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agenttrace.core.models import Step

# Try to import tiktoken for accurate token counting
# Declare variable with proper type for mypy
tiktoken: ModuleType | None

try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    tiktoken = None


# Model to encoding mapping for tiktoken
MODEL_ENCODING_MAP: dict[str, str] = {
    # OpenAI models
    "gpt-4": "cl100k_base",
    "gpt-4-turbo": "cl100k_base",
    "gpt-4o": "o200k_base",
    "gpt-4o-mini": "o200k_base",
    "gpt-3.5-turbo": "cl100k_base",
    "o1": "o200k_base",
    "o1-mini": "o200k_base",
    "o1-preview": "o200k_base",
    # Anthropic models (approximation using cl100k)
    "claude-3-opus": "cl100k_base",
    "claude-3-sonnet": "cl100k_base",
    "claude-3-haiku": "cl100k_base",
    "claude-3.5-sonnet": "cl100k_base",
    "claude-3.5-haiku": "cl100k_base",
    "claude-opus-4": "cl100k_base",
    "claude-sonnet-4": "cl100k_base",
    # Google models (approximation)
    "gemini-1.5-pro": "cl100k_base",
    "gemini-1.5-flash": "cl100k_base",
    "gemini-2.0-flash": "cl100k_base",
    "gemini-pro": "cl100k_base",
    # Mistral models (approximation)
    "mistral-large": "cl100k_base",
    "mistral-medium": "cl100k_base",
    "mistral-small": "cl100k_base",
}


def count_tokens(text: str, model: str | None = None) -> int:
    """
    Count tokens in text.

    Uses tiktoken if available and model is known, otherwise
    falls back to len(text) // 4 approximation.

    Args:
        text: The text to count tokens for.
        model: Optional model name for accurate counting.

    Returns:
        Number of tokens.
    """
    if not text:
        return 0

    if TIKTOKEN_AVAILABLE and tiktoken is not None and model:
        encoding_name = MODEL_ENCODING_MAP.get(model)
        if encoding_name:
            try:
                encoding = tiktoken.get_encoding(encoding_name)
                return len(encoding.encode(text))
            except Exception:  # nosec B110 - intentional fallback
                pass

        # Try to get encoding for the model directly
        try:
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except Exception:  # nosec B110 - intentional fallback
            pass

    # Fallback: approximate as len(text) / 4
    return len(text) // 4


@dataclass
class ModelPricing:
    """Pricing information for a model."""

    model: str
    input_cost_per_token: float | None = None
    output_cost_per_token: float | None = None
    input_cost_per_1k_tokens: float | None = None
    output_cost_per_1k_tokens: float | None = None

    def get_input_cost_per_token(self) -> float:
        """Get input cost per token."""
        if self.input_cost_per_token is not None:
            return self.input_cost_per_token
        if self.input_cost_per_1k_tokens is not None:
            return self.input_cost_per_1k_tokens / 1000
        return 0.0

    def get_output_cost_per_token(self) -> float:
        """Get output cost per token."""
        if self.output_cost_per_token is not None:
            return self.output_cost_per_token
        if self.output_cost_per_1k_tokens is not None:
            return self.output_cost_per_1k_tokens / 1000
        return 0.0


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    pricing: ModelPricing,
) -> float:
    """
    Estimate cost for a given token count.

    Args:
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        pricing: Model pricing information.

    Returns:
        Estimated cost in USD.
    """
    input_cost = input_tokens * pricing.get_input_cost_per_token()
    output_cost = output_tokens * pricing.get_output_cost_per_token()
    return input_cost + output_cost


# Default pricing data for common models (as of January 2025)
DEFAULT_PRICING: list[ModelPricing] = [
    # OpenAI models
    ModelPricing(
        model="gpt-4",
        input_cost_per_1k_tokens=0.03,
        output_cost_per_1k_tokens=0.06,
    ),
    ModelPricing(
        model="gpt-4-turbo",
        input_cost_per_1k_tokens=0.01,
        output_cost_per_1k_tokens=0.03,
    ),
    ModelPricing(
        model="gpt-4o",
        input_cost_per_1k_tokens=0.0025,
        output_cost_per_1k_tokens=0.01,
    ),
    ModelPricing(
        model="gpt-4o-mini",
        input_cost_per_1k_tokens=0.00015,
        output_cost_per_1k_tokens=0.0006,
    ),
    ModelPricing(
        model="gpt-3.5-turbo",
        input_cost_per_1k_tokens=0.0005,
        output_cost_per_1k_tokens=0.0015,
    ),
    ModelPricing(
        model="o1",
        input_cost_per_1k_tokens=0.015,
        output_cost_per_1k_tokens=0.06,
    ),
    ModelPricing(
        model="o1-mini",
        input_cost_per_1k_tokens=0.003,
        output_cost_per_1k_tokens=0.012,
    ),
    ModelPricing(
        model="o1-preview",
        input_cost_per_1k_tokens=0.015,
        output_cost_per_1k_tokens=0.06,
    ),
    # Anthropic models
    ModelPricing(
        model="claude-3-opus",
        input_cost_per_1k_tokens=0.015,
        output_cost_per_1k_tokens=0.075,
    ),
    ModelPricing(
        model="claude-3-sonnet",
        input_cost_per_1k_tokens=0.003,
        output_cost_per_1k_tokens=0.015,
    ),
    ModelPricing(
        model="claude-3-haiku",
        input_cost_per_1k_tokens=0.00025,
        output_cost_per_1k_tokens=0.00125,
    ),
    ModelPricing(
        model="claude-3.5-sonnet",
        input_cost_per_1k_tokens=0.003,
        output_cost_per_1k_tokens=0.015,
    ),
    ModelPricing(
        model="claude-3.5-haiku",
        input_cost_per_1k_tokens=0.0008,
        output_cost_per_1k_tokens=0.004,
    ),
    ModelPricing(
        model="claude-opus-4",
        input_cost_per_1k_tokens=0.015,
        output_cost_per_1k_tokens=0.075,
    ),
    ModelPricing(
        model="claude-sonnet-4",
        input_cost_per_1k_tokens=0.003,
        output_cost_per_1k_tokens=0.015,
    ),
    # Google Gemini models
    ModelPricing(
        model="gemini-1.5-pro",
        input_cost_per_1k_tokens=0.00125,
        output_cost_per_1k_tokens=0.005,
    ),
    ModelPricing(
        model="gemini-1.5-flash",
        input_cost_per_1k_tokens=0.000075,
        output_cost_per_1k_tokens=0.0003,
    ),
    ModelPricing(
        model="gemini-2.0-flash",
        input_cost_per_1k_tokens=0.0001,
        output_cost_per_1k_tokens=0.0004,
    ),
    ModelPricing(
        model="gemini-pro",
        input_cost_per_1k_tokens=0.0005,
        output_cost_per_1k_tokens=0.0015,
    ),
    # Mistral models
    ModelPricing(
        model="mistral-large",
        input_cost_per_1k_tokens=0.002,
        output_cost_per_1k_tokens=0.006,
    ),
    ModelPricing(
        model="mistral-medium",
        input_cost_per_1k_tokens=0.00275,
        output_cost_per_1k_tokens=0.0081,
    ),
    ModelPricing(
        model="mistral-small",
        input_cost_per_1k_tokens=0.0002,
        output_cost_per_1k_tokens=0.0006,
    ),
]


def normalize_model_name(model: str) -> str:
    """
    Normalize a model name for matching.

    Handles various naming conventions and extracts the base model name.

    Args:
        model: The model name to normalize.

    Returns:
        Normalized model name.
    """
    if not model:
        return ""

    # Convert to lowercase
    normalized = model.lower().strip()

    # Common provider prefixes to strip
    prefixes = [
        "openai/",
        "anthropic/",
        "google/",
        "mistral/",
        "azure/",
        "together/",
        "groq/",
        "anyscale/",
    ]
    for prefix in prefixes:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]

    # Handle date suffixes (e.g., gpt-4-0613, claude-3-sonnet-20240229)
    # Keep the base model name
    normalized = re.sub(r"-\d{4}-?\d{2}-?\d{2}$", "", normalized)
    normalized = re.sub(r"-\d{4}$", "", normalized)

    # Handle version suffixes like -latest, -preview
    # Keep these as they may affect pricing
    # normalized = re.sub(r"-(latest|preview)$", "", normalized)

    return normalized


def find_best_pricing_match(
    model: str, pricing_map: dict[str, ModelPricing]
) -> ModelPricing | None:
    """
    Find the best matching pricing for a model using fuzzy matching.

    Args:
        model: The model name to find pricing for.
        pricing_map: Map of known model names to pricing.

    Returns:
        Best matching ModelPricing or None.
    """
    if not model:
        return None

    normalized = normalize_model_name(model)

    # Try exact match first
    if normalized in pricing_map:
        return pricing_map[normalized]

    # Try matching with the original model name
    if model in pricing_map:
        return pricing_map[model]

    # Try prefix matching (e.g., "gpt-4-0613" matches "gpt-4")
    # Sort by length descending to match most specific first
    for known_model in sorted(pricing_map.keys(), key=len, reverse=True):
        if normalized.startswith(known_model):
            return pricing_map[known_model]

    # Try if known model is prefix of normalized (e.g., "claude-3.5-sonnet" for "claude-3.5-sonnet-v2")
    for known_model in sorted(pricing_map.keys(), key=len, reverse=True):
        normalized_known = normalize_model_name(known_model)
        if normalized.startswith(normalized_known):
            return pricing_map[known_model]

    # Try fuzzy matching for common patterns
    # Handle Claude model naming variations
    claude_mappings = {
        "claude-3-5-sonnet": "claude-3.5-sonnet",
        "claude-35-sonnet": "claude-3.5-sonnet",
        "claude-3-5-haiku": "claude-3.5-haiku",
        "claude-35-haiku": "claude-3.5-haiku",
        "claude-4-opus": "claude-opus-4",
        "claude-4-sonnet": "claude-sonnet-4",
    }
    for variant, canonical in claude_mappings.items():
        if variant in normalized and canonical in pricing_map:
            return pricing_map[canonical]

    return None


@dataclass
class TokenEnrichmentProcessor:
    """
    Processor for enriching steps with token counts and costs.

    Counts tokens in step inputs/outputs and calculates costs
    based on model pricing. Includes fuzzy matching for model variants.
    """

    pricing_data: list[ModelPricing] = field(default_factory=list)
    use_default_pricing: bool = True
    _pricing_map: dict[str, ModelPricing] = field(
        default_factory=dict,
        init=False,
    )

    def __post_init__(self) -> None:
        """Build pricing lookup map."""
        # Add default pricing first
        if self.use_default_pricing:
            for pricing in DEFAULT_PRICING:
                self._pricing_map[pricing.model] = pricing
                # Also add normalized version
                normalized = normalize_model_name(pricing.model)
                if normalized != pricing.model:
                    self._pricing_map[normalized] = pricing

        # Custom pricing overrides defaults
        for pricing in self.pricing_data:
            self._pricing_map[pricing.model] = pricing
            normalized = normalize_model_name(pricing.model)
            if normalized != pricing.model:
                self._pricing_map[normalized] = pricing

    def get_pricing(self, model: str) -> ModelPricing | None:
        """
        Get pricing for a model with fuzzy matching.

        Args:
            model: The model name to get pricing for.

        Returns:
            ModelPricing if found, None otherwise.
        """
        return find_best_pricing_match(model, self._pricing_map)

    def enrich_step(self, step: Step) -> None:
        """
        Enrich a step with token counts and cost.

        Only processes LLM steps. Skips if tokens already set.

        Args:
            step: The step to enrich.
        """
        from agenttrace.core.models import StepType

        # Only enrich LLM steps
        if step.type != StepType.LLM:
            return

        model = step.model_name

        # Count input tokens if not already set
        if step.input_tokens is None:
            input_text = self._extract_text(step.inputs)
            if input_text:
                step.input_tokens = count_tokens(input_text, model)

        # Count output tokens if not already set
        if step.output_tokens is None:
            output_text = self._extract_text(step.outputs)
            if output_text:
                step.output_tokens = count_tokens(output_text, model)

        # Calculate cost if pricing available and tokens counted
        if model and step.cost_usd is None:
            pricing = self.get_pricing(model)
            if pricing:
                input_tokens = step.input_tokens or 0
                output_tokens = step.output_tokens or 0
                step.cost_usd = estimate_cost(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    pricing=pricing,
                )

    def _extract_text(self, data: dict[str, Any] | None) -> str:
        """Extract text content from inputs/outputs dict."""
        if not data:
            return ""

        texts: list[str] = []

        for _key, value in data.items():
            if isinstance(value, str):
                texts.append(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        texts.append(item)
                    elif isinstance(item, dict):
                        # Handle message format {"content": "..."}
                        content = item.get("content")
                        if isinstance(content, str):
                            texts.append(content)
            elif isinstance(value, dict):
                content = value.get("content")
                if isinstance(content, str):
                    texts.append(content)

        return " ".join(texts)
