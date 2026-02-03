#!/usr/bin/env python3
"""Basic Evaluation - Create and run a simple evaluation set.

This example demonstrates the core evaluation workflow:
1. Initialize TraceCraft with SQLite storage
2. Create an evaluation set with metrics
3. Add test cases
4. Run the evaluation
5. View results

Prerequisites:
    - TraceCraft installed (pip install tracecraft)

Environment Variables:
    - None required

External Services:
    - None required

Usage:
    python examples/06-evaluation/01_basic_eval.py

Expected Output:
    - Evaluation results showing pass/fail for each case
    - Overall pass rate and summary
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import tracecraft
from tracecraft.evaluation import (
    EvaluationCase,
    EvaluationMetricConfig,
    EvaluationSet,
    MetricFramework,
    run_evaluation_sync,
)


def main() -> None:
    """Run the basic evaluation example."""
    print("=" * 60)
    print("TraceCraft Basic Evaluation Example")
    print("=" * 60)

    # Step 1: Initialize TraceCraft with SQLite storage
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    runtime = tracecraft.init(
        storage=db_path,  # .db extension auto-selects SQLite storage
        console=True,
    )
    store = runtime.storage

    print(f"\nUsing temporary database: {db_path}")

    # Step 2: Create an evaluation set with metrics
    print("\n--- Creating Evaluation Set ---")

    eval_set = EvaluationSet(
        name="math-baseline",
        description="Test basic math operations",
        metrics=[
            # Exact match metric - output must match expected exactly
            EvaluationMetricConfig(
                name="exact_match",
                framework=MetricFramework.BUILTIN,
                metric_type="exact_match",
                threshold=1.0,  # Must match exactly
            ),
            # Contains metric - output must contain expected text
            EvaluationMetricConfig(
                name="contains_answer",
                framework=MetricFramework.BUILTIN,
                metric_type="contains",
                threshold=1.0,
                parameters={"text": "answer"},  # Optional: specify text to find
            ),
        ],
        default_threshold=0.7,
        pass_rate_threshold=0.8,  # 80% of cases must pass
        cases=[
            # Test case 1: Simple addition
            EvaluationCase(
                name="addition-test-1",
                input={"question": "What is 2+2?"},
                expected_output={"answer": "4"},
            ),
            # Test case 2: Another addition
            EvaluationCase(
                name="addition-test-2",
                input={"question": "What is 3+3?"},
                expected_output={"answer": "6"},
            ),
            # Test case 3: Subtraction
            EvaluationCase(
                name="subtraction-test-1",
                input={"question": "What is 5-2?"},
                expected_output={"answer": "3"},
            ),
            # Test case 4: Multiplication
            EvaluationCase(
                name="multiplication-test-1",
                input={"question": "What is 4*3?"},
                expected_output={"answer": "12"},
            ),
        ],
    )

    print(f"Created evaluation set: {eval_set.name}")
    print(f"  Metrics: {[m.name for m in eval_set.metrics]}")
    print(f"  Cases: {len(eval_set.cases)}")

    # Step 3: Define an output generator (simulates LLM responses)
    def math_solver(case: EvaluationCase) -> str:
        """Simulate an LLM solving math problems.

        In a real scenario, this would call your LLM/agent.
        """
        question = case.input.get("question", "")

        # Simple math parsing (in real code, you'd call an LLM)
        if "2+2" in question:
            return "4"
        elif "3+3" in question:
            return "6"
        elif "5-2" in question:
            return "3"
        elif "4*3" in question:
            return "12"
        return "unknown"

    # Step 4: Run the evaluation
    print("\n--- Running Evaluation ---")

    # Option A: Synchronous execution
    result = run_evaluation_sync(
        eval_set,
        output_generator=math_solver,
        store=store,  # Store results in SQLite
    )

    # Step 5: View results
    print("\n--- Evaluation Results ---")
    print(f"Status: {result.status.value}")
    print(f"Total cases: {result.total_cases}")
    print(f"Passed: {result.passed_cases}")
    print(f"Failed: {result.failed_cases}")
    print(f"Pass rate: {result.pass_rate:.1%}")
    print(f"Overall passed: {'YES' if result.overall_passed else 'NO'}")

    if result.duration_ms:
        print(f"Duration: {result.duration_ms:.1f}ms")

    # Print per-case results
    print("\n--- Per-Case Results ---")
    for case_result in result.results:
        status = "PASS" if case_result.passed else "FAIL"
        print(f"  [{status}] Case: {case_result.evaluation_case_id}")
        if case_result.scores:
            for score in case_result.scores:
                score_status = "PASS" if score.passed else "FAIL"
                print(f"         {score.metric_name}: {score.score:.2f} [{score_status}]")

    # Cleanup
    Path(db_path).unlink(missing_ok=True)

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nWhat just happened:")
    print("1. Created an evaluation set with exact_match and contains metrics")
    print("2. Added 4 test cases for math operations")
    print("3. Ran evaluation with a simulated math solver")
    print("4. Results stored in SQLite for history tracking")
    print("\nNext steps:")
    print("- Try 02_from_traces.py to create evals from existing traces")
    print("- Try 03_deepeval_metrics.py for LLM-specific metrics")


if __name__ == "__main__":
    main()
