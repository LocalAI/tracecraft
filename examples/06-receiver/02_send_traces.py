#!/usr/bin/env python3
"""Send Traces to OTLP Receiver - Simulates an instrumented application.

This example sends OTLP traces to the TraceCraft receiver, simulating
what an OpenTelemetry-instrumented application would do.

Generates a variety of trace patterns:
- Simple LLM-only calls
- Tool use patterns
- RAG (retrieval) patterns
- Multi-step workflows
- Complex 10+ step traces

Prerequisites:
    - Receiver running (see 01_receiver_demo.py)
    - requests library: pip install requests

Usage:
    # First start the receiver in another terminal:
    python examples/06-receiver/01_receiver_demo.py

    # Then run this script:
    python examples/06-receiver/02_send_traces.py

Expected Output:
    - Traces sent successfully to the receiver
    - View in TUI: tracecraft ui sqlite://traces/receiver_demo.db
"""

from __future__ import annotations

import json
import random
import time
import uuid
from dataclasses import dataclass, field

import requests

# OTLP receiver endpoint
RECEIVER_URL = "http://127.0.0.1:4318/v1/traces"

# Sample data for variety
MODELS = [
    ("gpt-4o-mini", "openai", 0.15, 0.60),
    ("gpt-4o", "openai", 2.50, 10.00),
    ("claude-3-haiku", "anthropic", 0.25, 1.25),
    ("claude-3-sonnet", "anthropic", 3.00, 15.00),
    ("gemini-1.5-flash", "google", 0.075, 0.30),
]

TOOLS = [
    ("get_weather", {"city": "San Francisco"}, {"temperature": 68, "conditions": "Sunny"}),
    (
        "web_search",
        {"query": "Python tutorials"},
        {"results": 15, "top_url": "https://docs.python.org"},
    ),
    ("calculator", {"expression": "sqrt(144)"}, {"result": 12.0}),
    ("database_query", {"sql": "SELECT * FROM users"}, {"rows": 42, "time_ms": 15}),
    ("send_email", {"to": "user@example.com"}, {"status": "sent", "id": "msg_123"}),
    ("file_read", {"path": "/data/config.json"}, {"size_bytes": 1024, "exists": True}),
    ("api_call", {"endpoint": "/users/1"}, {"user": "john_doe", "status": 200}),
    ("code_execute", {"language": "python"}, {"output": "Hello World", "exit_code": 0}),
]


def generate_id() -> str:
    """Generate a 16-character hex ID."""
    return uuid.uuid4().hex[:16]


@dataclass
class Span:
    """Represents an OTLP span."""

    name: str
    span_type: str  # AGENT, LLM, TOOL, RETRIEVAL, WORKFLOW
    parent_id: str | None = None
    span_id: str = field(default_factory=generate_id)
    duration_ms: int = field(default_factory=lambda: random.randint(100, 2000))
    model: tuple | None = None  # (name, provider, input_cost, output_cost)
    tool: tuple | None = None  # (name, params, output)
    input_data: dict | None = None
    output_data: dict | None = None
    error: str | None = None


