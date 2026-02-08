"""
Framework integration tests for OTLP Receiver.

Tests that validate trace structures produced by popular AI frameworks
are correctly parsed and stored. Uses simulated OTLP payloads that match
actual framework output patterns.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from tracecraft.core.models import StepType
from tracecraft.receiver.server import OTLPReceiverServer
from tracecraft.storage.jsonl import JSONLTraceStore


@pytest.mark.integration
class TestPydanticAIIntegration:
    """
    Test receiving traces from PydanticAI with OTel instrumentation.

    PydanticAI traces typically have:
    - Root span for agent run with gen_ai.agent.name
    - Child LLM spans with gen_ai.request.model
    - Tool call spans with tool.name when tools are used
    """

    def test_receive_pydantic_ai_agent_trace(self) -> None:
        """PydanticAI agent run produces valid AgentRun in storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JSONLTraceStore(Path(tmpdir) / "traces.jsonl")
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=0)
            client = TestClient(server._create_app())

            # Simulate PydanticAI trace structure
            otlp_json = {
                "resourceSpans": [
                    {
                        "resource": {
                            "attributes": [
                                {
                                    "key": "service.name",
                                    "value": {"stringValue": "pydantic-ai-app"},
                                },
                                {
                                    "key": "telemetry.sdk.name",
                                    "value": {"stringValue": "opentelemetry"},
                                },
                            ]
                        },
                        "scopeSpans": [
                            {
                                "scope": {"name": "pydantic-ai"},
                                "spans": [
                                    {
                                        "traceId": "aabbccdd11223344aabbccdd11223344",
                                        "spanId": "1111111111111111",
                                        "name": "pydantic_ai.agent.run",
                                        "kind": 1,
                                        "startTimeUnixNano": "1704067200000000000",
                                        "endTimeUnixNano": "1704067210000000000",
                                        "attributes": [
                                            {
                                                "key": "gen_ai.agent.name",
                                                "value": {"stringValue": "CustomerSupportAgent"},
                                            },
                                            {
                                                "key": "gen_ai.system",
                                                "value": {"stringValue": "openai"},
                                            },
                                        ],
                                    },
                                    {
                                        "traceId": "aabbccdd11223344aabbccdd11223344",
                                        "spanId": "2222222222222222",
                                        "parentSpanId": "1111111111111111",
                                        "name": "gpt-4",
                                        "kind": 3,
                                        "startTimeUnixNano": "1704067201000000000",
                                        "endTimeUnixNano": "1704067205000000000",
                                        "attributes": [
                                            {
                                                "key": "gen_ai.request.model",
                                                "value": {"stringValue": "gpt-4"},
                                            },
                                            {
                                                "key": "gen_ai.system",
                                                "value": {"stringValue": "openai"},
                                            },
                                            {
                                                "key": "gen_ai.usage.input_tokens",
                                                "value": {"intValue": "150"},
                                            },
                                            {
                                                "key": "gen_ai.usage.output_tokens",
                                                "value": {"intValue": "75"},
                                            },
                                        ],
                                    },
                                ],
                            }
                        ],
                    }
                ]
            }

            response = client.post("/v1/traces", json=otlp_json)
            assert response.status_code == 200

            store.invalidate_cache()
            traces = store.list_all()
            assert len(traces) == 1

            trace = traces[0]
            assert trace.agent_name == "CustomerSupportAgent"
            assert trace.total_tokens == 225  # 150 + 75

    def test_pydantic_ai_tool_calls_as_steps(self) -> None:
        """PydanticAI tool calls appear as TOOL steps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JSONLTraceStore(Path(tmpdir) / "traces.jsonl")
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=0)
            client = TestClient(server._create_app())

            otlp_json = {
                "resourceSpans": [
                    {
                        "resource": {"attributes": []},
                        "scopeSpans": [
                            {
                                "spans": [
                                    {
                                        "traceId": "aabbccdd11223344aabbccdd11223344",
                                        "spanId": "1111111111111111",
                                        "name": "agent_run",
                                        "startTimeUnixNano": "1704067200000000000",
                                        "endTimeUnixNano": "1704067210000000000",
                                        "attributes": [
                                            {
                                                "key": "gen_ai.agent.name",
                                                "value": {"stringValue": "ToolAgent"},
                                            },
                                        ],
                                    },
                                    {
                                        "traceId": "aabbccdd11223344aabbccdd11223344",
                                        "spanId": "2222222222222222",
                                        "parentSpanId": "1111111111111111",
                                        "name": "search_database",
                                        "startTimeUnixNano": "1704067201000000000",
                                        "endTimeUnixNano": "1704067202000000000",
                                        "attributes": [
                                            {
                                                "key": "tool.name",
                                                "value": {"stringValue": "search_database"},
                                            },
                                            {
                                                "key": "tool.parameters",
                                                "value": {
                                                    "stringValue": '{"query": "customer orders"}'
                                                },
                                            },
                                        ],
                                    },
                                    {
                                        "traceId": "aabbccdd11223344aabbccdd11223344",
                                        "spanId": "3333333333333333",
                                        "parentSpanId": "1111111111111111",
                                        "name": "gpt-4",
                                        "startTimeUnixNano": "1704067203000000000",
                                        "endTimeUnixNano": "1704067205000000000",
                                        "attributes": [
                                            {
                                                "key": "gen_ai.request.model",
                                                "value": {"stringValue": "gpt-4"},
                                            },
                                        ],
                                    },
                                ],
                            }
                        ],
                    }
                ]
            }

            response = client.post("/v1/traces", json=otlp_json)
            assert response.status_code == 200

            store.invalidate_cache()
            traces = store.list_all()
            trace = traces[0]

            # Find the tool step
            tool_steps = [s for s in trace.steps[0].children if s.type == StepType.TOOL]
            assert len(tool_steps) == 1
            assert tool_steps[0].name == "search_database"

    def test_pydantic_ai_llm_attributes(self) -> None:
        """LLM model/tokens captured from PydanticAI spans."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JSONLTraceStore(Path(tmpdir) / "traces.jsonl")
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=0)
            client = TestClient(server._create_app())

            otlp_json = {
                "resourceSpans": [
                    {
                        "resource": {"attributes": []},
                        "scopeSpans": [
                            {
                                "spans": [
                                    {
                                        "traceId": "aabbccdd11223344aabbccdd11223344",
                                        "spanId": "1111111111111111",
                                        "name": "claude-3-opus",
                                        "startTimeUnixNano": "1704067200000000000",
                                        "endTimeUnixNano": "1704067205000000000",
                                        "attributes": [
                                            {
                                                "key": "gen_ai.request.model",
                                                "value": {"stringValue": "claude-3-opus-20240229"},
                                            },
                                            {
                                                "key": "gen_ai.system",
                                                "value": {"stringValue": "anthropic"},
                                            },
                                            {
                                                "key": "gen_ai.usage.input_tokens",
                                                "value": {"intValue": "1000"},
                                            },
                                            {
                                                "key": "gen_ai.usage.output_tokens",
                                                "value": {"intValue": "500"},
                                            },
                                            {
                                                "key": "gen_ai.usage.cost",
                                                "value": {"doubleValue": 0.0375},
                                            },
                                        ],
                                    },
                                ],
                            }
                        ],
                    }
                ]
            }

            response = client.post("/v1/traces", json=otlp_json)
            assert response.status_code == 200

            store.invalidate_cache()
            traces = store.list_all()
            step = traces[0].steps[0]

            assert step.model_name == "claude-3-opus-20240229"
            assert step.model_provider == "anthropic"
            assert step.input_tokens == 1000
            assert step.output_tokens == 500
            assert step.cost_usd == pytest.approx(0.0375)


