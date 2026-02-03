"""
Evaluation runner for TraceCraft.

Orchestrates the execution of evaluation sets against test cases,
using configured metrics from various frameworks.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from tracecraft.evaluation.adapters.base import MetricResult, get_adapter
from tracecraft.evaluation.models import (
    EvaluationCase,
    EvaluationMetricConfig,
    EvaluationResult,
    EvaluationRun,
    EvaluationSet,
    EvaluationStatus,
    MetricFramework,
    MetricScore,
)

if TYPE_CHECKING:
    from tracecraft.storage.sqlite import SQLiteTraceStore

logger = logging.getLogger(__name__)


@dataclass
class ProgressInfo:
    """Progress information for evaluation."""

    total_cases: int
    completed_cases: int
    passed_cases: int
    failed_cases: int
    current_case: str | None = None
    current_metric: str | None = None
    elapsed_ms: float = 0.0

    @property
    def progress_percent(self) -> float:
        if self.total_cases == 0:
            return 100.0
        return (self.completed_cases / self.total_cases) * 100


ProgressCallback = Callable[[ProgressInfo], None]
OutputGenerator = Callable[[EvaluationCase], Any]


@dataclass
class EvaluationRunResult:
    """Result of running an evaluation set."""

    run_id: UUID
    evaluation_set_id: UUID
    status: EvaluationStatus
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    overall_passed: bool
    metric_averages: dict[str, float] = field(default_factory=dict)
    results: list[EvaluationResult] = field(default_factory=list)
    duration_ms: float = 0.0
    error: str | None = None


class EvaluationRunner:
    """
    Runs evaluation sets with concurrent execution.

    Handles:
    - Parallel evaluation of cases with configurable concurrency
    - Multiple metrics per case
    - Progress callbacks for UI updates
    - Optional output generation for cases without expected outputs
    - Result persistence to SQLite
    """

    def __init__(
        self,
        store: SQLiteTraceStore | None = None,
        max_workers: int = 4,
    ) -> None:
        """
        Initialize the evaluation runner.

        Args:
            store: SQLite store for persisting results (optional).
            max_workers: Maximum concurrent case evaluations.
        """
        self.store = store
        self.max_workers = max_workers
        self._cancelled = False
        self._semaphore: asyncio.Semaphore | None = None

    async def run(
        self,
        eval_set: EvaluationSet | dict[str, Any],
        *,
        output_generator: OutputGenerator | None = None,
        on_progress: ProgressCallback | None = None,
        run_id: UUID | None = None,
    ) -> EvaluationRunResult:
        """
        Run an evaluation set.

        Args:
            eval_set: The evaluation set to run (model or dict).
            output_generator: Optional function to generate outputs for cases.
            on_progress: Optional callback for progress updates.
            run_id: Optional pre-existing run ID (for resuming).

        Returns:
            EvaluationRunResult with all scores and pass/fail status.
        """
        self._cancelled = False
        self._semaphore = asyncio.Semaphore(self.max_workers)
        start_time = time.time()

        # Convert dict to model if needed
        if isinstance(eval_set, dict):
            eval_set = EvaluationSet.model_validate(eval_set)

        # Create or get run
        if run_id is None:
            run_id = UUID(str(eval_set.id))
            if self.store:
                run_id = UUID(self.store.create_evaluation_run(str(eval_set.id)))

        # Update run status
        if self.store:
            self.store.update_evaluation_run(
                str(run_id),
                status=EvaluationStatus.RUNNING.value,
            )

        # Initialize progress
        progress = ProgressInfo(
            total_cases=len(eval_set.cases),
            completed_cases=0,
            passed_cases=0,
            failed_cases=0,
        )

        results: list[EvaluationResult] = []
        metric_scores: dict[str, list[float]] = {}

        try:
            # Run evaluations concurrently
            tasks = [
                self._evaluate_case(
                    case=case,
                    metrics=eval_set.metrics,
                    output_generator=output_generator,
                    progress=progress,
                    on_progress=on_progress,
                )
                for case in eval_set.cases
            ]

            case_results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(case_results):
                if isinstance(result, Exception):
                    # Handle failed case
                    error_result = EvaluationResult(
                        evaluation_run_id=run_id,
                        evaluation_case_id=eval_set.cases[i].id,
                        passed=False,
                        error=str(result),
                    )
                    results.append(error_result)
                    progress.failed_cases += 1
                else:
                    result.evaluation_run_id = run_id
                    results.append(result)

                    # Aggregate scores by metric
                    for score in result.scores:
                        if score.metric_name not in metric_scores:
                            metric_scores[score.metric_name] = []
                        metric_scores[score.metric_name].append(score.score)

                progress.completed_cases += 1
                if on_progress:
                    on_progress(progress)

            # Calculate averages
            metric_averages = {
                name: sum(scores) / len(scores) if scores else 0.0
                for name, scores in metric_scores.items()
            }

            # Calculate pass rate
            pass_rate = (
                progress.passed_cases / progress.total_cases if progress.total_cases > 0 else 0.0
            )
            overall_passed = pass_rate >= eval_set.pass_rate_threshold

            duration_ms = (time.time() - start_time) * 1000

            # Save results
            if self.store:
                for result in results:
                    self.store.save_evaluation_result(
                        run_id=str(run_id),
                        case_id=str(result.evaluation_case_id),
                        scores=[
                            s.model_dump()
                            if hasattr(s, "model_dump")
                            else s.to_dict()
                            if hasattr(s, "to_dict")
                            else {
                                "metric_name": s.metric_name,
                                "score": s.score,
                                "passed": s.passed,
                                "reason": s.reason,
                                "details": s.details,
                            }
                            for s in result.scores
                        ],
                        passed=result.passed,
                        trace_id=str(result.trace_id) if result.trace_id else None,
                        actual_output=result.actual_output,
                        overall_score=result.overall_score,
                        duration_ms=result.duration_ms,
                        error=result.error,
                    )

                self.store.update_evaluation_run(
                    str(run_id),
                    status=EvaluationStatus.COMPLETED.value,
                    passed_cases=progress.passed_cases,
                    failed_cases=progress.failed_cases,
                    overall_pass_rate=pass_rate,
                    metric_averages=metric_averages,
                    passed=overall_passed,
                    completed_at=datetime.now(UTC).isoformat(),
                    duration_ms=duration_ms,
                )

            return EvaluationRunResult(
                run_id=run_id,
                evaluation_set_id=eval_set.id,
                status=EvaluationStatus.COMPLETED,
                total_cases=progress.total_cases,
                passed_cases=progress.passed_cases,
                failed_cases=progress.failed_cases,
                pass_rate=pass_rate,
                overall_passed=overall_passed,
                metric_averages=metric_averages,
                results=results,
                duration_ms=duration_ms,
            )

        except Exception as e:
            logger.exception("Evaluation run failed")
            duration_ms = (time.time() - start_time) * 1000

            if self.store:
                self.store.update_evaluation_run(
                    str(run_id),
                    status=EvaluationStatus.FAILED.value,
                    error=str(e),
                    completed_at=datetime.now(UTC).isoformat(),
                    duration_ms=duration_ms,
                )

            return EvaluationRunResult(
                run_id=run_id,
                evaluation_set_id=eval_set.id,
                status=EvaluationStatus.FAILED,
                total_cases=progress.total_cases,
                passed_cases=progress.passed_cases,
                failed_cases=progress.failed_cases,
                pass_rate=0.0,
                overall_passed=False,
                duration_ms=duration_ms,
                error=str(e),
            )

    async def _evaluate_case(
        self,
        case: EvaluationCase,
        metrics: list[EvaluationMetricConfig],
        output_generator: OutputGenerator | None,
        progress: ProgressInfo,
        on_progress: ProgressCallback | None,
    ) -> EvaluationResult:
        """Evaluate a single case against all metrics."""
        async with self._semaphore:
            if self._cancelled:
                raise asyncio.CancelledError("Evaluation cancelled")

            progress.current_case = case.name
            if on_progress:
                on_progress(progress)

            start_time = time.time()

            # Generate output if needed
            actual_output: Any = None
            if output_generator:
                try:
                    actual_output = await self._run_generator(output_generator, case)
                except Exception as e:
                    return EvaluationResult(
                        evaluation_run_id=UUID("00000000-0000-0000-0000-000000000000"),
                        evaluation_case_id=case.id,
                        passed=False,
                        error=f"Output generation failed: {e}",
                        duration_ms=(time.time() - start_time) * 1000,
                    )
            elif case.actual_output:
                # Use stored actual output (from trace/step) for comparison
                actual_output = case.actual_output
            elif case.expected_output:
                # Fallback: use expected output for non-comparison metrics (json_valid, length_check)
                # WARNING: This means comparison metrics like exact_match will trivially pass
                logger.warning(
                    f"Case {case.name}: No actual_output and no output_generator. "
                    "Using expected_output which may cause comparison metrics to pass trivially."
                )
                actual_output = case.expected_output

            # Evaluate against all metrics
            metric_results: list[MetricScore] = []
            all_passed = True
            total_weighted_score = 0.0
            total_weight = 0.0

            for metric_config in metrics:
                progress.current_metric = metric_config.name
                if on_progress:
                    on_progress(progress)

                try:
                    adapter = get_adapter(metric_config.framework.value)
                    result = await adapter.evaluate(case, actual_output, metric_config)

                    score = MetricScore(
                        metric_name=result.metric_name,
                        framework=metric_config.framework,
                        score=result.score,
                        threshold=metric_config.threshold,
                        passed=result.passed,
                        reason=result.reason,
                        details=result.details,
                    )
                    metric_results.append(score)

                    if not result.passed:
                        all_passed = False

                    total_weighted_score += result.score * metric_config.weight
                    total_weight += metric_config.weight

                except Exception as e:
                    logger.warning(f"Metric {metric_config.name} failed: {e}")
                    score = MetricScore(
                        metric_name=metric_config.name,
                        framework=metric_config.framework,
                        score=0.0,
                        threshold=metric_config.threshold,
                        passed=False,
                        reason=f"Evaluation error: {e}",
                    )
                    metric_results.append(score)
                    all_passed = False

            # Calculate overall score
            overall_score = total_weighted_score / total_weight if total_weight > 0 else 0.0

            duration_ms = (time.time() - start_time) * 1000

            # Update progress
            if all_passed:
                progress.passed_cases += 1
            else:
                progress.failed_cases += 1

            return EvaluationResult(
                evaluation_run_id=UUID("00000000-0000-0000-0000-000000000000"),  # Set later
                evaluation_case_id=case.id,
                actual_output=actual_output
                if isinstance(actual_output, dict)
                else {"output": str(actual_output)},
                scores=metric_results,
                overall_score=overall_score,
                passed=all_passed,
                duration_ms=duration_ms,
            )

    async def _run_generator(self, generator: OutputGenerator, case: EvaluationCase) -> Any:
        """Run output generator, handling sync and async functions."""
        import inspect

        if inspect.iscoroutinefunction(generator):
            return await generator(case)
        else:
            # Run sync function in thread pool
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, generator, case)

    def cancel(self) -> None:
        """Cancel the current evaluation run."""
        self._cancelled = True


def run_evaluation_sync(
    eval_set: EvaluationSet | dict[str, Any],
    store: SQLiteTraceStore | None = None,
    output_generator: OutputGenerator | None = None,
    on_progress: ProgressCallback | None = None,
) -> EvaluationRunResult:
    """
    Synchronous wrapper for running evaluations.

    Convenience function for non-async contexts.

    Args:
        eval_set: The evaluation set to run.
        store: Optional SQLite store for persistence.
        output_generator: Optional output generator function.
        on_progress: Optional progress callback.

    Returns:
        EvaluationRunResult with all scores.
    """
    runner = EvaluationRunner(store=store)
    return asyncio.run(
        runner.run(
            eval_set,
            output_generator=output_generator,
            on_progress=on_progress,
        )
    )
