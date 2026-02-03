#!/usr/bin/env python3
"""HTML Reports - Generate self-contained trace reports.

Demonstrates how to generate HTML reports for trace visualization,
sharing, and debugging.

Prerequisites:
    - TraceCraft installed

Environment Variables:
    - None required

External Services:
    - None required

Usage:
    python examples/03-exporters/04_html_reports.py

Expected Output:
    - HTML file at trace_report.html
    - Report opens automatically in browser
"""

from __future__ import annotations

import webbrowser
from datetime import UTC, datetime
from pathlib import Path

import tracecraft
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from tracecraft.exporters.html import HTMLExporter
from tracecraft.instrumentation.decorators import trace_agent, trace_llm, trace_tool


def main() -> None:
    """Generate an HTML report from a traced workflow."""
    print("=" * 60)
    print("TraceCraft HTML Report Generation")
    print("=" * 60)

    # Initialize TraceCraft (console only, we'll use HTML exporter separately)
    runtime = tracecraft.init(console=True, jsonl=False)

    # Define traced functions for a realistic workflow
    @trace_tool(name="search_documents")
    def search_documents(query: str) -> list[str]:
        """Search for relevant documents."""
        return [
            f"Document 1 about {query}",
            f"Document 2 about {query}",
            f"Document 3 about {query}",
        ]

    @trace_tool(name="extract_facts")
    def extract_facts(document: str) -> dict[str, str]:
        """Extract key facts from a document."""
        return {
            "source": document,
            "fact1": "Important finding A",
            "fact2": "Important finding B",
        }

    @trace_llm(name="summarizer", model="gpt-4", provider="openai")
    def summarize(facts: list[dict[str, str]]) -> str:
        """Summarize extracted facts."""
        return f"Summary based on {len(facts)} documents: Key insights..."

    @trace_llm(name="answerer", model="gpt-4", provider="openai")
    def generate_answer(summary: str, question: str) -> str:
        """Generate final answer."""
        return f"Based on {summary[:30]}..., the answer to '{question}' is: 42"

    @trace_agent(name="research_agent")
    def research_agent(question: str) -> str:
        """Research agent that searches, extracts, and summarizes."""
        # Search for documents
        documents = search_documents(question)

        # Extract facts from each document
        all_facts = []
        for doc in documents:
            facts = extract_facts(doc)
            all_facts.append(facts)

        # Summarize all facts
        summary = summarize(all_facts)

        # Generate answer
        answer = generate_answer(summary, question)

        return answer

    @trace_agent(name="qa_agent")
    def qa_agent(questions: list[str]) -> dict[str, str]:
        """QA agent that answers multiple questions."""
        answers = {}
        for q in questions:
            answers[q] = research_agent(q)
        return answers

    # Run the traced workflow
    print("\n--- Running traced workflow ---\n")

    run = AgentRun(name="qa_session", start_time=datetime.now(UTC))

    with run_context(run):
        result = qa_agent(
            [
                "What is the meaning of life?",
                "How does quantum computing work?",
            ]
        )

    runtime.end_run(run)

    # Generate HTML report
    print("\n--- Generating HTML report ---")
    output_path = Path("trace_report.html")
    html_exporter = HTMLExporter(filepath=str(output_path))
    html_exporter.export(run)

    print(f"\nHTML report generated: {output_path.absolute()}")

    # Show results
    print("\nResults:")
    for question, answer in result.items():
        print(f"  Q: {question}")
        print(f"  A: {answer}\n")

    # Open in browser
    print("Opening report in browser...")
    webbrowser.open(f"file://{output_path.absolute()}")

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nHTML Report Features:")
    print("  - Self-contained (no external dependencies)")
    print("  - Interactive trace tree visualization")
    print("  - Timing and hierarchy information")
    print("  - Shareable via email or hosting")
    print("\nUse cases:")
    print("  - Debugging complex agent workflows")
    print("  - Sharing traces with team members")
    print("  - Creating documentation")
    print("  - Offline trace analysis")


if __name__ == "__main__":
    main()
