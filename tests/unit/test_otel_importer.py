"""
Unit tests for OTelImporter.

Tests the conversion of OTLP spans to TraceCraft AgentRun objects.
"""

from __future__ import annotations

import pytest

from tracecraft.core.models import StepType
from tracecraft.receiver.importer import OTelImporter


class TestOTelImporterBasics:
    """Test basic OTelImporter functionality."""

    def test_import_single_span_llm_step(self) -> None:
        """Single LLM span converts to AgentRun with one Step."""
        importer = OTelImporter()

        otlp_json = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "my-agent"}}
                        ]
                    },
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "0123456789abcdef0123456789abcdef",
                                    "spanId": "0123456789abcdef",
                                    "name": "chat_completion",
                                    "startTimeUnixNano": "1704067200000000000",
                                    "endTimeUnixNano": "1704067201000000000",
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
                                        {
                                            "key": "gen_ai.usage.output_tokens",
                                            "value": {"intValue": "50"},
                                        },
                                    ],
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        runs = importer.import_from_json(otlp_json)

        assert len(runs) == 1
        run = runs[0]
        assert run.name == "chat_completion"
        assert len(run.steps) == 1

        step = run.steps[0]
        assert step.type == StepType.LLM
        assert step.model_name == "gpt-4"
        assert step.model_provider == "openai"
        assert step.input_tokens == 100
        assert step.output_tokens == 50
        assert step.duration_ms == 1000.0

    def test_import_nested_spans_hierarchy(self) -> None:
        """Parent-child spans become Step.children."""
        importer = OTelImporter()

        otlp_json = {
            "resourceSpans": [
                {
                    "resource": {"attributes": []},
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "0123456789abcdef0123456789abcdef",
                                    "spanId": "1111111111111111",
                                    "name": "agent_run",
                                    "startTimeUnixNano": "1704067200000000000",
                                    "endTimeUnixNano": "1704067205000000000",
                                    "attributes": [
                                        {
                                            "key": "gen_ai.agent.name",
                                            "value": {"stringValue": "research_agent"},
                                        }
                                    ],
                                },
                                {
                                    "traceId": "0123456789abcdef0123456789abcdef",
                                    "spanId": "2222222222222222",
                                    "parentSpanId": "1111111111111111",
                                    "name": "gpt-4-call",
                                    "startTimeUnixNano": "1704067201000000000",
                                    "endTimeUnixNano": "1704067203000000000",
                                    "attributes": [
                                        {
                                            "key": "gen_ai.request.model",
                                            "value": {"stringValue": "gpt-4"},
                                        }
                                    ],
                                },
                                {
                                    "traceId": "0123456789abcdef0123456789abcdef",
                                    "spanId": "3333333333333333",
                                    "parentSpanId": "1111111111111111",
                                    "name": "tool_call",
                                    "startTimeUnixNano": "1704067203000000000",
                                    "endTimeUnixNano": "1704067204000000000",
                                    "attributes": [
                                        {
                                            "key": "tool.name",
                                            "value": {"stringValue": "search"},
                                        }
                                    ],
                                },
                            ]
                        }
                    ],
                }
            ]
        }

        runs = importer.import_from_json(otlp_json)

        assert len(runs) == 1
        run = runs[0]
        assert len(run.steps) == 1

        parent_step = run.steps[0]
        assert parent_step.type == StepType.AGENT
        assert parent_step.name == "agent_run"
        assert len(parent_step.children) == 2

        # Children should be sorted by start time
        llm_step = parent_step.children[0]
        assert llm_step.type == StepType.LLM
        assert llm_step.name == "gpt-4-call"

        tool_step = parent_step.children[1]
        assert tool_step.type == StepType.TOOL
        assert tool_step.name == "tool_call"


