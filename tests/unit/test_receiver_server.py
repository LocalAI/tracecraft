"""
Unit tests for OTLP Receiver Server.

Tests the HTTP endpoints for receiving OTLP traces.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from starlette.testclient import TestClient

from tracecraft.receiver.server import OTLPReceiverServer
from tracecraft.storage.jsonl import JSONLTraceStore
from tracecraft.storage.sqlite import SQLiteTraceStore


class TestOTLPReceiverServerBasics:
    """Test basic server functionality."""

    def test_health_endpoint(self) -> None:
        """GET /health returns 200."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JSONLTraceStore(Path(tmpdir) / "traces.jsonl")
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=4318)

            # Create test client
            client = TestClient(server._create_app())

            response = client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"status": "healthy"}

    def test_receive_json_traces(self) -> None:
        """POST /v1/traces with JSON body."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JSONLTraceStore(Path(tmpdir) / "traces.jsonl")
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=4318)

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

            response = client.post(
                "/v1/traces",
                json=otlp_json,
                headers={"Content-Type": "application/json"},
            )

            assert response.status_code == 200
            assert response.json()["status"] == "ok"
            assert response.json()["traces_received"] == 1

    def test_traces_saved_to_storage(self) -> None:
        """Received traces appear in storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "traces.jsonl"
            store = JSONLTraceStore(store_path)
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=4318)

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
                                        "name": "saved_trace",
                                        "startTimeUnixNano": "1704067200000000000",
                                        "endTimeUnixNano": "1704067201000000000",
                                        "attributes": [
                                            {
                                                "key": "gen_ai.request.model",
                                                "value": {"stringValue": "gpt-4"},
                                            }
                                        ],
                                    }
                                ]
                            }
                        ],
                    }
                ]
            }

            response = client.post("/v1/traces", json=otlp_json)
            assert response.status_code == 200

            # Verify trace was saved
            store.invalidate_cache()
            traces = store.list_all()
            assert len(traces) == 1
            assert traces[0].name == "saved_trace"
            assert len(traces[0].steps) == 1
            assert traces[0].steps[0].model_name == "gpt-4"

    def test_invalid_payload_returns_400(self) -> None:
        """Malformed data returns error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JSONLTraceStore(Path(tmpdir) / "traces.jsonl")
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=4318)

            client = TestClient(server._create_app())

            # Send invalid JSON
            response = client.post(
                "/v1/traces",
                content=b"not valid json",
                headers={"Content-Type": "application/json"},
            )

            assert response.status_code == 400
            assert "error" in response.json()

    def test_empty_spans_handled(self) -> None:
        """Empty spans list is handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JSONLTraceStore(Path(tmpdir) / "traces.jsonl")
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=4318)

            client = TestClient(server._create_app())

            otlp_json = {"resourceSpans": []}

            response = client.post("/v1/traces", json=otlp_json)
            assert response.status_code == 200
            assert response.json()["traces_received"] == 0


class TestSQLiteStorage:
    """Test with SQLite storage backend."""

    def test_receive_with_sqlite_storage(self) -> None:
        """Traces are saved to SQLite correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "traces.db"
            store = SQLiteTraceStore(store_path)
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=4318)

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
                                        "name": "sqlite_trace",
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

            # Verify trace was saved
            traces = store.list_all()
            assert len(traces) == 1
            assert traces[0].name == "sqlite_trace"


class TestMultipleSpans:
    """Test handling of multiple spans and traces."""

    def test_receive_nested_spans(self) -> None:
        """Nested spans are correctly hierarchized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JSONLTraceStore(Path(tmpdir) / "traces.jsonl")
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=4318)

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
                                        "spanId": "1111111111111111",
                                        "name": "parent",
                                        "startTimeUnixNano": "1704067200000000000",
                                        "endTimeUnixNano": "1704067205000000000",
                                        "attributes": [],
                                    },
                                    {
                                        "traceId": "0123456789abcdef0123456789abcdef",
                                        "spanId": "2222222222222222",
                                        "parentSpanId": "1111111111111111",
                                        "name": "child",
                                        "startTimeUnixNano": "1704067201000000000",
                                        "endTimeUnixNano": "1704067202000000000",
                                        "attributes": [],
                                    },
                                ]
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

            # Parent should have child
            parent = traces[0].steps[0]
            assert parent.name == "parent"
            assert len(parent.children) == 1
            assert parent.children[0].name == "child"

    def test_receive_multiple_traces(self) -> None:
        """Multiple traces in one request are handled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JSONLTraceStore(Path(tmpdir) / "traces.jsonl")
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=4318)

            client = TestClient(server._create_app())

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

            response = client.post("/v1/traces", json=otlp_json)
            assert response.status_code == 200
            assert response.json()["traces_received"] == 2

            store.invalidate_cache()
            traces = store.list_all()
            assert len(traces) == 2


class TestServerLifecycle:
    """Test server start/stop lifecycle."""

    def test_server_url_property(self) -> None:
        """Server URL is correctly formatted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JSONLTraceStore(Path(tmpdir) / "traces.jsonl")
            server = OTLPReceiverServer(store=store, host="0.0.0.0", port=4318)

            assert server.url == "http://0.0.0.0:4318"

    def test_server_not_running_initially(self) -> None:
        """Server is not running until started."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JSONLTraceStore(Path(tmpdir) / "traces.jsonl")
            server = OTLPReceiverServer(store=store, host="127.0.0.1", port=4318)

            assert not server.is_running
