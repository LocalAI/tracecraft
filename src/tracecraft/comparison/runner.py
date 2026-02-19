"""
Comparison runner for executing trace comparisons via LLM providers.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from tracecraft.comparison.models import ComparisonRequest, ComparisonResult
from tracecraft.comparison.prompts import PromptManager
from tracecraft.processors.enrichment import (
    DEFAULT_PRICING,
    ModelPricing,
    normalize_model_name,
)

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun, Step
    from tracecraft.storage.base import BaseTraceStore

logger = logging.getLogger(__name__)


class ComparisonRunner:
    """Executes trace comparisons using LLM providers.

    Supports OpenAI and Anthropic providers. The runner:
    1. Loads traces from storage
    2. Formats them for comparison
    3. Sends to LLM with selected prompt
    4. Returns structured result

    Example:
        runner = ComparisonRunner(store)
        request = ComparisonRequest(
            trace_a_id=trace_a.id,
            trace_b_id=trace_b.id,
            prompt_id="diff-summary",
            model="gpt-4o",
            provider="openai"
        )
        result = await runner.run_comparison(request)
        print(result.output)
    """

    def __init__(self, store: BaseTraceStore) -> None:
        """Initialize comparison runner.

        Args:
            store: Storage backend to load traces from.
        """
        self.store = store
        self.prompt_manager = PromptManager()
        self._pricing_map: dict[str, ModelPricing] = {}
        self._init_pricing()

    def _init_pricing(self) -> None:
        """Initialize pricing lookup map."""
        for p in DEFAULT_PRICING:
            self._pricing_map[p.model] = p
            normalized = normalize_model_name(p.model)
            if normalized != p.model:
                self._pricing_map[normalized] = p

    async def run_comparison(self, request: ComparisonRequest) -> ComparisonResult:
        """Run a comparison between two traces.

        Args:
            request: The comparison request with trace IDs and settings.

        Returns:
            ComparisonResult with the LLM output and metadata.

        Raises:
            ValueError: If traces not found or prompt not found.
            RuntimeError: If provider is not available.
        """
        # Load traces
        trace_a = self.store.get(str(request.trace_a_id))
        trace_b = self.store.get(str(request.trace_b_id))

        if not trace_a:
            raise ValueError(f"Trace A not found: {request.trace_a_id}")
        if not trace_b:
            raise ValueError(f"Trace B not found: {request.trace_b_id}")

        # Get prompt
        prompt = self.prompt_manager.get_prompt(request.prompt_id)
        if not prompt:
            raise ValueError(f"Prompt not found: {request.prompt_id}")

        # Format traces
        trace_a_text = self._format_trace(trace_a)
        trace_b_text = self._format_trace(trace_b)

        # Build final prompt
        final_prompt = prompt.template.format(
            trace_a=trace_a_text,
            trace_b=trace_b_text,
        )

        # Call provider
        start_time = time.perf_counter()
        if request.provider == "openai":
            output, input_tokens, output_tokens = await self._call_openai(
                final_prompt, request.model
            )
        elif request.provider == "anthropic":
            output, input_tokens, output_tokens = await self._call_anthropic(
                final_prompt, request.model
            )
        else:
            raise ValueError(f"Unsupported provider: {request.provider}")

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Calculate cost
        cost_usd = self._calculate_cost(request.model, input_tokens, output_tokens)

        logger.info(
            f"Comparison completed: {input_tokens + output_tokens} tokens, "
            f"${cost_usd:.4f}, {duration_ms:.0f}ms"
        )

        return ComparisonResult(
            request=request,
            output=output,
            tokens_used=input_tokens + output_tokens,
            cost_usd=cost_usd,
        )

    def _format_trace(self, trace: AgentRun) -> str:
        """Format trace for LLM consumption.

        Creates a concise representation with key information.

        Args:
            trace: The trace to format.

        Returns:
            Formatted string representation.
        """
        data: dict[str, Any] = {
            "name": trace.name,
            "duration_ms": trace.duration_ms,
            "total_tokens": trace.total_tokens,
            "total_cost_usd": trace.total_cost_usd,
            "error_count": trace.error_count,
            "steps_count": len(trace.steps),
        }

        if trace.error:
            data["error"] = trace.error

        if trace.tags:
            data["tags"] = trace.tags

        # Format steps summary
        steps_summary = []
        for step in trace.steps:
            step_data = self._format_step(step)
            steps_summary.append(step_data)

        data["steps"] = steps_summary

        return json.dumps(data, indent=2, default=str)

    def _format_step(self, step: Step, depth: int = 0) -> dict[str, Any]:
        """Format a single step recursively.

        Args:
            step: The step to format.
            depth: Current nesting depth.

        Returns:
            Dict with step information.
        """
        data: dict[str, Any] = {
            "name": step.name,
            "type": step.type.value if step.type else "unknown",
        }

        if step.duration_ms:
            data["duration_ms"] = round(step.duration_ms, 2)

        if step.model_name:
            data["model"] = step.model_name

        total_tokens = (step.input_tokens or 0) + (step.output_tokens or 0)
        if total_tokens:
            data["tokens"] = total_tokens

        if step.error:
            data["error"] = step.error[:200]  # Truncate long errors

        # Include key inputs (truncated)
        if step.inputs:
            inputs_summary = {}
            for k, v in step.inputs.items():
                if k in ("messages", "prompt", "query", "input"):
                    str_v = str(v)
                    inputs_summary[k] = str_v[:500] + "..." if len(str_v) > 500 else str_v
            if inputs_summary:
                data["inputs"] = inputs_summary

        # Include key outputs (truncated)
        if step.outputs:
            outputs_summary = {}
            for k, v in step.outputs.items():
                if k in ("content", "output", "result", "response"):
                    str_v = str(v)
                    outputs_summary[k] = str_v[:500] + "..." if len(str_v) > 500 else str_v
            if outputs_summary:
                data["outputs"] = outputs_summary

        # Recurse into children (limit depth)
        if step.children and depth < 3:
            data["children"] = [
                self._format_step(child, depth + 1)
                for child in step.children[:10]  # Limit children shown
            ]

        return data

    async def _call_openai(self, prompt: str, model: str) -> tuple[str, int, int]:
        """Call OpenAI API.

        Args:
            prompt: The formatted comparison prompt.
            model: Model to use.

        Returns:
            Tuple of (output, input_tokens, output_tokens).
        """
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise RuntimeError(
                "openai package required. Install with: pip install tracecraft[openai]"
            )

        client = AsyncOpenAI()

        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )

        output = response.choices[0].message.content or ""
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        return output, input_tokens, output_tokens

    async def _call_anthropic(self, prompt: str, model: str) -> tuple[str, int, int]:
        """Call Anthropic API.

        Args:
            prompt: The formatted comparison prompt.
            model: Model to use.

        Returns:
            Tuple of (output, input_tokens, output_tokens).
        """
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise RuntimeError(
                "anthropic package required. Install with: pip install tracecraft[anthropic]"
            )

        client = AsyncAnthropic()

        response = await client.messages.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )

        output = ""
        for block in response.content:
            if hasattr(block, "text"):
                output += block.text

        usage = response.usage
        input_tokens = usage.input_tokens if usage else 0
        output_tokens = usage.output_tokens if usage else 0

        return output, input_tokens, output_tokens

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on model pricing.

        Args:
            model: Model name.
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.

        Returns:
            Estimated cost in USD.
        """
        # Try exact match first
        pricing = self._pricing_map.get(model)

        # Try normalized name
        if not pricing:
            normalized = normalize_model_name(model)
            pricing = self._pricing_map.get(normalized)

        # Try partial match
        if not pricing:
            model_lower = model.lower()
            for key, p in self._pricing_map.items():
                if key in model_lower or model_lower in key:
                    pricing = p
                    break

        if not pricing:
            logger.debug(f"No pricing found for model: {model}")
            return 0.0

        input_cost = input_tokens * pricing.get_input_cost_per_token()
        output_cost = output_tokens * pricing.get_output_cost_per_token()
        return float(input_cost + output_cost)
