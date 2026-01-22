# 06 - Evaluation

> **Status: Coming Soon** - This section is planned but examples are not yet implemented.
> See the DeepEval and RAGAS documentation for integration patterns.

Integrate AgentTrace with evaluation frameworks for quality assurance.

## Overview

AgentTrace integrates with popular evaluation frameworks:

- **DeepEval** - LLM evaluation metrics
- **RAGAS** - RAG-specific evaluation
- **MLflow** - LLM judges and experiment tracking

## Examples

| # | Example | Description |
|---|---------|-------------|
| 1 | `01_deepeval_basic.py` | Convert traces to test cases |
| 2 | `02_deepeval_metrics.py` | Faithfulness, relevancy, etc. |
| 3 | `03_ragas_evaluation.py` | RAG-specific metrics |
| 4 | `04_mlflow_judges.py` | MLflow LLM judges |
| 5 | `05_golden_datasets.py` | Creating test datasets from traces |

## Prerequisites

```bash
# DeepEval
pip install deepeval

# RAGAS
pip install ragas datasets

# MLflow
pip install mlflow
```

## DeepEval Integration

### Convert Traces to Test Cases

```python
from agenttrace.integrations.deepeval import traces_to_test_cases

test_cases = traces_to_test_cases(
    "traces/agenttrace.jsonl",
    filter_fn=lambda step: step.type.value == "llm",
)
```

### Run Evaluation

```python
from agenttrace.integrations.deepeval import evaluate_traces

results = evaluate_traces(
    "traces/agenttrace.jsonl",
    metrics=["faithfulness", "answer_relevancy"],
)
print(f"Pass rate: {results.pass_rate}")
```

### Available Metrics

- `faithfulness` - Is the output faithful to the input?
- `answer_relevancy` - Is the answer relevant to the question?
- `contextual_precision` - Are relevant chunks ranked higher?
- `contextual_recall` - Are all relevant chunks retrieved?
- `hallucination` - Does the output contain hallucinations?

## RAGAS for RAG Evaluation

```python
from agenttrace.integrations.ragas import evaluate_rag_traces

results = evaluate_rag_traces(
    "traces/agenttrace.jsonl",
    metrics=["context_precision", "context_recall", "faithfulness"],
)
```

### RAGAS Metrics

- `context_precision` - Relevant chunks in top results
- `context_recall` - All relevant info retrieved
- `faithfulness` - Answer grounded in context
- `answer_relevancy` - Answer addresses the question

## MLflow LLM Judges

```python
from agenttrace.integrations.mlflow import evaluate_with_judges

results = evaluate_with_judges(
    traces="traces/agenttrace.jsonl",
    judges=["relevance", "faithfulness"],
)
```

## Golden Datasets

Create test datasets from production traces:

```python
from agenttrace.integrations.datasets import (
    create_golden_dataset,
    filter_high_quality_traces,
)

# Filter high-quality traces
good_traces = filter_high_quality_traces(
    "traces/agenttrace.jsonl",
    min_faithfulness=0.9,
    max_latency_ms=5000,
)

# Create golden dataset
dataset = create_golden_dataset(good_traces)
dataset.save("golden_dataset.jsonl")
```

## Continuous Evaluation

Run evaluation in CI/CD:

```python
from agenttrace.integrations.deepeval import evaluate_traces

results = evaluate_traces("traces/ci_traces.jsonl")

if results.pass_rate < 0.95:
    print(f"Quality gate failed: {results.pass_rate:.1%}")
    sys.exit(1)
```

## Quality Thresholds

Combine with alerting:

```python
from agenttrace.alerting import QualityScoreProcessor, QualityThreshold

monitor = QualityScoreProcessor(
    thresholds=[
        QualityThreshold(
            metric="faithfulness",
            min_value=0.8,
            window_size=100,
        ),
    ],
)
```

## Next Steps

- [05-alerting/](../05-alerting/) - Alert on quality degradation
- [08-real-world/](../08-real-world/) - See evaluation in complete apps
