#!/usr/bin/env python3
"""
Async Context Propagation Example

Demonstrates advanced async context propagation including:
- gather_with_context for parallel tasks
- create_task_with_context for background tasks
- run_in_executor_with_context for thread pool operations
- capture_context/restore_context for manual propagation
- TraceContext dataclass for full context capture

Run: python examples/09-advanced/06_async_context.py
"""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from tracecraft import TraceCraftRuntime, trace_agent, trace_tool
from tracecraft.contrib.async_helpers import (
    TraceContext,
    capture_context,
    create_task_with_context,
    gather_with_context,
    restore_context,
    run_in_executor_with_context,
)
from tracecraft.core.context import get_current_run, get_current_runtime

# =============================================================================
# Demo 1: TraceContext Dataclass
# =============================================================================


def demo_trace_context_dataclass():
    """Demonstrate the TraceContext dataclass."""
    print("\n" + "=" * 60)
    print("Demo 1: TraceContext Dataclass")
    print("=" * 60)

    runtime = TraceCraftRuntime(console=False, jsonl=False)

    print("\n--- Empty Context ---")
    ctx_empty = capture_context()
    print(f"TraceContext: {ctx_empty}")
    print(f"is_empty(): {ctx_empty.is_empty()}")

    print("\n--- Context with Runtime ---")
    with runtime.trace_context():
        ctx_runtime = capture_context()
        print(f"TraceContext: {ctx_runtime}")
        print(f"is_empty(): {ctx_runtime.is_empty()}")
        print(f"Has runtime: {ctx_runtime.runtime is not None}")

        with runtime.run("test_run") as run:
            ctx_full = capture_context()
            print("\n--- Context with Runtime + Run ---")
            print(f"TraceContext: {ctx_full}")
            print(f"Has runtime: {ctx_full.runtime is not None}")
            print(f"Has run: {ctx_full.run is not None}")


# =============================================================================
# Demo 2: gather_with_context
# =============================================================================


def demo_gather_with_context():
    """Demonstrate gather_with_context for parallel tasks."""
    print("\n" + "=" * 60)
    print("Demo 2: gather_with_context")
    print("=" * 60)

    runtime = TraceCraftRuntime(console=False, jsonl=False)

    async def task_1() -> dict[str, Any]:
        """First parallel task."""
        await asyncio.sleep(0.01)
        return {
            "task": "task_1",
            "has_run": get_current_run() is not None,
            "has_runtime": get_current_runtime() is not None,
        }

    async def task_2() -> dict[str, Any]:
        """Second parallel task."""
        await asyncio.sleep(0.01)
        return {
            "task": "task_2",
            "has_run": get_current_run() is not None,
            "has_runtime": get_current_runtime() is not None,
        }

    async def task_3() -> dict[str, Any]:
        """Third parallel task."""
        await asyncio.sleep(0.01)
        return {
            "task": "task_3",
            "has_run": get_current_run() is not None,
            "has_runtime": get_current_runtime() is not None,
        }

    async def run_demo():
        with runtime.trace_context():
            with runtime.run("parallel_demo"):
                print("\n--- Without gather_with_context (context lost) ---")
                results_plain = await asyncio.gather(task_1(), task_2(), task_3())
                for r in results_plain:
                    print(f"  {r['task']}: has_run={r['has_run']}, has_runtime={r['has_runtime']}")

                print("\n--- With gather_with_context (context preserved) ---")
                results_with_ctx = await gather_with_context(task_1(), task_2(), task_3())
                for r in results_with_ctx:
                    print(f"  {r['task']}: has_run={r['has_run']}, has_runtime={r['has_runtime']}")

    asyncio.run(run_demo())


# =============================================================================
# Demo 3: create_task_with_context
# =============================================================================


def demo_create_task_with_context():
    """Demonstrate create_task_with_context for background tasks."""
    print("\n" + "=" * 60)
    print("Demo 3: create_task_with_context")
    print("=" * 60)

    runtime = TraceCraftRuntime(console=False, jsonl=False)
    results: list[dict[str, Any]] = []

    async def background_task(task_id: int) -> None:
        """Background task that needs trace context."""
        await asyncio.sleep(0.01)
        results.append(
            {
                "task_id": task_id,
                "has_run": get_current_run() is not None,
                "has_runtime": get_current_runtime() is not None,
            }
        )

    async def run_demo():
        with runtime.trace_context():
            with runtime.run("background_demo"):
                print("\n--- Creating background tasks ---")

                # Plain asyncio.create_task loses context
                task_plain = asyncio.create_task(background_task(1))

                # create_task_with_context preserves context
                task_with_ctx = create_task_with_context(background_task(2), name="traced_task")

                # Wait for both
                await task_plain
                await task_with_ctx

        print("\n--- Results ---")
        for r in sorted(results, key=lambda x: x["task_id"]):
            method = "plain" if r["task_id"] == 1 else "with_context"
            print(
                f"  Task {r['task_id']} ({method}): has_run={r['has_run']}, has_runtime={r['has_runtime']}"
            )

    asyncio.run(run_demo())