class TestOTelGenAIAttributes:
    """Test OTel GenAI attribute mapping."""

    def test_import_otel_genai_attributes(self) -> None:
        """gen_ai.* attributes map correctly."""
        importer = OTelImporter()

        otlp_json = {
            "resourceSpans": [
                {
                    "resource": {"attributes": []},
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "0123456789abcdef0123456789abcdef",
                                    "spanId": "0123456789abcdef",
                                    "name": "llm_call",
                                    "startTimeUnixNano": "1704067200000000000",
                                    "endTimeUnixNano": "1704067201000000000",
                                    "attributes": [
                                        {
                                            "key": "gen_ai.request.model",
                                            "value": {"stringValue": "claude-3-opus"},
                                        },
                                        {
                                            "key": "gen_ai.system",
                                            "value": {"stringValue": "anthropic"},
                                        },
                                        {
                                            "key": "gen_ai.usage.input_tokens",
                                            "value": {"intValue": "500"},
                                        },
                                        {
                                            "key": "gen_ai.usage.output_tokens",
                                            "value": {"intValue": "1000"},
                                        },
                                        {
                                            "key": "gen_ai.usage.cost",
                                            "value": {"doubleValue": 0.05},
                                        },
                                    ],
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        runs = importer.import_from_json(otlp_json)
        step = runs[0].steps[0]

        assert step.model_name == "claude-3-opus"
        assert step.model_provider == "anthropic"
        assert step.input_tokens == 500
        assert step.output_tokens == 1000
        assert step.cost_usd == 0.05


class TestOpenInferenceAttributes:
    """Test OpenInference attribute mapping."""

    def test_import_openinference_attributes(self) -> None:
        """llm.*, tool.* attributes map correctly."""
        importer = OTelImporter()

        otlp_json = {
            "resourceSpans": [
                {
                    "resource": {"attributes": []},
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "0123456789abcdef0123456789abcdef",
                                    "spanId": "0123456789abcdef",
                                    "name": "llm_call",
                                    "startTimeUnixNano": "1704067200000000000",
                                    "endTimeUnixNano": "1704067201000000000",
                                    "attributes": [
                                        {
                                            "key": "llm.model_name",
                                            "value": {"stringValue": "gpt-4-turbo"},
                                        },
                                        {
                                            "key": "llm.provider",
                                            "value": {"stringValue": "openai"},
                                        },
                                        {
                                            "key": "llm.token_count.prompt",
                                            "value": {"intValue": "200"},
                                        },
                                        {
                                            "key": "llm.token_count.completion",
                                            "value": {"intValue": "300"},
                                        },
                                    ],
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        runs = importer.import_from_json(otlp_json)
        step = runs[0].steps[0]

        assert step.model_name == "gpt-4-turbo"
        assert step.model_provider == "openai"
        assert step.input_tokens == 200
        assert step.output_tokens == 300


class TestStepTypeInference:
    """Test step type inference from attributes."""

    def test_infer_step_type_from_attributes(self) -> None:
        """StepType inferred when tracecraft.step.type absent."""
        importer = OTelImporter()

        # Test tool type inference
        otlp_json = {
            "resourceSpans": [
                {
                    "resource": {"attributes": []},
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "0123456789abcdef0123456789abcdef",
                                    "spanId": "0123456789abcdef",
                                    "name": "search_tool",
                                    "startTimeUnixNano": "1704067200000000000",
                                    "endTimeUnixNano": "1704067201000000000",
                                    "attributes": [
                                        {
                                            "key": "tool.name",
                                            "value": {"stringValue": "web_search"},
                                        },
                                        {
                                            "key": "tool.parameters",
                                            "value": {"stringValue": '{"query": "test"}'},
                                        },
                                    ],
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        runs = importer.import_from_json(otlp_json)
        step = runs[0].steps[0]
        assert step.type == StepType.TOOL

    def test_infer_retrieval_type(self) -> None:
        """Retrieval type inferred from retrieval.* attributes."""
        importer = OTelImporter()

        otlp_json = {
            "resourceSpans": [
                {
                    "resource": {"attributes": []},
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "0123456789abcdef0123456789abcdef",
                                    "spanId": "0123456789abcdef",
                                    "name": "vector_search",
                                    "startTimeUnixNano": "1704067200000000000",
                                    "endTimeUnixNano": "1704067201000000000",
                                    "attributes": [
                                        {
                                            "key": "retrieval.query",
                                            "value": {"stringValue": "What is the capital?"},
                                        }
                                    ],
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        runs = importer.import_from_json(otlp_json)
        step = runs[0].steps[0]
        assert step.type == StepType.RETRIEVAL

    def test_explicit_tracecraft_step_type(self) -> None:
        """tracecraft.step.type takes precedence."""
        importer = OTelImporter()

        otlp_json = {
            "resourceSpans": [
                {
                    "resource": {"attributes": []},
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "0123456789abcdef0123456789abcdef",
                                    "spanId": "0123456789abcdef",
                                    "name": "memory_store",
                                    "startTimeUnixNano": "1704067200000000000",
                                    "endTimeUnixNano": "1704067201000000000",
                                    "attributes": [
                                        {
                                            "key": "tracecraft.step.type",
                                            "value": {"stringValue": "memory"},
                                        }
                                    ],
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        runs = importer.import_from_json(otlp_json)
        step = runs[0].steps[0]
        assert step.type == StepType.MEMORY


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_import_error_spans(self) -> None:
        """Error status maps to step.error."""
        importer = OTelImporter()

        otlp_json = {
            "resourceSpans": [
                {
                    "resource": {"attributes": []},
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "0123456789abcdef0123456789abcdef",
                                    "spanId": "0123456789abcdef",
                                    "name": "failed_call",
                                    "startTimeUnixNano": "1704067200000000000",
                                    "endTimeUnixNano": "1704067201000000000",
                                    "status": {
                                        "code": 2,
                                        "message": "Rate limit exceeded",
                                    },
                                    "attributes": [
                                        {
                                            "key": "error.type",
                                            "value": {"stringValue": "RateLimitError"},
                                        }
                                    ],
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        runs = importer.import_from_json(otlp_json)
        step = runs[0].steps[0]

        assert step.error == "Rate limit exceeded"
        assert step.error_type == "RateLimitError"
        assert runs[0].error_count == 1

    def test_import_multiple_traces(self) -> None:
        """Multiple trace_ids produce multiple AgentRuns."""
        importer = OTelImporter()

        otlp_json = {
            "resourceSpans": [
                {
                    "resource": {"attributes": []},
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1",
                                    "spanId": "1111111111111111",
                                    "name": "trace_1",
                                    "startTimeUnixNano": "1704067200000000000",
                                    "endTimeUnixNano": "1704067201000000000",
                                    "attributes": [],
                                },
                                {
                                    "traceId": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa2",
                                    "spanId": "2222222222222222",
                                    "name": "trace_2",
                                    "startTimeUnixNano": "1704067200000000000",
                                    "endTimeUnixNano": "1704067201000000000",
                                    "attributes": [],
                                },
                            ]
                        }
                    ],
                }
            ]
        }

        runs = importer.import_from_json(otlp_json)
        assert len(runs) == 2


class TestIOExtraction:
    """Test input/output extraction from attributes."""

    def test_extract_input_output_values(self) -> None:
        """input.value and output.value are extracted."""
        importer = OTelImporter()

        otlp_json = {
            "resourceSpans": [
                {
                    "resource": {"attributes": []},
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "0123456789abcdef0123456789abcdef",
                                    "spanId": "0123456789abcdef",
                                    "name": "llm_call",
                                    "startTimeUnixNano": "1704067200000000000",
                                    "endTimeUnixNano": "1704067201000000000",
                                    "attributes": [
                                        {
                                            "key": "input.value",
                                            "value": {"stringValue": '{"prompt": "Hello"}'},
                                        },
                                        {
                                            "key": "output.value",
                                            "value": {"stringValue": '{"response": "Hi there!"}'},
                                        },
                                    ],
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        runs = importer.import_from_json(otlp_json)
        step = runs[0].steps[0]

        assert step.inputs == {"prompt": "Hello"}
        assert step.outputs == {"response": "Hi there!"}

    def test_extract_indexed_message_format(self) -> None:
        """Indexed message format (gen_ai.prompt.0.content) is extracted correctly."""
        importer = OTelImporter()

        otlp_json = {
            "resourceSpans": [
                {
                    "resource": {"attributes": []},
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "0123456789abcdef0123456789abcdef",
                                    "spanId": "0123456789abcdef",
                                    "name": "openai.chat",
                                    "startTimeUnixNano": "1704067200000000000",
                                    "endTimeUnixNano": "1704067201000000000",
                                    "attributes": [
                                        {
                                            "key": "gen_ai.request.model",
                                            "value": {"stringValue": "gpt-4o-mini"},
                                        },
                                        {
                                            "key": "gen_ai.usage.prompt_tokens",
                                            "value": {"intValue": "100"},
                                        },
                                        {
                                            "key": "gen_ai.usage.completion_tokens",
                                            "value": {"intValue": "50"},
                                        },
                                        {
                                            "key": "gen_ai.prompt.0.role",
                                            "value": {"stringValue": "user"},
                                        },
                                        {
                                            "key": "gen_ai.prompt.0.content",
                                            "value": {"stringValue": "What is 2+2?"},
                                        },
                                        {
                                            "key": "gen_ai.completion.0.role",
                                            "value": {"stringValue": "assistant"},
                                        },
                                        {
                                            "key": "gen_ai.completion.0.content",
                                            "value": {"stringValue": "4"},
                                        },
                                    ],
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        runs = importer.import_from_json(otlp_json)
        step = runs[0].steps[0]

        # Indexed format extracts to prompt/response for single messages
        assert step.inputs == {"prompt": "What is 2+2?"}
        assert step.outputs == {"response": "4"}
        assert step.input_tokens == 100
        assert step.output_tokens == 50

    def test_extract_tool_parameters(self) -> None:
        """tool.parameters are extracted as inputs."""
        importer = OTelImporter()

        otlp_json = {
            "resourceSpans": [
                {
                    "resource": {"attributes": []},
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "0123456789abcdef0123456789abcdef",
                                    "spanId": "0123456789abcdef",
                                    "name": "search",
                                    "startTimeUnixNano": "1704067200000000000",
                                    "endTimeUnixNano": "1704067201000000000",
                                    "attributes": [
                                        {
                                            "key": "tool.name",
                                            "value": {"stringValue": "search"},
                                        },
                                        {
                                            "key": "tool.parameters",
                                            "value": {"stringValue": '{"query": "Python async"}'},
                                        },
                                    ],
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        runs = importer.import_from_json(otlp_json)
        step = runs[0].steps[0]

        assert step.inputs == {"query": "Python async"}


class TestAggregation:
    """Test aggregation of tokens and costs."""

    def test_aggregate_tokens_and_cost(self) -> None:
        """Tokens and costs are summed across all steps."""
        importer = OTelImporter()

        otlp_json = {
            "resourceSpans": [
                {
                    "resource": {"attributes": []},
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "0123456789abcdef0123456789abcdef",
                                    "spanId": "1111111111111111",
                                    "name": "agent",
                                    "startTimeUnixNano": "1704067200000000000",
                                    "endTimeUnixNano": "1704067205000000000",
                                    "attributes": [],
                                },
                                {
                                    "traceId": "0123456789abcdef0123456789abcdef",
                                    "spanId": "2222222222222222",
                                    "parentSpanId": "1111111111111111",
                                    "name": "llm_1",
                                    "startTimeUnixNano": "1704067201000000000",
                                    "endTimeUnixNano": "1704067202000000000",
                                    "attributes": [
                                        {
                                            "key": "gen_ai.usage.input_tokens",
                                            "value": {"intValue": "100"},
                                        },
                                        {
                                            "key": "gen_ai.usage.output_tokens",
                                            "value": {"intValue": "50"},
                                        },
                                        {
                                            "key": "gen_ai.usage.cost",
                                            "value": {"doubleValue": 0.01},
                                        },
                                    ],
                                },
                                {
                                    "traceId": "0123456789abcdef0123456789abcdef",
                                    "spanId": "3333333333333333",
                                    "parentSpanId": "1111111111111111",
                                    "name": "llm_2",
                                    "startTimeUnixNano": "1704067203000000000",
                                    "endTimeUnixNano": "1704067204000000000",
                                    "attributes": [
                                        {
                                            "key": "gen_ai.usage.input_tokens",
                                            "value": {"intValue": "200"},
                                        },
                                        {
                                            "key": "gen_ai.usage.output_tokens",
                                            "value": {"intValue": "100"},
                                        },
                                        {
                                            "key": "gen_ai.usage.cost",
                                            "value": {"doubleValue": 0.02},
                                        },
                                    ],
                                },
                            ]
                        }
                    ],
                }
            ]
        }

        runs = importer.import_from_json(otlp_json)
        run = runs[0]

        # Total tokens: 100 + 50 + 200 + 100 = 450
        assert run.total_tokens == 450
        # Total cost: 0.01 + 0.02 = 0.03
        assert run.total_cost_usd == pytest.approx(0.03)


class TestEdgeCases:
    """Test edge cases and malformed data handling."""

    def test_empty_trace_id_handled(self) -> None:
        """Empty trace_id is handled gracefully."""
        importer = OTelImporter()

        otlp_json = {
            "resourceSpans": [
                {
                    "resource": {"attributes": []},
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "",  # Empty!
                                    "spanId": "1111111111111111",
                                    "name": "test_span",
                                    "startTimeUnixNano": "1704067200000000000",
                                    "endTimeUnixNano": "1704067201000000000",
                                    "attributes": [],
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        runs = importer.import_from_json(otlp_json)
        assert len(runs) == 1
        # Should get a valid UUID (all zeros for empty)
        assert runs[0].id is not None

    def test_invalid_hex_trace_id_handled(self) -> None:
        """Invalid hex characters in trace_id are handled."""
        importer = OTelImporter()

        otlp_json = {
            "resourceSpans": [
                {
                    "resource": {"attributes": []},
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "invalid-hex-xyz!!!",  # Invalid!
                                    "spanId": "also-invalid!!!",
                                    "name": "test_span",
                                    "startTimeUnixNano": "1704067200000000000",
                                    "endTimeUnixNano": "1704067201000000000",
                                    "attributes": [],
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        runs = importer.import_from_json(otlp_json)
        assert len(runs) == 1
        # Should get a valid UUID (hashed)
        assert runs[0].id is not None

    def test_negative_duration_clamped_to_zero(self) -> None:
        """Malformed data with end < start has duration clamped to 0."""
        importer = OTelImporter()

        otlp_json = {
            "resourceSpans": [
                {
                    "resource": {"attributes": []},
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "0123456789abcdef0123456789abcdef",
                                    "spanId": "1111111111111111",
                                    "name": "test_span",
                                    # end_time < start_time (malformed)
                                    "startTimeUnixNano": "1704067205000000000",
                                    "endTimeUnixNano": "1704067200000000000",
                                    "attributes": [],
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        runs = importer.import_from_json(otlp_json)
        run = runs[0]
        step = run.steps[0]

        # Duration should be 0, not negative
        assert step.duration_ms >= 0
        assert run.duration_ms >= 0

    def test_tool_parameters_merged_with_input_value(self) -> None:
        """Tool parameters are merged with input.value, not overwritten."""
        importer = OTelImporter()

        otlp_json = {
            "resourceSpans": [
                {
                    "resource": {"attributes": []},
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "0123456789abcdef0123456789abcdef",
                                    "spanId": "1111111111111111",
                                    "name": "tool_call",
                                    "startTimeUnixNano": "1704067200000000000",
                                    "endTimeUnixNano": "1704067201000000000",
                                    "attributes": [
                                        {
                                            "key": "input.value",
                                            "value": {"stringValue": '{"context": "some context"}'},
                                        },
                                        {
                                            "key": "tool.parameters",
                                            "value": {"stringValue": '{"query": "search term"}'},
                                        },
                                        {
                                            "key": "tool.name",
                                            "value": {"stringValue": "search"},
                                        },
                                    ],
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        runs = importer.import_from_json(otlp_json)
        step = runs[0].steps[0]

        # Both should be present
        assert "context" in step.inputs
        assert "query" in step.inputs

    def test_missing_span_id_handled(self) -> None:
        """Missing spanId is handled gracefully."""
        importer = OTelImporter()

        otlp_json = {
            "resourceSpans": [
                {
                    "resource": {"attributes": []},
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "0123456789abcdef0123456789abcdef",
                                    # spanId missing
                                    "name": "test_span",
                                    "startTimeUnixNano": "1704067200000000000",
                                    "endTimeUnixNano": "1704067201000000000",
                                    "attributes": [],
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        runs = importer.import_from_json(otlp_json)
        assert len(runs) == 1
        # Should get a valid Step with a UUID
        assert runs[0].steps[0].id is not None

    def test_agent_run_gets_input_output_from_root_step(self) -> None:
        """AgentRun.input and AgentRun.output are populated from root step."""
        importer = OTelImporter()

        otlp_json = {
            "resourceSpans": [
                {
                    "resource": {"attributes": []},
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "0123456789abcdef0123456789abcdef",
                                    "spanId": "1111111111111111",
                                    "name": "agent_run",
                                    "startTimeUnixNano": "1704067200000000000",
                                    "endTimeUnixNano": "1704067205000000000",
                                    "attributes": [
                                        {
                                            "key": "input.value",
                                            "value": {
                                                "stringValue": '{"query": "What is the weather?"}'
                                            },
                                        },
                                        {
                                            "key": "output.value",
                                            "value": {"stringValue": '{"answer": "It is sunny."}'},
                                        },
                                    ],
                                },
                            ]
                        }
                    ],
                }
            ]
        }

        runs = importer.import_from_json(otlp_json)
        run = runs[0]

        # AgentRun should have input/output from root step
        assert run.input == {"query": "What is the weather?"}
        assert run.output == {"answer": "It is sunny."}
