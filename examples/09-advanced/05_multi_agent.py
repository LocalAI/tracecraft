#!/usr/bin/env python3
"""Multi-Agent Collaboration - Orchestrate multiple specialized agents.

Demonstrates how to trace a complex multi-agent system where multiple
specialized agents collaborate under a coordinator to complete tasks.

Prerequisites:
    - TraceCraft installed

Environment Variables:
    - None required

External Services:
    - None required

Usage:
    python examples/09-advanced/05_multi_agent.py

Expected Output:
    - Trace showing coordinator delegating to specialized agents
    - Hierarchical trace with nested agent calls
"""

from __future__ import annotations

from datetime import UTC, datetime

import tracecraft
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from tracecraft.instrumentation.decorators import trace_agent, trace_llm, trace_tool

# Initialize TraceCraft
runtime = tracecraft.init(
    console=True,
    jsonl=True,
    jsonl_path="traces.jsonl",
)


# ============================================================================
# Tools
# ============================================================================


@trace_tool(name="web_search")
def web_search(query: str) -> list[str]:
    """Search the web for information."""
    return [
        f"Result 1 for '{query}'",
        f"Result 2 for '{query}'",
        f"Result 3 for '{query}'",
    ]


@trace_tool(name="database_lookup")
def database_lookup(table: str, query: str) -> dict[str, str]:
    """Look up data in a database."""
    return {
        "table": table,
        "query": query,
        "results": f"Found 10 matching records for {query}",
    }


@trace_tool(name="calculator")
def calculator(expression: str) -> float:
    """Perform mathematical calculations."""
    try:
        return float(eval(expression))  # noqa: S307
    except Exception:
        return 0.0


@trace_tool(name="code_executor")
def code_executor(code: str) -> str:
    """Execute code and return results."""
    return f"Executed: {code[:50]}... Output: Success"


# ============================================================================
# LLM Calls (Simulated)
# ============================================================================


@trace_llm(name="planner_llm", model="gpt-4", provider="openai")
def plan_task(task: str) -> list[str]:
    """Break down a task into subtasks."""
    return [
        f"Subtask 1: Research {task}",
        f"Subtask 2: Analyze {task}",
        f"Subtask 3: Synthesize {task}",
    ]


@trace_llm(name="analyzer_llm", model="gpt-4", provider="openai")
def analyze_data(data: str) -> str:
    """Analyze provided data."""
    return f"Analysis: The data shows {data[:30]}..."


@trace_llm(name="synthesizer_llm", model="gpt-4", provider="openai")
def synthesize_results(results: list[str]) -> str:
    """Synthesize multiple results into a cohesive answer."""
    return f"Synthesis of {len(results)} results: Comprehensive findings..."


# ============================================================================
# Specialized Agents
# ============================================================================


@trace_agent(name="research_agent")
def research_agent(topic: str) -> str:
    """Agent specialized in research tasks.

    This agent:
    1. Searches the web for information
    2. Looks up related data in a database
    3. Analyzes the combined data
    """
    # Search for information
    search_results = web_search(topic)

    # Look up in database
    db_data = database_lookup("knowledge_base", topic)

    # Analyze combined data
    analysis = analyze_data(f"{search_results} + {db_data}")

    return analysis


@trace_agent(name="data_agent")
def data_agent(query: str) -> dict[str, str]:
    """Agent specialized in data operations.

    This agent:
    1. Queries the database
    2. Performs calculations
    3. Analyzes the results
    """
    # Query database
    raw_data = database_lookup("analytics", query)

    # Perform calculations
    score = calculator("100 * 0.85")

    # Analyze
    analysis = analyze_data(f"Score: {score}, Data: {raw_data}")

    return {
        "query": query,
        "score": str(score),
        "analysis": analysis,
    }


@trace_agent(name="code_agent")
def code_agent(task: str) -> str:
    """Agent specialized in code generation and execution.

    This agent:
    1. Generates code based on the task
    2. Executes the code
    3. Returns the results
    """
    # Generate code (simulated)
    code = f"def solve_{task.replace(' ', '_')}(): return 42"

    # Execute
    result = code_executor(code)

    return result


# ============================================================================
# Coordinator Agent
# ============================================================================


@trace_agent(name="coordinator_agent")
def coordinator_agent(task: str) -> dict[str, str]:
    """Main coordinator that orchestrates other agents.

    The coordinator:
    1. Plans the task and breaks it into subtasks
    2. Delegates subtasks to specialized agents
    3. Collects and synthesizes results
    """
    # Plan the task
    subtasks = plan_task(task)

    results = {}

    # Delegate to specialized agents
    results["research"] = research_agent(subtasks[0])
    results["data"] = str(data_agent(subtasks[1]))
    results["code"] = code_agent(subtasks[2])

    # Synthesize all results
    final_result = synthesize_results(list(results.values()))
    results["final"] = final_result

    return results


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    """Run the multi-agent example."""
    print("=" * 60)
    print("TraceCraft Multi-Agent Collaboration")
    print("=" * 60)

    # Create a run
    run = AgentRun(
        name="multi_agent_collaboration",
        start_time=datetime.now(UTC),
    )

    with run_context(run):
        result = coordinator_agent("Analyze market trends and provide recommendations")

    runtime.end_run(run)

    print("\n" + "=" * 60)
    print("Results:")
    for key, value in result.items():
        print(f"  {key}: {value[:50]}..." if len(value) > 50 else f"  {key}: {value}")
    print("=" * 60)

    # Print trace statistics
    def count_steps(steps: list, level: int = 0) -> tuple[int, int]:
        """Count total steps and max depth."""
        total = len(steps)
        max_depth = level
        for step in steps:
            child_count, child_depth = count_steps(step.children, level + 1)
            total += child_count
            max_depth = max(max_depth, child_depth)
        return total, max_depth

    total_steps, max_depth = count_steps(run.steps)
    print("\nTrace Statistics:")
    print(f"  Total steps: {total_steps}")
    print(f"  Max depth: {max_depth}")
    print(f"  Run duration: {run.duration_ms:.2f}ms")

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nKey patterns demonstrated:")
    print("  - Coordinator delegating to specialized agents")
    print("  - Each agent using appropriate tools")
    print("  - Hierarchical trace structure")
    print("  - Result synthesis across agents")


if __name__ == "__main__":
    main()