# =============================================================================
# Demo 4: run_in_executor_with_context
# =============================================================================


def demo_run_in_executor_with_context():
    """Demonstrate run_in_executor_with_context for thread pool operations."""
    print("\n" + "=" * 60)
    print("Demo 4: run_in_executor_with_context")
    print("=" * 60)

    runtime = TraceCraftRuntime(console=False, jsonl=False)

    def cpu_intensive_work(data: str) -> dict[str, Any]:
        """CPU-bound work that runs in thread pool."""
        # Simulate CPU work
        time.sleep(0.01)
        return {
            "data": data,
            "processed": True,
            "has_run": get_current_run() is not None,
            "has_runtime": get_current_runtime() is not None,
        }

    async def run_demo():
        with runtime.trace_context():
            with runtime.run("executor_demo"):
                print("\n--- Running CPU work in executor ---")

                # With context propagation
                result = await run_in_executor_with_context(
                    cpu_intensive_work,
                    "test_data",
                )

                print(f"Result: {result}")

                # With custom executor
                print("\n--- Using custom thread pool ---")
                with ThreadPoolExecutor(max_workers=2) as executor:
                    result2 = await run_in_executor_with_context(
                        cpu_intensive_work,
                        "custom_executor_data",
                        executor=executor,
                    )
                    print(f"Result with custom executor: {result2}")

    asyncio.run(run_demo())


# =============================================================================
# Demo 5: Manual capture_context / restore_context
# =============================================================================


def demo_manual_context_propagation():
    """Demonstrate manual context capture and restoration."""
    print("\n" + "=" * 60)
    print("Demo 5: Manual capture_context / restore_context")
    print("=" * 60)

    runtime = TraceCraftRuntime(console=False, jsonl=False)

    async def run_demo():
        with runtime.trace_context():
            with runtime.run("manual_context_demo"):
                print("\n--- Capturing context ---")
                ctx = capture_context()
                print(f"Captured: {ctx}")

                # Simulate passing context to another system
                async def remote_callback(trace_ctx: TraceContext) -> dict[str, Any]:
                    """Simulates a callback that receives context."""
                    # Without restore_context
                    plain_result = {
                        "has_run": get_current_run() is not None,
                        "has_runtime": get_current_runtime() is not None,
                    }

                    # With restore_context
                    with restore_context(trace_ctx):
                        restored_result = {
                            "has_run": get_current_run() is not None,
                            "has_runtime": get_current_runtime() is not None,
                        }

                    return {
                        "without_restore": plain_result,
                        "with_restore": restored_result,
                    }

                # Later, in a callback
                print("\n--- Restoring context in callback ---")
                result = await remote_callback(ctx)
                print(f"Without restore_context: {result['without_restore']}")
                print(f"With restore_context: {result['with_restore']}")

    asyncio.run(run_demo())


# =============================================================================
# Demo 6: Complex Nested Async Patterns
# =============================================================================


def demo_complex_nested_patterns():
    """Demonstrate context propagation in complex nested patterns."""
    print("\n" + "=" * 60)
    print("Demo 6: Complex Nested Async Patterns")
    print("=" * 60)

    runtime = TraceCraftRuntime(console=True, jsonl=False)

    @trace_agent(name="coordinator")
    async def coordinator() -> list[str]:
        """Coordinator that spawns parallel workers."""
        # Spawn workers in parallel
        results = await gather_with_context(
            worker("task-a"),
            worker("task-b"),
            worker("task-c"),
        )
        return results

    @trace_tool(name="worker")
    async def worker(task_id: str) -> str:
        """Worker that processes a task."""
        await asyncio.sleep(0.01)

        # Worker can spawn sub-tasks
        if task_id == "task-b":
            sub_results = await gather_with_context(
                sub_task(f"{task_id}-1"),
                sub_task(f"{task_id}-2"),
            )
            return f"Worker {task_id} completed with subtasks: {sub_results}"

        return f"Worker {task_id} completed"

    @trace_tool(name="sub_task")
    async def sub_task(sub_id: str) -> str:
        """Sub-task spawned by a worker."""
        await asyncio.sleep(0.005)
        return f"Sub-task {sub_id} done"

    async def run_demo():
        print("\n--- Running complex nested workflow ---")
        with runtime.trace_context():
            with runtime.run("nested_workflow"):
                results = await coordinator()

        print("\n--- Results ---")
        for r in results:
            print(f"  {r}")

    asyncio.run(run_demo())


