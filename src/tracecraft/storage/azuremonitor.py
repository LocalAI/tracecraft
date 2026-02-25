"""
Azure Monitor read-only trace store for TraceCraft TUI.

Auth: DefaultAzureCredential (managed identity → Azure CLI → env vars).
Requires: tracecraft[storage-azuremonitor]
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from tracecraft.storage._cache import TTLCache
from tracecraft.storage.base import BaseTraceStore, TraceQuery

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun

logger = logging.getLogger(__name__)


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert an Azure Logs query row to a plain dict."""
    if hasattr(row, "_asdict"):
        return dict(row._asdict())
    if hasattr(row, "__dict__"):
        return {k: v for k, v in row.__dict__.items() if not k.startswith("_")}
    # Try column-based access
    try:
        return dict(zip(row._fields, row))
    except AttributeError:
        return {}


def _parse_custom_dimensions(cd: Any) -> dict[str, Any]:
    """Parse customDimensions from a Logs row (may be dict or JSON string)."""
    if cd is None:
        return {}
    if isinstance(cd, dict):
        return cd
    if isinstance(cd, str):
        try:
            import json

            parsed = json.loads(cd)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _operation_id_to_uuid(operation_id: str) -> uuid.UUID:
    """Convert an Azure operation_Id to a deterministic UUID."""
    # operation_Id is typically a GUID already; try parsing it
    try:
        return uuid.UUID(operation_id)
    except ValueError:
        # Fall back to uuid5 from name
        return uuid.uuid5(uuid.NAMESPACE_DNS, operation_id)


def _rows_to_agent_run(rows: list[dict[str, Any]], operation_id: str) -> AgentRun | None:
    """
    Convert a group of Azure Monitor rows (same operation_Id) to an AgentRun.

    Args:
        rows: List of row dicts sharing the same operation_Id.
        operation_id: The Azure operation ID / trace ID for this group.

    Returns:
        AgentRun if rows are non-empty, None otherwise.
    """
    from tracecraft.core.models import AgentRun, Step, StepType

    if not rows:
        return None

    run_id = _operation_id_to_uuid(operation_id)

    # Find root row (operation_ParentId empty or equals self)
    root_row = None
    for row in rows:
        parent_id = row.get("operation_ParentId") or ""
        if not parent_id or parent_id == operation_id:
            root_row = row
            break
    if root_row is None:
        root_row = rows[0]

    name = root_row.get("name") or "azure-trace"
    start_time = root_row.get("timestamp")
    if start_time is None:
        start_time = datetime.now(UTC)
    elif isinstance(start_time, str):
        try:
            start_time = datetime.fromisoformat(start_time)
        except ValueError:
            start_time = datetime.now(UTC)
    if hasattr(start_time, "tzinfo") and start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=UTC)

    duration_ms: float | None = root_row.get("duration")

    success = root_row.get("success")
    result_code = root_row.get("resultCode")
    error: str | None = None
    if success is False or success == "False" or success == 0:
        error = str(result_code) if result_code is not None else "request_failed"

    # Build steps from all rows
    steps: list[Step] = []
    for row in rows:
        item_type = row.get("itemType") or row.get("type") or ""
        if item_type in ("request", "AppRequests"):
            step_type = StepType.AGENT
        elif item_type in ("dependency", "AppDependencies"):
            step_type = StepType.TOOL
        elif item_type in ("exception", "AppExceptions"):
            step_type = StepType.ERROR
        else:
            step_type = StepType.WORKFLOW

        row_start = row.get("timestamp") or start_time
        if isinstance(row_start, str):
            try:
                row_start = datetime.fromisoformat(row_start)
            except ValueError:
                row_start = start_time
        if hasattr(row_start, "tzinfo") and row_start.tzinfo is None:
            row_start = row_start.replace(tzinfo=UTC)

        row_duration = row.get("duration")
        cd = _parse_custom_dimensions(row.get("customDimensions"))

        step_error: str | None = None
        row_success = row.get("success")
        if row_success is False or row_success == "False" or row_success == 0:
            step_error = str(row.get("resultCode") or "failed")

        step = Step(
            trace_id=run_id,
            type=step_type,
            name=row.get("name") or row.get("target") or "operation",
            start_time=row_start,
            duration_ms=float(row_duration) if row_duration is not None else None,
            attributes=cd,
            model_name=cd.get("gen_ai.request.model"),
            input_tokens=int(cd["gen_ai.usage.input_tokens"])
            if "gen_ai.usage.input_tokens" in cd
            else None,
            output_tokens=int(cd["gen_ai.usage.output_tokens"])
            if "gen_ai.usage.output_tokens" in cd
            else None,
            error=step_error,
        )
        steps.append(step)

    error_count = sum(1 for s in steps if s.error)

    return AgentRun(
        id=run_id,
        name=name,
        start_time=start_time,
        duration_ms=float(duration_ms) if duration_ms is not None else None,
        error=error,
        error_count=error_count,
        cloud_provider="azure",
        cloud_trace_id=operation_id,
        steps=steps,
    )


