"""
AWS X-Ray read-only trace store for TraceCraft TUI.

Auth: boto3 credential chain (env vars, ~/.aws/credentials, instance profile).
Requires: tracecraft[storage-xray] or tracecraft[aws]
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from tracecraft.storage._cache import TTLCache
from tracecraft.storage.base import BaseTraceStore, TraceQuery

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun

logger = logging.getLogger(__name__)

DATADOG_SITES = {  # not used here — just for consistency
    "us1": "api.datadoghq.com",
}


def _xray_id_to_uuid(xray_id: str) -> uuid.UUID:
    """Convert X-Ray trace ID (1-xxxxxxxx-yyyyyyyyyyyyyyyy) to a UUID."""
    # X-Ray IDs: "1-5e1b0a1a-74f6b2c8c5c7e2d3a1b2c3d4" (96-bit hex after prefix)
    # Strip the "1-" version prefix and the epoch portion
    parts = xray_id.split("-")
    hex_parts = parts[1:] if len(parts) >= 3 else parts
    hex_str = "".join(hex_parts).replace("-", "")
    # Pad to 32 hex chars
    hex_str = hex_str.ljust(32, "0")[:32]
    return uuid.UUID(hex_str)


def _parse_timestamp(ts: Any) -> datetime:
    """Convert X-Ray float timestamp to datetime."""
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=UTC)
    return datetime.now(UTC)


def _infer_step_type_from_segment(segment: dict[str, Any]) -> str:
    """Infer TraceCraft StepType string from an X-Ray subsegment."""
    namespace = segment.get("namespace", "")
    annotations = segment.get("annotations", {}) or {}
    # Check for GenAI signals
    for key in annotations:
        if key.startswith("gen_ai."):
            return "llm"
    if namespace in ("aws", "remote"):
        return "tool"
    http = segment.get("http")
    if http:
        return "tool"
    return "workflow"


def _build_step(segment: dict[str, Any], trace_id: uuid.UUID) -> Any:
    """Build a TraceCraft Step from an X-Ray subsegment dict."""
    from tracecraft.core.models import Step, StepType

    step_type_str = _infer_step_type_from_segment(segment)
    try:
        step_type = StepType(step_type_str)
    except ValueError:
        step_type = StepType.WORKFLOW

    start_ts = segment.get("start_time", time.time())
    end_ts = segment.get("end_time")
    start_dt = _parse_timestamp(start_ts)
    end_dt = _parse_timestamp(end_ts) if end_ts else None
    duration_ms: float | None = None
    if end_ts:
        duration_ms = (float(end_ts) - float(start_ts)) * 1000

    annotations = segment.get("annotations") or {}
    metadata_raw = segment.get("metadata") or {}
    # Flatten metadata (it may be nested by namespace)
    metadata: dict[str, Any] = {}
    if isinstance(metadata_raw, dict):
        for ns_val in metadata_raw.values():
            if isinstance(ns_val, dict):
                metadata.update(ns_val)
            else:
                metadata["_raw"] = ns_val
    attributes: dict[str, Any] = {**annotations, **metadata}

    # HTTP I/O
    inputs: dict[str, Any] = {}
    outputs: dict[str, Any] = {}
    http = segment.get("http") or {}
    if isinstance(http, dict):
        req = http.get("request") or {}
        resp = http.get("response") or {}
        if req:
            inputs["http_request"] = req
        if resp:
            outputs["http_response"] = resp

    # GenAI annotations override
    if "input" in annotations:
        inputs["input"] = annotations["input"]
    if "output" in annotations:
        outputs["output"] = annotations["output"]

    error: str | None = None
    error_type: str | None = None
    if segment.get("fault") or segment.get("error"):
        cause = segment.get("cause") or {}
        exceptions = cause.get("exceptions") if isinstance(cause, dict) else None
        if exceptions:
            first_exc = exceptions[0] if exceptions else {}
            error = first_exc.get("message", "fault")
            error_type = first_exc.get("type")
        else:
            error = "fault" if segment.get("fault") else "error"

    return Step(
        trace_id=trace_id,
        type=step_type,
        name=segment.get("name", "unknown"),
        start_time=start_dt,
        end_time=end_dt,
        duration_ms=duration_ms,
        inputs=inputs,
        outputs=outputs,
        attributes=attributes,
        model_name=annotations.get("gen_ai.request.model"),
        input_tokens=int(annotations["gen_ai.usage.input_tokens"])
        if "gen_ai.usage.input_tokens" in annotations
        else None,
        output_tokens=int(annotations["gen_ai.usage.output_tokens"])
        if "gen_ai.usage.output_tokens" in annotations
        else None,
        error=error,
        error_type=error_type,
    )


def _build_steps_recursive(
    subsegments: list[dict[str, Any]],
    trace_id: uuid.UUID,
) -> list[Any]:
    """Recursively build Step tree from X-Ray subsegments."""
    steps = []
    for sub in subsegments:
        step = _build_step(sub, trace_id)
        nested = sub.get("subsegments") or []
        if nested:
            step.children = _build_steps_recursive(nested, trace_id)
        steps.append(step)
    return steps


def _segment_to_agent_run(segment: dict[str, Any], xray_trace_id: str) -> Any:
    """Convert an X-Ray top-level segment to an AgentRun."""
    from tracecraft.core.models import AgentRun

    run_id = _xray_id_to_uuid(xray_trace_id)
    start_ts = segment.get("start_time", time.time())
    end_ts = segment.get("end_time")
    start_dt = _parse_timestamp(start_ts)
    end_dt = _parse_timestamp(end_ts) if end_ts else None
    duration_ms: float | None = None
    if end_ts:
        duration_ms = (float(end_ts) - float(start_ts)) * 1000

    annotations = segment.get("annotations") or {}
    metadata_raw = segment.get("metadata") or {}
    metadata: dict[str, Any] = {}
    if isinstance(metadata_raw, dict):
        for ns_val in metadata_raw.values():
            if isinstance(ns_val, dict):
                metadata.update(ns_val)
    attributes: dict[str, Any] = {**annotations, **metadata}

    error: str | None = None
    if segment.get("fault"):
        error = "fault"
    elif segment.get("error"):
        error = "error"

    subsegments = segment.get("subsegments") or []
    steps = _build_steps_recursive(subsegments, run_id)

    # Count errors
    def _count_errors(segs: list[dict[str, Any]]) -> int:
        total = 0
        for s in segs:
            if s.get("fault") or s.get("error"):
                total += 1
            total += _count_errors(s.get("subsegments") or [])
        return total

    error_count = _count_errors(subsegments)
    if error:
        error_count += 1

    total_tokens = 0
    if "gen_ai.usage.input_tokens" in annotations:
        total_tokens += int(annotations["gen_ai.usage.input_tokens"])
    if "gen_ai.usage.output_tokens" in annotations:
        total_tokens += int(annotations["gen_ai.usage.output_tokens"])

    return AgentRun(
        id=run_id,
        name=segment.get("name", "xray-trace"),
        start_time=start_dt,
        end_time=end_dt,
        duration_ms=duration_ms,
        error=error,
        error_count=error_count,
        total_tokens=total_tokens,
        attributes=attributes,
        cloud_provider="aws",
        cloud_trace_id=xray_trace_id,
        steps=steps,
    )


class XRayTraceStore(BaseTraceStore):
    """
    Read-only AWS X-Ray trace store for the TraceCraft TUI.

    Fetches traces from AWS X-Ray using the boto3 credential chain.
    Supports filtering by service name; other filters are applied in Python.

    Example:
        store = XRayTraceStore(region="us-east-1", service_name="my-agent")
        traces = store.list_all(limit=20)
    """

    def __init__(
        self,
        region: str = "us-east-1",
        service_name: str | None = None,
        lookback_hours: int = 1,
        cache_ttl_seconds: int = 60,
    ) -> None:
        """
        Initialize the X-Ray trace store.

        Args:
            region: AWS region name.
            service_name: Optional service name to filter traces. None = all.
            lookback_hours: How many hours back list_all() queries.
            cache_ttl_seconds: TTL for the in-memory cache in seconds.

        Raises:
            ImportError: If boto3 is not installed.
        """
        try:
            import boto3
        except ImportError:
            raise ImportError(
                "boto3 is required for XRayTraceStore. "
                "Install with: pip install tracecraft[storage-xray]"
            )
        self._client = boto3.client("xray", region_name=region)
        self._service_name = service_name
        self._lookback_hours = lookback_hours
        self._cache = TTLCache(ttl_seconds=cache_ttl_seconds)

    def save(self, run: AgentRun, project_id: str | None = None) -> None:  # noqa: ARG002
        """Not supported — this store is read-only."""
        raise NotImplementedError("XRayTraceStore is read-only")

    def delete(self, trace_id: str) -> bool:
        """Not supported — this store is read-only."""
        raise NotImplementedError("XRayTraceStore is read-only")

    def list_all(self, limit: int = 100, offset: int = 0) -> list[AgentRun]:
        """
        List traces from X-Ray, using the TTL cache.

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

    def _fetch_all(self) -> list[AgentRun]:
        """Fetch all traces from X-Ray for the lookback window."""
        import time as _time

        end_time = _time.time()
        start_time = end_time - self._lookback_hours * 3600

        # Build X-Ray filter expression
        filter_expr = ""
        if self._service_name:
            filter_expr = f'service("{self._service_name}")'

        # Collect trace IDs from summaries
        trace_ids: list[str] = []
        try:
            kwargs: dict[str, Any] = {
                "StartTime": start_time,
                "EndTime": end_time,
            }
            if filter_expr:
                kwargs["FilterExpression"] = filter_expr

            paginator = self._client.get_paginator("get_trace_summaries")
            for page in paginator.paginate(**kwargs):
                for summary in page.get("TraceSummaries", []):
                    tid = summary.get("Id")
                    if tid:
                        trace_ids.append(tid)
        except Exception as exc:
            logger.warning("XRayTraceStore: failed to get trace summaries: %s", exc)
            return []

        if not trace_ids:
            return []

        # Batch fetch traces (max 5 per AWS limit)
        runs: list[AgentRun] = []
        batch_size = 5
        for i in range(0, len(trace_ids), batch_size):
            batch = trace_ids[i : i + batch_size]
            try:
                response = self._client.batch_get_traces(TraceIds=batch)
                for trace in response.get("Traces", []):
                    xray_id = trace.get("Id", "")
                    segments = trace.get("Segments", [])
                    if not segments:
                        continue
                    # Use the first (root) segment
                    try:
                        import json

                        doc = json.loads(segments[0].get("Document", "{}"))
                    except Exception:
                        doc = {}
                    try:
                        run = _segment_to_agent_run(doc, xray_id)
                        runs.append(run)
                    except Exception as exc:
                        logger.debug("XRayTraceStore: failed to map trace %s: %s", xray_id, exc)
            except Exception as exc:
                logger.warning("XRayTraceStore: batch_get_traces failed: %s", exc)

        return runs

    def get(self, trace_id: str) -> AgentRun | None:
        """
        Fetch a single trace by its X-Ray trace ID or UUID string.

        Args:
            trace_id: X-Ray trace ID or UUID.

        Returns:
            AgentRun if found, None otherwise.
        """
        try:
            import json

            response = self._client.batch_get_traces(TraceIds=[trace_id])
            traces = response.get("Traces", [])
            if not traces:
                return None
            trace = traces[0]
            segments = trace.get("Segments", [])
            if not segments:
                return None
            doc = json.loads(segments[0].get("Document", "{}"))
            from tracecraft.core.models import AgentRun as _AgentRun

            return cast(_AgentRun, _segment_to_agent_run(doc, trace.get("Id", trace_id)))
        except Exception as exc:
            logger.warning("XRayTraceStore.get(%s) failed: %s", trace_id, exc)
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
        """Count traces matching the query."""
        if query is None:
            return len(self.list_all(limit=10000))
        return len(self.query(query))

    def invalidate_cache(self) -> None:
        """Invalidate the in-memory cache."""
        self._cache.invalidate()


def _apply_query_filters(runs: list[AgentRun], query: TraceQuery) -> list[AgentRun]:
    """Apply TraceQuery filters to a list of AgentRun objects in Python."""
    from datetime import datetime as _dt

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
            cutoff = _dt.fromisoformat(query.start_time_after)
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=UTC)
            result = [r for r in result if r.start_time >= cutoff]
        except ValueError:
            pass

    if query.start_time_before is not None:
        try:
            cutoff = _dt.fromisoformat(query.start_time_before)
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=UTC)
            result = [r for r in result if r.start_time <= cutoff]
        except ValueError:
            pass

    # Ordering
    reverse = query.order_desc
    if query.order_by == "duration_ms":
        result = sorted(result, key=lambda r: r.duration_ms or 0, reverse=reverse)
    else:
        result = sorted(result, key=lambda r: r.start_time, reverse=reverse)

    # Pagination
    start = query.offset
    end = query.offset + query.limit
    return result[start:end]
