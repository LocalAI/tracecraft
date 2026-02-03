"""
Dataset conversion utilities for TraceCraft.

Convert between TraceCraft traces and common dataset formats.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def traces_to_csv(
    traces: str | Path | list[Any],
    output_path: str | Path,
    columns: list[str] | None = None,
    filter_fn: Callable[[Any], bool] | None = None,
) -> int:
    """
    Export traces to CSV format.

    Args:
        traces: Path to JSONL or list of AgentRun.
        output_path: Output CSV file path.
        columns: Columns to include. Defaults to common fields.
        filter_fn: Optional filter function for steps.

    Returns:
        Number of rows written.

    Example:
        from tracecraft.datasets import traces_to_csv

        count = traces_to_csv(
            "traces/tracecraft.jsonl",
            "export/traces.csv",
            columns=["name", "input", "output", "duration_ms", "cost_usd"]
        )
        print(f"Exported {count} rows")
    """
    columns = columns or [
        "trace_id",
        "trace_name",
        "step_id",
        "step_name",
        "step_type",
        "input",
        "output",
        "model",
        "duration_ms",
        "input_tokens",
        "output_tokens",
        "cost_usd",
        "error",
    ]

    # Load traces if path provided
    if isinstance(traces, (str, Path)):
        traces = _load_traces_from_jsonl(traces)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    row_count = 0

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()

        for run in traces:
            for step in _flatten_steps(run.steps):
                # Apply filter
                if filter_fn and not filter_fn(step):
                    continue

                row = {
                    "trace_id": str(run.id),
                    "trace_name": run.name,
                    "step_id": str(step.id),
                    "step_name": step.name,
                    "step_type": step.type.value,
                    "input": json.dumps(step.inputs) if step.inputs else "",
                    "output": json.dumps(step.outputs) if step.outputs else "",
                    "model": step.model_name or "",
                    "duration_ms": step.duration_ms or 0,
                    "input_tokens": step.input_tokens or 0,
                    "output_tokens": step.output_tokens or 0,
                    "cost_usd": step.cost_usd or 0,
                    "error": step.error or "",
                }

                # Only write columns that exist in the row
                writer.writerow({k: row.get(k, "") for k in columns})
                row_count += 1

    return row_count


def traces_to_huggingface(
    traces: str | Path | list[Any],
    filter_fn: Callable[[Any], bool] | None = None,
    include_metadata: bool = True,
) -> Any:
    """
    Convert traces to HuggingFace Dataset format.

    Args:
        traces: Path to JSONL or list of AgentRun.
        filter_fn: Optional filter function for steps.
        include_metadata: Whether to include trace metadata.

    Returns:
        HuggingFace Dataset object.

    Example:
        from tracecraft.datasets import traces_to_huggingface

        dataset = traces_to_huggingface("traces/tracecraft.jsonl")
        dataset.push_to_hub("my-org/llm-traces")
    """
    try:
        from datasets import Dataset
    except ImportError:
        raise ImportError("datasets required. Install with: pip install datasets")

    # Load traces if path provided
    if isinstance(traces, (str, Path)):
        traces = _load_traces_from_jsonl(traces)

    records = []

    for run in traces:
        for step in _flatten_steps(run.steps):
            # Apply filter
            if filter_fn and not filter_fn(step):
                continue

            record: dict[str, Any] = {
                "input": json.dumps(step.inputs) if step.inputs else "",
                "output": json.dumps(step.outputs) if step.outputs else "",
                "step_type": step.type.value,
                "step_name": step.name,
            }

            if include_metadata:
                record.update(
                    {
                        "trace_id": str(run.id),
                        "trace_name": run.name,
                        "step_id": str(step.id),
                        "model": step.model_name or "",
                        "duration_ms": step.duration_ms or 0,
                        "input_tokens": step.input_tokens or 0,
                        "output_tokens": step.output_tokens or 0,
                        "cost_usd": step.cost_usd or 0,
                        "error": step.error or "",
                    }
                )

            records.append(record)

    return Dataset.from_list(records)


def traces_to_jsonl(
    traces: str | Path | list[Any],
    output_path: str | Path,
    filter_fn: Callable[[Any], bool] | None = None,
    format_type: str = "openai",
) -> int:
    """
    Export traces to JSONL format for fine-tuning or analysis.

    Args:
        traces: Path to JSONL or list of AgentRun.
        output_path: Output JSONL file path.
        filter_fn: Optional filter function for steps.
        format_type: Output format - "openai", "anthropic", or "raw".

    Returns:
        Number of records written.

    Example:
        from tracecraft.datasets import traces_to_jsonl

        # Export in OpenAI fine-tuning format
        count = traces_to_jsonl(
            "traces/tracecraft.jsonl",
            "finetune/train.jsonl",
            format_type="openai"
        )
    """
    # Load traces if path provided
    if isinstance(traces, (str, Path)):
        traces = _load_traces_from_jsonl(traces)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    record_count = 0

    with output_path.open("w", encoding="utf-8") as f:
        for run in traces:
            for step in _flatten_steps(run.steps):
                # Apply filter
                if filter_fn and not filter_fn(step):
                    continue

                # Only process LLM steps for fine-tuning formats
                if format_type in ["openai", "anthropic"] and step.type.value != "llm":
                    continue

                if format_type == "openai":
                    record = _format_openai(step)
                elif format_type == "anthropic":
                    record = _format_anthropic(step)
                else:  # raw
                    record = _format_raw(run, step)

                if record:
                    f.write(json.dumps(record) + "\n")
                    record_count += 1

    return record_count


def create_golden_dataset(
    traces: str | Path | list[Any],
    output_path: str | Path,
    filter_fn: Callable[[Any], bool] | None = None,
    include_expected: bool = True,
) -> int:
    """
    Create a golden dataset from traces for regression testing.

    Args:
        traces: Source traces.
        output_path: Output JSONL path.
        filter_fn: Filter function for selecting examples.
        include_expected: Include outputs as expected values.

    Returns:
        Number of examples created.

    Example:
        from tracecraft.datasets import create_golden_dataset

        # Create golden dataset from successful runs
        create_golden_dataset(
            "traces/tracecraft.jsonl",
            "datasets/golden.jsonl",
            filter_fn=lambda step: step.error is None and step.type.value == "llm"
        )
    """
    # Load traces if path provided
    if isinstance(traces, (str, Path)):
        traces = _load_traces_from_jsonl(traces)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    example_count = 0

    with output_path.open("w", encoding="utf-8") as f:
        for run in traces:
            for step in _flatten_steps(run.steps):
                # Apply filter
                if filter_fn and not filter_fn(step):
                    continue

                # Default: only successful LLM steps
                if filter_fn is None:
                    if step.type.value != "llm" or step.error:
                        continue

                example: dict[str, Any] = {
                    "input": step.inputs,
                    "metadata": {
                        "source_trace_id": str(run.id),
                        "source_step_id": str(step.id),
                        "step_name": step.name,
                        "model": step.model_name,
                    },
                }

                if include_expected:
                    example["expected_output"] = step.outputs

                f.write(json.dumps(example) + "\n")
                example_count += 1

    return example_count


def create_finetuning_dataset(
    traces: str | Path | list[Any],
    output_path: str | Path,
    format_type: str = "openai",
    system_prompt: str | None = None,
    filter_fn: Callable[[Any], bool] | None = None,
    min_quality_score: float | None = None,
) -> int:
    """
    Create a fine-tuning dataset from traces.

    Args:
        traces: Source traces.
        output_path: Output JSONL path.
        format_type: Output format - "openai" or "anthropic".
        system_prompt: Optional system prompt to use for all examples.
        filter_fn: Filter function for selecting examples.
        min_quality_score: Minimum quality score to include (if available).

    Returns:
        Number of examples created.

    Example:
        from tracecraft.datasets import create_finetuning_dataset

        # Create OpenAI fine-tuning dataset
        create_finetuning_dataset(
            "traces/tracecraft.jsonl",
            "finetune/train.jsonl",
            format_type="openai",
            system_prompt="You are a helpful assistant.",
            filter_fn=lambda step: step.error is None
        )
    """
    # Load traces if path provided
    if isinstance(traces, (str, Path)):
        traces = _load_traces_from_jsonl(traces)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    example_count = 0

    with output_path.open("w", encoding="utf-8") as f:
        for run in traces:
            for step in _flatten_steps(run.steps):
                # Only LLM steps
                if step.type.value != "llm":
                    continue

                # Skip errors
                if step.error:
                    continue

                # Apply filter
                if filter_fn and not filter_fn(step):
                    continue

                # Check quality score if provided
                if min_quality_score is not None:
                    quality = (step.attributes or {}).get("quality_score", 1.0)
                    if quality < min_quality_score:
                        continue

                if format_type == "openai":
                    record = _format_openai_finetune(step, system_prompt)
                elif format_type == "anthropic":
                    record = _format_anthropic_finetune(step, system_prompt)
                else:
                    raise ValueError(f"Unknown format_type: {format_type}")

                if record:
                    f.write(json.dumps(record) + "\n")
                    example_count += 1

    return example_count


def _load_traces_from_jsonl(path: str | Path) -> list[Any]:
    """Load traces from JSONL file."""
    from tracecraft.core.models import AgentRun

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Trace file not found: {path}")

    traces = []
    with path.open() as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                traces.append(AgentRun.model_validate(data))
    return traces


def _flatten_steps(steps: list[Any]) -> list[Any]:
    """Flatten nested steps into a list."""
    result = []
    for step in steps:
        result.append(step)
        if step.children:
            result.extend(_flatten_steps(step.children))
    return result


def _format_openai(step: Any) -> dict[str, Any] | None:
    """Format step for OpenAI fine-tuning."""
    messages = _extract_messages(step)
    if not messages:
        return None

    output = _extract_output_text(step)
    if not output:
        return None

    # Add assistant message
    messages.append({"role": "assistant", "content": output})

    return {"messages": messages}


def _format_anthropic(step: Any) -> dict[str, Any] | None:
    """Format step for Anthropic fine-tuning."""
    messages = _extract_messages(step)
    if not messages:
        return None

    output = _extract_output_text(step)
    if not output:
        return None

    # Anthropic format separates system from messages
    system = None
    filtered_messages = []
    for msg in messages:
        if msg.get("role") == "system":
            system = msg.get("content")
        else:
            filtered_messages.append(msg)

    # Add assistant message
    filtered_messages.append({"role": "assistant", "content": output})

    result: dict[str, Any] = {"messages": filtered_messages}
    if system:
        result["system"] = system

    return result


def _format_raw(run: Any, step: Any) -> dict[str, Any]:
    """Format step as raw data."""
    return {
        "trace_id": str(run.id),
        "trace_name": run.name,
        "step_id": str(step.id),
        "step_name": step.name,
        "step_type": step.type.value,
        "model": step.model_name,
        "inputs": step.inputs,
        "outputs": step.outputs,
        "duration_ms": step.duration_ms,
        "input_tokens": step.input_tokens,
        "output_tokens": step.output_tokens,
        "cost_usd": step.cost_usd,
        "error": step.error,
    }


def _format_openai_finetune(step: Any, system_prompt: str | None) -> dict[str, Any] | None:
    """Format for OpenAI fine-tuning with optional system prompt."""
    messages = _extract_messages(step)
    if not messages:
        return None

    output = _extract_output_text(step)
    if not output:
        return None

    # Add system prompt if provided and not already present
    if system_prompt:
        has_system = any(m.get("role") == "system" for m in messages)
        if not has_system:
            messages.insert(0, {"role": "system", "content": system_prompt})

    # Add assistant message
    messages.append({"role": "assistant", "content": output})

    return {"messages": messages}


def _format_anthropic_finetune(step: Any, system_prompt: str | None) -> dict[str, Any] | None:
    """Format for Anthropic fine-tuning with optional system prompt."""
    messages = _extract_messages(step)
    if not messages:
        return None

    output = _extract_output_text(step)
    if not output:
        return None

    # Extract existing system or use provided
    system = system_prompt
    filtered_messages = []
    for msg in messages:
        if msg.get("role") == "system":
            if not system_prompt:
                system = msg.get("content")
        else:
            filtered_messages.append(msg)

    # Add assistant message
    filtered_messages.append({"role": "assistant", "content": output})

    result: dict[str, Any] = {"messages": filtered_messages}
    if system:
        result["system"] = system

    return result


def _extract_messages(step: Any) -> list[dict[str, str]]:
    """Extract messages from step inputs."""
    inputs = step.inputs or {}

    if "messages" in inputs:
        return [
            {"role": m.get("role", "user"), "content": str(m.get("content", ""))}
            for m in inputs["messages"]
        ]

    # Try to construct from common fields
    messages = []

    if "system_prompt" in inputs or "system" in inputs:
        system = inputs.get("system_prompt") or inputs.get("system")
        messages.append({"role": "system", "content": str(system)})

    user_content = (
        inputs.get("prompt")
        or inputs.get("user_prompt")
        or inputs.get("query")
        or inputs.get("input")
        or inputs.get("question")
    )
    if user_content:
        messages.append({"role": "user", "content": str(user_content)})

    return messages


def _extract_output_text(step: Any) -> str:
    """Extract output text from step."""
    outputs = step.outputs or {}

    for key in ["result", "response", "content", "answer", "output", "text"]:
        if key in outputs:
            return str(outputs[key])

    if "message" in outputs:
        msg = outputs["message"]
        if isinstance(msg, dict) and "content" in msg:
            return str(msg["content"])
        return str(msg)

    return str(outputs) if outputs else ""