def _apply_query_filters(runs: list[AgentRun], query: TraceQuery) -> list[AgentRun]:
    """
    Apply TraceQuery filters to a list of AgentRun objects in Python.

    Args:
        runs: Full list of AgentRun objects to filter.
        query: TraceQuery specifying filter criteria and pagination.

    Returns:
        Filtered and paginated list of AgentRun objects.
    """
    result = runs

    if query.name is not None:
        result = [r for r in result if r.name == query.name]

    if query.name_contains is not None:
        result = [r for r in result if query.name_contains.lower() in r.name.lower()]

    if query.has_error is not None:
        if query.has_error:
            result = [r for r in result if r.error or r.error_count > 0]
        else:
            result = [r for r in result if not r.error and r.error_count == 0]

    if query.min_duration_ms is not None:
        result = [r for r in result if r.duration_ms and r.duration_ms >= query.min_duration_ms]

    if query.max_duration_ms is not None:
        result = [r for r in result if r.duration_ms and r.duration_ms <= query.max_duration_ms]

    if query.start_time_after is not None:
        try:
            cutoff = datetime.fromisoformat(query.start_time_after)
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=UTC)
            result = [r for r in result if r.start_time >= cutoff]
        except ValueError:
            pass

    if query.start_time_before is not None:
        try:
            cutoff = datetime.fromisoformat(query.start_time_before)
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=UTC)
            result = [r for r in result if r.start_time <= cutoff]
        except ValueError:
            pass

    reverse = query.order_desc
    if query.order_by == "duration_ms":
        result = sorted(result, key=lambda r: r.duration_ms or 0, reverse=reverse)
    else:
        result = sorted(result, key=lambda r: r.start_time, reverse=reverse)

    return result[query.offset : query.offset + query.limit]


