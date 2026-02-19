#!/usr/bin/env python3
"""Manual validation script for auto-instrumentation.

This script runs auto-instrumented API calls and saves traces to both
JSONL and SQLite for manual TUI verification.

Usage:
    # Load API keys and run
    export $(cat .env | xargs)
    uv run python scripts/validate_auto_instrumentation.py

    # Then verify in TUI
    uv run tracecraft ui traces/auto_validation.jsonl
    uv run tracecraft ui traces/auto_validation.db
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import tracecraft
from tracecraft.storage.sqlite import SQLiteTraceStore


def check_api_key() -> bool:
    """Check if OpenAI API key is set."""
    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set")
        print("Run: export $(cat .env | xargs)")
        return False
    return True


def test_openai_auto(runtime: tracecraft.TALRuntime, store: SQLiteTraceStore) -> None:
    """Test OpenAI auto-instrumentation."""
    import openai

    from tracecraft.core.context import run_context
    from tracecraft.core.models import AgentRun

    print("\n[1/4] Testing OpenAI auto-instrumentation...")

    run = AgentRun(name="validation_openai", start_time=datetime.now(UTC))

    with run_context(run):
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": "Say 'OpenAI auto-instrumentation validated' exactly."}
            ],
            max_tokens=50,
        )
        result = response.choices[0].message.content
        print(f"   Response: {result}")

    runtime.end_run(run)
    store.save(run)

    steps = len(run.steps)
    print(f"   Steps captured: {steps}")
    if steps > 0:
        print(f"   Step types: {[s.type.value for s in run.steps]}")
        print("   ✓ OpenAI auto-instrumentation PASSED")
    else:
        print("   ✗ OpenAI auto-instrumentation FAILED - no steps captured")


def test_langchain_auto(runtime: tracecraft.TALRuntime, store: SQLiteTraceStore) -> None:
    """Test LangChain auto-instrumentation."""
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        print("\n[2/4] Skipping LangChain - not installed")
        return

    from tracecraft.core.context import run_context
    from tracecraft.core.models import AgentRun

    print("\n[2/4] Testing LangChain auto-instrumentation...")

    run = AgentRun(name="validation_langchain", start_time=datetime.now(UTC))

    with run_context(run):
        llm = ChatOpenAI(model="gpt-4o-mini", max_tokens=50)
        result = llm.invoke("Say 'LangChain auto-instrumentation validated' exactly.")
        print(f"   Response: {result.content}")

    runtime.end_run(run)
    store.save(run)

    steps = len(run.steps)
    print(f"   Steps captured: {steps}")
    if steps > 0:
        print(f"   Step types: {[s.type.value for s in run.steps]}")
        print("   ✓ LangChain auto-instrumentation PASSED")
    else:
        print("   ✗ LangChain auto-instrumentation FAILED - no steps captured")


def test_langgraph_auto(runtime: tracecraft.TALRuntime, store: SQLiteTraceStore) -> None:
    """Test LangGraph auto-instrumentation."""
    try:
        from langchain_openai import ChatOpenAI
        from langgraph.graph import END, StateGraph
        from typing_extensions import TypedDict
    except ImportError:
        print("\n[3/4] Skipping LangGraph - not installed")
        return

    from tracecraft.core.context import run_context
    from tracecraft.core.models import AgentRun

    print("\n[3/4] Testing LangGraph auto-instrumentation...")

    class State(TypedDict):
        messages: list[str]
        response: str

    llm = ChatOpenAI(model="gpt-4o-mini", max_tokens=50)

    def process_node(state: State) -> State:
        response = llm.invoke(state["messages"][-1])
        return {"messages": state["messages"], "response": response.content or ""}

    graph = StateGraph(State)
    graph.add_node("process", process_node)
    graph.set_entry_point("process")
    graph.add_edge("process", END)
    compiled = graph.compile()

    run = AgentRun(name="validation_langgraph", start_time=datetime.now(UTC))

    with run_context(run):
        result = compiled.invoke(
            {
                "messages": ["Say 'LangGraph auto-instrumentation validated' exactly."],
                "response": "",
            }
        )
        print(f"   Response: {result['response']}")

    runtime.end_run(run)
    store.save(run)

    steps = len(run.steps)
    print(f"   Steps captured: {steps}")
    if steps > 0:
        print(f"   Step types: {[s.type.value for s in run.steps]}")
        print("   ✓ LangGraph auto-instrumentation PASSED")
    else:
        print("   ✗ LangGraph auto-instrumentation FAILED - no steps captured")


def test_llamaindex_auto(runtime: tracecraft.TALRuntime, store: SQLiteTraceStore) -> None:
    """Test LlamaIndex auto-instrumentation."""
    try:
        from llama_index.core.llms import ChatMessage
        from llama_index.llms.openai import OpenAI
    except ImportError:
        print("\n[4/4] Skipping LlamaIndex - not installed")
        return

    from tracecraft.core.context import run_context
    from tracecraft.core.models import AgentRun

    print("\n[4/4] Testing LlamaIndex auto-instrumentation...")

    run = AgentRun(name="validation_llamaindex", start_time=datetime.now(UTC))

    with run_context(run):
        llm = OpenAI(model="gpt-4o-mini", max_tokens=50)
        response = llm.chat(
            [
                ChatMessage(
                    role="user", content="Say 'LlamaIndex auto-instrumentation validated' exactly."
                )
            ]
        )
        print(f"   Response: {response.message.content}")

    runtime.end_run(run)
    store.save(run)

    steps = len(run.steps)
    print(f"   Steps captured: {steps}")
    if steps > 0:
        print(f"   Step types: {[s.type.value for s in run.steps]}")
        print("   ✓ LlamaIndex auto-instrumentation PASSED")
    else:
        print("   ✗ LlamaIndex auto-instrumentation FAILED - no steps captured")


def main() -> int:
    """Run validation tests."""
    if not check_api_key():
        return 1

    # Create output directory
    traces_dir = Path("traces")
    traces_dir.mkdir(exist_ok=True)

    jsonl_path = traces_dir / "auto_validation.jsonl"
    sqlite_path = traces_dir / "auto_validation.db"

    # Remove old files
    if jsonl_path.exists():
        jsonl_path.unlink()
    if sqlite_path.exists():
        sqlite_path.unlink()

    print("=" * 60)
    print("Auto-Instrumentation Validation")
    print("=" * 60)
    print("\nOutput files:")
    print(f"  JSONL:  {jsonl_path}")
    print(f"  SQLite: {sqlite_path}")

    # Initialize with all auto-instrumentation
    print("\nInitializing TraceCraft with auto_instrument=True...")
    runtime = tracecraft.init(
        console=True,
        jsonl=True,
        jsonl_path=str(jsonl_path),
        auto_instrument=True,
    )

    # Create SQLite store
    store = SQLiteTraceStore(str(sqlite_path))

    # Run tests
    test_openai_auto(runtime, store)
    test_langchain_auto(runtime, store)
    test_langgraph_auto(runtime, store)
    test_llamaindex_auto(runtime, store)

    # Cleanup
    store.close()
    runtime.shutdown()

    print("\n" + "=" * 60)
    print("Validation Complete!")
    print("=" * 60)
    print("\nTo verify in TUI, run:")
    print(f"  uv run tracecraft ui {jsonl_path}")
    print(f"  uv run tracecraft ui {sqlite_path}")
    print("\nCheck that:")
    print("  - All traces appear in the trace table")
    print("  - Waterfall view shows step timing")
    print("  - Metrics panel shows token counts")
    print("  - Step types are correct (llm, agent, etc.)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
