"""Sample trace data fixtures for demos and testing.

This module provides pre-built AgentRun examples covering various scenarios:
- Simple chat completions
- RAG pipelines with retrieval
- Multi-agent orchestration
- Tool-using agents
- Error scenarios (rate limits, timeouts)
- Cloud provider integrations (Azure, AWS, GCP)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from tracecraft.core.models import AgentRun, Step, StepType


def generate_sample_traces(base_time: datetime | None = None) -> list[AgentRun]:
    """Generate comprehensive sample trace data for demo mode.

    Creates 20 diverse trace examples covering common LLM application patterns.

    Args:
        base_time: Base timestamp for traces. Defaults to current UTC time.

    Returns:
        List of AgentRun objects with realistic sample data.

    Example:
        >>> from tracecraft.core.fixtures import generate_sample_traces
        >>> traces = generate_sample_traces()
        >>> len(traces)
        20
    """
    if base_time is None:
        base_time = datetime.now(UTC)

    traces: list[AgentRun] = []

    # =========================================================================
    # TRACE 1: Simple GPT-4o Chat
    # =========================================================================
    t1_id = uuid4()
    traces.append(
        AgentRun(
            id=t1_id,
            name="chat_completion",
            description="Simple question-answer with GPT-4o",
            start_time=base_time - timedelta(hours=6),
            duration_ms=1523.5,
            total_tokens=847,
            total_cost_usd=0.0127,
            tags=["chat", "openai"],
            steps=[
                Step(
                    trace_id=t1_id,
                    type=StepType.LLM,
                    name="gpt-4o",
                    start_time=base_time - timedelta(hours=6),
                    duration_ms=1523.5,
                    model_name="gpt-4o",
                    model_provider="openai",
                    input_tokens=312,
                    output_tokens=535,
                    cost_usd=0.0127,
                    inputs={
                        "messages": [
                            {"role": "system", "content": "You are a helpful assistant."},
                            {
                                "role": "user",
                                "content": "Explain quantum computing in simple terms.",
                            },
                        ]
                    },
                    outputs={
                        "content": "Quantum computing harnesses quantum mechanics to process "
                        "information differently than classical computers. While traditional "
                        "computers use bits (0 or 1), quantum computers use qubits that can "
                        "exist in multiple states simultaneously through superposition."
                    },
                )
            ],
        )
    )

    # =========================================================================
    # TRACE 2: Claude Sonnet with System Prompt
    # =========================================================================
    t2_id = uuid4()
    traces.append(
        AgentRun(
            id=t2_id,
            name="code_review",
            description="Code review with Claude 3.5 Sonnet",
            start_time=base_time - timedelta(hours=5, minutes=30),
            duration_ms=4821.3,
            total_tokens=2456,
            total_cost_usd=0.0221,
            tags=["code", "anthropic", "review"],
            steps=[
                Step(
                    trace_id=t2_id,
                    type=StepType.LLM,
                    name="claude-3-5-sonnet",
                    start_time=base_time - timedelta(hours=5, minutes=30),
                    duration_ms=4821.3,
                    model_name="claude-3-5-sonnet-20241022",
                    model_provider="anthropic",
                    input_tokens=1856,
                    output_tokens=600,
                    cost_usd=0.0221,
                    inputs={
                        "system": "You are an expert code reviewer.",
                        "messages": [
                            {
                                "role": "user",
                                "content": "Review this Python function:\n\n"
                                'def process_user(data):\n    query = f"SELECT * FROM '
                                "users WHERE id = {data['id']}\"\n    return db.execute(query)",
                            }
                        ],
                    },
                    outputs={
                        "content": "CRITICAL: SQL Injection vulnerability detected. "
                        "Use parameterized queries instead."
                    },
                )
            ],
        )
    )

    # =========================================================================
    # TRACE 3: RAG Pipeline with Vector Search
    # =========================================================================
    t3_id = uuid4()
    traces.append(
        AgentRun(
            id=t3_id,
            name="rag_financial_query",
            description="RAG query for financial data",
            start_time=base_time - timedelta(hours=5),
            duration_ms=3421.8,
            total_tokens=3156,
            total_cost_usd=0.0315,
            tags=["rag", "finance", "retrieval"],
            steps=[
                Step(
                    trace_id=t3_id,
                    type=StepType.RETRIEVAL,
                    name="vector_search",
                    start_time=base_time - timedelta(hours=5),
                    duration_ms=245.3,
                    inputs={"query": "Q3 2024 revenue breakdown by region", "top_k": 5},
                    outputs={
                        "num_results": 5,
                        "chunks": [
                            "North America revenue: $45.2M (+12% YoY)",
                            "EMEA revenue: $28.7M (+8% YoY)",
                            "APAC revenue: $18.3M (+22% YoY)",
                        ],
                    },
                    attributes={"vector_db": "pinecone", "similarity": "cosine"},
                ),
                Step(
                    trace_id=t3_id,
                    type=StepType.LLM,
                    name="synthesis",
                    start_time=base_time - timedelta(hours=5) + timedelta(milliseconds=250),
                    duration_ms=3176.5,
                    model_name="claude-3-5-sonnet-20241022",
                    model_provider="anthropic",
                    input_tokens=2456,
                    output_tokens=700,
                    cost_usd=0.0315,
                    inputs={
                        "system": "Synthesize financial data into a clear summary.",
                        "context": "[Retrieved chunks about Q3 revenue]",
                    },
                    outputs={
                        "content": "Q3 2024 Total Revenue: $92.2M (+13.3% YoY). "
                        "APAC showed strongest growth at 22%."
                    },
                ),
            ],
        )
    )

    # =========================================================================
    # TRACE 4: Research Agent with Multiple Tools
    # =========================================================================
    t4_id = uuid4()
    traces.append(
        AgentRun(
            id=t4_id,
            name="research_agent",
            description="AI research agent with web search and analysis",
            agent_name="ResearchAgent",
            agent_id="research-v2",
            start_time=base_time - timedelta(hours=4),
            duration_ms=15734.2,
            total_tokens=8523,
            total_cost_usd=0.1278,
            tags=["agent", "research", "tools"],
            steps=[
                Step(
                    trace_id=t4_id,
                    type=StepType.AGENT,
                    name="research_coordinator",
                    start_time=base_time - timedelta(hours=4),
                    duration_ms=15734.2,
                    children=[
                        Step(
                            trace_id=t4_id,
                            type=StepType.LLM,
                            name="planning",
                            start_time=base_time - timedelta(hours=4),
                            duration_ms=1200.0,
                            model_name="gpt-4o",
                            model_provider="openai",
                            input_tokens=500,
                            output_tokens=350,
                            cost_usd=0.0125,
                            inputs={"task": "Research latest developments in AI safety"},
                            outputs={
                                "plan": "1. Search recent papers 2. Analyze trends 3. Synthesize"
                            },
                        ),
                        Step(
                            trace_id=t4_id,
                            type=StepType.TOOL,
                            name="web_search",
                            start_time=base_time - timedelta(hours=4) + timedelta(seconds=2),
                            duration_ms=2500.0,
                            inputs={"query": "AI safety research 2024 papers"},
                            outputs={"results": 10, "sources": ["arxiv", "openai", "anthropic"]},
                        ),
                        Step(
                            trace_id=t4_id,
                            type=StepType.TOOL,
                            name="web_search",
                            start_time=base_time - timedelta(hours=4) + timedelta(seconds=5),
                            duration_ms=1800.0,
                            inputs={"query": "constitutional AI RLHF alignment"},
                            outputs={"results": 8},
                        ),
                        Step(
                            trace_id=t4_id,
                            type=StepType.TOOL,
                            name="fetch_url",
                            start_time=base_time - timedelta(hours=4) + timedelta(seconds=7),
                            duration_ms=3200.0,
                            inputs={"url": "https://arxiv.org/abs/2024.12345"},
                            outputs={"title": "Scalable Oversight Methods", "abstract": "..."},
                        ),
                        Step(
                            trace_id=t4_id,
                            type=StepType.LLM,
                            name="analysis",
                            start_time=base_time - timedelta(hours=4) + timedelta(seconds=11),
                            duration_ms=3800.0,
                            model_name="gpt-4o",
                            model_provider="openai",
                            input_tokens=4500,
                            output_tokens=1200,
                            cost_usd=0.0678,
                        ),
                        Step(
                            trace_id=t4_id,
                            type=StepType.LLM,
                            name="synthesis",
                            start_time=base_time - timedelta(hours=4) + timedelta(seconds=15),
                            duration_ms=3234.2,
                            model_name="gpt-4o",
                            model_provider="openai",
                            input_tokens=1523,
                            output_tokens=450,
                            cost_usd=0.0475,
                            outputs={
                                "summary": "Key AI safety trends: 1) Constitutional AI advances "
                                "2) Scalable oversight 3) Interpretability breakthroughs"
                            },
                        ),
                    ],
                )
            ],
        )
    )

    # =========================================================================
    # TRACE 5: Code Generation Agent
    # =========================================================================
    t5_id = uuid4()
    traces.append(
        AgentRun(
            id=t5_id,
            name="code_gen_agent",
            description="Code generation with execution",
            agent_name="CodeAgent",
            start_time=base_time - timedelta(hours=3, minutes=30),
            duration_ms=22456.7,
            total_tokens=12934,
            total_cost_usd=0.1934,
            tags=["agent", "code", "execution"],
            steps=[
                Step(
                    trace_id=t5_id,
                    type=StepType.AGENT,
                    name="code_assistant",
                    start_time=base_time - timedelta(hours=3, minutes=30),
                    duration_ms=22456.7,
                    children=[
                        Step(
                            trace_id=t5_id,
                            type=StepType.LLM,
                            name="generate_code",
                            start_time=base_time - timedelta(hours=3, minutes=30),
                            duration_ms=3200.0,
                            model_name="claude-3-5-sonnet-20241022",
                            model_provider="anthropic",
                            input_tokens=1200,
                            output_tokens=600,
                            cost_usd=0.0162,
                        ),
                        Step(
                            trace_id=t5_id,
                            type=StepType.TOOL,
                            name="code_execute",
                            start_time=base_time
                            - timedelta(hours=3, minutes=30)
                            + timedelta(seconds=4),
                            duration_ms=856.2,
                            inputs={"code": "merge_sorted([1,3,5], [2,4,6])"},
                            outputs={"result": "[1, 2, 3, 4, 5, 6]", "exit_code": 0},
                        ),
                        Step(
                            trace_id=t5_id,
                            type=StepType.EVALUATION,
                            name="code_quality",
                            start_time=base_time
                            - timedelta(hours=3, minutes=30)
                            + timedelta(seconds=6),
                            duration_ms=1866.0,
                            model_name="gpt-4o",
                            model_provider="openai",
                            input_tokens=2000,
                            output_tokens=300,
                            cost_usd=0.0245,
                            outputs={"quality_score": 0.95, "time_complexity": "O(n+m)"},
                        ),
                    ],
                )
            ],
        )
    )

    # =========================================================================
    # TRACE 6: Customer Support Agent with Memory
    # =========================================================================
    t6_id = uuid4()
    traces.append(
        AgentRun(
            id=t6_id,
            name="support_agent",
            description="Customer support with memory",
            agent_name="SupportBot",
            session_id="session_abc123",
            user_id="user_42",
            start_time=base_time - timedelta(hours=3),
            duration_ms=9823.4,
            total_tokens=5678,
            total_cost_usd=0.0851,
            tags=["agent", "support", "memory"],
            steps=[
                Step(
                    trace_id=t6_id,
                    type=StepType.AGENT,
                    name="support_coordinator",
                    start_time=base_time - timedelta(hours=3),
                    duration_ms=9823.4,
                    children=[
                        Step(
                            trace_id=t6_id,
                            type=StepType.MEMORY,
                            name="load_context",
                            start_time=base_time - timedelta(hours=3),
                            duration_ms=123.4,
                            inputs={"user_id": "user_42"},
                            outputs={"previous_tickets": 3, "tier": "premium"},
                        ),
                        Step(
                            trace_id=t6_id,
                            type=StepType.LLM,
                            name="understand_intent",
                            start_time=base_time - timedelta(hours=3) + timedelta(milliseconds=150),
                            duration_ms=1200.0,
                            model_name="gpt-4o-mini",
                            model_provider="openai",
                            input_tokens=600,
                            output_tokens=150,
                            cost_usd=0.0011,
                        ),
                        Step(
                            trace_id=t6_id,
                            type=StepType.TOOL,
                            name="db_query",
                            start_time=base_time - timedelta(hours=3) + timedelta(seconds=2),
                            duration_ms=234.5,
                            outputs={"order_id": "ORD-78923", "status": "in_transit"},
                        ),
                        Step(
                            trace_id=t6_id,
                            type=StepType.GUARDRAIL,
                            name="tone_check",
                            start_time=base_time - timedelta(hours=3) + timedelta(seconds=5),
                            duration_ms=156.0,
                            outputs={"passed": True, "tone_score": 0.92},
                        ),
                    ],
                )
            ],
        )
    )

    # =========================================================================
    # TRACE 7: Multi-Agent Orchestration
    # =========================================================================
    t7_id = uuid4()
    traces.append(
        AgentRun(
            id=t7_id,
            name="multi_agent_report",
            description="Multi-agent report generation",
            agent_name="OrchestratorAgent",
            start_time=base_time - timedelta(hours=2, minutes=30),
            duration_ms=45678.9,
            total_tokens=28456,
            total_cost_usd=0.4267,
            tags=["multi-agent", "orchestration"],
            steps=[
                Step(
                    trace_id=t7_id,
                    type=StepType.AGENT,
                    name="orchestrator",
                    start_time=base_time - timedelta(hours=2, minutes=30),
                    duration_ms=45678.9,
                    children=[
                        Step(
                            trace_id=t7_id,
                            type=StepType.LLM,
                            name="task_decomposition",
                            start_time=base_time - timedelta(hours=2, minutes=30),
                            duration_ms=2500.0,
                            model_name="gpt-4o",
                            model_provider="openai",
                            input_tokens=1200,
                            output_tokens=800,
                            cost_usd=0.032,
                        ),
                        Step(
                            trace_id=t7_id,
                            type=StepType.AGENT,
                            name="data_collector",
                            start_time=base_time
                            - timedelta(hours=2, minutes=30)
                            + timedelta(seconds=3),
                            duration_ms=12000.0,
                        ),
                        Step(
                            trace_id=t7_id,
                            type=StepType.AGENT,
                            name="competitor_analyst",
                            start_time=base_time
                            - timedelta(hours=2, minutes=30)
                            + timedelta(seconds=3),
                            duration_ms=15000.0,
                        ),
                        Step(
                            trace_id=t7_id,
                            type=StepType.EVALUATION,
                            name="quality_review",
                            start_time=base_time
                            - timedelta(hours=2, minutes=30)
                            + timedelta(seconds=30),
                            duration_ms=3500.0,
                            model_name="gpt-4o",
                            model_provider="openai",
                            outputs={"quality_score": 0.94},
                        ),
                    ],
                )
            ],
        )
    )

    # =========================================================================
    # TRACE 8: Rate Limit Error
    # =========================================================================
    t8_id = uuid4()
    traces.append(
        AgentRun(
            id=t8_id,
            name="failed_generation",
            description="Request failed due to rate limit",
            start_time=base_time - timedelta(hours=2),
            duration_ms=523.1,
            total_tokens=150,
            error="RateLimitError: Rate limit exceeded",
            error_count=1,
            tags=["error", "rate-limit"],
            steps=[
                Step(
                    trace_id=t8_id,
                    type=StepType.LLM,
                    name="gpt-4o",
                    start_time=base_time - timedelta(hours=2),
                    duration_ms=523.1,
                    model_name="gpt-4o",
                    model_provider="openai",
                    input_tokens=150,
                    output_tokens=0,
                    error="RateLimitError: Rate limit exceeded",
                    error_type="RateLimitError",
                )
            ],
        )
    )

    # =========================================================================
    # TRACE 9: Validation Retry
    # =========================================================================
    t9_id = uuid4()
    traces.append(
        AgentRun(
            id=t9_id,
            name="structured_output_retry",
            description="Structured output with validation retry",
            start_time=base_time - timedelta(hours=1, minutes=45),
            duration_ms=6234.5,
            total_tokens=3200,
            total_cost_usd=0.048,
            error_count=1,
            tags=["structured", "validation", "retry"],
            steps=[
                Step(
                    trace_id=t9_id,
                    type=StepType.LLM,
                    name="generate_json_attempt_1",
                    start_time=base_time - timedelta(hours=1, minutes=45),
                    duration_ms=2100.0,
                    model_name="gpt-4o-mini",
                    model_provider="openai",
                    error="ValidationError: Missing required field",
                    error_type="ValidationError",
                ),
                Step(
                    trace_id=t9_id,
                    type=StepType.GUARDRAIL,
                    name="schema_validation",
                    start_time=base_time - timedelta(hours=1, minutes=45) + timedelta(seconds=3),
                    duration_ms=34.5,
                    outputs={"passed": False, "missing_fields": ["email"]},
                ),
                Step(
                    trace_id=t9_id,
                    type=StepType.LLM,
                    name="generate_json_attempt_2",
                    start_time=base_time - timedelta(hours=1, minutes=45) + timedelta(seconds=4),
                    duration_ms=2300.0,
                    model_name="gpt-4o-mini",
                    model_provider="openai",
                ),
                Step(
                    trace_id=t9_id,
                    type=StepType.GUARDRAIL,
                    name="schema_validation",
                    start_time=base_time - timedelta(hours=1, minutes=45) + timedelta(seconds=7),
                    duration_ms=28.0,
                    outputs={"passed": True},
                ),
            ],
        )
    )

    # =========================================================================
    # TRACE 10: Content Moderation
    # =========================================================================
    t10_id = uuid4()
    traces.append(
        AgentRun(
            id=t10_id,
            name="content_moderation",
            description="Content moderation pipeline",
            start_time=base_time - timedelta(hours=1, minutes=30),
            duration_ms=4567.8,
            total_tokens=2100,
            total_cost_usd=0.0315,
            tags=["moderation", "guardrail", "safety"],
            steps=[
                Step(
                    trace_id=t10_id,
                    type=StepType.WORKFLOW,
                    name="moderation_pipeline",
                    start_time=base_time - timedelta(hours=1, minutes=30),
                    duration_ms=4567.8,
                    children=[
                        Step(
                            trace_id=t10_id,
                            type=StepType.GUARDRAIL,
                            name="toxicity_check",
                            start_time=base_time - timedelta(hours=1, minutes=30),
                            duration_ms=234.5,
                            outputs={"passed": True, "toxicity_score": 0.02},
                        ),
                        Step(
                            trace_id=t10_id,
                            type=StepType.GUARDRAIL,
                            name="pii_detection",
                            start_time=base_time
                            - timedelta(hours=1, minutes=30)
                            + timedelta(milliseconds=300),
                            duration_ms=156.0,
                            outputs={"passed": True, "pii_found": []},
                        ),
                        Step(
                            trace_id=t10_id,
                            type=StepType.LLM,
                            name="generate_response",
                            start_time=base_time
                            - timedelta(hours=1, minutes=30)
                            + timedelta(seconds=1),
                            duration_ms=2800.0,
                            model_name="gpt-4o",
                            model_provider="openai",
                        ),
                    ],
                )
            ],
        )
    )

    # =========================================================================
    # TRACE 11: Streaming Content
    # =========================================================================
    t11_id = uuid4()
    traces.append(
        AgentRun(
            id=t11_id,
            name="blog_generation",
            description="Streaming blog post generation",
            start_time=base_time - timedelta(hours=1),
            duration_ms=18234.5,
            total_tokens=6500,
            total_cost_usd=0.0975,
            tags=["streaming", "content"],
            steps=[
                Step(
                    trace_id=t11_id,
                    type=StepType.LLM,
                    name="content_generation",
                    start_time=base_time - timedelta(hours=1),
                    duration_ms=15734.5,
                    model_name="claude-3-5-sonnet-20241022",
                    model_provider="anthropic",
                    input_tokens=1200,
                    output_tokens=4400,
                    is_streaming=True,
                )
            ],
        )
    )

    # =========================================================================
    # TRACE 12: Azure OpenAI
    # =========================================================================
    t12_id = uuid4()
    traces.append(
        AgentRun(
            id=t12_id,
            name="azure_enterprise_chat",
            description="Enterprise chat via Azure OpenAI",
            cloud_provider="azure",
            start_time=base_time - timedelta(minutes=45),
            duration_ms=3456.7,
            total_tokens=1850,
            total_cost_usd=0.0278,
            tags=["azure", "enterprise"],
            steps=[
                Step(
                    trace_id=t12_id,
                    type=StepType.LLM,
                    name="gpt-4-deployment",
                    start_time=base_time - timedelta(minutes=45),
                    duration_ms=3456.7,
                    model_name="gpt-4",
                    model_provider="azure",
                    attributes={"azure_deployment": "gpt-4-east-us"},
                )
            ],
        )
    )

    # =========================================================================
    # TRACE 13: AWS Bedrock
    # =========================================================================
    t13_id = uuid4()
    traces.append(
        AgentRun(
            id=t13_id,
            name="bedrock_analysis",
            description="Document analysis via AWS Bedrock",
            cloud_provider="aws",
            start_time=base_time - timedelta(minutes=30),
            duration_ms=5678.9,
            total_tokens=3200,
            total_cost_usd=0.048,
            tags=["aws", "bedrock"],
            steps=[
                Step(
                    trace_id=t13_id,
                    type=StepType.RETRIEVAL,
                    name="s3_document_load",
                    start_time=base_time - timedelta(minutes=30),
                    duration_ms=1200.0,
                    inputs={"bucket": "company-docs", "key": "reports/annual-2024.pdf"},
                ),
                Step(
                    trace_id=t13_id,
                    type=StepType.LLM,
                    name="claude-3-sonnet",
                    start_time=base_time - timedelta(minutes=30) + timedelta(seconds=2),
                    duration_ms=4478.9,
                    model_name="anthropic.claude-3-sonnet-20240229-v1:0",
                    model_provider="bedrock",
                ),
            ],
        )
    )

    # =========================================================================
    # TRACE 14: GCP Vertex AI
    # =========================================================================
    t14_id = uuid4()
    traces.append(
        AgentRun(
            id=t14_id,
            name="vertex_multimodal",
            description="Multimodal analysis via Vertex AI",
            cloud_provider="gcp",
            start_time=base_time - timedelta(minutes=20),
            duration_ms=4234.5,
            total_tokens=2800,
            total_cost_usd=0.042,
            tags=["gcp", "vertex", "gemini"],
            steps=[
                Step(
                    trace_id=t14_id,
                    type=StepType.LLM,
                    name="gemini-1.5-pro",
                    start_time=base_time - timedelta(minutes=20),
                    duration_ms=4234.5,
                    model_name="gemini-1.5-pro",
                    model_provider="vertex",
                )
            ],
        )
    )

    # =========================================================================
    # TRACE 15: Timeout Error
    # =========================================================================
    t15_id = uuid4()
    traces.append(
        AgentRun(
            id=t15_id,
            name="timeout_failure",
            description="Request timed out",
            start_time=base_time - timedelta(minutes=15),
            duration_ms=30000.0,
            total_tokens=500,
            error="TimeoutError: Request timed out after 30s",
            error_count=1,
            tags=["error", "timeout"],
            steps=[
                Step(
                    trace_id=t15_id,
                    type=StepType.LLM,
                    name="gpt-4o",
                    start_time=base_time - timedelta(minutes=15),
                    duration_ms=30000.0,
                    model_name="gpt-4o",
                    model_provider="openai",
                    error="TimeoutError: Request timed out",
                    error_type="TimeoutError",
                )
            ],
        )
    )

    # =========================================================================
    # TRACE 16: Document Processing
    # =========================================================================
    t16_id = uuid4()
    traces.append(
        AgentRun(
            id=t16_id,
            name="document_processing",
            description="Document processing pipeline",
            start_time=base_time - timedelta(minutes=10),
            duration_ms=28456.7,
            total_tokens=15934,
            total_cost_usd=0.2391,
            tags=["workflow", "document"],
            steps=[
                Step(
                    trace_id=t16_id,
                    type=StepType.WORKFLOW,
                    name="document_pipeline",
                    start_time=base_time - timedelta(minutes=10),
                    duration_ms=28456.7,
                    children=[
                        Step(
                            trace_id=t16_id,
                            type=StepType.RETRIEVAL,
                            name="document_load",
                            start_time=base_time - timedelta(minutes=10),
                            duration_ms=856.2,
                        ),
                        Step(
                            trace_id=t16_id,
                            type=StepType.LLM,
                            name="entity_extraction",
                            start_time=base_time - timedelta(minutes=10) + timedelta(seconds=1),
                            duration_ms=4500.0,
                            model_name="claude-3-5-sonnet-20241022",
                            model_provider="anthropic",
                        ),
                        Step(
                            trace_id=t16_id,
                            type=StepType.GUARDRAIL,
                            name="compliance_check",
                            start_time=base_time - timedelta(minutes=10) + timedelta(seconds=6),
                            duration_ms=234.5,
                            outputs={"passed": True},
                        ),
                    ],
                )
            ],
        )
    )

    # =========================================================================
    # TRACE 17: Embedding Batch
    # =========================================================================
    t17_id = uuid4()
    traces.append(
        AgentRun(
            id=t17_id,
            name="embedding_batch",
            description="Batch embedding generation",
            start_time=base_time - timedelta(minutes=5),
            duration_ms=1234.5,
            total_tokens=2400,
            total_cost_usd=0.00024,
            tags=["embedding", "batch"],
            steps=[
                Step(
                    trace_id=t17_id,
                    type=StepType.LLM,
                    name="text-embedding-3-small",
                    start_time=base_time - timedelta(minutes=5),
                    duration_ms=1234.5,
                    model_name="text-embedding-3-small",
                    model_provider="openai",
                    input_tokens=2400,
                    output_tokens=0,
                )
            ],
        )
    )

    # =========================================================================
    # TRACE 18: Chat with Tools
    # =========================================================================
    t18_id = uuid4()
    traces.append(
        AgentRun(
            id=t18_id,
            name="chat_with_tools",
            description="Chat with calculator and weather",
            session_id="chat_session_xyz",
            start_time=base_time - timedelta(minutes=3),
            duration_ms=4567.8,
            total_tokens=1800,
            total_cost_usd=0.027,
            tags=["chat", "tools"],
            steps=[
                Step(
                    trace_id=t18_id,
                    type=StepType.LLM,
                    name="tool_selection",
                    start_time=base_time - timedelta(minutes=3),
                    duration_ms=1200.0,
                    model_name="gpt-4o",
                    model_provider="openai",
                ),
                Step(
                    trace_id=t18_id,
                    type=StepType.TOOL,
                    name="calculator",
                    start_time=base_time - timedelta(minutes=3) + timedelta(seconds=2),
                    duration_ms=50.0,
                    inputs={"expression": "85.50 * 0.15"},
                    outputs={"result": 12.825},
                ),
                Step(
                    trace_id=t18_id,
                    type=StepType.TOOL,
                    name="weather",
                    start_time=base_time - timedelta(minutes=3) + timedelta(seconds=2),
                    duration_ms=800.0,
                    outputs={"temperature": "45F"},
                ),
            ],
        )
    )

    # =========================================================================
    # TRACE 19: Claude Opus
    # =========================================================================
    t19_id = uuid4()
    traces.append(
        AgentRun(
            id=t19_id,
            name="deep_analysis",
            description="Complex reasoning with Claude Opus",
            start_time=base_time - timedelta(minutes=2),
            duration_ms=45678.9,
            total_tokens=18500,
            total_cost_usd=0.5550,
            tags=["opus", "expensive"],
            steps=[
                Step(
                    trace_id=t19_id,
                    type=StepType.LLM,
                    name="claude-opus",
                    start_time=base_time - timedelta(minutes=2),
                    duration_ms=45678.9,
                    model_name="claude-opus-4-20250514",
                    model_provider="anthropic",
                    input_tokens=12000,
                    output_tokens=6500,
                    cost_usd=0.5550,
                )
            ],
        )
    )

    # =========================================================================
    # TRACE 20: Quick Response
    # =========================================================================
    t20_id = uuid4()
    traces.append(
        AgentRun(
            id=t20_id,
            name="quick_answer",
            description="Fast response with GPT-4o-mini",
            start_time=base_time - timedelta(minutes=1),
            duration_ms=456.7,
            total_tokens=180,
            total_cost_usd=0.00027,
            tags=["fast", "cheap"],
            steps=[
                Step(
                    trace_id=t20_id,
                    type=StepType.LLM,
                    name="gpt-4o-mini",
                    start_time=base_time - timedelta(minutes=1),
                    duration_ms=456.7,
                    model_name="gpt-4o-mini",
                    model_provider="openai",
                    input_tokens=80,
                    output_tokens=100,
                    cost_usd=0.00027,
                )
            ],
        )
    )

    return traces


# Backwards compatibility alias
generate_example_traces = generate_sample_traces