class AzureMonitorTraceStore(BaseTraceStore):
    """
    Read-only Azure Monitor trace store for the TraceCraft TUI.

    Reads traces from Azure Log Analytics using Kusto queries.
    Authentication is handled by DefaultAzureCredential (managed identity,
    Azure CLI, environment variables — in that order).

    Example:
        store = AzureMonitorTraceStore(workspace_id="xxx", service_name="my-agent")
        traces = store.list_all(limit=20)
    """

    def __init__(
        self,
        workspace_id: str | None = None,
        service_name: str | None = None,
        lookback_hours: int = 1,
        cache_ttl_seconds: int = 60,
    ) -> None:
        """
        Initialize the Azure Monitor trace store.

        Args:
            workspace_id: Log Analytics workspace ID. Falls back to the
                ``AZURE_MONITOR_WORKSPACE_ID`` environment variable.
            service_name: Optional service name filter (cloud_RoleName).
            lookback_hours: How many hours back list_all() queries.
            cache_ttl_seconds: TTL for the in-memory cache in seconds.

        Raises:
            ImportError: If azure-monitor-query or azure-identity is not installed.
            ValueError: If workspace_id cannot be determined from arguments or env.
        """
        try:
            from azure.identity import DefaultAzureCredential
            from azure.monitor.query import LogsQueryClient
        except ImportError:
            raise ImportError(
                "azure-monitor-query and azure-identity are required for AzureMonitorTraceStore. "
                "Install with: pip install tracecraft[storage-azuremonitor]"
            )

        self._workspace_id = workspace_id or os.environ.get("AZURE_MONITOR_WORKSPACE_ID")
        if not self._workspace_id:
            raise ValueError(
                "workspace_id is required. "
                "Set AZURE_MONITOR_WORKSPACE_ID env var or pass workspace_id."
            )

        self._client = LogsQueryClient(credential=DefaultAzureCredential())
        self._service_name = service_name
        self._lookback_hours = lookback_hours
        self._cache = TTLCache(ttl_seconds=cache_ttl_seconds)

    def save(self, run: AgentRun, project_id: str | None = None) -> None:  # noqa: ARG002
        """Not supported — this store is read-only."""
        raise NotImplementedError("AzureMonitorTraceStore is read-only")

    def delete(self, trace_id: str) -> bool:
        """Not supported — this store is read-only."""
        raise NotImplementedError("AzureMonitorTraceStore is read-only")

    def list_all(self, limit: int = 100, offset: int = 0) -> list[AgentRun]:
        """
        List traces from Azure Monitor, using the TTL cache.

        Args:
            limit: Maximum number of traces to return.
            offset: Number of traces to skip (applied after caching).

        Returns:
            List of AgentRun objects.
        """
        cached = self._cache.get("list_all")
        if cached is not None:
            return cached[offset : offset + limit]

        runs = self._fetch_all()
        self._cache.set("list_all", runs)
        return runs[offset : offset + limit]

    def _build_list_query(self) -> str:
        """Build Kusto query for listing traces within the lookback window."""
        hours = self._lookback_hours
        query = f"union AppRequests, AppDependencies\n| where timestamp >= ago({hours}h)"
        if self._service_name:
            query += f'\n| where cloud_RoleName == "{self._service_name}"'
        query += "\n| extend trace_id = operation_Id\n| order by timestamp asc"
        return query

    def _fetch_all(self) -> list[AgentRun]:
        """Fetch all traces from Azure Monitor for the lookback window."""
        try:
            from azure.monitor.query import LogsQueryStatus

            query = self._build_list_query()
            timespan = timedelta(hours=self._lookback_hours + 1)

            response = self._client.query_workspace(
                workspace_id=self._workspace_id,
                query=query,
                timespan=timespan,
            )

            if response.status == LogsQueryStatus.PARTIAL:
                logger.warning("AzureMonitorTraceStore: partial results returned")
            elif response.status != LogsQueryStatus.SUCCESS:
                logger.warning("AzureMonitorTraceStore: query failed: %s", response.status)
                return []

            table = response.tables[0] if response.tables else None
            if table is None:
                return []

            # Group rows by operation_Id
            groups: dict[str, list[dict[str, Any]]] = {}
            for row in table.rows:
                row_dict = dict(zip(table.columns, row))
                op_id = str(row_dict.get("operation_Id") or row_dict.get("trace_id") or "")
                if not op_id:
                    continue
                groups.setdefault(op_id, []).append(row_dict)

            runs: list[AgentRun] = []
            for op_id, op_rows in groups.items():
                try:
                    run = _rows_to_agent_run(op_rows, op_id)
                    if run:
                        runs.append(run)
                except Exception as exc:
                    logger.debug(
                        "AzureMonitorTraceStore: failed to map operation %s: %s", op_id, exc
                    )

            return runs

        except Exception as exc:
            logger.warning("AzureMonitorTraceStore: failed to fetch traces: %s", exc)
            return []

    def get(self, trace_id: str) -> AgentRun | None:
        """
        Fetch a single trace by its Azure operation ID.

        Args:
            trace_id: Azure operation_Id (typically a GUID).

        Returns:
            AgentRun if found, None otherwise.
        """
        try:
            from azure.monitor.query import LogsQueryStatus

            query = (
                f"union AppRequests, AppDependencies, AppExceptions\n"
                f'| where operation_Id == "{trace_id}"\n'
                f"| order by timestamp asc"
            )

            response = self._client.query_workspace(
                workspace_id=self._workspace_id,
                query=query,
                timespan=timedelta(days=7),
            )

            if response.status not in (LogsQueryStatus.SUCCESS, LogsQueryStatus.PARTIAL):
                return None

            table = response.tables[0] if response.tables else None
            if table is None:
                return None

            rows = [dict(zip(table.columns, row)) for row in table.rows]
            return _rows_to_agent_run(rows, trace_id)

        except Exception as exc:
            logger.warning("AzureMonitorTraceStore.get(%s) failed: %s", trace_id, exc)
            return None

    def query(self, query: TraceQuery) -> list[AgentRun]:
        """
        Query traces with filters (applied in Python after fetching from cache).

        Args:
            query: TraceQuery with filter criteria.

        Returns:
            Filtered list of AgentRun objects.
        """
        all_runs = self.list_all(limit=10000)
        return _apply_query_filters(all_runs, query)

    def count(self, query: TraceQuery | None = None) -> int:
        """
        Count traces matching the query.

        Args:
            query: Optional filter query. If None, counts all traces.

        Returns:
            Number of matching traces.
        """
        if query is None:
            return len(self.list_all(limit=10000))
        return len(self.query(query))

    def invalidate_cache(self) -> None:
        """Invalidate the in-memory TTL cache."""
        self._cache.invalidate()
