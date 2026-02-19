"""
Data models for trace comparison feature.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    pass


@dataclass
class ComparisonPrompt:
    """A reusable comparison prompt template.

    Attributes:
        id: Unique identifier for the prompt.
        name: Human-readable name.
        template: Prompt template with {trace_a} and {trace_b} placeholders.
        description: Optional description of what this prompt does.
        is_builtin: Whether this is a builtin prompt (cannot be deleted).
    """

    id: str
    name: str
    template: str
    description: str = ""
    is_builtin: bool = False


@dataclass
class ComparisonRequest:
    """Request to compare two traces.

    Attributes:
        trace_a_id: UUID of the first trace (marked trace).
        trace_b_id: UUID of the second trace (current trace).
        prompt_id: ID of the comparison prompt to use.
        model: Model identifier (e.g., "gpt-4o", "claude-sonnet-4-20250514").
        provider: Provider name ("openai" or "anthropic").
    """

    trace_a_id: UUID
    trace_b_id: UUID
    prompt_id: str
    model: str
    provider: str


@dataclass
class ComparisonResult:
    """Result of a trace comparison.

    Attributes:
        id: Unique identifier for this result.
        request: The original comparison request.
        output: The LLM's comparison output.
        tokens_used: Total tokens used (input + output).
        cost_usd: Estimated cost in USD.
        created_at: When the comparison was completed.
        saved: Whether this result has been persisted.
    """

    request: ComparisonRequest
    output: str
    tokens_used: int
    cost_usd: float
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    saved: bool = False
