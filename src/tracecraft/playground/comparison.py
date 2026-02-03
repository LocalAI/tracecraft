"""
Comparison utilities for the playground.

Provides utilities for comparing LLM outputs, generating diffs,
and tracking iteration history.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tracecraft.core.models import Step
    from tracecraft.playground.providers.base import ReplayResult
    from tracecraft.storage.sqlite import SQLiteTraceStore


@dataclass
class Iteration:
    """A single iteration in prompt development."""

    prompt: str
    """The prompt used for this iteration."""

    output: str
    """The output generated."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    """When this iteration was created."""

    tokens: int = 0
    """Total tokens used."""

    duration_ms: float = 0.0
    """Duration of the call."""

    notes: str = ""
    """Optional notes about this iteration."""

    @classmethod
    def from_replay_result(
        cls,
        prompt: str,
        result: ReplayResult,
        notes: str = "",
    ) -> Iteration:
        """Create an iteration from a replay result."""
        return cls(
            prompt=prompt,
            output=result.output,
            tokens=result.total_tokens,
            duration_ms=result.duration_ms,
            notes=notes,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "prompt": self.prompt,
            "output": self.output,
            "timestamp": self.timestamp.isoformat(),
            "tokens": self.tokens,
            "duration_ms": self.duration_ms,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Iteration:
        """Create from dictionary."""
        return cls(
            prompt=data["prompt"],
            output=data["output"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            tokens=data.get("tokens", 0),
            duration_ms=data.get("duration_ms", 0.0),
            notes=data.get("notes", ""),
        )


@dataclass
class IterationHistory:
    """
    History of prompt iterations for a step.

    Tracks all the different prompts tried and their outputs,
    allowing you to compare and select the best version.
    """

    step_id: str
    """The step ID this history is for."""

    step_name: str
    """The step name."""

    model: str
    """The model used."""

    original_prompt: str
    """The original prompt from the trace."""

    original_output: str
    """The original output from the trace."""

    iterations: list[Iteration] = field(default_factory=list)
    """List of iterations tried."""

    def add_iteration(
        self,
        prompt: str,
        result: ReplayResult,
        notes: str = "",
    ) -> Iteration:
        """Add a new iteration to the history."""
        iteration = Iteration.from_replay_result(prompt, result, notes)
        self.iterations.append(iteration)
        return iteration

    @property
    def best_iteration(self) -> Iteration | None:
        """
        Get the iteration marked as best (most recent with notes containing 'best').

        Returns:
            The best iteration, or the most recent if none marked.
        """
        # Look for one marked as best
        for iteration in reversed(self.iterations):
            if "best" in iteration.notes.lower():
                return iteration

        # Return most recent
        return self.iterations[-1] if self.iterations else None

    def save(self, path: str | Path) -> None:
        """
        Save the iteration history to a JSON file.

        Args:
            path: Path to save to.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "step_id": self.step_id,
            "step_name": self.step_name,
            "model": self.model,
            "original_prompt": self.original_prompt,
            "original_output": self.original_output,
            "iterations": [i.to_dict() for i in self.iterations],
        }

        with path.open("w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> IterationHistory:
        """
        Load iteration history from a JSON file.

        Args:
            path: Path to load from.

        Returns:
            Loaded IterationHistory.
        """
        path = Path(path)

        with path.open() as f:
            data = json.load(f)

        return cls(
            step_id=data["step_id"],
            step_name=data["step_name"],
            model=data["model"],
            original_prompt=data["original_prompt"],
            original_output=data["original_output"],
            iterations=[Iteration.from_dict(i) for i in data.get("iterations", [])],
        )

    @classmethod
    def from_step(cls, step: Step) -> IterationHistory:
        """
        Create a new iteration history from a traced step.

        Args:
            step: The step to create history for.

        Returns:
            New IterationHistory.
        """
        # Extract original prompt
        original_prompt = _extract_prompt(step)
        original_output = _extract_output(step)

        return cls(
            step_id=str(step.id),
            step_name=step.name,
            model=step.model_name or "unknown",
            original_prompt=original_prompt,
            original_output=original_output,
        )

    # =========================================================================
    # SQLite Persistence Methods
    # =========================================================================

    def save_iteration_to_store(
        self,
        store: SQLiteTraceStore,
        trace_id: str,
        prompt: str,
        result: ReplayResult,
        notes: str = "",
        trace_version_id: str | None = None,
    ) -> str:
        """
        Save a single iteration to SQLite store and add to local history.

        Args:
            store: The SQLite store to save to.
            trace_id: The trace ID.
            prompt: The prompt used.
            result: The replay result.
            notes: Optional notes.
            trace_version_id: Optional version to link to.

        Returns:
            The iteration ID.
        """
        # Save to store
        iteration_id = store.save_iteration(
            trace_id=trace_id,
            step_id=self.step_id,
            prompt=prompt,
            output=result.output,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            duration_ms=result.duration_ms,
            notes=notes,
            trace_version_id=trace_version_id,
        )

        # Also add to local history
        self.add_iteration(prompt, result, notes)

        return iteration_id

    @classmethod
    def load_from_store(
        cls,
        store: SQLiteTraceStore,
        trace_id: str,
        step: Step,
    ) -> IterationHistory:
        """
        Load iteration history from SQLite store for a step.

        Args:
            store: The SQLite store to load from.
            trace_id: The trace ID.
            step: The step to load history for.

        Returns:
            IterationHistory populated with iterations from store.
        """
        # Create base history from step
        history = cls.from_step(step)

        # Load iterations from store
        iterations = store.get_iterations(trace_id, step_id=str(step.id))
        for it in iterations:
            history.iterations.append(
                Iteration(
                    prompt=it["prompt"],
                    output=it["output"] or "",
                    timestamp=datetime.fromisoformat(it["created_at"]),
                    tokens=it["input_tokens"] + it["output_tokens"],
                    duration_ms=it["duration_ms"],
                    notes=it["notes"] or "",
                )
            )

        return history

    def save_all_to_store(
        self,
        store: SQLiteTraceStore,
        trace_id: str,
        trace_version_id: str | None = None,
    ) -> list[str]:
        """
        Save all iterations to SQLite store.

        Args:
            store: The SQLite store to save to.
            trace_id: The trace ID.
            trace_version_id: Optional version to link to.

        Returns:
            List of iteration IDs.
        """
        iteration_ids = []
        for iteration in self.iterations:
            iteration_id = store.save_iteration(
                trace_id=trace_id,
                step_id=self.step_id,
                prompt=iteration.prompt,
                output=iteration.output,
                input_tokens=iteration.tokens,  # Total tokens stored
                output_tokens=0,
                duration_ms=iteration.duration_ms,
                notes=iteration.notes,
                trace_version_id=trace_version_id,
            )
            iteration_ids.append(iteration_id)

        return iteration_ids


def _extract_prompt(step: Step) -> str:
    """Extract the system/main prompt from a step."""
    inputs = step.inputs or {}

    # Check for system prompt
    if "system_prompt" in inputs:
        return inputs["system_prompt"]
    if "system" in inputs:
        return inputs["system"]

    # Check messages for system
    if "messages" in inputs:
        for msg in inputs["messages"]:
            if msg.get("role") == "system":
                return msg.get("content", "")

    # Fall back to prompt field
    if "prompt" in inputs:
        return inputs["prompt"]

    return ""


def _extract_output(step: Step) -> str:
    """Extract output text from a step."""
    outputs = step.outputs or {}

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

    return str(outputs) if outputs else ""


def generate_diff(original: str, modified: str, context_lines: int = 3) -> str:
    """
    Generate a unified diff between two strings.

    Args:
        original: The original text.
        modified: The modified text.
        context_lines: Number of context lines to include.

    Returns:
        Unified diff string.
    """
    import difflib

    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)

    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile="original",
        tofile="modified",
        n=context_lines,
    )

    return "".join(diff)