def build_otlp_payload(trace_name: str, spans: list[Span]) -> dict:
    """Build an OTLP trace payload from spans."""
    trace_id = uuid.uuid4().hex
    now_ns = int(time.time() * 1_000_000_000)

    # Calculate timing for each span
    current_time = now_ns
    span_times: dict[str, tuple[int, int]] = {}

    for span in spans:
        start = current_time
        end = start + (span.duration_ms * 1_000_000)
        span_times[span.span_id] = (start, end)
        current_time = end + random.randint(10_000_000, 50_000_000)  # Small gap

    # Build OTLP spans
    otlp_spans = []
    for span in spans:
        start_ns, end_ns = span_times[span.span_id]
        attributes = []

        # Add type-specific attributes
        if span.span_type == "AGENT":
            attributes.append({"key": "gen_ai.agent.name", "value": {"stringValue": span.name}})
            attributes.append({"key": "tracecraft.step.type", "value": {"stringValue": "AGENT"}})

        elif span.span_type == "LLM" and span.model:
            model_name, provider, input_cost, output_cost = span.model
            input_tokens = random.randint(100, 1500)
            output_tokens = random.randint(50, 400)
            cost = (input_tokens * input_cost + output_tokens * output_cost) / 1_000_000

            attributes.extend(
                [
                    {"key": "gen_ai.request.model", "value": {"stringValue": model_name}},
                    {"key": "gen_ai.system", "value": {"stringValue": provider}},
                    {"key": "gen_ai.usage.input_tokens", "value": {"intValue": str(input_tokens)}},
                    {
                        "key": "gen_ai.usage.output_tokens",
                        "value": {"intValue": str(output_tokens)},
                    },
                    {"key": "gen_ai.usage.cost", "value": {"doubleValue": round(cost, 6)}},
                ]
            )

        elif span.span_type == "TOOL" and span.tool:
            tool_name, params, output = span.tool
            attributes.extend(
                [
                    {"key": "tool.name", "value": {"stringValue": tool_name}},
                    {"key": "tracecraft.step.type", "value": {"stringValue": "TOOL"}},
                    {"key": "tool.parameters", "value": {"stringValue": json.dumps(params)}},
                ]
            )
            span.output_data = output

        elif span.span_type == "RETRIEVAL":
            attributes.append(
                {"key": "tracecraft.step.type", "value": {"stringValue": "RETRIEVAL"}}
            )
            attributes.append({"key": "retrieval.query", "value": {"stringValue": span.name}})

        elif span.span_type == "WORKFLOW":
            attributes.append({"key": "tracecraft.step.type", "value": {"stringValue": "WORKFLOW"}})

        # Add input/output if present
        if span.input_data:
            attributes.append(
                {"key": "input.value", "value": {"stringValue": json.dumps(span.input_data)}}
            )
        if span.output_data:
            attributes.append(
                {"key": "output.value", "value": {"stringValue": json.dumps(span.output_data)}}
            )

        # Add error if present
        if span.error:
            attributes.append({"key": "error.message", "value": {"stringValue": span.error}})

        otlp_span = {
            "traceId": trace_id,
            "spanId": span.span_id,
            "name": span.name,
            "kind": 1,
            "startTimeUnixNano": str(start_ns),
            "endTimeUnixNano": str(end_ns),
            "attributes": attributes,
        }

        if span.parent_id:
            otlp_span["parentSpanId"] = span.parent_id

        otlp_spans.append(otlp_span)

    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "demo-agent"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "tracecraft-demo"},
                        "spans": otlp_spans,
                    }
                ],
            }
        ]
    }


def create_simple_llm_trace() -> tuple[dict, str]:
    """Pattern 1: Simple LLM call (2 steps)."""
    model = random.choice(MODELS)
    agent = Span("QuickAnswer", "AGENT", input_data={"question": "What is 2+2?"})
    llm = Span(
        model[0],
        "LLM",
        parent_id=agent.span_id,
        model=model,
        input_data={"prompt": "What is 2+2?"},
        output_data={"response": "The answer is 4."},
    )
    agent.output_data = {"answer": "4"}

    return build_otlp_payload("simple_llm", [agent, llm]), "Simple LLM (2 steps)"


def create_tool_use_trace() -> tuple[dict, str]:
    """Pattern 2: LLM with tool use (3 steps)."""
    model = random.choice(MODELS)
    tool = random.choice(TOOLS)

    agent = Span("ToolUser", "AGENT", input_data={"task": f"Use {tool[0]}"})
    llm = Span(
        model[0],
        "LLM",
        parent_id=agent.span_id,
        model=model,
        output_data={"action": f"call {tool[0]}"},
    )
    tool_span = Span(tool[0], "TOOL", parent_id=agent.span_id, tool=tool)
    agent.output_data = {"result": tool[2]}

    return build_otlp_payload("tool_use", [agent, llm, tool_span]), "Tool Use (3 steps)"


