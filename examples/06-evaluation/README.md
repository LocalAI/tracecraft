# 06 - Evaluation

Integrate TraceCraft with evaluation frameworks for quality assurance of LLM outputs.

## Overview

TraceCraft provides a comprehensive evaluation system that supports:

- **Built-in Metrics** - Exact match, contains, regex, length checks, JSON validation
- **DeepEval Integration** - Faithfulness, answer relevancy, hallucination detection
- **RAGAS Integration** - Context precision, context recall, RAG-specific metrics
- **MLflow Integration** - LLM judges and experiment tracking
- **LLM-as-Judge** - Custom evaluation criteria using LLMs

## Examples

| # | Example | Description |
|---|---------|-------------|
| 1 | [`01_basic_eval.py`](01_basic_eval.py) | Create evaluation sets, add cases, run evaluations |
| 2 | [`02_from_traces.py`](02_from_traces.py) | Create evaluation sets from existing traces |
| 3 | [`03_deepeval_metrics.py`](03_deepeval_metrics.py) | Using DeepEval metrics (faithfulness, relevancy) |
| 4 | [`04_ragas_rag.py`](04_ragas_rag.py) | RAG-specific evaluation with RAGAS |
| 5 | [`05_llm_judge.py`](05_llm_judge.py) | LLM-as-judge for custom evaluation criteria |
| 6 | [`06_ci_integration.py`](06_ci_integration.py) | Running evaluations in CI/CD pipelines |

## Prerequisites

```bash
# Core (included with TraceCraft)
pip install tracecraft

# DeepEval (optional)
pip install deepeval

# RAGAS (optional)
pip install ragas datasets

# MLflow (optional)
pip install mlflow
```

## Quick Start

### Basic Evaluation

```python
from tracecraft.evaluation import (
    EvaluationCase,
    EvaluationMetricConfig,
    EvaluationSet,
    MetricFramework,
    run_evaluation_sync,
)

# Create evaluation set
eval_set = EvaluationSet(
    name="my-eval",
    metrics=[
        EvaluationMetricConfig(
            name="exact_match",
            framework=MetricFramework.BUILTIN,
            metric_type="exact_match",
            threshold=1.0,
        ),
    ],
    cases=[
        EvaluationCase(
            name="test-1",
            input={"question": "What is 2+2?"},
            expected_output={"answer": "4"},
        ),
    ],
)

# Define output generator
def my_llm(case):
    return "4"  # Your LLM call here

# Run evaluation
result = run_evaluation_sync(eval_set, output_generator=my_llm)
print(f"Pass rate: {result.pass_rate:.1%}")
```

### Available Built-in Metrics

| Metric | Description | Parameters |
|--------|-------------|------------|
| `exact_match` | Output matches expected exactly | - |
| `contains` | Output contains expected text | `text` (optional) |
| `not_contains` | Output does not contain text | `text` |
| `regex_match` | Output matches regex pattern | `pattern` |
| `json_valid` | Output is valid JSON | - |
| `length_check` | Output within length bounds | `min_length`, `max_length` |
| `llm_judge` | LLM evaluates output | `criteria`, `model` |

### DeepEval Metrics

```python
EvaluationMetricConfig(
    name="faithfulness",
    framework=MetricFramework.DEEPEVAL,
    metric_type="faithfulness",
    threshold=0.7,
)
```

Available types: `faithfulness`, `answer_relevancy`, `hallucination`, `bias`, `toxicity`

### RAGAS Metrics

```python
EvaluationMetricConfig(
    name="context_precision",
    framework=MetricFramework.RAGAS,
    metric_type="context_precision",
    threshold=0.7,
)
```

Available types: `context_precision`, `context_recall`, `faithfulness`, `answer_relevancy`

## CLI Commands

```bash
# List evaluation sets
tracecraft eval list traces.db

# Create evaluation set
tracecraft eval create traces.db --name "my-eval" --metric "exact_match:builtin:1.0"

# Add test case
tracecraft eval add-case traces.db --set "my-eval" \
  --name "test-1" \
  --input '{"question": "What is 2+2?"}' \
  --expected '{"answer": "4"}'

# Run evaluation
tracecraft eval run traces.db my-eval --verbose

# View results
tracecraft eval results traces.db --run-id abc123

# Export evaluation set
tracecraft eval export traces.db my-eval --format json
```

## CI/CD Integration

```bash
# Set pass rate threshold
export TRACECRAFT_EVAL_THRESHOLD=0.9

# Run evaluation (exits 1 on failure)
python -m examples.06-evaluation.06_ci_integration

# Or use CLI
tracecraft eval run traces.db my-eval && echo "Passed" || echo "Failed"
```

### GitHub Actions Example

```yaml
- name: Run Evaluations
  run: |
    python -m tracecraft eval run traces.db quality-gate
  env:
    TRACECRAFT_EVAL_THRESHOLD: '0.9'
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

## Creating Golden Datasets

Create test cases from production traces:

```python
from tracecraft.storage.sqlite import SQLiteTraceStore

store = SQLiteTraceStore("traces.db")

# Create evaluation set
set_id = store.create_evaluation_set(
    name="golden-dataset",
    description="High-quality production samples",
)

# Add case from existing trace
store.create_case_from_trace(
    set_id=set_id,
    trace_id="abc123",
    name="production-case-1",
)
```

## Evaluation Results Storage

All evaluation runs are persisted for:

- Historical comparison
- Regression detection
- Quality dashboards
- Trend analysis

```python
# Get evaluation history
runs = store.list_evaluation_runs(set_id="my-eval-id")
for run in runs:
    print(f"Run {run['id']}: {run['overall_pass_rate']:.1%}")

# Get detailed results
results = store.get_evaluation_results(run_id="abc123")
```

## Next Steps

- [05-alerting/](../05-alerting/) - Alert on quality degradation
- [08-real-world/](../08-real-world/) - See evaluation in complete apps
