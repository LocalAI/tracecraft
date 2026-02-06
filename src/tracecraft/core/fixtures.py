"""
Example trace fixtures for TraceCraft.

This module contains example/demo trace generation code, extracted from
the core init module to maintain single responsibility principle.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun, Step


def generate_example_traces(base_time: datetime | None = None) -> list[AgentRun]:
    """
    Generate example traces for demonstration.

    Creates traces with nested hierarchies to demonstrate waterfall view.

    Args:
        base_time: Base time for trace timestamps. Defaults to now.

    Returns:
        List of AgentRun objects.
    """
    from tracecraft.core.models import AgentRun, Step, StepType

    if base_time is None:
        base_time = datetime.now(UTC)

    traces: list[AgentRun] = []

    # Add each example trace
    traces.append(_create_research_trace(base_time))
    traces.append(_create_code_generation_trace(base_time))
    traces.append(_create_rag_trace(base_time))
    traces.append(_create_guardrail_error_trace(base_time))
    traces.append(_create_support_agent_trace(base_time))

    return traces


def _create_research_trace(base_time: datetime) -> AgentRun:
    """Create multi-agent research trace (complex nested hierarchy)."""
    from tracecraft.core.models import AgentRun, Step, StepType

    t_id = uuid4()
    start = base_time - timedelta(minutes=30)

    return AgentRun(
        id=t_id,
        name="Research Assistant",
        description="Multi-agent research with planning, search, and synthesis",
        start_time=start,
        duration_ms=12500.0,
        total_tokens=8450,
        total_cost_usd=0.1234,
        tags=["research", "multi-agent"],
        environment="production",
        input={"query": "Compare the top 3 JavaScript frameworks for building dashboards"},
        output={"report": "Based on analysis, React leads in ecosystem..."},
        steps=[
            _create_planner_step(t_id, start),
            _create_researcher_step(t_id, start + timedelta(milliseconds=2000)),
            _create_synthesizer_step(t_id, start + timedelta(milliseconds=8500)),
        ],
    )


def _create_planner_step(trace_id: UUID, start: datetime) -> Step:
    """Create planner agent step with LLM child."""
    from tracecraft.core.models import Step, StepType

    return Step(
        id=uuid4(),
        trace_id=trace_id,
        type=StepType.AGENT,
        name="planner",
        start_time=start,
        duration_ms=2000.0,
        inputs={"query": "Compare JS frameworks"},
        outputs={"plan": ["search", "analyze", "synthesize"]},
        children=[
            Step(
                id=uuid4(),
                trace_id=trace_id,
                type=StepType.LLM,
                name="gpt-4o",
                start_time=start,
                duration_ms=1800.0,
                model_name="gpt-4o",
                input_tokens=150,
                output_tokens=320,
                cost_usd=0.0085,
            ),
        ],
    )


def _create_researcher_step(trace_id: UUID, start: datetime) -> Step:
    """Create researcher agent step with search and LLM children."""
    from tracecraft.core.models import Step, StepType

    search_steps = [
        _create_search_step(trace_id, start, "React dashboard 2024", 1200.0),
        _create_search_step(
            trace_id, start + timedelta(milliseconds=1200), "Vue dashboard 2024", 1100.0
        ),
        _create_search_step(
            trace_id, start + timedelta(milliseconds=2300), "Angular dashboard 2024", 1000.0
        ),
    ]

    return Step(
        id=uuid4(),
        trace_id=trace_id,
        type=StepType.AGENT,
        name="researcher",
        start_time=start,
        duration_ms=6500.0,
        inputs={"topics": ["React", "Vue", "Angular"]},
        outputs={"findings": {"React": "...", "Vue": "...", "Angular": "..."}},
        children=[
            *search_steps,
            Step(
                id=uuid4(),
                trace_id=trace_id,
                type=StepType.LLM,
                name="claude-3-5-sonnet",
                start_time=start + timedelta(milliseconds=3300),
                duration_ms=3200.0,
                model_name="claude-3-5-sonnet-20241022",
                input_tokens=2500,
                output_tokens=1800,
                cost_usd=0.0456,
            ),
        ],
    )


def _create_search_step(trace_id: UUID, start: datetime, query: str, duration_ms: float) -> Step:
    """Create a web search tool step."""
    from tracecraft.core.models import Step, StepType

    return Step(
        id=uuid4(),
        trace_id=trace_id,
        type=StepType.TOOL,
        name="web_search",
        start_time=start,
        duration_ms=duration_ms,
        inputs={"query": query},
        outputs={"results": ["url1", "url2", "url3"]},
    )


def _create_synthesizer_step(trace_id: UUID, start: datetime) -> Step:
    """Create synthesizer agent step."""
    from tracecraft.core.models import Step, StepType

    return Step(
        id=uuid4(),
        trace_id=trace_id,
        type=StepType.AGENT,
        name="synthesizer",
        start_time=start,
        duration_ms=4000.0,
        inputs={"findings": "..."},
        outputs={"report": "Based on analysis..."},
        children=[
            Step(
                id=uuid4(),
                trace_id=trace_id,
                type=StepType.RETRIEVAL,
                name="load_templates",
                start_time=start,
                duration_ms=300.0,
            ),
            Step(
                id=uuid4(),
                trace_id=trace_id,
                type=StepType.LLM,
                name="gpt-4o",
                start_time=start + timedelta(milliseconds=300),
                duration_ms=3700.0,
                model_name="gpt-4o",
                input_tokens=3200,
                output_tokens=2100,
                cost_usd=0.0693,
            ),
        ],
    )


def _create_code_generation_trace(base_time: datetime) -> AgentRun:
    """Create code generation trace (tool-heavy)."""
    from tracecraft.core.models import AgentRun, Step, StepType

    t_id = uuid4()
    start = base_time - timedelta(minutes=20)

    return AgentRun(
        id=t_id,
        name="Code Generator",
        description="Generate, test, and refine Python code",
        start_time=start,
        duration_ms=8200.0,
        total_tokens=4500,
        total_cost_usd=0.0678,
        tags=["code", "python", "testing"],
        input={"request": "Create a REST API endpoint with validation"},
        output={"code": "from fastapi import FastAPI..."},
        steps=[
            Step(
                id=uuid4(),
                trace_id=t_id,
                type=StepType.LLM,
                name="claude-3-5-sonnet",
                start_time=start,
                duration_ms=2500.0,
                model_name="claude-3-5-sonnet-20241022",
                input_tokens=200,
                output_tokens=1500,
                cost_usd=0.0285,
                inputs={"request": "Create REST API..."},
                outputs={"code": "from fastapi import..."},
            ),
            Step(
                id=uuid4(),
                trace_id=t_id,
                type=StepType.TOOL,
                name="syntax_check",
                start_time=start + timedelta(milliseconds=2500),
                duration_ms=150.0,
                inputs={"code": "..."},
                outputs={"valid": True},
            ),
            _create_test_run_step(t_id, start + timedelta(milliseconds=2650)),
            Step(
                id=uuid4(),
                trace_id=t_id,
                type=StepType.LLM,
                name="gpt-4o",
                start_time=start + timedelta(milliseconds=4450),
                duration_ms=2200.0,
                model_name="gpt-4o",
                input_tokens=1800,
                output_tokens=800,
                cost_usd=0.0312,
                inputs={"code": "...", "failures": ["test1", "test2"]},
                outputs={"fixed_code": "..."},
            ),
            Step(
                id=uuid4(),
                trace_id=t_id,
                type=StepType.TOOL,
                name="run_tests",
                start_time=start + timedelta(milliseconds=6650),
                duration_ms=1550.0,
                inputs={"code": "fixed_code"},
                outputs={"passed": 10, "failed": 0},
            ),
        ],
    )


def _create_test_run_step(trace_id: UUID, start: datetime) -> Step:
    """Create test run step with child test steps."""
    from tracecraft.core.models import Step, StepType

    return Step(
        id=uuid4(),
        trace_id=trace_id,
        type=StepType.TOOL,
        name="run_tests",
        start_time=start,
        duration_ms=1800.0,
        inputs={"code": "...", "test_suite": "unit"},
        outputs={"passed": 8, "failed": 2},
        children=[
            Step(
                id=uuid4(),
                trace_id=trace_id,
                type=StepType.TOOL,
                name="test_validation",
                start_time=start,
                duration_ms=600.0,
                outputs={"passed": True},
            ),
            Step(
                id=uuid4(),
                trace_id=trace_id,
                type=StepType.TOOL,
                name="test_endpoints",
                start_time=start + timedelta(milliseconds=600),
                duration_ms=800.0,
                outputs={"passed": 6, "failed": 2},
            ),
            Step(
                id=uuid4(),
                trace_id=trace_id,
                type=StepType.TOOL,
                name="test_errors",
                start_time=start + timedelta(milliseconds=1400),
                duration_ms=400.0,
                outputs={"passed": True},
            ),
        ],
    )


def _create_rag_trace(base_time: datetime) -> AgentRun:
    """Create RAG pipeline trace (retrieval focused)."""
    from tracecraft.core.models import AgentRun, Step, StepType

    t_id = uuid4()
    start = base_time - timedelta(minutes=15)

    return AgentRun(
        id=t_id,
        name="RAG Query",
        description="Retrieval-augmented generation for documentation",
        start_time=start,
        duration_ms=4800.0,
        total_tokens=2100,
        total_cost_usd=0.0234,
        tags=["rag", "documentation"],
        input={"query": "How do I configure authentication?"},
        output={"answer": "To configure authentication, first..."},
        steps=[
            Step(
                id=uuid4(),
                trace_id=t_id,
                type=StepType.LLM,
                name="query_expansion",
                start_time=start,
                duration_ms=800.0,
                model_name="gpt-4o-mini",
                input_tokens=50,
                output_tokens=150,
                cost_usd=0.0012,
            ),
            Step(
                id=uuid4(),
                trace_id=t_id,
                type=StepType.RETRIEVAL,
                name="vector_search",
                start_time=start + timedelta(milliseconds=800),
                duration_ms=450.0,
                inputs={"query": "configure authentication setup"},
                outputs={"docs": 5, "top_score": 0.94},
            ),
            Step(
                id=uuid4(),
                trace_id=t_id,
                type=StepType.RETRIEVAL,
                name="rerank",
                start_time=start + timedelta(milliseconds=1250),
                duration_ms=350.0,
                inputs={"docs": 5},
                outputs={"reranked": 3},
            ),
            Step(
                id=uuid4(),
                trace_id=t_id,
                type=StepType.LLM,
                name="answer_generation",
                start_time=start + timedelta(milliseconds=1600),
                duration_ms=3200.0,
                model_name="gpt-4o",
                input_tokens=1200,
                output_tokens=700,
                cost_usd=0.0222,
            ),
        ],
    )


def _create_guardrail_error_trace(base_time: datetime) -> AgentRun:
    """Create error case trace (guardrail blocked)."""
    from tracecraft.core.models import AgentRun, Step, StepType

    t_id = uuid4()
    start = base_time - timedelta(minutes=10)

    return AgentRun(
        id=t_id,
        name="Content Moderation Fail",
        description="Request blocked by content guardrail",
        start_time=start,
        duration_ms=1200.0,
        total_tokens=150,
        total_cost_usd=0.002,
        error_count=1,
        tags=["error", "guardrail"],
        error="GuardrailError: Content policy violation detected",
        error_type="GuardrailError",
        input={"message": "Help me with..."},
        steps=[
            Step(
                id=uuid4(),
                trace_id=t_id,
                type=StepType.GUARDRAIL,
                name="input_filter",
                start_time=start,
                duration_ms=200.0,
                outputs={"passed": True},
            ),
            Step(
                id=uuid4(),
                trace_id=t_id,
                type=StepType.LLM,
                name="gpt-4o-mini",
                start_time=start + timedelta(milliseconds=200),
                duration_ms=800.0,
                model_name="gpt-4o-mini",
                input_tokens=100,
                output_tokens=50,
                cost_usd=0.002,
            ),
            Step(
                id=uuid4(),
                trace_id=t_id,
                type=StepType.GUARDRAIL,
                name="output_filter",
                start_time=start + timedelta(milliseconds=1000),
                duration_ms=200.0,
                error="Content policy violation detected",
                error_type="GuardrailError",
                outputs={"passed": False, "reason": "policy_violation"},
            ),
        ],
    )


def _create_support_agent_trace(base_time: datetime) -> AgentRun:
    """Create customer support agent trace (memory + tools)."""
    from tracecraft.core.models import AgentRun, Step, StepType

    t_id = uuid4()
    start = base_time - timedelta(minutes=5)

    return AgentRun(
        id=t_id,
        name="Support Agent",
        description="Customer support with memory and order lookup",
        start_time=start,
        duration_ms=5500.0,
        total_tokens=1800,
        total_cost_usd=0.0156,
        tags=["support", "agent"],
        session_id="session_abc123",
        user_id="user_789",
        input={"message": "Can you check the status of my recent order?"},
        output={"response": "Your order #98765 was delivered yesterday at 2:34 PM."},
        steps=[
            Step(
                id=uuid4(),
                trace_id=t_id,
                type=StepType.MEMORY,
                name="load_session",
                start_time=start,
                duration_ms=150.0,
                outputs={"messages": 3, "context_loaded": True},
            ),
            _create_intent_router_step(t_id, start + timedelta(milliseconds=150)),
            Step(
                id=uuid4(),
                trace_id=t_id,
                type=StepType.TOOL,
                name="lookup_orders",
                start_time=start + timedelta(milliseconds=1650),
                duration_ms=800.0,
                inputs={"user_id": "user_789", "limit": 5},
                outputs={"orders": [{"id": "#98765", "status": "delivered"}]},
            ),
            Step(
                id=uuid4(),
                trace_id=t_id,
                type=StepType.TOOL,
                name="get_tracking",
                start_time=start + timedelta(milliseconds=2450),
                duration_ms=600.0,
                inputs={"order_id": "#98765"},
                outputs={"delivered_at": "2024-01-15T14:34:00Z"},
            ),
            Step(
                id=uuid4(),
                trace_id=t_id,
                type=StepType.LLM,
                name="response_gen",
                start_time=start + timedelta(milliseconds=3050),
                duration_ms=2200.0,
                model_name="gpt-4o",
                input_tokens=600,
                output_tokens=150,
                cost_usd=0.0096,
            ),
            Step(
                id=uuid4(),
                trace_id=t_id,
                type=StepType.MEMORY,
                name="save_session",
                start_time=start + timedelta(milliseconds=5250),
                duration_ms=250.0,
                outputs={"saved": True},
            ),
        ],
    )


def _create_intent_router_step(trace_id: UUID, start: datetime) -> Step:
    """Create intent router step with LLM child."""
    from tracecraft.core.models import Step, StepType

    return Step(
        id=uuid4(),
        trace_id=trace_id,
        type=StepType.AGENT,
        name="intent_router",
        start_time=start,
        duration_ms=1500.0,
        outputs={"intent": "order_status", "confidence": 0.95},
        children=[
            Step(
                id=uuid4(),
                trace_id=trace_id,
                type=StepType.LLM,
                name="gpt-4o-mini",
                start_time=start,
                duration_ms=1500.0,
                model_name="gpt-4o-mini",
                input_tokens=400,
                output_tokens=50,
                cost_usd=0.003,
            ),
        ],
    )