def create_rag_trace() -> tuple[dict, str]:
    """Pattern 3: RAG - Retrieval then LLM (3 steps)."""
    model = random.choice(MODELS)
    query = "How do I configure logging in Python?"

    agent = Span("RAGAssistant", "AGENT", input_data={"query": query})
    retrieval = Span(
        query,
        "RETRIEVAL",
        parent_id=agent.span_id,
        duration_ms=random.randint(50, 200),
        output_data={"documents": ["doc1.md", "doc2.md"], "scores": [0.95, 0.87]},
    )
    llm = Span(
        model[0],
        "LLM",
        parent_id=agent.span_id,
        model=model,
        input_data={"query": query, "context": "Retrieved docs..."},
        output_data={"response": "Use the logging module with basicConfig()..."},
    )
    agent.output_data = {"answer": "Use logging.basicConfig()..."}

    return build_otlp_payload("rag_query", [agent, retrieval, llm]), "RAG Pattern (3 steps)"


def create_multi_tool_trace() -> tuple[dict, str]:
    """Pattern 4: Multiple tools in sequence (5 steps)."""
    model = random.choice(MODELS)
    tools = random.sample(TOOLS, 3)

    agent = Span("MultiToolAgent", "AGENT", input_data={"task": "Complex multi-step task"})
    llm1 = Span(
        model[0], "LLM", parent_id=agent.span_id, model=model, output_data={"plan": "Step 1, 2, 3"}
    )
    tool1 = Span(tools[0][0], "TOOL", parent_id=agent.span_id, tool=tools[0])
    tool2 = Span(tools[1][0], "TOOL", parent_id=agent.span_id, tool=tools[1])
    tool3 = Span(tools[2][0], "TOOL", parent_id=agent.span_id, tool=tools[2])
    agent.output_data = {"completed": True, "tools_used": 3}

    return build_otlp_payload(
        "multi_tool", [agent, llm1, tool1, tool2, tool3]
    ), "Multi-Tool (5 steps)"


def create_workflow_trace() -> tuple[dict, str]:
    """Pattern 5: Workflow with sub-steps (6 steps)."""
    model = random.choice(MODELS)

    agent = Span("WorkflowRunner", "AGENT", input_data={"workflow": "data_pipeline"})
    step1 = Span(
        "validate_input",
        "WORKFLOW",
        parent_id=agent.span_id,
        duration_ms=50,
        output_data={"valid": True},
    )
    step2 = Span("fetch_data", "WORKFLOW", parent_id=agent.span_id, output_data={"rows": 1000})
    llm = Span(
        model[0],
        "LLM",
        parent_id=step2.span_id,
        model=model,
        input_data={"task": "Analyze data"},
        output_data={"insights": ["trend1", "trend2"]},
    )
    step3 = Span(
        "save_results",
        "WORKFLOW",
        parent_id=agent.span_id,
        output_data={"saved": True, "path": "/output/results.json"},
    )
    agent.output_data = {"status": "completed", "steps": 4}

    return build_otlp_payload("workflow", [agent, step1, step2, llm, step3]), "Workflow (5 steps)"


def create_error_trace() -> tuple[dict, str]:
    """Pattern 6: Trace with an error (3 steps)."""
    model = random.choice(MODELS)

    agent = Span("ErrorHandler", "AGENT", input_data={"risky_operation": True})
    llm = Span(model[0], "LLM", parent_id=agent.span_id, model=model)
    tool = Span(
        "api_call",
        "TOOL",
        parent_id=agent.span_id,
        tool=("api_call", {"endpoint": "/fail"}, None),
        error="ConnectionError: API timeout after 30s",
    )
    agent.output_data = {"status": "failed", "error": "API timeout"}

    return build_otlp_payload("error_case", [agent, llm, tool]), "Error Case (3 steps)"


