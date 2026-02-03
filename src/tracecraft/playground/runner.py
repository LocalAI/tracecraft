"""
Replay runner for executing traced LLM calls.

Provides high-level functions for replaying steps and comparing outputs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

from tracecraft.playground.providers.anthropic import AnthropicReplayProvider
from tracecraft.playground.providers.base import BaseReplayProvider, ReplayResult
from tracecraft.playground.providers.openai import OpenAIReplayProvider

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun, Step


# Default providers
_DEFAULT_PROVIDERS: list[BaseReplayProvider] = [
    OpenAIReplayProvider(),
    AnthropicReplayProvider(),
]


def get_provider_for_step(
    step: Step,
    providers: list[BaseReplayProvider] | None = None,
) -> BaseReplayProvider | None:
    """
    Find a provider that can replay the given step.

    Args:
        step: The step to find a provider for.
        providers: Optional list of providers. Uses defaults if not provided.

    Returns:
        A provider that can replay the step, or None if none found.
    """
    providers = providers or _DEFAULT_PROVIDERS

    for provider in providers:
        if provider.can_replay(step):
            return provider

    return None


async def replay_step(
    trace_id: str | UUID,
    step_id: str | UUID | None = None,
    step_name: str | None = None,
    trace_source: str | Path | list[Any] | None = None,
    modified_prompt: str | None = None,
    providers: list[BaseReplayProvider] | None = None,
    **kwargs: Any,
) -> ReplayResult:
    """
    Replay an LLM step from a trace.

    Args:
        trace_id: The trace ID containing the step.
        step_id: The specific step ID to replay.
        step_name: Alternatively, find step by name.
        trace_source: Path to JSONL file, or list of AgentRun objects.
        modified_prompt: Optional modified system prompt.
        providers: Optional list of replay providers.
        **kwargs: Additional arguments passed to the provider.

    Returns:
        ReplayResult with the output and metadata.

    Raises:
        ValueError: If step not found or no provider available.

    Example:
        from tracecraft.playground import replay_step

        # Replay a step with exact same parameters
        result = await replay_step(
            trace_id="abc123",
            step_id="def456",
            trace_source="traces/tracecraft.jsonl"
        )
        print(result.output)

        # Replay with modified prompt
        result = await replay_step(
            trace_id="abc123",
            step_name="gpt4_call",
            trace_source="traces/tracecraft.jsonl",
            modified_prompt="You are a helpful coding assistant."
        )
    """
    # Find the step
    step = _find_step(
        trace_id=trace_id,
        step_id=step_id,
        step_name=step_name,
        trace_source=trace_source,
    )

    if step is None:
        raise ValueError(
            f"Step not found: trace_id={trace_id}, step_id={step_id}, step_name={step_name}"
        )

    # Find a provider
    provider = get_provider_for_step(step, providers)

    if provider is None:
        raise ValueError(
            f"No provider available for model: {step.model_name}. "
            f"Supported models: OpenAI (gpt-*), Anthropic (claude-*)"
        )

    # Execute replay
    return await provider.replay(step, modified_prompt=modified_prompt, **kwargs)


async def compare_prompts(
    trace_id: str | UUID,
    step_id: str | UUID | None = None,
    step_name: str | None = None,
    trace_source: str | Path | list[Any] | None = None,
    modified_prompt: str | None = None,
    providers: list[BaseReplayProvider] | None = None,
    **kwargs: Any,
) -> ComparisonResult:
    """
    Compare original output with output from a modified prompt.

    Args:
        trace_id: The trace ID containing the step.
        step_id: The specific step ID to compare.
        step_name: Alternatively, find step by name.
        trace_source: Path to JSONL file, or list of AgentRun objects.
        modified_prompt: The modified system prompt to compare with.
        providers: Optional list of replay providers.
        **kwargs: Additional arguments passed to the provider.

    Returns:
        ComparisonResult with original and modified outputs.

    Example:
        from tracecraft.playground import compare_prompts

        comparison = await compare_prompts(
            trace_id="abc123",
            step_id="def456",
            trace_source="traces/tracecraft.jsonl",
            modified_prompt="Be more concise in your responses."
        )
        print(f"Original: {comparison.original_output[:100]}...")
        print(f"Modified: {comparison.modified_output[:100]}...")
        print(f"Diff: {comparison.diff}")
    """
    # Find the step
    step = _find_step(
        trace_id=trace_id,
        step_id=step_id,
        step_name=step_name,
        trace_source=trace_source,
    )

    if step is None:
        raise ValueError(
            f"Step not found: trace_id={trace_id}, step_id={step_id}, step_name={step_name}"
        )

    # Get original output from trace
    original_output = _extract_output_text(step)

    # Replay with modified prompt
    if modified_prompt is None:
        raise ValueError("modified_prompt is required for comparison")

    modified_result = await replay_step(
        trace_id=trace_id,
        step_id=step_id,
        step_name=step_name,
        trace_source=trace_source,
        modified_prompt=modified_prompt,
        providers=providers,
        **kwargs,
    )

    return ComparisonResult(
        original_output=original_output,
        modified_output=modified_result.output,
        modified_result=modified_result,
        step=step,
    )


class ComparisonResult:
    """Result from comparing original and modified prompts."""

    def __init__(
        self,
        original_output: str,
        modified_output: str,
        modified_result: ReplayResult,
        step: Step,
    ) -> None:
        self.original_output = original_output
        self.modified_output = modified_output
        self.modified_result = modified_result
        self.step = step

    @property
    def diff(self) -> str:
        """
        Generate a unified diff between original and modified outputs.

        Returns:
            Unified diff string.
        """
        import difflib

        original_lines = self.original_output.splitlines(keepends=True)
        modified_lines = self.modified_output.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile="original",
            tofile="modified",
        )

        return "".join(diff)

    @property
    def similarity(self) -> float:
        """
        Calculate similarity ratio between outputs.

        Returns:
            Float between 0 and 1, where 1 is identical.
        """
        import difflib

        return difflib.SequenceMatcher(
            None,
            self.original_output,
            self.modified_output,
        ).ratio()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "original_output": self.original_output,
            "modified_output": self.modified_output,
            "similarity": self.similarity,
            "modified_tokens": self.modified_result.total_tokens,
            "modified_duration_ms": self.modified_result.duration_ms,
            "step_id": str(self.step.id),
            "step_name": self.step.name,
            "model": self.step.model_name,
        }


def _find_step(
    trace_id: str | UUID,
    step_id: str | UUID | None = None,
    step_name: str | None = None,
    trace_source: str | Path | list[Any] | None = None,
) -> Step | None:
    """
    Find a step in traces.

    Args:
        trace_id: The trace ID.
        step_id: Optional step ID.
        step_name: Optional step name.
        trace_source: Trace source (file path or list of runs).

    Returns:
        The found step, or None.
    """
    from tracecraft.core.models import AgentRun

    # Load traces
    runs: list[AgentRun] = []

    if trace_source is None:
        # Try default trace file
        default_path = Path("traces/tracecraft.jsonl")
        if default_path.exists():
            trace_source = default_path

    if isinstance(trace_source, (str, Path)):
        path = Path(trace_source)
        if path.exists():
            with path.open() as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        runs.append(AgentRun.model_validate(data))
    elif isinstance(trace_source, list):
        runs = trace_source

    # Convert trace_id to string for comparison
    trace_id_str = str(trace_id)

    # Find the run
    run = None
    for r in runs:
        if str(r.id) == trace_id_str:
            run = r
            break

    if run is None:
        return None

    # Find the step
    return _find_step_in_run(run, step_id, step_name)


def _find_step_in_run(
    run: AgentRun,
    step_id: str | UUID | None = None,
    step_name: str | None = None,
) -> Step | None:
    """Find a step within a run."""
    step_id_str = str(step_id) if step_id else None

    def search_steps(steps: list[Step]) -> Step | None:
        for step in steps:
            # Match by ID
            if step_id_str and str(step.id) == step_id_str:
                return step

            # Match by name
            if step_name and step.name == step_name:
                return step

            # Search children
            if step.children:
                found = search_steps(step.children)
                if found:
                    return found

        return None

    return search_steps(run.steps)


def _extract_output_text(step: Step) -> str:
    """Extract output text from a step."""
    outputs = step.outputs or {}

    # Try common output formats
    if "result" in outputs:
        return str(outputs["result"])
    if "content" in outputs:
        return str(outputs["content"])
    if "text" in outputs:
        return str(outputs["text"])
    if "message" in outputs:
        msg = outputs["message"]
        if isinstance(msg, dict) and "content" in msg:
            return str(msg["content"])
        return str(msg)
    if "response" in outputs:
        return str(outputs["response"])

    # Return string representation of outputs
    return str(outputs) if outputs else ""
