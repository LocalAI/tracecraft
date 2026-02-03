#!/usr/bin/env python3
"""LLM-as-Judge Evaluation - Using LLMs to evaluate LLM outputs.

This example demonstrates how to use an LLM as a judge for
evaluating outputs based on custom criteria:
- Quality scoring
- Coherence checking
- Factual accuracy assessment
- Style and tone evaluation

Prerequisites:
    - TraceCraft installed (pip install tracecraft)
    - OpenAI or Anthropic API key (for LLM judge)

Environment Variables:
    - OPENAI_API_KEY: For OpenAI-based judge
    - ANTHROPIC_API_KEY: For Anthropic-based judge

External Services:
    - OpenAI or Anthropic API

Usage:
    export OPENAI_API_KEY=your-key-here
    python examples/06-evaluation/05_llm_judge.py

Expected Output:
    - LLM judge evaluations with reasoning
    - Scores based on custom criteria
"""

from __future__ import annotations

import os
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
    """Run the LLM-as-judge evaluation example."""
    print("=" * 60)
    print("TraceCraft LLM-as-Judge Evaluation Example")
    print("=" * 60)

    has_api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not has_api_key:
        print("\nNote: No LLM API key found.")
        print("Set OPENAI_API_KEY or ANTHROPIC_API_KEY for LLM-based judging.")
        print("This example will use built-in metrics for demonstration.")

    # Step 1: Initialize TraceCraft
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    runtime = tracecraft.init(
        storage=db_path,  # .db extension auto-selects SQLite storage
        console=True,
    )
    store = runtime.storage

    print(f"\nUsing temporary database: {db_path}")

    # Step 2: Configure LLM Judge metrics
    print("\n--- Configuring LLM Judge ---")

    if has_api_key:
        # Use LLM judge metric when API key is available
        metrics = [
            # Custom LLM judge with specific evaluation criteria
            EvaluationMetricConfig(
                name="quality_judge",
                framework=MetricFramework.BUILTIN,
                metric_type="llm_judge",
                threshold=0.7,
                parameters={
                    # Custom evaluation prompt
                    "criteria": """
                    Evaluate the response on a scale of 0.0 to 1.0 based on:
                    1. Accuracy: Is the information factually correct?
                    2. Completeness: Does it fully answer the question?
                    3. Clarity: Is it well-structured and easy to understand?
                    4. Conciseness: Is it appropriately brief without missing key info?

                    Provide a score and brief reasoning.
                    """,
                    "model": os.environ.get("OPENAI_API_KEY") and "gpt-4o-mini" or "claude-3-haiku",
                },
            ),
            # Additional built-in checks
            EvaluationMetricConfig(
                name="length_check",
                framework=MetricFramework.BUILTIN,
                metric_type="length_check",
                threshold=0.5,
                parameters={
                    "min_length": 20,
                    "max_length": 500,
                },
            ),
        ]
        print("Using LLM judge + length check metrics")
    else:
        # Fallback to built-in metrics
        metrics = [
            EvaluationMetricConfig(
                name="contains",
                framework=MetricFramework.BUILTIN,
                metric_type="contains",
                threshold=1.0,
            ),
            EvaluationMetricConfig(
                name="length_check",
                framework=MetricFramework.BUILTIN,
                metric_type="length_check",
                threshold=0.5,
                parameters={
                    "min_length": 10,
                    "max_length": 200,
                },
            ),
        ]
        print("Using built-in metrics (no LLM API key)")

    # Step 3: Create evaluation cases
    print("\n--- Creating Test Cases ---")

    eval_set = EvaluationSet(
        name="response-quality-eval",
        description="Evaluate response quality using LLM-as-judge",
        metrics=metrics,
        pass_rate_threshold=0.6,
        cases=[
            # Case 1: Technical explanation
            EvaluationCase(
                name="explain-recursion",
                input={
                    "question": "Explain recursion in programming.",
                    "style": "educational",
                },
                expected_output={
                    "quality_criteria": "Clear, accurate, with example",
                },
            ),
            # Case 2: Summary task
            EvaluationCase(
                name="summarize-article",
                input={
                    "task": "Summarize the following text",
                    "text": "Machine learning is a subset of artificial intelligence "
                    "that focuses on developing algorithms that can learn from data. "
                    "Unlike traditional programming where rules are explicitly coded, "
                    "ML systems improve through experience. Common applications include "
                    "image recognition, natural language processing, and recommendation systems.",
                },
                expected_output={
                    "quality_criteria": "Concise, captures key points, accurate",
                },
            ),
            # Case 3: Creative writing
            EvaluationCase(
                name="write-haiku",
                input={
                    "task": "Write a haiku about programming",
                    "style": "creative",
                },
                expected_output={
                    "quality_criteria": "Follows 5-7-5 syllable pattern, thematic",
                },
            ),
            # Case 4: Code explanation
            EvaluationCase(
                name="explain-code",
                input={
                    "task": "Explain what this code does",
                    "code": "def fib(n): return n if n < 2 else fib(n-1) + fib(n-2)",
                },
                expected_output={
                    "quality_criteria": "Accurate, mentions recursion and Fibonacci",
                },
            ),
        ],
    )

    print(f"Created evaluation set: {eval_set.name}")
    print(f"  Cases: {len(eval_set.cases)}")

    # Step 4: Define output generator (simulated LLM responses)
    def response_generator(case: EvaluationCase) -> str:
        """Generate responses for evaluation.

        In production, this would be your actual LLM/agent.
        """
        case_name = case.name

        responses = {
            "explain-recursion": "Recursion is a programming technique where a function "
            "calls itself to solve smaller instances of the same problem. For example, "
            "calculating factorial: factorial(n) = n * factorial(n-1), with factorial(0) = 1. "
            "It requires a base case to prevent infinite loops.",
            "summarize-article": "Machine learning is an AI subset where algorithms learn from "
            "data rather than explicit programming. It enables applications like image "
            "recognition, NLP, and recommendation systems.",
            "write-haiku": "Code flows like water\n"
            "Bugs swim through logic streams\n"
            "Debug brings the dawn",
            "explain-code": "This code defines a recursive Fibonacci function. It returns n "
            "directly for n < 2 (base cases: fib(0)=0, fib(1)=1). Otherwise, it recursively "
            "computes fib(n-1) + fib(n-2) to find the nth Fibonacci number.",
        }

        return responses.get(case_name, "I cannot answer this question.")

    # Step 5: Run evaluation
    print("\n--- Running LLM Judge Evaluation ---")

    result = run_evaluation_sync(
        eval_set,
        output_generator=response_generator,
        store=store,
    )

    # Step 6: Display results
    print("\n--- Evaluation Results ---")
    print(f"Status: {result.status.value}")
    print(f"Total cases: {result.total_cases}")
    print(f"Passed: {result.passed_cases}")
    print(f"Failed: {result.failed_cases}")
    print(f"Pass rate: {result.pass_rate:.1%}")
    print(f"Overall passed: {'YES' if result.overall_passed else 'NO'}")

    print("\n--- Detailed Judge Results ---")
    for i, case_result in enumerate(result.results):
        case = eval_set.cases[i]
        status = "PASS" if case_result.passed else "FAIL"
        print(f"\n[{status}] {case.name}")

        if case_result.actual_output:
            output_preview = str(case_result.actual_output)[:100]
            if len(str(case_result.actual_output)) > 100:
                output_preview += "..."
            print(f"  Output: {output_preview}")

        if case_result.scores:
            print("  Scores:")
            for score in case_result.scores:
                status_icon = "PASS" if score.passed else "FAIL"
                print(f"    {score.metric_name}: {score.score:.2f} [{status_icon}]")
                if score.reason:
                    reason_preview = score.reason[:80]
                    if len(score.reason) > 80:
                        reason_preview += "..."
                    print(f"      Reason: {reason_preview}")

    # Cleanup
    Path(db_path).unlink(missing_ok=True)

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nLLM-as-Judge Benefits:")
    print("  - Evaluate subjective qualities (tone, style, helpfulness)")
    print("  - Custom criteria for your specific use case")
    print("  - Scalable quality assessment")
    print("\nConsiderations:")
    print("  - Judge model quality affects evaluations")
    print("  - Consider using a more capable model as judge")
    print("  - Combine with objective metrics for robustness")
    print("\nNext steps:")
    print("- Try 06_ci_integration.py for CI/CD pipeline evaluation")


if __name__ == "__main__":
    main()
