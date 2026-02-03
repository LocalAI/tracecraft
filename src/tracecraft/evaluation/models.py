"""
Evaluation data models for TraceCraft.

Defines the schema for evaluation sets, cases, runs, and results:
- MetricFramework: Enum of supported evaluation frameworks
- EvaluationStatus: Status of evaluation runs
- EvaluationMetricConfig: Configuration for a single metric
- EvaluationCase: Test case with input/expected output
- EvaluationSet: Collection of cases with metrics config
- EvaluationResult: Per-case evaluation result
- EvaluationRun: Complete evaluation run with aggregated results
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MetricFramework(str, Enum):
    """Supported evaluation metric frameworks."""

    BUILTIN = "builtin"  # Built-in: regex, exact, contains, llm_judge
    DEEPEVAL = "deepeval"  # DeepEval framework
    RAGAS = "ragas"  # RAGAS RAG evaluation
    MLFLOW = "mlflow"  # MLflow LLM evaluation


class EvaluationStatus(str, Enum):
    """Status of an evaluation run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EvaluationMetricConfig(BaseModel):
    """
    Configuration for a single evaluation metric.

    Defines which metric to use, from which framework, and the threshold.
    """

    name: str = Field(..., description="Metric name (e.g., 'faithfulness', 'exact_match')")
    framework: MetricFramework = Field(..., description="Framework providing the metric")
    metric_type: str = Field(
        ...,
        description="Specific metric type within framework (e.g., 'regex', 'answer_relevancy')",
    )
    threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Pass threshold (0.0-1.0)")
    weight: float = Field(default=1.0, ge=0.0, description="Weight for aggregation")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Metric-specific parameters"
    )

    model_config = {"extra": "forbid"}


class EvaluationCase(BaseModel):
    """
    A single test case for evaluation.

    Can be created manually or extracted from existing traces.
    """

    id: UUID = Field(default_factory=uuid4)
    evaluation_set_id: UUID | None = Field(default=None, description="Parent evaluation set")
    name: str = Field(..., description="Human-readable case name")

    # Core test data
    input: dict[str, Any] = Field(..., description="Input data for the case")
    expected_output: dict[str, Any] | None = Field(
        default=None, description="Expected output (for comparison metrics)"
    )
    actual_output: dict[str, Any] | None = Field(
        default=None,
        description="Actual output from trace/step (used when no output_generator)",
    )
    retrieval_context: list[str] = Field(
        default_factory=list, description="Retrieved context (for RAG metrics)"
    )

    # Provenance (if extracted from a trace)
    source_trace_id: UUID | None = Field(
        default=None, description="Trace this case was extracted from"
    )
    source_step_id: UUID | None = Field(
        default=None, description="Step this case was extracted from"
    )

    # Organization
    tags: list[str] = Field(default_factory=list, description="Tags for filtering")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"extra": "forbid"}


class EvaluationSet(BaseModel):
    """
    A collection of evaluation cases with metric configuration.

    Evaluation sets define what to evaluate and how to score it.
    """

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., description="Unique name for this evaluation set")
    description: str | None = Field(default=None, description="Optional description")

    # Organization
    project_id: UUID | None = Field(default=None, description="Associated project ID")
    tags: list[str] = Field(default_factory=list, description="Tags for filtering")

    # Metric configuration
    metrics: list[EvaluationMetricConfig] = Field(
        default_factory=list, description="Metrics to evaluate"
    )
    default_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Default pass threshold"
    )
    pass_rate_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Required pass rate for overall success",
    )

    # Cases
    cases: list[EvaluationCase] = Field(default_factory=list, description="Test cases in this set")

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = Field(default=None)

    model_config = {"extra": "forbid"}


class MetricScore(BaseModel):
    """Score from a single metric evaluation."""

    metric_name: str
    framework: MetricFramework
    score: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(ge=0.0, le=1.0)
    passed: bool
    reason: str | None = Field(default=None, description="Explanation for score")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Additional metric-specific details"
    )

    model_config = {"extra": "forbid"}


class EvaluationResult(BaseModel):
    """
    Result of evaluating a single case.

    Contains scores from all configured metrics.
    """

    id: UUID = Field(default_factory=uuid4)
    evaluation_run_id: UUID
    evaluation_case_id: UUID
    trace_id: UUID | None = Field(default=None, description="Trace generated during evaluation")

    # Output captured during evaluation
    actual_output: dict[str, Any] | None = Field(default=None, description="Actual output produced")

    # Scores
    scores: list[MetricScore] = Field(default_factory=list, description="Per-metric scores")
    overall_score: float | None = Field(default=None, description="Weighted average score")
    passed: bool = Field(default=False, description="Whether case passed all metrics")

    # Performance
    duration_ms: float | None = Field(default=None, description="Evaluation duration")
    error: str | None = Field(default=None, description="Error if evaluation failed")

    model_config = {"extra": "forbid"}


class EvaluationRun(BaseModel):
    """
    A complete evaluation run.

    Represents a single execution of an evaluation set.
    """

    id: UUID = Field(default_factory=uuid4)
    evaluation_set_id: UUID
    status: EvaluationStatus = Field(default=EvaluationStatus.PENDING)

    # Counts
    total_cases: int = Field(default=0)
    passed_cases: int = Field(default=0)
    failed_cases: int = Field(default=0)

    # Aggregated metrics
    overall_pass_rate: float | None = Field(default=None)
    metric_averages: dict[str, float] = Field(
        default_factory=dict, description="Average score per metric"
    )
    passed: bool | None = Field(default=None, description="Whether run met pass_rate_threshold")

    # Results
    results: list[EvaluationResult] = Field(default_factory=list, description="Per-case results")

    # Timing
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = Field(default=None)
    duration_ms: float | None = Field(default=None)

    # Error (if entire run failed)
    error: str | None = Field(default=None)

    model_config = {"extra": "forbid"}


class EvaluationRunSummary(BaseModel):
    """
    Summary of an evaluation run for display purposes.

    Lighter weight than full EvaluationRun.
    """

    id: UUID
    evaluation_set_id: UUID
    evaluation_set_name: str
    status: EvaluationStatus
    total_cases: int
    passed_cases: int
    failed_cases: int
    overall_pass_rate: float | None
    passed: bool | None
    started_at: datetime
    completed_at: datetime | None
    duration_ms: float | None

    model_config = {"extra": "forbid"}
