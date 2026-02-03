#!/usr/bin/env python3
"""
Processor Pipeline Example

Demonstrates the processor pipeline including:
- SAFETY vs EFFICIENCY ordering
- Custom processor injection
- Redaction, sampling, and enrichment processors
- Performance considerations

Run: python examples/04-production/processors/01_processor_pipeline.py
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from tracecraft.core.config import (
    ProcessorOrder,
    RedactionConfig,
    SamplingConfig,
    TraceCraftConfig,
)
from tracecraft.core.models import AgentRun, Step, StepType
from tracecraft.core.runtime import TALRuntime

# =============================================================================
# Helper: Create sample run with PII
# =============================================================================


def create_sample_run(include_pii: bool = True, include_error: bool = False) -> AgentRun:
    """Create a sample run for testing processors."""
    run_id = uuid4()

    # Create step with or without PII
    if include_pii:
        step_inputs = {
            "prompt": "Contact me at user@example.com or call 555-123-4567",
            "user_email": "user@example.com",
        }
        step_outputs = {"response": "Email sent to user@example.com"}
    else:
        step_inputs = {"prompt": "Hello, how are you?"}
        step_outputs = {"response": "I'm doing well!"}

    step = Step(
        trace_id=run_id,
        type=StepType.LLM,
        name="llm_call",
        start_time=datetime.now(UTC),
        inputs=step_inputs,
        outputs=step_outputs,
        model_name="gpt-4",
    )

    if include_error:
        step.error = "API rate limit exceeded"
        step.error_type = "RateLimitError"

    # Finalize step
    step.end_time = datetime.now(UTC)
    step.duration_ms = 100.0

    run = AgentRun(
        id=run_id,
        name="sample_run",
        start_time=datetime.now(UTC),
        steps=[step],
        error_count=1 if include_error else 0,
    )
    run.end_time = datetime.now(UTC)
    run.duration_ms = 150.0

    return run


# =============================================================================
# Demo 1: SAFETY vs EFFICIENCY Ordering
# =============================================================================


def demo_processor_ordering():
    """Demonstrate SAFETY vs EFFICIENCY processor ordering."""
    print("\n" + "=" * 60)
    print("Demo 1: SAFETY vs EFFICIENCY Processor Ordering")
    print("=" * 60)

    # SAFETY order (default)
    print("\n--- SAFETY Order (Default) ---")
    print("Pipeline: Enrichment -> Redaction -> Sampling")
    print("Use case: Compliance-sensitive environments")
    print("Benefit: PII is always redacted before sampling decision")

    safety_config = TraceCraftConfig(
        processor_order=ProcessorOrder.SAFETY,
        redaction=RedactionConfig(enabled=True),
        sampling=SamplingConfig(rate=0.5),
        console_enabled=False,
        jsonl_enabled=False,
    )

    safety_runtime = TALRuntime(console=False, jsonl=False, config=safety_config)
    print(f"Processor names: {[p.name for p in safety_runtime._processors]}")

    # EFFICIENCY order
    print("\n--- EFFICIENCY Order ---")
    print("Pipeline: Sampling -> Redaction -> Enrichment")
    print("Use case: High-throughput, cost-sensitive environments")
    print("Benefit: Samples first to reduce processing overhead")

    efficiency_config = TraceCraftConfig(
        processor_order=ProcessorOrder.EFFICIENCY,
        redaction=RedactionConfig(enabled=True),
        sampling=SamplingConfig(rate=0.5),
        console_enabled=False,
        jsonl_enabled=False,
    )

    efficiency_runtime = TALRuntime(console=False, jsonl=False, config=efficiency_config)
    print(f"Processor names: {[p.name for p in efficiency_runtime._processors]}")


# =============================================================================
# Demo 2: Redaction Processor in Action
# =============================================================================


def demo_redaction_processor():
    """Demonstrate the redaction processor."""
    print("\n" + "=" * 60)
    print("Demo 2: Redaction Processor")
    print("=" * 60)

    from tracecraft.processors.base import RedactionProcessorAdapter
    from tracecraft.processors.redaction import RedactionProcessor

    # Create redaction processor
    processor = RedactionProcessor()
    adapter = RedactionProcessorAdapter(processor)

    # Create run with PII
    run = create_sample_run(include_pii=True)

    print("\n--- Before Redaction ---")
    print(f"Step inputs: {run.steps[0].inputs}")
    print(f"Step outputs: {run.steps[0].outputs}")

    # Process the run
    processed_run = adapter.process(run)

    print("\n--- After Redaction ---")
    print(f"Step inputs: {processed_run.steps[0].inputs}")
    print(f"Step outputs: {processed_run.steps[0].outputs}")

    # Original run is unchanged
    print("\n--- Original Run (Unchanged) ---")
    print(f"Step inputs: {run.steps[0].inputs}")


# =============================================================================
# Demo 3: Sampling Processor in Action
# =============================================================================


def demo_sampling_processor():
    """Demonstrate the sampling processor."""
    print("\n" + "=" * 60)
    print("Demo 3: Sampling Processor")
    print("=" * 60)

    from tracecraft.processors.base import SamplingProcessorAdapter
    from tracecraft.processors.sampling import SamplingProcessor

    # Scenario 1: Drop at 0% rate
    print("\n--- Scenario: 0% Sampling Rate ---")
    processor = SamplingProcessor(default_rate=0.0)
    adapter = SamplingProcessorAdapter(processor)

    run = create_sample_run(include_pii=False)
    result = adapter.process(run)
    print(f"Run kept: {result is not None}")

    # Scenario 2: Keep at 100% rate
    print("\n--- Scenario: 100% Sampling Rate ---")
    processor = SamplingProcessor(default_rate=1.0)
    adapter = SamplingProcessorAdapter(processor)

    run = create_sample_run(include_pii=False)
    result = adapter.process(run)
    print(f"Run kept: {result is not None}")
    if result:
        print(f"should_export: {result.should_export}")

    # Scenario 3: Always keep errors
    print("\n--- Scenario: 0% Rate, but Keep Errors ---")
    processor = SamplingProcessor(default_rate=0.0, always_keep_errors=True)
    adapter = SamplingProcessorAdapter(processor)

    run = create_sample_run(include_pii=False, include_error=True)
    result = adapter.process(run)
    print(f"Run with error kept: {result is not None}")
    if result:
        print(f"Sample reason: {result.sample_reason}")


# =============================================================================
# Demo 4: Enrichment Processor in Action
# =============================================================================


def demo_enrichment_processor():
    """Demonstrate the token enrichment processor."""
    print("\n" + "=" * 60)
    print("Demo 4: Enrichment Processor (Token Counting)")
    print("=" * 60)

    from tracecraft.processors.base import EnrichmentProcessorAdapter
    from tracecraft.processors.enrichment import TokenEnrichmentProcessor

    # Create enrichment processor
    processor = TokenEnrichmentProcessor()
    adapter = EnrichmentProcessorAdapter(processor)

    # Create run with LLM step
    run = create_sample_run(include_pii=False)

    print("\n--- Before Enrichment ---")
    print(f"Input tokens: {run.steps[0].input_tokens}")
    print(f"Output tokens: {run.steps[0].output_tokens}")

    # Process the run
    processed_run = adapter.process(run)

    print("\n--- After Enrichment ---")
    print(f"Input tokens: {processed_run.steps[0].input_tokens}")
    print(f"Output tokens: {processed_run.steps[0].output_tokens}")


# =============================================================================
# Demo 5: Full Pipeline Processing
# =============================================================================


def demo_full_pipeline():
    """Demonstrate full pipeline processing."""
    print("\n" + "=" * 60)
    print("Demo 5: Full Pipeline Processing")
    print("=" * 60)

    # Create runtime with all processors
    config = TraceCraftConfig(
        processor_order=ProcessorOrder.SAFETY,
        redaction=RedactionConfig(enabled=True),
        sampling=SamplingConfig(rate=1.0),  # Keep all for demo
        console_enabled=False,
        jsonl_enabled=False,
    )

    # Track what's exported
    exported_runs: list[AgentRun] = []
    mock_exporter = MagicMock()
    mock_exporter.export.side_effect = lambda run: exported_runs.append(run)

    runtime = TALRuntime(
        console=False,
        jsonl=False,
        config=config,
        exporters=[mock_exporter],
    )

    print(f"\nProcessor pipeline: {[p.name for p in runtime._processors]}")

    # Create run with PII
    run = create_sample_run(include_pii=True)

    print("\n--- Original Run ---")
    print(f"Inputs: {run.steps[0].inputs}")

    # Export (processes through pipeline)
    runtime.export(run)

    print("\n--- After Pipeline Processing ---")
    if exported_runs:
        print(f"Inputs (redacted): {exported_runs[0].steps[0].inputs}")
        print(f"Input tokens (enriched): {exported_runs[0].steps[0].input_tokens}")


# =============================================================================
# Demo 6: Performance Comparison
# =============================================================================


def demo_performance_comparison():
    """Compare performance of SAFETY vs EFFICIENCY ordering."""
    print("\n" + "=" * 60)
    print("Demo 6: Performance Comparison")
    print("=" * 60)

    n_runs = 100

    # Create runs
    runs = [create_sample_run(include_pii=True) for _ in range(n_runs)]

    # SAFETY mode
    safety_config = TraceCraftConfig(
        processor_order=ProcessorOrder.SAFETY,
        redaction=RedactionConfig(enabled=True),
        sampling=SamplingConfig(rate=0.1),  # Drop 90%
        console_enabled=False,
        jsonl_enabled=False,
    )

    mock_exporter = MagicMock()
    safety_runtime = TALRuntime(
        console=False, jsonl=False, config=safety_config, exporters=[mock_exporter]
    )

    start = time.perf_counter()
    for run in runs:
        safety_runtime.export(run)
    safety_time = time.perf_counter() - start
    safety_exports = mock_exporter.export.call_count

    # EFFICIENCY mode
    efficiency_config = TraceCraftConfig(
        processor_order=ProcessorOrder.EFFICIENCY,
        redaction=RedactionConfig(enabled=True),
        sampling=SamplingConfig(rate=0.1),  # Drop 90%
        console_enabled=False,
        jsonl_enabled=False,
    )

    mock_exporter2 = MagicMock()
    efficiency_runtime = TALRuntime(
        console=False, jsonl=False, config=efficiency_config, exporters=[mock_exporter2]
    )

    # Recreate runs for fair comparison
    runs = [create_sample_run(include_pii=True) for _ in range(n_runs)]

    start = time.perf_counter()
    for run in runs:
        efficiency_runtime.export(run)
    efficiency_time = time.perf_counter() - start
    efficiency_exports = mock_exporter2.export.call_count

    print(f"\n--- Results for {n_runs} runs with 10% sampling ---")
    print("\nSAFETY Mode:")
    print(f"  Time: {safety_time * 1000:.2f} ms")
    print(f"  Exported: {safety_exports} runs")
    print(f"  Note: All {n_runs} runs processed through enrichment and redaction")

    print("\nEFFICIENCY Mode:")
    print(f"  Time: {efficiency_time * 1000:.2f} ms")
    print(f"  Exported: {efficiency_exports} runs")
    print(f"  Note: Only ~{n_runs * 0.1:.0f} runs processed through enrichment and redaction")

    if efficiency_time < safety_time:
        improvement = (safety_time - efficiency_time) / safety_time * 100
        print(f"\nEFFICIENCY mode was {improvement:.1f}% faster")
    else:
        print("\nNote: Results may vary with small sample sizes")


# =============================================================================
# Main
# =============================================================================


def main():
    """Run all processor pipeline demos."""
    print("\n" + "#" * 60)
    print("# TraceCraft Processor Pipeline Examples")
    print("#" * 60)

    demo_processor_ordering()
    demo_redaction_processor()
    demo_sampling_processor()
    demo_enrichment_processor()
    demo_full_pipeline()
    demo_performance_comparison()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