def create_complex_trace() -> tuple[dict, str]:
    """Pattern 7: Complex 12-step trace with nested structure."""
    models = random.sample(MODELS, 3)
    tools = random.sample(TOOLS, 4)

    # Root agent
    agent = Span(
        "ComplexResearchAgent",
        "AGENT",
        duration_ms=15000,
        input_data={"research_topic": "Climate change impacts on agriculture"},
    )

    # Phase 1: Planning
    plan_llm = Span(
        models[0][0],
        "LLM",
        parent_id=agent.span_id,
        model=models[0],
        input_data={"task": "Create research plan"},
        output_data={"plan": ["gather data", "analyze", "summarize"]},
    )

    # Phase 2: Data gathering (sub-workflow)
    gather_workflow = Span(
        "gather_data", "WORKFLOW", parent_id=agent.span_id, input_data={"sources": 3}
    )

    # Multiple retrievals
    retrieval1 = Span(
        "search: climate data",
        "RETRIEVAL",
        parent_id=gather_workflow.span_id,
        duration_ms=150,
        output_data={"docs": 5, "relevance": 0.92},
    )
    retrieval2 = Span(
        "search: agriculture studies",
        "RETRIEVAL",
        parent_id=gather_workflow.span_id,
        duration_ms=180,
        output_data={"docs": 8, "relevance": 0.88},
    )

    # Tool calls for data
    tool1 = Span(tools[0][0], "TOOL", parent_id=gather_workflow.span_id, tool=tools[0])
    tool2 = Span(tools[1][0], "TOOL", parent_id=gather_workflow.span_id, tool=tools[1])

    gather_workflow.output_data = {"total_sources": 15}

    # Phase 3: Analysis
    analyze_llm = Span(
        models[1][0],
        "LLM",
        parent_id=agent.span_id,
        model=models[1],
        input_data={"data_points": 15, "task": "Analyze patterns"},
        output_data={"findings": ["finding1", "finding2", "finding3"]},
    )

    # Additional tool for computation
    tool3 = Span(tools[2][0], "TOOL", parent_id=agent.span_id, tool=tools[2])

    # Phase 4: Synthesis
    synthesis_workflow = Span("synthesize_findings", "WORKFLOW", parent_id=agent.span_id)

    synthesis_llm = Span(
        models[2][0],
        "LLM",
        parent_id=synthesis_workflow.span_id,
        model=models[2],
        input_data={"findings": 3, "format": "report"},
        output_data={"report": "Executive summary: Climate change affects..."},
    )

    tool4 = Span(tools[3][0], "TOOL", parent_id=synthesis_workflow.span_id, tool=tools[3])

    synthesis_workflow.output_data = {"report_generated": True}

    agent.output_data = {
        "status": "completed",
        "total_sources": 15,
        "findings": 3,
        "report_path": "/output/climate_report.pdf",
    }

    spans = [
        agent,
        plan_llm,
        gather_workflow,
        retrieval1,
        retrieval2,
        tool1,
        tool2,
        analyze_llm,
        tool3,
        synthesis_workflow,
        synthesis_llm,
        tool4,
    ]

    return build_otlp_payload("complex_research", spans), "Complex Research (12 steps)"


# All trace generators
TRACE_GENERATORS = [
    create_simple_llm_trace,
    create_tool_use_trace,
    create_rag_trace,
    create_multi_tool_trace,
    create_workflow_trace,
    create_error_trace,
    create_complex_trace,
]


def main() -> None:
    """Send demo traces to the receiver."""
    print("=" * 60)
    print("TraceCraft Trace Sender Demo")
    print("=" * 60)

    # Check if receiver is running
    try:
        health = requests.get("http://127.0.0.1:4318/health", timeout=2)
        if health.status_code != 200:
            print("\nError: Receiver not healthy")
            return
    except requests.ConnectionError:
        print("\nError: Receiver not running!")
        print("Start the receiver first:")
        print("  python examples/06-receiver/01_receiver_demo.py")
        return

    print("\nReceiver is healthy!")
    print("-" * 60)

    # Send one of each trace type
    for i, generator in enumerate(TRACE_GENERATORS):
        payload, description = generator()
        spans = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]

        print(f"\n[{i + 1}/{len(TRACE_GENERATORS)}] {description}")

        response = requests.post(
            RECEIVER_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            print(f"  Spans: {len(spans)} | Status: {data['status']}")
        else:
            print(f"  Error: {response.status_code} - {response.text}")

        time.sleep(0.3)

    print("\n" + "=" * 60)
    print(f"Done! Sent {len(TRACE_GENERATORS)} unique trace patterns.")
    print("View with: tracecraft ui sqlite://traces/receiver_demo.db")
    print("=" * 60)


if __name__ == "__main__":
    main()