# =============================================================================
# Demo 7: Fan-out / Fan-in Pattern
# =============================================================================


def demo_fan_out_fan_in():
    """Demonstrate fan-out / fan-in pattern with context preservation."""
    print("\n" + "=" * 60)
    print("Demo 7: Fan-out / Fan-in Pattern")
    print("=" * 60)

    runtime = TraceCraftRuntime(console=False, jsonl=False)

    @trace_tool(name="fetch_chunk")
    async def fetch_chunk(chunk_id: int) -> dict[str, Any]:
        """Fetch a data chunk."""
        await asyncio.sleep(0.01 * chunk_id)  # Variable delay
        return {"chunk_id": chunk_id, "data": f"chunk_{chunk_id}_data"}

    @trace_tool(name="process_chunk")
    async def process_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
        """Process a data chunk."""
        await asyncio.sleep(0.005)
        return {**chunk, "processed": True}

    @trace_agent(name="aggregator")
    async def aggregate_results(results: list[dict[str, Any]]) -> dict[str, Any]:
        """Aggregate all processed chunks."""
        return {
            "total_chunks": len(results),
            "chunks": [r["chunk_id"] for r in results],
        }

    async def run_demo():
        print("\n--- Fan-out: Fetching chunks in parallel ---")

        with runtime.trace_context():
            with runtime.run("fan_out_fan_in") as run:
                # Fan-out: Fetch all chunks in parallel
                chunks = await gather_with_context(
                    fetch_chunk(1),
                    fetch_chunk(2),
                    fetch_chunk(3),
                    fetch_chunk(4),
                )
                print(f"Fetched {len(chunks)} chunks")

                # Process each chunk (can also be parallel)
                print("Processing chunks...")
                processed = await gather_with_context(*[process_chunk(c) for c in chunks])
                print(f"Processed {len(processed)} chunks")

                # Fan-in: Aggregate results
                print("Aggregating results...")
                final = await aggregate_results(processed)
                print(f"Final result: {final}")

    asyncio.run(run_demo())


# =============================================================================
# Demo 8: Context with Background Monitoring
# =============================================================================


def demo_background_monitoring():
    """Demonstrate context in background monitoring tasks."""
    print("\n" + "=" * 60)
    print("Demo 8: Background Monitoring with Context")
    print("=" * 60)

    runtime = TraceCraftRuntime(console=False, jsonl=False)
    monitoring_data: list[dict[str, Any]] = []

    async def monitor_task(ctx: TraceContext) -> None:
        """Background task that monitors and reports."""
        while True:
            with restore_context(ctx):
                current_run = get_current_run()
                if current_run:
                    monitoring_data.append(
                        {
                            "run_name": current_run.name,
                            "step_count": len(current_run.steps),
                            "time": asyncio.get_event_loop().time(),
                        }
                    )
            await asyncio.sleep(0.01)

    async def run_demo():
        print("\n--- Running with background monitor ---")

        with runtime.trace_context():
            with runtime.run("monitored_workflow") as run:
                # Capture context for monitor
                ctx = capture_context()

                # Start background monitor
                monitor = asyncio.create_task(monitor_task(ctx))

                # Do some work
                for i in range(3):
                    await asyncio.sleep(0.02)
                    # Simulate adding steps
                    pass

                # Stop monitor
                monitor.cancel()
                try:
                    await monitor
                except asyncio.CancelledError:
                    pass

        print(f"\n--- Monitoring captured {len(monitoring_data)} snapshots ---")
        for data in monitoring_data[:3]:  # Show first 3
            print(f"  Run: {data['run_name']}")

    asyncio.run(run_demo())


# =============================================================================
# Main
# =============================================================================


def main():
    """Run all async context demos."""
    print("\n" + "#" * 60)
    print("# TraceCraft Async Context Propagation Examples")
    print("#" * 60)

    demo_trace_context_dataclass()
    demo_gather_with_context()
    demo_create_task_with_context()
    demo_run_in_executor_with_context()
    demo_manual_context_propagation()
    demo_complex_nested_patterns()
    demo_fan_out_fan_in()
    demo_background_monitoring()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
