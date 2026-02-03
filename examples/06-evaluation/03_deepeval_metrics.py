#!/usr/bin/env python3
"""DeepEval Metrics - Using DeepEval for LLM evaluation.

This example demonstrates how to use DeepEval metrics for
comprehensive LLM evaluation including:
- Faithfulness
- Answer Relevancy
- Hallucination detection
- Bias detection
- Toxicity detection

Prerequisites:
    - TraceCraft installed (pip install tracecraft)
    - DeepEval installed (pip install deepeval)
    - OpenAI API key (for LLM-based metrics)

Environment Variables:
    - OPENAI_API_KEY: Required for DeepEval metrics

External Services:
    - OpenAI API (for metric evaluation)

Usage:
    export OPENAI_API_KEY=your-key-here
    python examples/06-evaluation/03_deepeval_metrics.py

Expected Output:
    - Evaluation results with DeepEval metric scores
    - Detailed explanations for each metric
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Check for DeepEval installation
try:
    import deepeval  # noqa: F401

    DEEPEVAL_AVAILABLE = True
except ImportError:
    DEEPEVAL_AVAILABLE = False

import tracecraft
from tracecraft.evaluation import (
    EvaluationCase,
    EvaluationMetricConfig,
    EvaluationSet,
    MetricFramework,
    run_evaluation_sync,
)


def main() -> None:
    """Run the DeepEval metrics example."""
    print("=" * 60)
    print("TraceCraft DeepEval Metrics Example")
    print("=" * 60)

    if not DEEPEVAL_AVAILABLE:
        print("\nDeepEval is not installed.")
        print("Install it with: pip install deepeval")
        print("\nThis example will demonstrate the API with built-in metrics instead.")
        print("When DeepEval is installed, uncomment the DeepEval metrics below.")

    if not os.environ.get("OPENAI_API_KEY") and DEEPEVAL_AVAILABLE:
        print("\nWarning: OPENAI_API_KEY not set.")
        print("DeepEval metrics require an OpenAI API key for LLM-based evaluation.")
        print("Set it with: export OPENAI_API_KEY=your-key-here")

    # Step 1: Initialize TraceCraft
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    runtime = tracecraft.init(
        storage=db_path,  # .db extension auto-selects SQLite storage
        console=True,
    )
    store = runtime.storage

    print(f"\nUsing temporary database: {db_path}")

    # Step 2: Define metrics configuration
    print("\n--- Configuring Metrics ---")

    if DEEPEVAL_AVAILABLE and os.environ.get("OPENAI_API_KEY"):
        # Use DeepEval metrics when available
        metrics = [
            # Faithfulness: Is the output faithful to the context?
            EvaluationMetricConfig(
                name="faithfulness",
                framework=MetricFramework.DEEPEVAL,
                metric_type="faithfulness",
                threshold=0.7,
            ),
            # Answer Relevancy: Is the answer relevant to the question?
            EvaluationMetricConfig(
                name="answer_relevancy",
                framework=MetricFramework.DEEPEVAL,
                metric_type="answer_relevancy",
                threshold=0.7,
            ),
            # Hallucination: Does the output contain hallucinations?
            EvaluationMetricConfig(
                name="hallucination",
                framework=MetricFramework.DEEPEVAL,
                metric_type="hallucination",
                threshold=0.3,  # Lower is better for hallucination
            ),
        ]
        print("Using DeepEval metrics: faithfulness, answer_relevancy, hallucination")
    else:
        # Fallback to built-in metrics for demonstration
        metrics = [
            EvaluationMetricConfig(
                name="contains_check",
                framework=MetricFramework.BUILTIN,
                metric_type="contains",
                threshold=1.0,
            ),
            EvaluationMetricConfig(
                name="json_valid",
                framework=MetricFramework.BUILTIN,
                metric_type="json_valid",
                threshold=1.0,
            ),
        ]
        print("Using built-in metrics (DeepEval not available)")

    # Step 3: Create evaluation cases for RAG scenario
    print("\n--- Creating RAG Evaluation Cases ---")

    # RAG-style cases with retrieval context
    eval_set = EvaluationSet(
        name="rag-quality-eval",
        description="Evaluate RAG system output quality",
        metrics=metrics,
        pass_rate_threshold=0.7,
        cases=[
            # Case 1: Factual question with good context
            EvaluationCase(
                name="factual-with-context",
                input={
                    "question": "What is the capital of France?",
                    "context": "France is a country in Western Europe. "
                    "Its capital city is Paris, which is known for the Eiffel Tower.",
                },
                expected_output={
                    "answer": "The capital of France is Paris.",
                },
                retrieval_context=[
                    "France is a country in Western Europe.",
                    "Its capital city is Paris, which is known for the Eiffel Tower.",
                ],
            ),
            # Case 2: Technical question
            EvaluationCase(
                name="technical-question",
                input={
                    "question": "What is Python used for?",
                    "context": "Python is a versatile programming language used for "
                    "web development, data science, machine learning, and automation.",
                },
                expected_output={
                    "answer": "Python is used for web development, data science, "
                    "machine learning, and automation.",
                },
                retrieval_context=[
                    "Python is a versatile programming language.",
                    "Python is used for web development, data science, ML, and automation.",
                ],
            ),
            # Case 3: Question requiring inference
            EvaluationCase(
                name="inference-required",
                input={
                    "question": "Is Python good for beginners?",
                    "context": "Python has a simple syntax that is easy to read and write. "
                    "It is often recommended as a first programming language.",
                },
                expected_output={
                    "answer": "Yes, Python is good for beginners due to its simple syntax.",
                },
                retrieval_context=[
                    "Python has a simple syntax that is easy to read and write.",
                    "It is often recommended as a first programming language.",
                ],
            ),
        ],
    )

    print(f"Created evaluation set: {eval_set.name}")
    print(f"  Cases: {len(eval_set.cases)}")

    # Step 4: Define output generator (simulated RAG system)
    def rag_system(case: EvaluationCase) -> str:
        """Simulate a RAG system response.

        In production, this would be your actual RAG pipeline.
        """
        question = case.input.get("question", "")
        context = case.input.get("context", "")

        # Simple template-based response (in reality, use an LLM)
        responses = {
            "What is the capital of France?": "The capital of France is Paris.",
            "What is Python used for?": "Python is used for web development, data science, "
            "machine learning, and automation.",
            "Is Python good for beginners?": "Yes, Python is excellent for beginners "
            "because of its simple and readable syntax.",
        }

        return responses.get(question, f"Based on the context: {context[:50]}...")

    # Step 5: Run evaluation
    print("\n--- Running Evaluation ---")

    result = run_evaluation_sync(
        eval_set,
        output_generator=rag_system,
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

    print("\n--- Detailed Results ---")
    for i, case_result in enumerate(result.results):
        case = eval_set.cases[i]
        status = "PASS" if case_result.passed else "FAIL"
        print(f"\n[{status}] {case.name}")
        print(f"  Question: {case.input.get('question', 'N/A')}")
        if case_result.scores:
            print("  Scores:")
            for score in case_result.scores:
                score_status = "PASS" if score.passed else "FAIL"
                print(f"    {score.metric_name}: {score.score:.2f} [{score_status}]")
                if score.reason:
                    print(f"      Reason: {score.reason}")

    # Cleanup
    Path(db_path).unlink(missing_ok=True)

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nDeepEval Metrics Available:")
    print("  - faithfulness: Is output grounded in context?")
    print("  - answer_relevancy: Is answer relevant to question?")
    print("  - hallucination: Does output contain fabricated info?")
    print("  - bias: Does output contain unfair bias?")
    print("  - toxicity: Does output contain harmful content?")
    print("\nTo use DeepEval:")
    print("  1. pip install deepeval")
    print("  2. export OPENAI_API_KEY=your-key")
    print("  3. Re-run this example")
    print("\nNext steps:")
    print("- Try 04_ragas_rag.py for RAGAS evaluation")


if __name__ == "__main__":
    main()
