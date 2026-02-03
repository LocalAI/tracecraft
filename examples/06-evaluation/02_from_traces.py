#!/usr/bin/env python3
"""Evaluation from Traces - Create evaluation sets from existing traces.

This example demonstrates how to:
1. Capture traces from LLM operations
2. Create evaluation cases from those traces
3. Run evaluations against the captured data

This is useful for:
- Creating golden datasets from production traffic
- Regression testing after model/prompt changes
- Quality monitoring of real-world interactions

Prerequisites:
    - TraceCraft installed (pip install tracecraft)

Environment Variables:
    - None required

External Services:
    - None required

Usage:
    python examples/06-evaluation/02_from_traces.py

Expected Output:
    - Traces captured from simulated LLM calls
    - Evaluation set created from those traces
    - Evaluation results comparing outputs
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
from tracecraft.instrumentation.decorators import trace_llm
from tracecraft.storage.sqlite import SQLiteTraceStore


def main() -> None:
    """Run the from-traces evaluation example."""
    print("=" * 60)
    print("TraceCraft Evaluation from Traces Example")
    print("=" * 60)

    # Step 1: Initialize TraceCraft with SQLite storage
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    runtime = tracecraft.init(
        storage=db_path,  # .db extension auto-selects SQLite storage
        console=True,
    )

    print(f"\nUsing temporary database: {db_path}")

    # Step 2: Capture some traces (simulating production traffic)
    print("\n--- Capturing Traces ---")

    @trace_llm(name="qa_bot", model="gpt-4o-mini")
    def qa_bot(question: str) -> str:
        """Simulated Q&A bot that answers questions."""
        # In reality, this would call an LLM
        answers = {
            "What is Python?": "Python is a high-level programming language.",
            "What is the capital of France?": "The capital of France is Paris.",
            "What is 2+2?": "2+2 equals 4.",
        }
        return answers.get(question, "I don't know the answer.")

    # Capture some interactions
    captured_questions = [
        "What is Python?",
        "What is the capital of France?",
        "What is 2+2?",
    ]

    trace_ids = []
    for question in captured_questions:
        with runtime.run(f"qa_session_{question[:10]}") as run:
            response = qa_bot(question)
            print(f"  Q: {question}")
            print(f"  A: {response}")
            trace_ids.append(str(run.id))

    print(f"\nCaptured {len(trace_ids)} traces")

    # Step 3: Create evaluation cases from traces
    print("\n--- Creating Evaluation Set from Traces ---")

    store = SQLiteTraceStore(db_path)

    # Create an evaluation set
    set_id = store.create_evaluation_set(
        name="qa-bot-golden-set",
        description="Golden dataset from production Q&A interactions",
        metrics=[
            {
                "name": "contains_answer",
                "framework": "builtin",
                "metric_type": "contains",
                "threshold": 1.0,
            },
        ],
        pass_rate_threshold=0.9,
    )

    print(f"Created evaluation set: qa-bot-golden-set (ID: {set_id})")

    # Create cases from captured traces
    expected_answers = {
        "What is Python?": "programming language",
        "What is the capital of France?": "Paris",
        "What is 2+2?": "4",
    }

    case_ids = []
    for i, (question, expected) in enumerate(expected_answers.items()):
        case_id = store.add_evaluation_case(
            set_id=set_id,
            name=f"qa-case-{i + 1}",
            input_data={"question": question},
            expected_output={"answer": expected},
            # Link to original trace
            source_trace_id=trace_ids[i] if i < len(trace_ids) else None,
        )
        case_ids.append(case_id)
        print(f"  Created case: qa-case-{i + 1}")

    # Step 4: Load the evaluation set for running
    print("\n--- Running Evaluation ---")

    # Build the EvaluationSet model from stored data
    stored_set = store.get_evaluation_set(set_id)
    stored_cases = store.get_evaluation_cases(set_id)

    eval_set = EvaluationSet(
        id=set_id,
        name=stored_set["name"],
        description=stored_set.get("description"),
        metrics=[
            EvaluationMetricConfig(
                name="contains_answer",
                framework=MetricFramework.BUILTIN,
                metric_type="contains",
                threshold=1.0,
            ),
        ],
        pass_rate_threshold=stored_set.get("pass_rate_threshold", 0.8),
        cases=[
            EvaluationCase(
                id=case["id"],
                name=case["name"],
                input=case["input"],
                expected_output=case.get("expected_output"),
            )
            for case in stored_cases
        ],
    )

    # Define an output generator using our Q&A bot
    def generate_output(case: EvaluationCase) -> str:
        """Generate output using the Q&A bot."""
        question = case.input.get("question", "")
        return qa_bot(question)

    # Run evaluation
    result = run_evaluation_sync(
        eval_set,
        output_generator=generate_output,
        store=store,
    )

    # Step 5: View results
    print("\n--- Evaluation Results ---")
    print(f"Status: {result.status.value}")
    print(f"Total cases: {result.total_cases}")
    print(f"Passed: {result.passed_cases}")
    print(f"Failed: {result.failed_cases}")
    print(f"Pass rate: {result.pass_rate:.1%}")
    print(f"Overall passed: {'YES' if result.overall_passed else 'NO'}")

    # Step 6: Check stored results
    print("\n--- Stored Results ---")
    runs = store.list_evaluation_runs(set_id=set_id)
    print(f"Total runs stored: {len(runs)}")
    for run in runs:
        print(f"  Run {run['id'][:8]}...")
        print(f"    Status: {run['status']}")
        print(f"    Passed: {run.get('passed_cases', 0)} / {run.get('total_cases', 0)}")

    # Cleanup
    Path(db_path).unlink(missing_ok=True)

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nWhat just happened:")
    print("1. Captured traces from simulated Q&A interactions")
    print("2. Created an evaluation set from those traces")
    print("3. Linked test cases to original trace IDs")
    print("4. Ran evaluation and stored results")
    print("\nUse cases:")
    print("- Create golden datasets from high-quality production interactions")
    print("- Test regressions when changing models or prompts")
    print("- Monitor quality over time with historical comparisons")
    print("\nNext steps:")
    print("- Try 03_deepeval_metrics.py for advanced LLM evaluation")


if __name__ == "__main__":
    main()
