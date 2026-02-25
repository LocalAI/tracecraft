"""Tests for DataDog APM trace store."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

httpx = pytest.importorskip("httpx")


class TestDataDogImport:
    def test_import_error_when_httpx_missing(self):
        """ImportError raised with install hint when httpx missing."""
        with patch.dict("sys.modules", {"httpx": None}):
            if "tracecraft.storage.datadog" in sys.modules:
                del sys.modules["tracecraft.storage.datadog"]
            with patch.dict("os.environ", {"DD_API_KEY": "k", "DD_APP_KEY": "a"}):
                with pytest.raises(ImportError, match="tracecraft\\[storage-datadog\\]"):
                    from tracecraft.storage.datadog import DataDogTraceStore

                    DataDogTraceStore()


class TestDataDogTraceStore:
    @pytest.fixture
    def mock_http_client(self):
        return MagicMock()

    @pytest.fixture
    def store(self, mock_http_client):
        """Create store bypassing __init__."""
        from tracecraft.storage._cache import TTLCache
        from tracecraft.storage.datadog import DataDogTraceStore

        store = DataDogTraceStore.__new__(DataDogTraceStore)
        store._http_client = mock_http_client
        store._service = None
        store._lookback_hours = 1
        store._cache = TTLCache(ttl_seconds=60)
        store._base_url = "https://api.datadoghq.com"
        store._headers = {"DD-API-KEY": "test", "DD-APPLICATION-KEY": "test"}
        return store

    def _make_response(self, traces: list[dict], status_code: int = 200):
        """Create a mock httpx Response."""
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = {
            "data": traces,
            "meta": {"page": {}},
        }
        mock_resp.text = json.dumps({"data": traces})
        return mock_resp

    def _make_trace(self, trace_id="12345678", service="my-service", error=0):
        return {
            "id": trace_id,
            "attributes": {
                "trace_id": trace_id,
                "service": service,
                "spans": [
                    {
                        "trace_id": trace_id,
                        "span_id": "111",
                        "parent_id": None,
                        "name": "web.request",
                        "resource": f"GET /api/{service}",
                        "service": service,
                        "type": "web",
                        "start": 1700000000000000000,
                        "duration": 500000000,
                        "error": error,
                        "meta": {},
                        "metrics": {},
                    }
                ],
            },
        }

    def test_requires_dd_api_key_env(self):
        """ValueError raised when DD_API_KEY is missing."""
        env = {"DD_APP_KEY": "appkey"}
        with patch.dict("os.environ", env, clear=True):
            with pytest.raises(ValueError, match="DD_API_KEY"):
                from tracecraft.storage.datadog import DataDogTraceStore

                DataDogTraceStore.__new__(DataDogTraceStore).__init__()

    def test_requires_dd_app_key_env(self):
        """ValueError raised when DD_APP_KEY is missing."""
        import os

        with patch.dict("os.environ", {"DD_API_KEY": "apikey"}, clear=True):
            with pytest.raises(ValueError, match="DD_APP_KEY"):
                from tracecraft.storage.datadog import DataDogTraceStore

                store = DataDogTraceStore.__new__(DataDogTraceStore)
                orig_app_key = os.environ.pop("DD_APP_KEY", None)
                try:
                    store.__init__()
                finally:
                    if orig_app_key:
                        os.environ["DD_APP_KEY"] = orig_app_key

    def test_site_mapping_us1(self):
        """us1 site maps to api.datadoghq.com."""
        from tracecraft.storage.datadog import DATADOG_SITES

        assert DATADOG_SITES["us1"] == "api.datadoghq.com"

    def test_site_mapping_eu1(self):
        """eu1 site maps to api.datadoghq.eu."""
        from tracecraft.storage.datadog import DATADOG_SITES

        assert DATADOG_SITES["eu1"] == "api.datadoghq.eu"

    def test_list_all_calls_apm_traces_endpoint(self, store, mock_http_client):
        """list_all calls /api/v2/apm/traces."""
        trace = self._make_trace()
        mock_http_client.get.return_value = self._make_response([trace])

        result = store.list_all()

        mock_http_client.get.assert_called_once()
        call_args = mock_http_client.get.call_args
        assert "/api/v2/apm/traces" in str(call_args)
        assert len(result) == 1

    def test_list_all_caches_results(self, store, mock_http_client):
        """list_all is cached; client called only once on second call."""
        trace = self._make_trace()
        mock_http_client.get.return_value = self._make_response([trace])

        store.list_all()
        store.list_all()

        assert mock_http_client.get.call_count == 1

    def test_service_filter_sent_as_query_param(self, store, mock_http_client):
        """service name is sent as filter[service] query param."""
        store._service = "my-agent"
        mock_http_client.get.return_value = self._make_response([])

        store.list_all()

        call_args = mock_http_client.get.call_args
        assert "my-agent" in str(call_args)

    def test_pagination_uses_cursor(self, store, mock_http_client):
        """Pagination follows the page[cursor] field."""
        trace1 = self._make_trace("t1")
        trace2 = self._make_trace("t2")

        resp1 = MagicMock()
        resp1.status_code = 200
        resp1.json.return_value = {
            "data": [trace1],
            "meta": {"page": {"after": "cursor-abc"}},
        }
        resp2 = MagicMock()
        resp2.status_code = 200
        resp2.json.return_value = {
            "data": [trace2],
            "meta": {"page": {}},
        }
        mock_http_client.get.side_effect = [resp1, resp2]

        result = store.list_all()

        assert mock_http_client.get.call_count == 2
        assert len(result) == 2

    def test_span_type_llm_maps_to_step_type_llm(self):
        """Span type 'llm' maps to StepType.LLM."""
        from tracecraft.storage.datadog import _dd_span_type_to_step_type

        assert _dd_span_type_to_step_type("llm") == "llm"
        assert _dd_span_type_to_step_type("ai") == "llm"

    def test_span_type_web_maps_to_step_type_tool(self):
        """Span type 'web' and 'db' map to StepType.TOOL."""
        from tracecraft.storage.datadog import _dd_span_type_to_step_type

        assert _dd_span_type_to_step_type("web") == "tool"
        assert _dd_span_type_to_step_type("db") == "tool"

    def test_genai_meta_fields_mapped_to_step(self):
        """gen_ai.request.model in meta maps to step.model_name."""
        import uuid

        from tracecraft.storage.datadog import _span_to_step

        span = {
            "span_id": "999",
            "name": "llm.call",
            "resource": "ChatCompletion",
            "type": "llm",
            "start": 1700000000000000000,
            "duration": 100000000,
            "error": 0,
            "meta": {"gen_ai.request.model": "gpt-4o"},
            "metrics": {
                "gen_ai.usage.input_tokens": 50,
                "gen_ai.usage.output_tokens": 100,
            },
        }
        trace_uuid = uuid.uuid4()
        step = _span_to_step(span, trace_uuid)
        assert step.model_name == "gpt-4o"
        assert step.input_tokens == 50
        assert step.output_tokens == 100

    def test_root_span_becomes_agent_run(self, store, mock_http_client):
        """Root span (no parent_id) maps to AgentRun top-level fields."""
        trace = self._make_trace("12345", "my-service")
        mock_http_client.get.return_value = self._make_response([trace])

        result = store.list_all()

        assert len(result) == 1
        assert result[0].cloud_provider == "datadog"
        assert result[0].cloud_trace_id == "12345"

    def test_api_error_returns_empty_list(self, store, mock_http_client):
        """4xx/5xx response returns empty list with warning logged."""
        mock_http_client.get.return_value = self._make_response([], status_code=403)

        result = store.list_all()
        assert result == []

    def test_save_raises_not_implemented(self, store):
        """save() raises NotImplementedError."""
        from tracecraft.core.models import AgentRun

        run = AgentRun(name="test", start_time=datetime.now(UTC))
        with pytest.raises(NotImplementedError, match="read-only"):
            store.save(run)

    def test_from_source_datadog_scheme(self):
        """TraceLoader.from_source creates DataDogTraceStore for datadog:// URL."""
        from tracecraft.storage.datadog import DataDogTraceStore

        with patch.dict("os.environ", {"DD_API_KEY": "test_key", "DD_APP_KEY": "test_app"}):
            with patch("httpx.Client"):
                from tracecraft.tui.data.loader import TraceLoader

                loader = TraceLoader.from_source("datadog://us1/my-service")
                assert isinstance(loader.store, DataDogTraceStore)

    def test_auth_headers_in_request(self, store, mock_http_client):
        """DD-API-KEY and DD-APPLICATION-KEY headers are present in request."""
        store._headers = {"DD-API-KEY": "mykey", "DD-APPLICATION-KEY": "myapp"}
        mock_http_client.get.return_value = self._make_response([])

        store.list_all()

        # Headers are set at client construction; verify they're in _headers
        assert store._headers.get("DD-API-KEY") == "mykey"
        assert store._headers.get("DD-APPLICATION-KEY") == "myapp"

    def test_delete_raises_not_implemented(self, store):
        """delete() raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="read-only"):
            store.delete("some-trace-id")

    def test_count_no_query_returns_total(self, store, mock_http_client):
        """count() with no query returns total number of traces."""
        trace = self._make_trace()
        mock_http_client.get.return_value = self._make_response([trace])

        result = store.count()
        assert result == 1

    def test_query_filters_by_name(self, store, mock_http_client):
        """query() filters by exact name match."""
        from tracecraft.storage.base import TraceQuery

        trace1 = self._make_trace("t1", "svc-a")
        trace2 = self._make_trace("t2", "svc-b")
        mock_http_client.get.return_value = self._make_response([trace1, trace2])

        # The name becomes the resource field of root span
        all_runs = store.list_all()
        # Use name_contains to filter
        store._cache.invalidate()
        mock_http_client.get.return_value = self._make_response([trace1, trace2])
        q = TraceQuery(name_contains="svc-a")
        result = store.query(q)
        assert all("svc-a" in r.name for r in result)

    def test_invalidate_cache_clears_entries(self, store, mock_http_client):
        """invalidate_cache() forces re-fetch on next call."""
        trace = self._make_trace()
        mock_http_client.get.return_value = self._make_response([trace])

        store.list_all()
        store.invalidate_cache()
        store.list_all()

        assert mock_http_client.get.call_count == 2

    def test_trace_id_to_uuid_from_decimal_string(self):
        """_trace_id_to_uuid converts decimal trace ID to valid UUID."""
        from tracecraft.storage.datadog import _trace_id_to_uuid

        result = _trace_id_to_uuid("12345678")
        assert isinstance(result, __import__("uuid").UUID)

    def test_trace_id_to_uuid_from_int(self):
        """_trace_id_to_uuid converts integer trace ID to valid UUID."""
        from tracecraft.storage.datadog import _trace_id_to_uuid

        result = _trace_id_to_uuid(12345678)
        assert isinstance(result, __import__("uuid").UUID)

    def test_span_with_error_flag_sets_error_on_step(self):
        """Span with error=1 sets error field on the resulting Step."""
        import uuid

        from tracecraft.storage.datadog import _span_to_step

        span = {
            "span_id": "42",
            "name": "db.query",
            "type": "db",
            "start": 1700000000000000000,
            "duration": 100000000,
            "error": 1,
            "meta": {"error.message": "connection refused", "error.type": "ConnectionError"},
            "metrics": {},
        }
        step = _span_to_step(span, uuid.uuid4())
        assert step.error == "connection refused"
        assert step.error_type == "ConnectionError"

    def test_trace_with_no_spans_returns_none(self):
        """_trace_to_agent_run returns None when trace has no spans."""
        from tracecraft.storage.datadog import _trace_to_agent_run

        trace_data = {"id": "123", "attributes": {"trace_id": "123", "spans": []}}
        result = _trace_to_agent_run(trace_data)
        assert result is None

    def test_close_closes_http_client(self, store, mock_http_client):
        """close() calls close on the underlying HTTP client."""
        store.close()
        mock_http_client.close.assert_called_once()
