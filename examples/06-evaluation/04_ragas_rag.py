#!/usr/bin/env python3
"""RAGAS Evaluation - RAG-specific evaluation with RAGAS framework.

This example demonstrates how to use RAGAS (Retrieval Augmented Generation
Assessment) for evaluating RAG systems:
- Context Precision: Are relevant chunks ranked higher?
- Context Recall: Are all relevant chunks retrieved?
- Faithfulness: Is the answer grounded in the context?
- Answer Relevancy: Does the answer address the question?

Prerequisites:
    - TraceCraft installed (pip install tracecraft)
    - RAGAS installed (pip install ragas datasets)
    - OpenAI API key (for LLM-based metrics)

Environment Variables:
    - OPENAI_API_KEY: Required for RAGAS metrics

External Services:
    - OpenAI API (for metric evaluation)

Usage:
    export OPENAI_API_KEY=your-key-here
    python examples/06-evaluation/04_ragas_rag.py

Expected Output:
    - RAG-specific evaluation scores
    - Analysis of retrieval and generation quality
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Check for RAGAS installation
try:
    import ragas  # noqa: F401

    RAGAS_AVAILABLE = True
except ImportError:
    RAGAS_AVAILABLE = False

import tracecraft
from tracecraft.evaluation import (
    EvaluationCase,
    EvaluationMetricConfig,
    EvaluationSet,
    MetricFramework,
    run_evaluation_sync,
)


def main() -> None:
    """Run the RAGAS evaluation example."""
    print("=" * 60)
    print("TraceCraft RAGAS Evaluation Example")
    print("=" * 60)

    if not RAGAS_AVAILABLE:
        print("\nRAGAS is not installed.")
        print("Install it with: pip install ragas datasets")
        print("\nThis example will demonstrate the API with built-in metrics instead.")

    if not os.environ.get("OPENAI_API_KEY") and RAGAS_AVAILABLE:
        print("\nWarning: OPENAI_API_KEY not set.")
        print("RAGAS metrics require an OpenAI API key.")

    # Step 1: Initialize TraceCraft
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    runtime = tracecraft.init(
        storage=db_path,  # .db extension auto-selects SQLite storage
        console=True,
    )
    store = runtime.storage

    print(f"\nUsing temporary database: {db_path}")

    # Step 2: Define RAGAS metrics configuration
    print("\n--- Configuring RAGAS Metrics ---")

    if RAGAS_AVAILABLE and os.environ.get("OPENAI_API_KEY"):
        metrics = [
            # Context Precision: Measures if relevant context is ranked higher
            EvaluationMetricConfig(
                name="context_precision",
                framework=MetricFramework.RAGAS,
                metric_type="context_precision",
                threshold=0.7,
            ),
            # Context Recall: Measures if all relevant context was retrieved
            EvaluationMetricConfig(
                name="context_recall",
                framework=MetricFramework.RAGAS,
                metric_type="context_recall",
                threshold=0.7,
            ),
            # Faithfulness: Is the answer grounded in context?
            EvaluationMetricConfig(
                name="faithfulness",
                framework=MetricFramework.RAGAS,
                metric_type="faithfulness",
                threshold=0.8,
            ),
            # Answer Relevancy: Does answer address the question?
            EvaluationMetricConfig(
                name="answer_relevancy",
                framework=MetricFramework.RAGAS,
                metric_type="answer_relevancy",
                threshold=0.7,
            ),
        ]
        print(
            "Using RAGAS metrics: context_precision, context_recall, faithfulness, answer_relevancy"
        )
    else:
        metrics = [
            EvaluationMetricConfig(
                name="contains",
                framework=MetricFramework.BUILTIN,
                metric_type="contains",
                threshold=1.0,
            ),
        ]
        print("Using built-in metrics (RAGAS not available)")

    # Step 3: Create RAG evaluation cases
    print("\n--- Creating RAG Evaluation Cases ---")

    # Simulated knowledge base documents
    knowledge_base = {
        "doc1": "Python was created by Guido van Rossum and first released in 1991.",
        "doc2": "Python is known for its simple and readable syntax.",
        "doc3": "Python supports multiple programming paradigms including procedural, "
        "object-oriented, and functional programming.",
        "doc4": "Machine learning libraries like TensorFlow and PyTorch are written for Python.",
        "doc5": "Python's package manager pip makes it easy to install third-party libraries.",
    }

    eval_set = EvaluationSet(
        name="rag-system-eval",
        description="Comprehensive RAG system evaluation with RAGAS",
        metrics=metrics,
        pass_rate_threshold=0.75,
        cases=[
            # Case 1: Simple factual retrieval
            EvaluationCase(
                name="python-creator",
                input={
                    "question": "Who created Python?",
                },
                expected_output={
                    "answer": "Python was created by Guido van Rossum.",
                },
                # The context that was retrieved for this question
                retrieval_context=[
                    knowledge_base["doc1"],  # Relevant
                    knowledge_base["doc2"],  # Somewhat relevant
                ],
            ),
            # Case 2: Multi-document question
            EvaluationCase(
                name="python-features",
                input={
                    "question": "What are the key features of Python?",
                },
                expected_output={
                    "answer": "Python has simple syntax and supports multiple paradigms.",
                },
                retrieval_context=[
                    knowledge_base["doc2"],  # Relevant
                    knowledge_base["doc3"],  # Relevant
                    knowledge_base["doc5"],  # Somewhat relevant
                ],
            ),
            # Case 3: Technical question about ML
            EvaluationCase(
                name="python-ml",
                input={
                    "question": "Can Python be used for machine learning?",
                },
                expected_output={
                    "answer": "Yes, Python has popular ML libraries like TensorFlow and PyTorch.",
                },
                retrieval_context=[
                    knowledge_base["doc4"],  # Highly relevant
                    knowledge_base["doc3"],  # Somewhat relevant
                ],
            ),
        ],
    )

    print(f"Created evaluation set: {eval_set.name}")
    print(f"  Cases: {len(eval_set.cases)}")

    # Step 4: Define RAG system output generator
    def rag_pipeline(case: EvaluationCase) -> str:
        """Simulate a RAG pipeline response.

        In production, this would:
        1. Retrieve relevant documents
        2. Pass to LLM with context
        3. Return generated answer
        """
        question = case.input.get("question", "")
        context = case.retrieval_context

        # Simulated LLM response based on context
        responses = {
            "Who created Python?": "Python was created by Guido van Rossum. "
            "It was first released in 1991.",
            "What are the key features of Python?": "Python is known for its simple "
            "and readable syntax. It supports multiple programming paradigms including "
            "procedural, object-oriented, and functional programming.",
            "Can Python be used for machine learning?": "Yes, Python is widely used for "
            "machine learning. Popular libraries like TensorFlow and PyTorch are "
            "available for Python.",
        }

        return responses.get(question, f"Based on the retrieved context: {context[0][:50]}...")

    # Step 5: Run evaluation
    print("\n--- Running RAGAS Evaluation ---")

    result = run_evaluation_sync(
        eval_set,
        output_generator=rag_pipeline,
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

    print("\n--- Per-Case Analysis ---")
    for i, case_result in enumerate(result.results):
        case = eval_set.cases[i]
        status = "PASS" if case_result.passed else "FAIL"
        print(f"\n[{status}] {case.name}")
        print(f"  Question: {case.input.get('question')}")
        print(f"  Context docs: {len(case.retrieval_context)}")

        if case_result.scores:
            print("  RAGAS Scores:")
            for score in case_result.scores:
                bar = "#" * int(score.score * 10) + "-" * (10 - int(score.score * 10))
                status_icon = "PASS" if score.passed else "FAIL"
                print(f"    {score.metric_name:20s} [{bar}] {score.score:.2f} {status_icon}")

    # Cleanup
    Path(db_path).unlink(missing_ok=True)

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nRAGAS Metrics Explained:")
    print("  - context_precision: Are relevant docs ranked first?")
    print("  - context_recall: Were all needed docs retrieved?")
    print("  - faithfulness: Is answer grounded in context?")
    print("  - answer_relevancy: Does answer address the question?")
    print("\nTo use RAGAS:")
    print("  1. pip install ragas datasets")
    print("  2. export OPENAI_API_KEY=your-key")
    print("  3. Re-run this example")
    print("\nNext steps:")
    print("- Try 05_llm_judge.py for custom LLM-as-judge evaluation")


if __name__ == "__main__":
    main()
