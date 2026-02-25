"""Tests for AWS X-Ray trace store."""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

boto3 = pytest.importorskip("boto3")


class TestXRayTraceStoreImport:
    """Tests for import error handling."""

    def test_import_error_when_boto3_missing(self):
        """ImportError raised with install hint when boto3 missing."""
        with patch.dict("sys.modules", {"boto3": None}):
            if "tracecraft.storage.xray" in sys.modules:
                del sys.modules["tracecraft.storage.xray"]
            with pytest.raises(ImportError, match="tracecraft\\[storage-xray\\]"):
                from tracecraft.storage.xray import XRayTraceStore

                XRayTraceStore()


class TestXRayTraceStore:
    """Tests for XRayTraceStore with mocked boto3."""

    @pytest.fixture
    def mock_boto3(self):
        mock = MagicMock()
        return mock

    @pytest.fixture
    def store(self, mock_boto3):
        """Create store bypassing __init__."""
        from tracecraft.storage._cache import TTLCache
        from tracecraft.storage.xray import XRayTraceStore

        store = XRayTraceStore.__new__(XRayTraceStore)
        store._client = MagicMock()
        store._service_name = None
        store._lookback_hours = 1
        store._cache = TTLCache(ttl_seconds=60)
        return store

    def _make_trace_response(self, trace_id="1-aabbccdd-001122334455667788990011"):
        segment_doc = {
            "id": "seg1",
            "name": "my-service",
            "start_time": 1700000000.0,
            "end_time": 1700000001.0,
            "subsegments": [],
        }
        return {
            "Traces": [
                {
                    "Id": trace_id,
                    "Segments": [{"Document": json.dumps(segment_doc)}],
                }
            ]
        }

    def _make_summary_page(self, trace_ids):
        return {"TraceSummaries": [{"Id": tid} for tid in trace_ids]}

    def test_list_all_calls_get_trace_summaries(self, store):
        """list_all uses get_trace_summaries to enumerate IDs."""
        trace_id = "1-aabbccdd-001122334455667788990011"
        # Mock paginator
        paginator = MagicMock()
        paginator.paginate.return_value = [self._make_summary_page([trace_id])]
        store._client.get_paginator.return_value = paginator
        store._client.batch_get_traces.return_value = self._make_trace_response(trace_id)

        result = store.list_all(limit=10)

        store._client.get_paginator.assert_called_with("get_trace_summaries")
        assert len(result) == 1
        assert result[0].name == "my-service"

    def test_list_all_caches_results(self, store):
        """list_all is called twice but API is called only once."""
        trace_id = "1-aabbccdd-001122334455667788990011"
        paginator = MagicMock()
        paginator.paginate.return_value = [self._make_summary_page([trace_id])]
        store._client.get_paginator.return_value = paginator
        store._client.batch_get_traces.return_value = self._make_trace_response(trace_id)

        store.list_all()
        store.list_all()

        assert store._client.get_paginator.call_count == 1

    def test_list_all_cache_expires(self, store):
        """Cache with ttl=0 results in two API calls."""
        from tracecraft.storage._cache import TTLCache

        store._cache = TTLCache(ttl_seconds=0)

        trace_id = "1-aabbccdd-001122334455667788990011"
        paginator = MagicMock()
        paginator.paginate.return_value = [self._make_summary_page([trace_id])]
        store._client.get_paginator.return_value = paginator
        store._client.batch_get_traces.return_value = self._make_trace_response(trace_id)

        store.list_all()
        time.sleep(0.01)
        store.list_all()

        assert store._client.get_paginator.call_count == 2

    def test_get_trace_by_id(self, store):
        """get() calls batch_get_traces with the correct trace ID."""
        trace_id = "1-aabbccdd-001122334455667788990011"
        store._client.batch_get_traces.return_value = self._make_trace_response(trace_id)

        result = store.get(trace_id)

        store._client.batch_get_traces.assert_called_once_with(TraceIds=[trace_id])
        assert result is not None
        assert result.name == "my-service"

    def test_get_returns_none_on_empty(self, store):
        """get() returns None when no traces found."""
        store._client.batch_get_traces.return_value = {"Traces": []}
        result = store.get("missing-id")
        assert result is None

    def test_query_with_name_filter(self, store):
        """query() filters by name in Python."""
        from tracecraft.storage.base import TraceQuery

        trace_id = "1-aabbccdd-001122334455667788990011"
        paginator = MagicMock()
        paginator.paginate.return_value = [self._make_summary_page([trace_id])]
        store._client.get_paginator.return_value = paginator
        store._client.batch_get_traces.return_value = self._make_trace_response(trace_id)

        result = store.query(TraceQuery(name="my-service"))
        assert len(result) == 1

        result_no_match = store.query(TraceQuery(name="other-service"))
        assert len(result_no_match) == 0

    def test_query_with_error_filter(self, store):
        """query() filters by has_error in Python."""
        from tracecraft.storage.base import TraceQuery

        trace_id = "1-aabbccdd-001122334455667788990011"
        seg = {
            "id": "seg1",
            "name": "my-service",
            "start_time": 1700000000.0,
            "end_time": 1700000001.0,
            "fault": True,
            "subsegments": [],
        }
        paginator = MagicMock()
        paginator.paginate.return_value = [self._make_summary_page([trace_id])]
        store._client.get_paginator.return_value = paginator
        store._client.batch_get_traces.return_value = {
            "Traces": [{"Id": trace_id, "Segments": [{"Document": json.dumps(seg)}]}]
        }

        result = store.query(TraceQuery(has_error=True))
        assert len(result) == 1
        assert result[0].error == "fault"

        result_no_err = store.query(TraceQuery(has_error=False))
        assert len(result_no_err) == 0

    def test_query_with_time_filter(self, store):
        """query() applies start_time_after/before filters in Python."""
        from tracecraft.storage.base import TraceQuery

        trace_id = "1-aabbccdd-001122334455667788990011"
        paginator = MagicMock()
        paginator.paginate.return_value = [self._make_summary_page([trace_id])]
        store._client.get_paginator.return_value = paginator
        store._client.batch_get_traces.return_value = self._make_trace_response(trace_id)

        # The trace start_time is 1700000000.0 = 2023-11-14T22:13:20+00:00
        result = store.query(TraceQuery(start_time_after="2023-01-01T00:00:00+00:00"))
        assert len(result) == 1

        result_future = store.query(TraceQuery(start_time_after="2030-01-01T00:00:00+00:00"))
        assert len(result_future) == 0

    def test_save_raises_not_implemented(self, store):
        """save() always raises NotImplementedError."""
        from tracecraft.core.models import AgentRun

        run = AgentRun(name="test", start_time=datetime.now(UTC))
        with pytest.raises(NotImplementedError, match="read-only"):
            store.save(run)

    def test_delete_raises_not_implemented(self, store):
        """delete() always raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="read-only"):
            store.delete("some-id")

    def test_count_returns_len_of_query(self, store):
        """count() returns length of list_all()."""
        trace_id = "1-aabbccdd-001122334455667788990011"
        paginator = MagicMock()
        paginator.paginate.return_value = [self._make_summary_page([trace_id])]
        store._client.get_paginator.return_value = paginator
        store._client.batch_get_traces.return_value = self._make_trace_response(trace_id)

        assert store.count() == 1

    def test_segment_to_agent_run_mapping(self, store):
        """AgentRun fields are correctly mapped from X-Ray segment."""
        from tracecraft.storage.xray import _segment_to_agent_run

        seg = {
            "name": "my-agent",
            "start_time": 1700000000.0,
            "end_time": 1700000002.5,
            "annotations": {
                "gen_ai.usage.input_tokens": 100,
                "gen_ai.usage.output_tokens": 50,
            },
            "subsegments": [],
        }
        run = _segment_to_agent_run(seg, "1-aabbccdd-001122334455667788990011")
        assert run.name == "my-agent"
        assert run.cloud_provider == "aws"
        assert run.duration_ms == pytest.approx(2500.0)
        assert run.total_tokens == 150

    def test_subsegment_to_step_type_aws(self, store):
        """namespace='aws' maps to StepType.TOOL."""
        from tracecraft.storage.xray import _infer_step_type_from_segment

        seg = {"namespace": "aws", "name": "DynamoDB"}
        assert _infer_step_type_from_segment(seg) == "tool"

    def test_subsegment_to_step_type_genai(self, store):
        """gen_ai annotation maps to StepType.LLM."""
        from tracecraft.storage.xray import _infer_step_type_from_segment

        seg = {"annotations": {"gen_ai.request.model": "claude-3"}}
        assert _infer_step_type_from_segment(seg) == "llm"

    def test_api_error_returns_empty_list(self, store):
        """ClientError during list_all returns empty list with warning."""
        from botocore.exceptions import ClientError

        store._client.get_paginator.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "GetTraceSummaries",
        )
        result = store.list_all()
        assert result == []

    def test_from_source_xray_scheme(self):
        """TraceLoader.from_source creates XRayTraceStore for xray:// URL."""
        from tracecraft.storage.xray import XRayTraceStore

        with patch("boto3.client"):
            from tracecraft.tui.data.loader import TraceLoader

            loader = TraceLoader.from_source("xray://us-east-1/my-service")
            assert isinstance(loader.store, XRayTraceStore)

    def test_service_filter_expression(self, store):
        """Service name produces correct X-Ray filter expression."""
        store._service_name = "my-service"

        paginator = MagicMock()
        paginator.paginate.return_value = [{"TraceSummaries": []}]
        store._client.get_paginator.return_value = paginator

        store.list_all()

        call_kwargs = paginator.paginate.call_args[1]
        assert call_kwargs.get("FilterExpression") == 'service("my-service")'

    def test_no_filter_expression_when_service_none(self, store):
        """No FilterExpression sent when service_name is None."""
        store._service_name = None

        paginator = MagicMock()
        paginator.paginate.return_value = [{"TraceSummaries": []}]
        store._client.get_paginator.return_value = paginator

        store.list_all()

        call_kwargs = paginator.paginate.call_args[1]
        assert "FilterExpression" not in call_kwargs
