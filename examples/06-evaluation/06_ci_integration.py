#!/usr/bin/env python3
"""CI/CD Integration - Running evaluations in continuous integration pipelines.

This example demonstrates how to integrate TraceCraft evaluations
into CI/CD workflows:
- Quality gates based on pass rates
- Exit codes for pipeline integration
- JSON output for reporting
- Regression detection

Prerequisites:
    - TraceCraft installed (pip install tracecraft)

Environment Variables:
    - TRACECRAFT_EVAL_THRESHOLD: Custom pass rate threshold (default: 0.8)
    - CI: Set to 'true' when running in CI environment

External Services:
    - None required for basic example

Usage:
    # Local testing
    python examples/06-evaluation/06_ci_integration.py

    # In CI with custom threshold
    TRACECRAFT_EVAL_THRESHOLD=0.9 python examples/06-evaluation/06_ci_integration.py

Expected Output:
    - Evaluation results in CI-friendly format
    - Exit code 0 for pass, 1 for fail
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import tracecraft
from tracecraft.evaluation import (
    EvaluationCase,
    EvaluationMetricConfig,
    EvaluationSet,
    MetricFramework,
    run_evaluation_sync,
)


def get_eval_threshold() -> float:
    """Get evaluation threshold from environment or use default."""
    return float(os.environ.get("TRACECRAFT_EVAL_THRESHOLD", "0.8"))


def is_ci_environment() -> bool:
    """Check if running in CI environment."""
    ci_indicators = ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS", "CIRCLECI"]
    return any(os.environ.get(var) for var in ci_indicators)


def format_duration(ms: float | None) -> str:
    """Format duration in human-readable form."""
    if ms is None:
        return "N/A"
    if ms < 1000:
        return f"{ms:.0f}ms"
    return f"{ms / 1000:.2f}s"


def main() -> int:
    """Run CI/CD evaluation and return exit code."""
    is_ci = is_ci_environment()
    threshold = get_eval_threshold()

    # Header
    print("=" * 60)
    print("TraceCraft CI/CD Evaluation")
    print("=" * 60)
    print(f"Environment: {'CI' if is_ci else 'Local'}")
    print(f"Pass rate threshold: {threshold:.0%}")
    print(f"Timestamp: {datetime.now(UTC).isoformat()}")
    print()

    # Step 1: Initialize TraceCraft
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    runtime = tracecraft.init(
        storage=db_path,  # .db extension auto-selects SQLite storage
        console=not is_ci,  # Disable console output in CI
    )
    store = runtime.storage

    # Step 2: Load or create evaluation set
    # In real CI, you would load this from a config file or database
    eval_set = EvaluationSet(
        name="ci-quality-gate",
        description="CI/CD quality gate evaluation",
        metrics=[
            EvaluationMetricConfig(
                name="exact_match",
                framework=MetricFramework.BUILTIN,
                metric_type="exact_match",
                threshold=1.0,
            ),
            EvaluationMetricConfig(
                name="contains",
                framework=MetricFramework.BUILTIN,
                metric_type="contains",
                threshold=1.0,
            ),
        ],
        pass_rate_threshold=threshold,
        cases=[
            # Test cases representing expected behavior
            EvaluationCase(
                name="greeting-response",
                input={"prompt": "Say hello"},
                expected_output={"answer": "Hello!"},
                tags=["core", "greeting"],
            ),
            EvaluationCase(
                name="farewell-response",
                input={"prompt": "Say goodbye"},
                expected_output={"answer": "Goodbye!"},
                tags=["core", "farewell"],
            ),
            EvaluationCase(
                name="math-basic",
                input={"prompt": "What is 2+2?"},
                expected_output={"answer": "4"},
                tags=["core", "math"],
            ),
            EvaluationCase(
                name="math-complex",
                input={"prompt": "What is 10*5?"},
                expected_output={"answer": "50"},
                tags=["advanced", "math"],
            ),
            EvaluationCase(
                name="knowledge-question",
                input={"prompt": "What is Python?"},
                expected_output={"answer": "programming language"},
                tags=["knowledge"],
            ),
        ],
    )

    print(f"Evaluation set: {eval_set.name}")
    print(f"Test cases: {len(eval_set.cases)}")
    print()

    # Step 3: Define output generator (your system under test)
    def system_under_test(case: EvaluationCase) -> str:
        """Simulate the system being tested.

        In real CI, this would be your actual LLM/agent code.
        """
        prompt = case.input.get("prompt", "")

        # Simulated responses (some correct, some incorrect for demo)
        responses = {
            "Say hello": "Hello!",
            "Say goodbye": "Goodbye!",
            "What is 2+2?": "4",
            "What is 10*5?": "50",
            "What is Python?": "Python is a programming language.",
        }

        return responses.get(prompt, "I don't understand.")

    # Step 4: Run evaluation
    print("Running evaluation...")
    print("-" * 40)

    result = run_evaluation_sync(
        eval_set,
        output_generator=system_under_test,
        store=store,
    )

    # Step 5: Generate report
    print()
    print("EVALUATION RESULTS")
    print("=" * 40)
    print(f"Status:      {result.status.value.upper()}")
    print(f"Total:       {result.total_cases}")
    print(f"Passed:      {result.passed_cases}")
    print(f"Failed:      {result.failed_cases}")
    print(f"Pass rate:   {result.pass_rate:.1%}")
    print(f"Threshold:   {threshold:.0%}")
    print(f"Duration:    {format_duration(result.duration_ms)}")
    print()

    # Per-case details (verbose in local, summary in CI)
    if not is_ci:
        print("CASE DETAILS")
        print("-" * 40)
        for i, case_result in enumerate(result.results):
            case = eval_set.cases[i]
            status = "PASS" if case_result.passed else "FAIL"
            print(f"[{status}] {case.name}")
            if not case_result.passed and case_result.scores:
                for score in case_result.scores:
                    if not score.passed:
                        print(f"       {score.metric_name}: {score.score:.2f}")
        print()

    # Quality gate decision
    gate_passed = result.overall_passed

    print("QUALITY GATE")
    print("-" * 40)
    if gate_passed:
        print(f"PASSED - Pass rate {result.pass_rate:.1%} >= {threshold:.0%}")
    else:
        print(f"FAILED - Pass rate {result.pass_rate:.1%} < {threshold:.0%}")
    print()

    # Step 6: Generate JSON report for CI systems
    report = {
        "evaluation": {
            "name": eval_set.name,
            "timestamp": datetime.now(UTC).isoformat(),
            "status": result.status.value,
            "run_id": str(result.run_id),
        },
        "results": {
            "total_cases": result.total_cases,
            "passed_cases": result.passed_cases,
            "failed_cases": result.failed_cases,
            "pass_rate": result.pass_rate,
            "threshold": threshold,
            "duration_ms": result.duration_ms,
        },
        "quality_gate": {
            "passed": gate_passed,
            "reason": "Pass rate meets threshold" if gate_passed else "Pass rate below threshold",
        },
        "failed_cases": [
            {
                "name": eval_set.cases[i].name,
                "tags": eval_set.cases[i].tags,
            }
            for i, case_result in enumerate(result.results)
            if not case_result.passed
        ],
    }

    # Write JSON report
    report_path = Path(db_path).parent / "eval-report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"JSON report written to: {report_path}")

    # CI-specific output
    if is_ci:
        # GitHub Actions output format
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"\n::notice::Evaluation pass rate: {result.pass_rate:.1%}")
            if not gate_passed:
                print(
                    f"::error::Quality gate failed. Pass rate {result.pass_rate:.1%} < {threshold:.0%}"
                )

    # Cleanup
    Path(db_path).unlink(missing_ok=True)
    report_path.unlink(missing_ok=True)

    print()
    print("=" * 60)
    print("CI/CD Integration Tips:")
    print("=" * 60)
    print("""
1. Set pass rate threshold via environment:
   TRACECRAFT_EVAL_THRESHOLD=0.9 python your_eval.py

2. Use exit code for pipeline control:
   python eval.py && echo "Passed" || echo "Failed"

3. Parse JSON report for detailed analysis:
   cat eval-report.json | jq '.failed_cases[].name'

4. GitHub Actions workflow example:
   - name: Run Evaluations
     run: python -m tracecraft eval run db.sqlite my-eval-set
     env:
       TRACECRAFT_EVAL_THRESHOLD: '0.9'

5. GitLab CI example:
   evaluation:
     script:
       - python -m tracecraft eval run db.sqlite my-eval-set
     allow_failure: false
""")

    # Return exit code based on quality gate
    return 0 if gate_passed else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
