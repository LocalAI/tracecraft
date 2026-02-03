"""
Built-in evaluation metrics for TraceCraft.

Provides simple, dependency-free evaluation metrics:
- exact_match: Exact string comparison
- regex_match: Regular expression matching
- contains: Substring containment check
- json_valid: JSON validity check
- llm_judge: LLM-based evaluation (requires LLM provider)
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from tracecraft.evaluation.adapters.base import BaseMetricAdapter, MetricResult

if TYPE_CHECKING:
    from tracecraft.evaluation.models import EvaluationCase, EvaluationMetricConfig


class BuiltinMetricAdapter(BaseMetricAdapter):
    """
    Adapter for built-in evaluation metrics.

    These metrics have no external dependencies and work out of the box.
    """

    @property
    def framework_name(self) -> str:
        return "builtin"

    @property
    def supported_metrics(self) -> list[str]:
        return [
            "exact_match",
            "regex_match",
            "contains",
            "not_contains",
            "json_valid",
            "length_check",
            "llm_judge",
        ]

    async def evaluate(
        self,
        case: EvaluationCase,
        actual_output: str | dict[str, Any],
        metric_config: EvaluationMetricConfig,
    ) -> MetricResult:
        """Evaluate using the specified built-in metric."""
        metric_type = metric_config.metric_type

        if metric_type == "exact_match":
            return self._exact_match(case, actual_output, metric_config)
        elif metric_type == "regex_match":
            return self._regex_match(case, actual_output, metric_config)
        elif metric_type == "contains":
            return self._contains(case, actual_output, metric_config)
        elif metric_type == "not_contains":
            return self._not_contains(case, actual_output, metric_config)
        elif metric_type == "json_valid":
            return self._json_valid(case, actual_output, metric_config)
        elif metric_type == "length_check":
            return self._length_check(case, actual_output, metric_config)
        elif metric_type == "llm_judge":
            return await self._llm_judge(case, actual_output, metric_config)
        else:
            raise ValueError(f"Unsupported metric type: {metric_type}")

    def _normalize_output(self, output: str | dict[str, Any]) -> str:
        """Convert output to string for comparison."""
        if isinstance(output, dict):
            # Try to extract common output keys
            for key in ["output", "text", "content", "response", "answer"]:
                if key in output:
                    return str(output[key])
            return json.dumps(output, sort_keys=True)
        return str(output)

    def _get_expected(self, case: EvaluationCase) -> str | None:
        """Get expected output as string."""
        if case.expected_output is None:
            return None
        if isinstance(case.expected_output, dict):
            for key in ["output", "text", "content", "response", "answer"]:
                if key in case.expected_output:
                    return str(case.expected_output[key])
            return json.dumps(case.expected_output, sort_keys=True)
        return str(case.expected_output)

    def _exact_match(
        self,
        case: EvaluationCase,
        actual_output: str | dict[str, Any],
        metric_config: EvaluationMetricConfig,
    ) -> MetricResult:
        """Check for exact string match."""
        actual = self._normalize_output(actual_output)
        expected = self._get_expected(case)

        if expected is None:
            return MetricResult(
                metric_name="exact_match",
                score=0.0,
                passed=False,
                reason="No expected output to compare against",
            )

        # Check parameters for case sensitivity
        case_sensitive = metric_config.parameters.get("case_sensitive", True)
        strip_whitespace = metric_config.parameters.get("strip_whitespace", True)

        if strip_whitespace:
            actual = actual.strip()
            expected = expected.strip()

        if not case_sensitive:
            actual = actual.lower()
            expected = expected.lower()

        match = actual == expected
        score = 1.0 if match else 0.0
        passed = score >= metric_config.threshold

        return MetricResult(
            metric_name="exact_match",
            score=score,
            passed=passed,
            reason="Exact match"
            if match
            else f"Expected: {expected[:100]}..., Got: {actual[:100]}...",
            details={"case_sensitive": case_sensitive, "strip_whitespace": strip_whitespace},
        )

    def _regex_match(
        self,
        case: EvaluationCase,
        actual_output: str | dict[str, Any],
        metric_config: EvaluationMetricConfig,
    ) -> MetricResult:
        """Check if output matches a regex pattern."""
        actual = self._normalize_output(actual_output)

        # Pattern from config parameters or expected output
        pattern = metric_config.parameters.get("pattern")
        if pattern is None:
            expected = self._get_expected(case)
            if expected is None:
                return MetricResult(
                    metric_name="regex_match",
                    score=0.0,
                    passed=False,
                    reason="No pattern specified",
                )
            pattern = expected

        flags = 0
        if not metric_config.parameters.get("case_sensitive", True):
            flags |= re.IGNORECASE

        try:
            match = re.search(pattern, actual, flags)
            score = 1.0 if match else 0.0
            passed = score >= metric_config.threshold

            return MetricResult(
                metric_name="regex_match",
                score=score,
                passed=passed,
                reason=f"Pattern matched at {match.start()}-{match.end()}"
                if match
                else "Pattern not found",
                details={"pattern": pattern, "match_groups": match.groups() if match else None},
            )
        except re.error as e:
            return MetricResult(
                metric_name="regex_match",
                score=0.0,
                passed=False,
                reason=f"Invalid regex pattern: {e}",
            )

    def _contains(
        self,
        case: EvaluationCase,
        actual_output: str | dict[str, Any],
        metric_config: EvaluationMetricConfig,
    ) -> MetricResult:
        """Check if output contains a substring."""
        actual = self._normalize_output(actual_output)

        # Text to find from config parameters or expected output
        text = metric_config.parameters.get("text")
        if text is None:
            expected = self._get_expected(case)
            if expected is None:
                return MetricResult(
                    metric_name="contains",
                    score=0.0,
                    passed=False,
                    reason="No text specified to search for",
                )
            text = expected

        case_sensitive = metric_config.parameters.get("case_sensitive", True)

        if not case_sensitive:
            actual = actual.lower()
            text = text.lower()

        contains = text in actual
        score = 1.0 if contains else 0.0
        passed = score >= metric_config.threshold

        return MetricResult(
            metric_name="contains",
            score=score,
            passed=passed,
            reason=f"Found '{text[:50]}'" if contains else f"'{text[:50]}' not found in output",
        )

    def _not_contains(
        self,
        _case: EvaluationCase,
        actual_output: str | dict[str, Any],
        metric_config: EvaluationMetricConfig,
    ) -> MetricResult:
        """Check that output does NOT contain a substring."""
        actual = self._normalize_output(actual_output)

        text = metric_config.parameters.get("text")
        if text is None:
            return MetricResult(
                metric_name="not_contains",
                score=0.0,
                passed=False,
                reason="No text specified to check against",
            )

        case_sensitive = metric_config.parameters.get("case_sensitive", True)

        if not case_sensitive:
            actual = actual.lower()
            text = text.lower()

        not_contains = text not in actual
        score = 1.0 if not_contains else 0.0
        passed = score >= metric_config.threshold

        return MetricResult(
            metric_name="not_contains",
            score=score,
            passed=passed,
            reason="Text correctly absent"
            if not_contains
            else f"Unexpected text '{text[:50]}' found",
        )

    def _json_valid(
        self,
        _case: EvaluationCase,
        actual_output: str | dict[str, Any],
        metric_config: EvaluationMetricConfig,
    ) -> MetricResult:
        """Check if output is valid JSON."""
        if isinstance(actual_output, dict):
            # Already a dict, so valid JSON
            score = 1.0
            passed = score >= metric_config.threshold
            return MetricResult(
                metric_name="json_valid",
                score=score,
                passed=passed,
                reason="Output is already parsed JSON",
            )

        try:
            parsed = json.loads(actual_output)

            # Optional: check for required keys
            required_keys = metric_config.parameters.get("required_keys", [])
            if required_keys and isinstance(parsed, dict):
                missing = [k for k in required_keys if k not in parsed]
                if missing:
                    # Partial score based on how many keys are present
                    present_count = len(required_keys) - len(missing)
                    score = present_count / len(required_keys) if required_keys else 0.5
                    passed = score >= metric_config.threshold
                    return MetricResult(
                        metric_name="json_valid",
                        score=score,
                        passed=passed,
                        reason=f"Valid JSON but missing keys: {missing}",
                        details={"missing_keys": missing, "present_keys": present_count},
                    )

            score = 1.0
            passed = score >= metric_config.threshold
            return MetricResult(
                metric_name="json_valid",
                score=score,
                passed=passed,
                reason="Valid JSON",
                details={"type": type(parsed).__name__},
            )
        except json.JSONDecodeError as e:
            score = 0.0
            passed = score >= metric_config.threshold
            return MetricResult(
                metric_name="json_valid",
                score=score,
                passed=passed,
                reason=f"Invalid JSON: {e.msg} at position {e.pos}",
            )

    def _length_check(
        self,
        _case: EvaluationCase,
        actual_output: str | dict[str, Any],
        metric_config: EvaluationMetricConfig,
    ) -> MetricResult:
        """Check output length is within bounds."""
        actual = self._normalize_output(actual_output)
        length = len(actual)

        min_length = metric_config.parameters.get("min_length", 0)
        max_length = metric_config.parameters.get("max_length", float("inf"))

        in_range = min_length <= length <= max_length

        # Calculate score as how close to ideal range
        if in_range:
            score = 1.0
        elif length < min_length:
            score = length / min_length if min_length > 0 else 0.0
        else:
            score = max_length / length if length > 0 else 0.0

        passed = score >= metric_config.threshold

        return MetricResult(
            metric_name="length_check",
            score=score,
            passed=passed,
            reason=f"Length {length} is {'within' if in_range else 'outside'} range [{min_length}, {max_length}]",
            details={"length": length, "min_length": min_length, "max_length": max_length},
        )

    async def _llm_judge(
        self,
        case: EvaluationCase,
        actual_output: str | dict[str, Any],
        metric_config: EvaluationMetricConfig,
    ) -> MetricResult:
        """Use an LLM to evaluate the output."""
        # Get LLM provider from parameters
        provider = metric_config.parameters.get("provider", "openai")
        model = metric_config.parameters.get("model", "gpt-4o-mini")
        criteria = metric_config.parameters.get(
            "criteria",
            "Evaluate if the response is accurate, helpful, and relevant to the question.",
        )

        actual = self._normalize_output(actual_output)
        input_text = json.dumps(case.input) if isinstance(case.input, dict) else str(case.input)
        expected = self._get_expected(case) or "No expected output specified"

        # Build the prompt
        prompt = f"""You are an expert evaluator. Score the following response on a scale of 0.0 to 1.0.

