"""
Core data models for TraceCraft.

Defines the canonical schema for agent traces:
- StepType: Enum of step kinds (agent, llm, tool, etc.)
- Step: Individual step in an agent execution
- AgentRun: Complete trace of an agent invocation
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class StepType(str, Enum):
    """Types of steps in an agent trace."""

    AGENT = "agent"  # Top-level agent invocation
    LLM = "llm"  # LLM API call (chat, completion, embedding)
    TOOL = "tool"  # Tool/function invocation
    RETRIEVAL = "retrieval"  # RAG retrieval step
    MEMORY = "memory"  # Memory read/write
    GUARDRAIL = "guardrail"  # Safety/validation check
    EVALUATION = "evaluation"  # LLM output evaluation
    WORKFLOW = "workflow"  # Logical grouping of steps
    ERROR = "error"  # Error/exception step


class Step(BaseModel):
    """
    Represents a single step in an agent's execution.

    Steps form a tree structure via the children field and parent_id linkage.
    Each step captures timing, inputs/outputs, and optional LLM-specific metadata.
    """

    # Identifiers
    id: UUID = Field(default_factory=uuid4)
    parent_id: UUID | None = None
    trace_id: UUID

    # Core fields
    type: StepType
    name: str

    # Timing
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: float | None = None

    # Content (may be redacted before export)
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)

    # Metadata
    attributes: dict[str, Any] = Field(default_factory=dict)

    # LLM-specific
    model_name: str | None = None
    model_provider: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None

    # Streaming support
    is_streaming: bool = False
    streaming_chunks: list[str] = Field(default_factory=list)

    # Error handling
    error: str | None = None
    error_type: str | None = None

    # Hierarchy
    children: list[Step] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class AgentRun(BaseModel):
    """
    Represents a complete agent run/trace.

    An AgentRun is the top-level container for a single invocation of an agent,
    containing metadata about the run and a tree of Steps.
    """

    # Identifiers
    id: UUID = Field(default_factory=uuid4)

    # Core fields
    name: str
    description: str | None = None

    # Timing
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: float | None = None

    # Context
    session_id: str | None = None
    user_id: str | None = None
    environment: str = "development"
    tags: list[str] = Field(default_factory=list)

    # Agent identity (for OTel GenAI conventions)
    agent_name: str | None = None
    agent_id: str | None = None
    agent_description: str | None = None

    # Cloud platform metadata
    cloud_provider: str | None = None  # "azure", "aws", "gcp"
    cloud_trace_id: str | None = None  # Platform-specific trace ID

    # Root input/output
    input: Any = None
    output: Any = None

    # Step tree
    steps: list[Step] = Field(default_factory=list)

    # Aggregates
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    error_count: int = 0

    # Run-level error (if the entire run failed)
    error: str | None = None
    error_type: str | None = None

    # Custom attributes (for extensibility)
    attributes: dict[str, Any] = Field(default_factory=dict)

    # Sampling decision
    should_export: bool = True
    sample_reason: str | None = None

    model_config = {"extra": "forbid"}
