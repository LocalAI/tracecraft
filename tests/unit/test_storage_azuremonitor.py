"""Tests for Azure Monitor trace store."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("azure.monitor.query")


class TestAzureMonitorImport:
    def test_import_error_when_azure_monitor_missing(self) -> None:
        """ImportError raised with install hint when azure-monitor-query missing."""
        with patch.dict(
            "sys.modules",
            {
                "azure.monitor.query": None,
                "azure.identity": None,
            },
        ):
            if "tracecraft.storage.azuremonitor" in sys.modules:
                del sys.modules["tracecraft.storage.azuremonitor"]
            with pytest.raises(ImportError, match=r"tracecraft\[storage-azuremonitor\]"):
                from tracecraft.storage.azuremonitor import AzureMonitorTraceStore

                AzureMonitorTraceStore(workspace_id="ws-id")


class TestAzureMonitorTraceStore:
    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def store(self, mock_client: MagicMock) -> object:
        """Create store bypassing __init__ to avoid real Azure credential lookups."""
        from tracecraft.storage._cache import TTLCache
        from tracecraft.storage.azuremonitor import AzureMonitorTraceStore

        store = AzureMonitorTraceStore.__new__(AzureMonitorTraceStore)
        store._client = mock_client
        store._workspace_id = "test-workspace-id"
        store._service_name = None
        store._lookback_hours = 1
        store._cache = TTLCache(ttl_seconds=60)
        return store

    def _make_query_response(self, rows: list[dict], success: bool = True) -> MagicMock:
        """Create a mock LogsQueryResult with the given rows."""
        from azure.monitor.query import LogsQueryStatus

        mock_response = MagicMock()
        mock_response.status = LogsQueryStatus.SUCCESS if success else LogsQueryStatus.FAILURE
        mock_table = MagicMock()
        if rows:
            mock_table.columns = list(rows[0].keys())
            mock_table.rows = [list(r.values()) for r in rows]
        else:
            mock_table.columns = []
            mock_table.rows = []
        mock_response.tables = [mock_table]
        return mock_response

    def _make_sample_rows(
        self,
        operation_id: str = "op-123",
        service: str = "my-svc",
    ) -> list[dict]:
        return [
            {
                "operation_Id": operation_id,
                "operation_ParentId": "",
                "name": "GET /api/chat",
                "timestamp": datetime(2023, 11, 1, 12, 0, 0, tzinfo=UTC),
                "duration": 500.0,
                "success": True,
                "resultCode": "200",
                "cloud_RoleName": service,
                "customDimensions": {},
                "itemType": "request",
            }
        ]

    # -------------------------------------------------------------------------
    # Constructor / auth
    # -------------------------------------------------------------------------

    def test_requires_workspace_id(self) -> None:
        """ValueError raised when workspace_id cannot be determined from args or env."""
        import os

        backup = os.environ.pop("AZURE_MONITOR_WORKSPACE_ID", None)
        try:
            with (
                patch("azure.monitor.query.LogsQueryClient", return_value=MagicMock()),
                patch("azure.identity.DefaultAzureCredential"),
            ):
                if "tracecraft.storage.azuremonitor" in sys.modules:
                    del sys.modules["tracecraft.storage.azuremonitor"]
                from tracecraft.storage.azuremonitor import AzureMonitorTraceStore

                with pytest.raises(ValueError, match="workspace_id"):
                    AzureMonitorTraceStore(workspace_id=None)
        finally:
            if backup is not None:
                os.environ["AZURE_MONITOR_WORKSPACE_ID"] = backup

    def test_workspace_id_from_env(self) -> None:
        """AZURE_MONITOR_WORKSPACE_ID env var is used as workspace_id fallback."""
        from tracecraft.storage._cache import TTLCache
        from tracecraft.storage.azuremonitor import AzureMonitorTraceStore

        # Build a store manually to verify _workspace_id is set correctly
        store = AzureMonitorTraceStore.__new__(AzureMonitorTraceStore)
        store._workspace_id = "env-workspace-id"
        store._client = MagicMock()
        store._service_name = None
        store._lookback_hours = 1
        store._cache = TTLCache(ttl_seconds=60)

        assert store._workspace_id == "env-workspace-id"

    # -------------------------------------------------------------------------
    # list_all
    # -------------------------------------------------------------------------

    def test_list_all_runs_kusto_query(self, store: object, mock_client: MagicMock) -> None:
        """list_all invokes query_workspace with a Kusto query containing expected tables."""
        rows = self._make_sample_rows()
        mock_client.query_workspace.return_value = self._make_query_response(rows)

        result = store.list_all()

        mock_client.query_workspace.assert_called_once()
        call_args = mock_client.query_workspace.call_args
        assert "AppRequests" in str(call_args)
        assert "AppDependencies" in str(call_args)
        assert len(result) == 1

    def test_list_all_caches_results(self, store: object, mock_client: MagicMock) -> None:
        """list_all is cached; query_workspace called only once on second call."""
        rows = self._make_sample_rows()
        mock_client.query_workspace.return_value = self._make_query_response(rows)

        store.list_all()
        store.list_all()

        assert mock_client.query_workspace.call_count == 1

    def test_list_all_respects_limit_and_offset(
        self, store: object, mock_client: MagicMock
    ) -> None:
        """list_all applies limit and offset correctly to cached results."""
        # Two different operations → two AgentRuns
        rows = [
            {
                "operation_Id": f"op-{i}",
                "operation_ParentId": "",
                "name": f"run-{i}",
                "timestamp": datetime(2023, 11, 1, 12, i, 0, tzinfo=UTC),
                "duration": 100.0,
                "success": True,
                "resultCode": "200",
                "customDimensions": {},
                "itemType": "request",
            }
            for i in range(3)
        ]
        mock_client.query_workspace.return_value = self._make_query_response(rows)

        all_runs = store.list_all(limit=10)
        assert len(all_runs) == 3

        store._cache.invalidate()
        mock_client.query_workspace.return_value = self._make_query_response(rows)
        paged = store.list_all(limit=2, offset=1)
        assert len(paged) == 2

    # -------------------------------------------------------------------------
    # Kusto query construction
    # -------------------------------------------------------------------------

    def test_service_name_added_to_kusto_filter(self, store: object) -> None:
        """service_name is included in the Kusto WHERE clause."""
        store._service_name = "my-agent"
        query = store._build_list_query()
        assert 'cloud_RoleName == "my-agent"' in query

    def test_no_service_name_omits_role_filter(self, store: object) -> None:
        """When service_name is None, no cloud_RoleName filter is added."""
        store._service_name = None
        query = store._build_list_query()
        assert "cloud_RoleName" not in query

    def test_lookback_hours_used_in_query(self, store: object) -> None:
        """lookback_hours value appears in the Kusto ago() expression."""
        store._lookback_hours = 3
        query = store._build_list_query()
        assert "ago(3h)" in query

    # -------------------------------------------------------------------------
    # get() — single trace fetch
    # -------------------------------------------------------------------------

    def test_get_trace_by_id_queries_operation_id(
        self, store: object, mock_client: MagicMock
    ) -> None:
        """get() queries by operation_Id and returns a matching AgentRun."""
        rows = self._make_sample_rows(operation_id="abc-123")
        mock_client.query_workspace.return_value = self._make_query_response(rows)

        result = store.get("abc-123")

        call_args = mock_client.query_workspace.call_args
        assert "abc-123" in str(call_args)
        assert result is not None

    def test_get_returns_none_on_empty_table(self, store: object, mock_client: MagicMock) -> None:
        """get() returns None when query returns no rows."""
        mock_client.query_workspace.return_value = self._make_query_response([])

        result = store.get("nonexistent-id")

        assert result is None

    def test_get_returns_none_on_api_error(self, store: object, mock_client: MagicMock) -> None:
        """get() returns None when the API raises an exception."""
        mock_client.query_workspace.side_effect = Exception("Network error")

        result = store.get("some-id")

        assert result is None

    # -------------------------------------------------------------------------
    # Row → model mapping
    # -------------------------------------------------------------------------

    def test_apprequest_row_becomes_agent_run(self, store: object, mock_client: MagicMock) -> None:
        """AppRequests root row maps to an AgentRun with correct fields."""
        rows = self._make_sample_rows()
        mock_client.query_workspace.return_value = self._make_query_response(rows)

        result = store.list_all()

        assert len(result) == 1
        run = result[0]
        assert run.name == "GET /api/chat"
        assert run.cloud_provider == "azure"
        assert run.duration_ms == 500.0

    def test_appdependency_row_becomes_tool_step(
        self, store: object, mock_client: MagicMock
    ) -> None:
        """AppDependencies row maps to a Step with StepType.TOOL."""
        from tracecraft.core.models import StepType

        rows = [
            {
                "operation_Id": "op-456",
                "operation_ParentId": "",
                "name": "root-request",
                "timestamp": datetime(2023, 11, 1, 12, 0, 0, tzinfo=UTC),
                "duration": 300.0,
                "success": True,
                "resultCode": "200",
                "customDimensions": {},
                "itemType": "request",
            },
            {
                "operation_Id": "op-456",
                "operation_ParentId": "op-456",
                "name": "SQL | SELECT",
                "timestamp": datetime(2023, 11, 1, 12, 0, 0, tzinfo=UTC),
                "duration": 50.0,
                "success": True,
                "resultCode": "200",
                "customDimensions": {},
                "itemType": "dependency",
            },
        ]
        mock_client.query_workspace.return_value = self._make_query_response(rows)

        result = store.list_all()

        assert len(result) == 1
        tool_steps = [s for s in result[0].steps if s.type == StepType.TOOL]
        assert len(tool_steps) >= 1

    def test_appexception_row_becomes_error_step(
        self, store: object, mock_client: MagicMock
    ) -> None:
        """AppExceptions row maps to a Step with StepType.ERROR."""
        from tracecraft.core.models import StepType

        rows = [
            {
                "operation_Id": "op-789",
                "operation_ParentId": "",
                "name": "failed-request",
                "timestamp": datetime(2023, 11, 1, 12, 0, 0, tzinfo=UTC),
                "duration": 100.0,
                "success": False,
                "resultCode": "500",
                "customDimensions": {},
                "itemType": "request",
            },
            {
                "operation_Id": "op-789",
                "operation_ParentId": "op-789",
                "name": "NullReferenceException",
                "timestamp": datetime(2023, 11, 1, 12, 0, 0, tzinfo=UTC),
                "duration": None,
                "success": False,
                "resultCode": None,
                "customDimensions": {},
                "itemType": "exception",
            },
        ]
        mock_client.query_workspace.return_value = self._make_query_response(rows)

        result = store.list_all()

        assert len(result) == 1
        error_steps = [s for s in result[0].steps if s.type == StepType.ERROR]
        assert len(error_steps) >= 1

    def test_failed_request_sets_error_on_run(self, store: object, mock_client: MagicMock) -> None:
        """A root row with success=False populates the AgentRun.error field."""
        rows = [
            {
                "operation_Id": "op-fail",
                "operation_ParentId": "",
                "name": "broken-endpoint",
                "timestamp": datetime(2023, 11, 1, 12, 0, 0, tzinfo=UTC),
                "duration": 200.0,
                "success": False,
                "resultCode": "500",
                "customDimensions": {},
                "itemType": "request",
            }
        ]
        mock_client.query_workspace.return_value = self._make_query_response(rows)

        result = store.list_all()

        assert len(result) == 1
        assert result[0].error == "500"

    def test_custom_dimensions_set_on_step(self, store: object, mock_client: MagicMock) -> None:
        """customDimensions dict is stored in Step.attributes."""
        rows = [
            {
                "operation_Id": "op-cd",
                "operation_ParentId": "",
                "name": "llm-call",
                "timestamp": datetime(2023, 11, 1, 12, 0, 0, tzinfo=UTC),
                "duration": 100.0,
                "success": True,
                "resultCode": "200",
                "customDimensions": {
                    "gen_ai.request.model": "gpt-4",
                    "gen_ai.usage.input_tokens": "100",
                    "gen_ai.usage.output_tokens": "50",
                },
                "itemType": "request",
            }
        ]
        mock_client.query_workspace.return_value = self._make_query_response(rows)

        result = store.list_all()

        assert len(result) == 1
        step = result[0].steps[0]
        assert step.model_name == "gpt-4"
        assert step.input_tokens == 100
        assert step.output_tokens == 50

    def test_cloud_trace_id_matches_operation_id(
        self, store: object, mock_client: MagicMock
    ) -> None:
        """AgentRun.cloud_trace_id equals the Azure operation_Id."""
        rows = self._make_sample_rows(operation_id="my-op-guid")
        mock_client.query_workspace.return_value = self._make_query_response(rows)

        result = store.list_all()

        assert result[0].cloud_trace_id == "my-op-guid"

    # -------------------------------------------------------------------------
    # Error handling
    # -------------------------------------------------------------------------

    def test_api_error_returns_empty_list(self, store: object, mock_client: MagicMock) -> None:
        """API exception in list_all returns empty list rather than raising."""
        mock_client.query_workspace.side_effect = Exception("Authentication failed")

        result = store.list_all()
        assert result == []

    def test_partial_status_logs_warning(
        self, store: object, mock_client: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """PARTIAL query status emits a warning log but still returns results."""
        import logging

        from azure.monitor.query import LogsQueryStatus

        rows = self._make_sample_rows()
        mock_response = self._make_query_response(rows)
        mock_response.status = LogsQueryStatus.PARTIAL
        mock_client.query_workspace.return_value = mock_response

        with caplog.at_level(logging.WARNING):
            result = store.list_all()

        assert "partial" in caplog.text.lower()
        assert len(result) == 1

    # -------------------------------------------------------------------------
    # Read-only guards
    # -------------------------------------------------------------------------

    def test_save_raises_not_implemented(self, store: object) -> None:
        """save() raises NotImplementedError with a 'read-only' message."""
        from tracecraft.core.models import AgentRun

        run = AgentRun(name="test", start_time=datetime.now(UTC))
        with pytest.raises(NotImplementedError, match="read-only"):
            store.save(run)

    def test_delete_raises_not_implemented(self, store: object) -> None:
        """delete() raises NotImplementedError with a 'read-only' message."""
        with pytest.raises(NotImplementedError, match="read-only"):
            store.delete("some-id")

    # -------------------------------------------------------------------------
    # query() + count()
    # -------------------------------------------------------------------------

    def test_query_filters_by_name(self, store: object, mock_client: MagicMock) -> None:
        """query() with name filter returns only matching runs."""
        from tracecraft.storage.base import TraceQuery

        rows = [
            {
                "operation_Id": f"op-{i}",
                "operation_ParentId": "",
                "name": "target-run" if i == 0 else "other-run",
                "timestamp": datetime(2023, 11, 1, 12, i, 0, tzinfo=UTC),
                "duration": 100.0,
                "success": True,
                "resultCode": "200",
                "customDimensions": {},
                "itemType": "request",
            }
            for i in range(2)
        ]
        mock_client.query_workspace.return_value = self._make_query_response(rows)

        result = store.query(TraceQuery(name="target-run"))
        assert len(result) == 1
        assert result[0].name == "target-run"

    def test_query_filters_by_has_error(self, store: object, mock_client: MagicMock) -> None:
        """query() with has_error=True returns only runs with errors."""
        from tracecraft.storage.base import TraceQuery

        rows = [
            {
                "operation_Id": "op-ok",
                "operation_ParentId": "",
                "name": "ok-run",
                "timestamp": datetime(2023, 11, 1, 12, 0, 0, tzinfo=UTC),
                "duration": 100.0,
                "success": True,
                "resultCode": "200",
                "customDimensions": {},
                "itemType": "request",
            },
            {
                "operation_Id": "op-err",
                "operation_ParentId": "",
                "name": "error-run",
                "timestamp": datetime(2023, 11, 1, 12, 1, 0, tzinfo=UTC),
                "duration": 100.0,
                "success": False,
                "resultCode": "500",
                "customDimensions": {},
                "itemType": "request",
            },
        ]
        mock_client.query_workspace.return_value = self._make_query_response(rows)

        result = store.query(TraceQuery(has_error=True))
        assert all(r.error or r.error_count > 0 for r in result)

    def test_count_no_query_returns_total(self, store: object, mock_client: MagicMock) -> None:
        """count(None) returns total number of traces."""
        rows = self._make_sample_rows()
        mock_client.query_workspace.return_value = self._make_query_response(rows)

        assert store.count() == 1

    # -------------------------------------------------------------------------
    # Cache invalidation
    # -------------------------------------------------------------------------

    def test_invalidate_cache_forces_refetch(self, store: object, mock_client: MagicMock) -> None:
        """After invalidate_cache(), list_all() re-queries the API."""
        rows = self._make_sample_rows()
        mock_client.query_workspace.return_value = self._make_query_response(rows)

        store.list_all()
        store.invalidate_cache()
        store.list_all()

        assert mock_client.query_workspace.call_count == 2

    # -------------------------------------------------------------------------
    # TraceLoader integration
    # -------------------------------------------------------------------------

    def test_from_source_azuremonitor_scheme(self) -> None:
        """TraceLoader.from_source creates AzureMonitorTraceStore for azuremonitor:// URLs."""
        from tracecraft.storage.azuremonitor import AzureMonitorTraceStore
        from tracecraft.tui.data.loader import TraceLoader

        with patch.object(AzureMonitorTraceStore, "__init__", return_value=None):
            loader = TraceLoader.from_source("azuremonitor://my-workspace/my-service")
            assert isinstance(loader.store, AzureMonitorTraceStore)
