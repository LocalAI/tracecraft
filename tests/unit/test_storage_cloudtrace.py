"""Tests for GCP Cloud Trace trace store."""

from __future__ import annotations

import sys
import time
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("google.cloud.trace_v2")


class TestCloudTraceImport:
    def test_import_error_when_google_cloud_missing(self):
        """ImportError raised with install hint when google-cloud-trace missing."""
        with patch.dict("sys.modules", {"google.cloud.trace_v2": None, "google.cloud": None}):
            if "tracecraft.storage.cloudtrace" in sys.modules:
                del sys.modules["tracecraft.storage.cloudtrace"]
            with pytest.raises(ImportError, match="tracecraft\\[storage-cloudtrace\\]"):
                from tracecraft.storage.cloudtrace import CloudTraceTraceStore

                CloudTraceTraceStore(project_id="proj")


class TestCloudTraceTraceStore:
    @pytest.fixture
    def mock_client(self):
        return MagicMock()

    @pytest.fixture
    def store(self, mock_client):
        """Create store bypassing __init__."""
        from tracecraft.storage._cache import TTLCache
        from tracecraft.storage.cloudtrace import CloudTraceTraceStore

        store = CloudTraceTraceStore.__new__(CloudTraceTraceStore)
        store._client = mock_client
        store._project_id = "test-project"
        store._service_name = None
        store._lookback_hours = 1
        store._cache = TTLCache(ttl_seconds=60)
        return store

    def _make_mock_trace(
        self,
        trace_id: str = "abc123def456789012345678901234ab",
        name: str = "test-span",
    ) -> MagicMock:
        """Create a mock Cloud Trace v2 Trace proto."""
        mock_trace = MagicMock()
        mock_trace.name = f"projects/test-project/traces/{trace_id}"

        root_span = MagicMock()
        root_span.span_id = "1234567890abcdef"
        root_span.parent_span_id = ""
        root_span.display_name.value = name
        root_span.start_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
        root_span.end_time = datetime(2023, 1, 1, 12, 0, 1, tzinfo=UTC)
        root_span.attributes.attribute_map = {}
        root_span.status.code = 0  # OK
        root_span.span_kind = 1  # INTERNAL

        mock_trace.spans = [root_span]
        return mock_trace

    def test_list_all_calls_list_traces(self, store, mock_client):
        """list_all invokes client.list_traces with the correct request."""
        mock_trace = self._make_mock_trace()
        mock_client.list_traces.return_value = [mock_trace]

        result = store.list_all(limit=10)

        mock_client.list_traces.assert_called_once()
        assert len(result) == 1
        assert result[0].name == "test-span"
        assert result[0].cloud_provider == "gcp"

    def test_list_all_caches_results(self, store, mock_client):
        """list_all is cached; client called only once on second call."""
        mock_trace = self._make_mock_trace()
        mock_client.list_traces.return_value = [mock_trace]

        store.list_all()
        store.list_all()

        assert mock_client.list_traces.call_count == 1

    def test_list_all_cache_expires(self, store, mock_client):
        """Cache with ttl=0 results in two API calls after sleep."""
        from tracecraft.storage._cache import TTLCache

        store._cache = TTLCache(ttl_seconds=0)
        mock_trace = self._make_mock_trace()
        mock_client.list_traces.return_value = [mock_trace]

        store.list_all()
        time.sleep(0.01)
        store.list_all()

        assert mock_client.list_traces.call_count == 2

    def test_get_trace_by_id(self, store, mock_client):
        """get() calls client.get_trace with the correct name."""
        mock_trace = self._make_mock_trace()
        mock_client.get_trace.return_value = mock_trace

        result = store.get("abc123def456789012345678901234ab")

        mock_client.get_trace.assert_called_once()
        call_args = mock_client.get_trace.call_args
        assert "abc123def456789012345678901234ab" in str(call_args)
        assert result is not None

    def test_get_returns_none_on_api_error(self, store, mock_client):
        """get() returns None when client raises an exception."""
        mock_client.get_trace.side_effect = Exception("Not found")
        result = store.get("nonexistent-trace-id")
        assert result is None

    def test_root_span_becomes_agent_run(self, store, mock_client):
        """Root span (no parent) maps to AgentRun top-level fields."""
        mock_trace = self._make_mock_trace(name="my-root-agent")
        mock_client.list_traces.return_value = [mock_trace]

        result = store.list_all()

        assert len(result) == 1
        assert result[0].name == "my-root-agent"
        assert result[0].cloud_trace_id is not None

    def test_cloud_trace_id_extracted_from_trace_name(self, store, mock_client):
        """cloud_trace_id is the hex suffix from the trace name."""
        trace_id = "abc123def456789012345678901234ab"
        mock_trace = self._make_mock_trace(trace_id=trace_id)
        mock_client.list_traces.return_value = [mock_trace]

        result = store.list_all()

        assert result[0].cloud_trace_id == trace_id

    def test_span_kind_to_step_type(self):
        """span_kind integer maps to correct TraceCraft step type."""
        from tracecraft.storage.cloudtrace import _span_kind_to_step_type

        assert _span_kind_to_step_type(3) == "tool"  # CLIENT
        assert _span_kind_to_step_type(4) == "tool"  # PRODUCER
        assert _span_kind_to_step_type(2) == "agent"  # SERVER
        assert _span_kind_to_step_type(5) == "agent"  # CONSUMER
        assert _span_kind_to_step_type(1) == "workflow"  # INTERNAL
        assert _span_kind_to_step_type(0) == "workflow"  # UNSPECIFIED

    def test_genai_attributes_mapped_to_step(self, store, mock_client):
        """gen_ai.request.model maps to step.model_name."""
        mock_trace = self._make_mock_trace()

        # Add a child span with gen_ai attributes
        child_span = MagicMock()
        child_span.span_id = "child1"
        child_span.parent_span_id = "1234567890abcdef"
        child_span.display_name.value = "llm-call"
        child_span.start_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
        child_span.end_time = datetime(2023, 1, 1, 12, 0, 0, 500000, tzinfo=UTC)

        mock_attr_val = MagicMock()
        mock_attr_val.string_value.value = "claude-3"
        child_span.attributes.attribute_map = {"gen_ai.request.model": mock_attr_val}
        child_span.status.code = 0
        child_span.span_kind = 1

        mock_trace.spans = [list(mock_trace.spans)[0], child_span]
        mock_client.list_traces.return_value = [mock_trace]

        result = store.list_all()

        assert len(result) == 1
        llm_steps = [s for s in result[0].steps if s.model_name == "claude-3"]
        assert len(llm_steps) == 1

    def test_child_span_step_type_llm_when_genai(self, store, mock_client):
        """Child span with gen_ai.* attributes maps to StepType.LLM."""
        from tracecraft.core.models import StepType

        mock_trace = self._make_mock_trace()
        child_span = MagicMock()
        child_span.span_id = "child2"
        child_span.parent_span_id = "1234567890abcdef"
        child_span.display_name.value = "llm-step"
        child_span.start_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
        child_span.end_time = datetime(2023, 1, 1, 12, 0, 1, tzinfo=UTC)

        mock_attr_val = MagicMock()
        mock_attr_val.string_value.value = "gpt-4"
        child_span.attributes.attribute_map = {"gen_ai.request.model": mock_attr_val}
        child_span.status.code = 0
        child_span.span_kind = 1  # INTERNAL but has gen_ai attrs

        mock_trace.spans = [list(mock_trace.spans)[0], child_span]
        mock_client.list_traces.return_value = [mock_trace]

        result = store.list_all()
        assert len(result[0].steps) == 1
        assert result[0].steps[0].type == StepType.LLM

    def test_error_status_code_captured(self, store, mock_client):
        """Non-OK status code on root span maps to AgentRun.error."""
        mock_trace = self._make_mock_trace()
        root_span = list(mock_trace.spans)[0]
        root_span.status.code = 2  # UNKNOWN — not OK
        root_span.status.message = "internal server error"
        mock_client.list_traces.return_value = [mock_trace]

        result = store.list_all()

        assert result[0].error == "internal server error"

    def test_ok_status_no_error(self, store, mock_client):
        """Status code 0 (OK) does not produce an error on AgentRun."""
        mock_trace = self._make_mock_trace()
        mock_client.list_traces.return_value = [mock_trace]

        result = store.list_all()

        assert result[0].error is None

    def test_api_error_returns_empty_list(self, store, mock_client):
        """API exception returns empty list with warning logged."""
        mock_client.list_traces.side_effect = Exception("API quota exceeded")

        result = store.list_all()
        assert result == []

    def test_save_raises_not_implemented(self, store):
        """save() raises NotImplementedError."""
        from tracecraft.core.models import AgentRun

        run = AgentRun(name="test", start_time=datetime.now(UTC))
        with pytest.raises(NotImplementedError, match="read-only"):
            store.save(run)

    def test_delete_raises_not_implemented(self, store):
        """delete() raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="read-only"):
            store.delete("some-trace-id")

    def test_count_no_query_returns_total(self, store, mock_client):
        """count() with no query returns total number of traces."""
        mock_client.list_traces.return_value = [
            self._make_mock_trace(trace_id="aaa" + "0" * 29, name="trace-1"),
            self._make_mock_trace(trace_id="bbb" + "0" * 29, name="trace-2"),
        ]

        assert store.count() == 2

    def test_count_with_query_filters(self, store, mock_client):
        """count() with query applies filters before counting."""
        from tracecraft.storage.base import TraceQuery

        mock_client.list_traces.return_value = [
            self._make_mock_trace(trace_id="aaa" + "0" * 29, name="trace-1"),
            self._make_mock_trace(trace_id="bbb" + "0" * 29, name="trace-2"),
        ]

        assert store.count(TraceQuery(name="trace-1")) == 1

    def test_query_with_name_filter(self, store, mock_client):
        """query() filters by name in Python after fetching."""
        from tracecraft.storage.base import TraceQuery

        mock_client.list_traces.return_value = [
            self._make_mock_trace(trace_id="aaa" + "0" * 29, name="agent-a"),
            self._make_mock_trace(trace_id="bbb" + "0" * 29, name="agent-b"),
        ]

        result = store.query(TraceQuery(name="agent-a"))
        assert len(result) == 1
        assert result[0].name == "agent-a"

    def test_query_with_error_filter(self, store, mock_client):
        """query() filters by has_error in Python."""
        from tracecraft.storage.base import TraceQuery

        ok_trace = self._make_mock_trace(trace_id="aaa" + "0" * 29, name="ok")
        err_trace = self._make_mock_trace(trace_id="bbb" + "0" * 29, name="err")
        err_span = list(err_trace.spans)[0]
        err_span.status.code = 2  # UNKNOWN
        err_span.status.message = "failure"

        mock_client.list_traces.return_value = [ok_trace, err_trace]

        result = store.query(TraceQuery(has_error=True))
        assert len(result) == 1
        assert result[0].name == "err"

    def test_invalidate_cache(self, store, mock_client):
        """invalidate_cache causes subsequent call to hit the API again."""
        mock_trace = self._make_mock_trace()
        mock_client.list_traces.return_value = [mock_trace]

        store.list_all()
        store.invalidate_cache()
        store.list_all()

        assert mock_client.list_traces.call_count == 2

    def test_service_name_filter_included_in_request(self, store, mock_client):
        """When service_name is set, filter is included in the request."""
        store._service_name = "my-service"
        mock_client.list_traces.return_value = []

        store.list_all()

        call_kwargs = mock_client.list_traces.call_args[1]
        request = call_kwargs.get("request", {})
        assert "filter" in request
        assert "my-service" in request["filter"]

    def test_no_filter_when_service_name_none(self, store, mock_client):
        """When service_name is None, no filter key in request."""
        store._service_name = None
        mock_client.list_traces.return_value = []

        store.list_all()

        call_kwargs = mock_client.list_traces.call_args[1]
        request = call_kwargs.get("request", {})
        assert "filter" not in request

    def test_spans_to_agent_run_no_spans_returns_none(self):
        """_spans_to_agent_run returns None for a trace with no spans."""
        from tracecraft.storage.cloudtrace import _spans_to_agent_run

        mock_trace = MagicMock()
        mock_trace.name = "projects/proj/traces/abc123"
        mock_trace.spans = []

        result = _spans_to_agent_run(mock_trace, "proj")
        assert result is None

    def test_hex_to_uuid_pads_short_id(self):
        """_hex_to_uuid pads a short hex string to 32 chars."""
        import uuid

        from tracecraft.storage.cloudtrace import _hex_to_uuid

        result = _hex_to_uuid("abc")
        # Should be a valid UUID
        assert isinstance(result, uuid.UUID)

    def test_proto_timestamp_to_datetime_with_datetime(self):
        """_proto_timestamp_to_datetime passes through a datetime with UTC tz."""
        from tracecraft.storage.cloudtrace import _proto_timestamp_to_datetime

        dt = datetime(2023, 6, 1, 12, 0, 0, tzinfo=UTC)
        result = _proto_timestamp_to_datetime(dt)
        assert result == dt

    def test_proto_timestamp_to_datetime_naive_gets_utc(self):
        """_proto_timestamp_to_datetime adds UTC to naive datetimes."""
        from tracecraft.storage.cloudtrace import _proto_timestamp_to_datetime

        naive = datetime(2023, 6, 1, 12, 0, 0)
        result = _proto_timestamp_to_datetime(naive)
        assert result.tzinfo is not None

    def test_proto_timestamp_to_datetime_none_returns_now(self):
        """_proto_timestamp_to_datetime returns a recent datetime for None."""
        from tracecraft.storage.cloudtrace import _proto_timestamp_to_datetime

        before = datetime.now(UTC)
        result = _proto_timestamp_to_datetime(None)
        after = datetime.now(UTC)
        assert before <= result <= after

    def test_decode_attribute_value_string(self):
        """_decode_attribute_value extracts .string_value.value."""
        from tracecraft.storage.cloudtrace import _decode_attribute_value

        attr = MagicMock()
        attr.string_value.value = "hello"
        assert _decode_attribute_value(attr) == "hello"

    def test_decode_attribute_value_fallback_to_str(self):
        """_decode_attribute_value falls back to str() on unknown objects."""
        from tracecraft.storage.cloudtrace import _decode_attribute_value

        class Weird:
            def __str__(self) -> str:
                return "weird"

            @property
            def string_value(self) -> None:  # type: ignore[override]
                raise AttributeError

        result = _decode_attribute_value(Weird())
        assert result == "weird"

    def test_from_source_cloudtrace_scheme(self):
        """TraceLoader.from_source creates CloudTraceTraceStore for cloudtrace:// URL."""
        from tracecraft.storage.cloudtrace import CloudTraceTraceStore

        mock_client = MagicMock()
        with patch("google.cloud.trace_v2.TraceServiceClient", return_value=mock_client):
            with patch("google.auth.default", return_value=(MagicMock(), "my-project")):
                from tracecraft.tui.data.loader import TraceLoader

                loader = TraceLoader.from_source("cloudtrace://my-project/my-service")
                assert isinstance(loader.store, CloudTraceTraceStore)
