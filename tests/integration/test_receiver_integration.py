"""
Integration tests for OTLP Receiver.

Tests the full flow: receive traces → storage → TUI loads.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tracecraft.receiver.server import OTLPReceiverServer
from tracecraft.storage.jsonl import JSONLTraceStore
from tracecraft.storage.sqlite import SQLiteTraceStore
from tracecraft.tui.data.loader import TraceLoader


@pytest.mark.integration
class TestReceiverToStorageFlow:
    """Test the complete receive → storage flow."""

    def test_receiver_to_jsonl_storage(self) -> None:
        """Traces received via HTTP are saved to JSONL and queryable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "traces.jsonl"
            store = JSONLTraceStore(store_path)
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=0)

            # Use test client instead of running actual server
            from starlette.testclient import TestClient

            client = TestClient(server._create_app())

            # Send a trace with LLM step
            otlp_json = {
                "resourceSpans": [
                    {
                        "resource": {
                            "attributes": [
                                {
                                    "key": "service.name",
                                    "value": {"stringValue": "test-agent"},
                                }
                            ]
                        },
                        "scopeSpans": [
                            {
                                "spans": [
                                    {
                                        "traceId": "0123456789abcdef0123456789abcdef",
                                        "spanId": "1111111111111111",
                                        "name": "agent_run",
                                        "startTimeUnixNano": "1704067200000000000",
                                        "endTimeUnixNano": "1704067210000000000",
                                        "attributes": [
                                            {
                                                "key": "gen_ai.agent.name",
                                                "value": {"stringValue": "test_agent"},
                                            }
                                        ],
                                    },
                                    {
                                        "traceId": "0123456789abcdef0123456789abcdef",
                                        "spanId": "2222222222222222",
                                        "parentSpanId": "1111111111111111",
                                        "name": "gpt-4-call",
                                        "startTimeUnixNano": "1704067201000000000",
                                        "endTimeUnixNano": "1704067205000000000",
                                        "attributes": [
                                            {
                                                "key": "gen_ai.request.model",
                                                "value": {"stringValue": "gpt-4"},
                                            },
                                            {
                                                "key": "gen_ai.usage.input_tokens",
                                                "value": {"intValue": "500"},
                                            },
                                            {
                                                "key": "gen_ai.usage.output_tokens",
                                                "value": {"intValue": "200"},
                                            },
                                        ],
                                    },
                                ]
                            }
                        ],
                    }
                ]
            }

            response = client.post("/v1/traces", json=otlp_json)
            assert response.status_code == 200

            # Load via TraceLoader (like TUI would)
            loader = TraceLoader.from_source(str(store_path))
            traces = loader.list_traces()

            assert len(traces) == 1
            trace = traces[0]
            assert trace.name == "agent_run"
            assert trace.agent_name == "test_agent"
            assert trace.total_tokens == 700  # 500 + 200

    def test_receiver_to_sqlite_storage(self) -> None:
        """Traces received via HTTP are saved to SQLite and queryable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "traces.db"
            store = SQLiteTraceStore(store_path)
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=0)

            from starlette.testclient import TestClient

            client = TestClient(server._create_app())

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
                                        "name": "sqlite_test",
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

            response = client.post("/v1/traces", json=otlp_json)
            assert response.status_code == 200

            # Query via TraceLoader
            loader = TraceLoader.from_source(f"sqlite://{store_path}")
            traces = loader.list_traces()

            assert len(traces) == 1
            assert traces[0].name == "sqlite_test"

    def test_multiple_traces_sequential(self) -> None:
        """Multiple traces sent sequentially are all saved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "traces.jsonl"
            store = JSONLTraceStore(store_path)
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=0)

            from starlette.testclient import TestClient

            client = TestClient(server._create_app())

            # Send 5 traces
            for i in range(5):
                trace_id = f"{'a' * 31}{i}"
                otlp_json = {
                    "resourceSpans": [
                        {
                            "resource": {"attributes": []},
                            "scopeSpans": [
                                {
                                    "spans": [
                                        {
                                            "traceId": trace_id,
                                            "spanId": f"{'1' * 15}{i}",
                                            "name": f"trace_{i}",
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
                response = client.post("/v1/traces", json=otlp_json)
                assert response.status_code == 200

            # All traces should be saved
            store.invalidate_cache()
            traces = store.list_all()
            assert len(traces) == 5


@pytest.mark.integration
class TestWatchModeSimulation:
    """Test simulated watch mode behavior."""

    def test_new_traces_appear_after_refresh(self) -> None:
        """New traces appear after loader.refresh()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "traces.jsonl"
            store = JSONLTraceStore(store_path)
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=0)

            from starlette.testclient import TestClient

            client = TestClient(server._create_app())

            # Create loader (like TUI would)
            loader = TraceLoader.from_source(str(store_path))

            # Initially no traces
            initial_traces = loader.list_traces()
            assert len(initial_traces) == 0

            # Send a trace
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
                                        "name": "new_trace",
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
            client.post("/v1/traces", json=otlp_json)

            # Refresh and check
            loader.refresh()
            new_traces = loader.list_traces()
            assert len(new_traces) == 1
            assert new_traces[0].name == "new_trace"

    def test_sqlite_watch_mode_refresh(self) -> None:
        """SQLite storage also supports watch mode refresh (default storage)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "traces.db"
            store = SQLiteTraceStore(store_path)
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=0)

            from starlette.testclient import TestClient

            client = TestClient(server._create_app())

            # Create loader with SQLite source (like TUI would)
            loader = TraceLoader.from_source(f"sqlite://{store_path}")

            # Initially no traces
            initial_traces = loader.list_traces()
            assert len(initial_traces) == 0

            # Send a trace
            otlp_json = {
                "resourceSpans": [
                    {
                        "resource": {"attributes": []},
                        "scopeSpans": [
                            {
                                "spans": [
                                    {
                                        "traceId": "aabbccdd11223344aabbccdd11223344",
                                        "spanId": "1234567890abcdef",
                                        "name": "sqlite_watch_test",
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
            response = client.post("/v1/traces", json=otlp_json)
            assert response.status_code == 200

            # Refresh and check - this is the core test for SQLite watch mode
            loader.refresh()
            new_traces = loader.list_traces()
            assert len(new_traces) == 1
            assert new_traces[0].name == "sqlite_watch_test"


@pytest.mark.integration
class TestSchemaDetection:
    """Test auto-detection of schema dialect."""

    def test_otel_genai_schema_detected(self) -> None:
        """OTel GenAI attributes are correctly mapped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JSONLTraceStore(Path(tmpdir) / "traces.jsonl")
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=0)

            from starlette.testclient import TestClient

            client = TestClient(server._create_app())

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
                                                "value": {"stringValue": "claude-3"},
                                            },
                                            {
                                                "key": "gen_ai.system",
                                                "value": {"stringValue": "anthropic"},
                                            },
                                        ],
                                    }
                                ]
                            }
                        ],
                    }
                ]
            }

            client.post("/v1/traces", json=otlp_json)

            store.invalidate_cache()
            traces = store.list_all()
            step = traces[0].steps[0]

            assert step.model_name == "claude-3"
            assert step.model_provider == "anthropic"

    def test_openinference_schema_detected(self) -> None:
        """OpenInference attributes are correctly mapped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JSONLTraceStore(Path(tmpdir) / "traces.jsonl")
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=0)

            from starlette.testclient import TestClient

            client = TestClient(server._create_app())

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
                                                "value": {"intValue": "100"},
                                            },
                                        ],
                                    }
                                ]
                            }
                        ],
                    }
                ]
            }

            client.post("/v1/traces", json=otlp_json)

            store.invalidate_cache()
            traces = store.list_all()
            step = traces[0].steps[0]

            assert step.model_name == "gpt-4-turbo"
            assert step.model_provider == "openai"
            assert step.input_tokens == 100