@pytest.mark.integration
class TestLangGraphIntegration:
    """
    Test receiving traces from LangGraph with OTel instrumentation.

    LangGraph traces typically have:
    - Root span for graph execution
    - Node spans for each graph node
    - LLM spans nested under nodes that make LLM calls
    """

    def test_receive_langgraph_workflow_trace(self) -> None:
        """LangGraph workflow produces multi-step AgentRun."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JSONLTraceStore(Path(tmpdir) / "traces.jsonl")
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=0)
            client = TestClient(server._create_app())

            # Simulate LangGraph workflow with multiple nodes
            otlp_json = {
                "resourceSpans": [
                    {
                        "resource": {
                            "attributes": [
                                {"key": "service.name", "value": {"stringValue": "langgraph-app"}},
                            ]
                        },
                        "scopeSpans": [
                            {
                                "scope": {"name": "langgraph"},
                                "spans": [
                                    {
                                        "traceId": "11112222333344445555666677778888",
                                        "spanId": "0000000000000001",
                                        "name": "ResearchGraph.invoke",
                                        "startTimeUnixNano": "1704067200000000000",
                                        "endTimeUnixNano": "1704067220000000000",
                                        "attributes": [
                                            {
                                                "key": "langgraph.graph.name",
                                                "value": {"stringValue": "ResearchGraph"},
                                            },
                                        ],
                                    },
                                    {
                                        "traceId": "11112222333344445555666677778888",
                                        "spanId": "0000000000000002",
                                        "parentSpanId": "0000000000000001",
                                        "name": "researcher_node",
                                        "startTimeUnixNano": "1704067201000000000",
                                        "endTimeUnixNano": "1704067210000000000",
                                        "attributes": [
                                            {
                                                "key": "langgraph.node.name",
                                                "value": {"stringValue": "researcher_node"},
                                            },
                                        ],
                                    },
                                    {
                                        "traceId": "11112222333344445555666677778888",
                                        "spanId": "0000000000000003",
                                        "parentSpanId": "0000000000000002",
                                        "name": "gpt-4-turbo",
                                        "startTimeUnixNano": "1704067202000000000",
                                        "endTimeUnixNano": "1704067208000000000",
                                        "attributes": [
                                            {
                                                "key": "gen_ai.request.model",
                                                "value": {"stringValue": "gpt-4-turbo"},
                                            },
                                            {
                                                "key": "gen_ai.usage.input_tokens",
                                                "value": {"intValue": "200"},
                                            },
                                            {
                                                "key": "gen_ai.usage.output_tokens",
                                                "value": {"intValue": "100"},
                                            },
                                        ],
                                    },
                                    {
                                        "traceId": "11112222333344445555666677778888",
                                        "spanId": "0000000000000004",
                                        "parentSpanId": "0000000000000001",
                                        "name": "writer_node",
                                        "startTimeUnixNano": "1704067211000000000",
                                        "endTimeUnixNano": "1704067219000000000",
                                        "attributes": [
                                            {
                                                "key": "langgraph.node.name",
                                                "value": {"stringValue": "writer_node"},
                                            },
                                        ],
                                    },
                                    {
                                        "traceId": "11112222333344445555666677778888",
                                        "spanId": "0000000000000005",
                                        "parentSpanId": "0000000000000004",
                                        "name": "gpt-4-turbo",
                                        "startTimeUnixNano": "1704067212000000000",
                                        "endTimeUnixNano": "1704067218000000000",
                                        "attributes": [
                                            {
                                                "key": "gen_ai.request.model",
                                                "value": {"stringValue": "gpt-4-turbo"},
                                            },
                                            {
                                                "key": "gen_ai.usage.input_tokens",
                                                "value": {"intValue": "300"},
                                            },
                                            {
                                                "key": "gen_ai.usage.output_tokens",
                                                "value": {"intValue": "150"},
                                            },
                                        ],
                                    },
                                ],
                            }
                        ],
                    }
                ]
            }

            response = client.post("/v1/traces", json=otlp_json)
            assert response.status_code == 200

            store.invalidate_cache()
            traces = store.list_all()
            assert len(traces) == 1

            trace = traces[0]
            # Should have 2 node children under root
            root = trace.steps[0]
            assert len(root.children) == 2
            # Total tokens across all LLM calls
            assert trace.total_tokens == 750  # 200+100 + 300+150

    def test_langgraph_node_as_workflow_step(self) -> None:
        """Each LangGraph node becomes a WORKFLOW step."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JSONLTraceStore(Path(tmpdir) / "traces.jsonl")
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=0)
            client = TestClient(server._create_app())

            otlp_json = {
                "resourceSpans": [
                    {
                        "resource": {"attributes": []},
                        "scopeSpans": [
                            {
                                "spans": [
                                    {
                                        "traceId": "11112222333344445555666677778888",
                                        "spanId": "0000000000000001",
                                        "name": "graph_run",
                                        "startTimeUnixNano": "1704067200000000000",
                                        "endTimeUnixNano": "1704067210000000000",
                                        "attributes": [],
                                    },
                                    {
                                        "traceId": "11112222333344445555666677778888",
                                        "spanId": "0000000000000002",
                                        "parentSpanId": "0000000000000001",
                                        "name": "process_node",
                                        "startTimeUnixNano": "1704067201000000000",
                                        "endTimeUnixNano": "1704067205000000000",
                                        "attributes": [
                                            {
                                                "key": "langgraph.node.name",
                                                "value": {"stringValue": "process_node"},
                                            },
                                        ],
                                    },
                                ],
                            }
                        ],
                    }
                ]
            }

            response = client.post("/v1/traces", json=otlp_json)
            assert response.status_code == 200

            store.invalidate_cache()
            traces = store.list_all()
            node_step = traces[0].steps[0].children[0]

            assert node_step.name == "process_node"
            assert node_step.type == StepType.WORKFLOW

    def test_langgraph_llm_calls_nested(self) -> None:
        """LLM calls within nodes are nested as children."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JSONLTraceStore(Path(tmpdir) / "traces.jsonl")
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=0)
            client = TestClient(server._create_app())

            otlp_json = {
                "resourceSpans": [
                    {
                        "resource": {"attributes": []},
                        "scopeSpans": [
                            {
                                "spans": [
                                    {
                                        "traceId": "11112222333344445555666677778888",
                                        "spanId": "0000000000000001",
                                        "name": "graph_run",
                                        "startTimeUnixNano": "1704067200000000000",
                                        "endTimeUnixNano": "1704067210000000000",
                                        "attributes": [],
                                    },
                                    {
                                        "traceId": "11112222333344445555666677778888",
                                        "spanId": "0000000000000002",
                                        "parentSpanId": "0000000000000001",
                                        "name": "llm_node",
                                        "startTimeUnixNano": "1704067201000000000",
                                        "endTimeUnixNano": "1704067209000000000",
                                        "attributes": [
                                            {
                                                "key": "langgraph.node.name",
                                                "value": {"stringValue": "llm_node"},
                                            },
                                        ],
                                    },
                                    {
                                        "traceId": "11112222333344445555666677778888",
                                        "spanId": "0000000000000003",
                                        "parentSpanId": "0000000000000002",
                                        "name": "gpt-4",
                                        "startTimeUnixNano": "1704067202000000000",
                                        "endTimeUnixNano": "1704067208000000000",
                                        "attributes": [
                                            {
                                                "key": "gen_ai.request.model",
                                                "value": {"stringValue": "gpt-4"},
                                            },
                                        ],
                                    },
                                ],
                            }
                        ],
                    }
                ]
            }

            response = client.post("/v1/traces", json=otlp_json)
            assert response.status_code == 200

            store.invalidate_cache()
            traces = store.list_all()
            root = traces[0].steps[0]
            node = root.children[0]
            llm_step = node.children[0]

            assert node.name == "llm_node"
            assert llm_step.type == StepType.LLM
            assert llm_step.model_name == "gpt-4"


@pytest.mark.integration
class TestLangChainIntegration:
    """
    Test receiving traces from LangChain with OTel instrumentation.

    LangChain traces typically use OpenInference conventions:
    - llm.model_name, llm.provider attributes
    - retriever.* for retrieval operations
    - tool.name for tool executions
    """

    def test_receive_langchain_chain_trace(self) -> None:
        """LangChain chain execution produces AgentRun."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JSONLTraceStore(Path(tmpdir) / "traces.jsonl")
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=0)
            client = TestClient(server._create_app())

            # Simulate LangChain with OpenInference attributes
            otlp_json = {
                "resourceSpans": [
                    {
                        "resource": {
                            "attributes": [
                                {"key": "service.name", "value": {"stringValue": "langchain-app"}},
                            ]
                        },
                        "scopeSpans": [
                            {
                                "scope": {"name": "openinference.instrumentation.langchain"},
                                "spans": [
                                    {
                                        "traceId": "aaaa1111bbbb2222cccc3333dddd4444",
                                        "spanId": "1000000000000001",
                                        "name": "RunnableSequence.invoke",
                                        "startTimeUnixNano": "1704067200000000000",
                                        "endTimeUnixNano": "1704067215000000000",
                                        "attributes": [
                                            {
                                                "key": "openinference.span.kind",
                                                "value": {"stringValue": "chain"},
                                            },
                                        ],
                                    },
                                    {
                                        "traceId": "aaaa1111bbbb2222cccc3333dddd4444",
                                        "spanId": "1000000000000002",
                                        "parentSpanId": "1000000000000001",
                                        "name": "ChatOpenAI.invoke",
                                        "startTimeUnixNano": "1704067201000000000",
                                        "endTimeUnixNano": "1704067210000000000",
                                        "attributes": [
                                            {
                                                "key": "llm.model_name",
                                                "value": {"stringValue": "gpt-3.5-turbo"},
                                            },
                                            {
                                                "key": "llm.provider",
                                                "value": {"stringValue": "openai"},
                                            },
                                            {
                                                "key": "llm.token_count.prompt",
                                                "value": {"intValue": "500"},
                                            },
                                            {
                                                "key": "llm.token_count.completion",
                                                "value": {"intValue": "250"},
                                            },
                                        ],
                                    },
                                ],
                            }
                        ],
                    }
                ]
            }

            response = client.post("/v1/traces", json=otlp_json)
            assert response.status_code == 200

            store.invalidate_cache()
            traces = store.list_all()
            assert len(traces) == 1

            trace = traces[0]
            llm_step = trace.steps[0].children[0]
            assert llm_step.model_name == "gpt-3.5-turbo"
            assert llm_step.model_provider == "openai"
            assert llm_step.input_tokens == 500
            assert llm_step.output_tokens == 250

    def test_langchain_retriever_as_retrieval_step(self) -> None:
        """LangChain retriever becomes RETRIEVAL step."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JSONLTraceStore(Path(tmpdir) / "traces.jsonl")
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=0)
            client = TestClient(server._create_app())

            otlp_json = {
                "resourceSpans": [
                    {
                        "resource": {"attributes": []},
                        "scopeSpans": [
                            {
                                "spans": [
                                    {
                                        "traceId": "aaaa1111bbbb2222cccc3333dddd4444",
                                        "spanId": "1000000000000001",
                                        "name": "RetrievalQA.invoke",
                                        "startTimeUnixNano": "1704067200000000000",
                                        "endTimeUnixNano": "1704067220000000000",
                                        "attributes": [],
                                    },
                                    {
                                        "traceId": "aaaa1111bbbb2222cccc3333dddd4444",
                                        "spanId": "1000000000000002",
                                        "parentSpanId": "1000000000000001",
                                        "name": "VectorStoreRetriever.invoke",
                                        "startTimeUnixNano": "1704067201000000000",
                                        "endTimeUnixNano": "1704067205000000000",
                                        "attributes": [
                                            {
                                                "key": "retriever.name",
                                                "value": {"stringValue": "VectorStoreRetriever"},
                                            },
                                            {
                                                "key": "retrieval.query",
                                                "value": {
                                                    "stringValue": "What is the capital of France?"
                                                },
                                            },
                                            {
                                                "key": "retrieval.documents",
                                                "value": {"intValue": "4"},
                                            },
                                        ],
                                    },
                                ],
                            }
                        ],
                    }
                ]
            }

            response = client.post("/v1/traces", json=otlp_json)
            assert response.status_code == 200

            store.invalidate_cache()
            traces = store.list_all()
            retrieval_step = traces[0].steps[0].children[0]

            assert retrieval_step.name == "VectorStoreRetriever.invoke"
            assert retrieval_step.type == StepType.RETRIEVAL

    def test_langchain_tool_execution(self) -> None:
        """LangChain tool calls appear as TOOL steps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JSONLTraceStore(Path(tmpdir) / "traces.jsonl")
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=0)
            client = TestClient(server._create_app())

            otlp_json = {
                "resourceSpans": [
                    {
                        "resource": {"attributes": []},
                        "scopeSpans": [
                            {
                                "spans": [
                                    {
                                        "traceId": "aaaa1111bbbb2222cccc3333dddd4444",
                                        "spanId": "1000000000000001",
                                        "name": "AgentExecutor.invoke",
                                        "startTimeUnixNano": "1704067200000000000",
                                        "endTimeUnixNano": "1704067230000000000",
                                        "attributes": [
                                            {
                                                "key": "gen_ai.agent.name",
                                                "value": {"stringValue": "LangChainAgent"},
                                            },
                                        ],
                                    },
                                    {
                                        "traceId": "aaaa1111bbbb2222cccc3333dddd4444",
                                        "spanId": "1000000000000002",
                                        "parentSpanId": "1000000000000001",
                                        "name": "Calculator",
                                        "startTimeUnixNano": "1704067205000000000",
                                        "endTimeUnixNano": "1704067206000000000",
                                        "attributes": [
                                            {
                                                "key": "tool.name",
                                                "value": {"stringValue": "Calculator"},
                                            },
                                            {
                                                "key": "tool.description",
                                                "value": {
                                                    "stringValue": "Useful for math operations"
                                                },
                                            },
                                            {
                                                "key": "input.value",
                                                "value": {"stringValue": '{"expression": "2 + 2"}'},
                                            },
                                            {"key": "output.value", "value": {"stringValue": "4"}},
                                        ],
                                    },
                                    {
                                        "traceId": "aaaa1111bbbb2222cccc3333dddd4444",
                                        "spanId": "1000000000000003",
                                        "parentSpanId": "1000000000000001",
                                        "name": "Search",
                                        "startTimeUnixNano": "1704067210000000000",
                                        "endTimeUnixNano": "1704067215000000000",
                                        "attributes": [
                                            {
                                                "key": "tool.name",
                                                "value": {"stringValue": "Search"},
                                            },
                                            {
                                                "key": "input.value",
                                                "value": {
                                                    "stringValue": '{"query": "weather today"}'
                                                },
                                            },
                                            {
                                                "key": "output.value",
                                                "value": {"stringValue": "Sunny, 72F"},
                                            },
                                        ],
                                    },
                                ],
                            }
                        ],
                    }
                ]
            }

            response = client.post("/v1/traces", json=otlp_json)
            assert response.status_code == 200

            store.invalidate_cache()
            traces = store.list_all()
            root = traces[0].steps[0]

            # Should have 2 tool children
            tool_steps = [s for s in root.children if s.type == StepType.TOOL]
            assert len(tool_steps) == 2

            # Verify tool names
            tool_names = {s.name for s in tool_steps}
            assert tool_names == {"Calculator", "Search"}