def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity ratio between two texts.

    Args:
        text1: First text.
        text2: Second text.

    Returns:
        Float between 0 and 1, where 1 is identical.
    """
    import difflib

    return difflib.SequenceMatcher(None, text1, text2).ratio()


def highlight_changes(original: str, modified: str) -> tuple[str, str]:
    """
    Highlight changes between original and modified text.

    Returns two strings with ANSI color codes highlighting
    additions (green) and deletions (red).

    Args:
        original: Original text.
        modified: Modified text.

    Returns:
        Tuple of (original_highlighted, modified_highlighted).
    """
    import difflib

    RED = "\033[91m"
    GREEN = "\033[92m"
    RESET = "\033[0m"

    matcher = difflib.SequenceMatcher(None, original, modified)

    original_highlighted = []
    modified_highlighted = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            original_highlighted.append(original[i1:i2])
            modified_highlighted.append(modified[j1:j2])
        elif tag == "replace":
            original_highlighted.append(f"{RED}{original[i1:i2]}{RESET}")
            modified_highlighted.append(f"{GREEN}{modified[j1:j2]}{RESET}")
        elif tag == "delete":
            original_highlighted.append(f"{RED}{original[i1:i2]}{RESET}")
        elif tag == "insert":
            modified_highlighted.append(f"{GREEN}{modified[j1:j2]}{RESET}")

    return "".join(original_highlighted), "".join(modified_highlighted)