Evaluation Criteria: {criteria}

User Input: {input_text}

Expected Output (for reference): {expected}

Actual Output: {actual}

Provide your evaluation in the following JSON format:
{{
    "score": <float between 0.0 and 1.0>,
    "reasoning": "<brief explanation of score>"
}}

Your evaluation:"""

        try:
            # Try to use available LLM provider
            score, reasoning = await self._call_llm_judge(provider, model, prompt)

            passed = score >= metric_config.threshold

            return MetricResult(
                metric_name="llm_judge",
                score=score,
                passed=passed,
                reason=reasoning,
                details={"provider": provider, "model": model, "criteria": criteria},
            )
        except Exception as e:
            return MetricResult(
                metric_name="llm_judge",
                score=0.0,
                passed=False,
                reason=f"LLM evaluation failed: {e}",
                details={"error": str(e)},
            )

    async def _call_llm_judge(self, provider: str, model: str, prompt: str) -> tuple[float, str]:
        """Call LLM provider for evaluation."""
        import os

        if provider == "openai":
            try:
                from openai import AsyncOpenAI

                client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
                response = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                )

                result = json.loads(response.choices[0].message.content)
                return float(result.get("score", 0.0)), result.get(
                    "reasoning", "No reasoning provided"
                )

            except ImportError:
                raise ValueError("OpenAI package not installed. Run: pip install openai")

        elif provider == "anthropic":
            try:
                from anthropic import AsyncAnthropic

                client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
                response = await client.messages.create(
                    model=model,
                    max_tokens=500,
                    messages=[{"role": "user", "content": prompt}],
                )

                # Parse JSON from response
                content = response.content[0].text
                # Extract JSON from response
                json_match = re.search(r"\{[^}]+\}", content)
                if json_match:
                    result = json.loads(json_match.group())
                    return float(result.get("score", 0.0)), result.get(
                        "reasoning", "No reasoning provided"
                    )
                raise ValueError("Could not parse JSON from response")

            except ImportError:
                raise ValueError("Anthropic package not installed. Run: pip install anthropic")

        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