@pytest.mark.integration
class TestMixedSchemaTraces:
    """Test handling traces with mixed schema conventions."""

    def test_trace_with_both_otel_and_openinference(self) -> None:
        """Traces with mixed attribute conventions are handled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JSONLTraceStore(Path(tmpdir) / "traces.jsonl")
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=0)
            client = TestClient(server._create_app())

            otlp_json = {
                "resourceSpans": [
                    {
                        "resource": {"attributes": []},
                        "scopeSpans": [
                            {
                                "spans": [
                                    {
                                        "traceId": "abcd1234abcd1234abcd1234abcd1234",
                                        "spanId": "0000000000000001",
                                        "name": "hybrid_agent",
                                        "startTimeUnixNano": "1704067200000000000",
                                        "endTimeUnixNano": "1704067220000000000",
                                        "attributes": [
                                            {
                                                "key": "gen_ai.agent.name",
                                                "value": {"stringValue": "HybridAgent"},
                                            },
                                        ],
                                    },
                                    # OTel GenAI style span
                                    {
                                        "traceId": "abcd1234abcd1234abcd1234abcd1234",
                                        "spanId": "0000000000000002",
                                        "parentSpanId": "0000000000000001",
                                        "name": "openai_call",
                                        "startTimeUnixNano": "1704067201000000000",
                                        "endTimeUnixNano": "1704067205000000000",
                                        "attributes": [
                                            {
                                                "key": "gen_ai.request.model",
                                                "value": {"stringValue": "gpt-4"},
                                            },
                                            {
                                                "key": "gen_ai.system",
                                                "value": {"stringValue": "openai"},
                                            },
                                            {
                                                "key": "gen_ai.usage.input_tokens",
                                                "value": {"intValue": "100"},
                                            },
                                        ],
                                    },
                                    # OpenInference style span
                                    {
                                        "traceId": "abcd1234abcd1234abcd1234abcd1234",
                                        "spanId": "0000000000000003",
                                        "parentSpanId": "0000000000000001",
                                        "name": "anthropic_call",
                                        "startTimeUnixNano": "1704067206000000000",
                                        "endTimeUnixNano": "1704067210000000000",
                                        "attributes": [
                                            {
                                                "key": "llm.model_name",
                                                "value": {"stringValue": "claude-3"},
                                            },
                                            {
                                                "key": "llm.provider",
                                                "value": {"stringValue": "anthropic"},
                                            },
                                            {
                                                "key": "llm.token_count.prompt",
                                                "value": {"intValue": "200"},
                                            },
                                        ],
                                    },
                                ],
                            }
                        ],
                    }
                ]
            }

            response = client.post("/v1/traces", json=otlp_json)
            assert response.status_code == 200

            store.invalidate_cache()
            traces = store.list_all()
            root = traces[0].steps[0]

            assert len(root.children) == 2

            # Both LLM steps should be correctly parsed
            llm_steps = [s for s in root.children if s.type == StepType.LLM]
            assert len(llm_steps) == 2

            # Check models from both conventions
            models = {s.model_name for s in llm_steps}
            assert models == {"gpt-4", "claude-3"}
