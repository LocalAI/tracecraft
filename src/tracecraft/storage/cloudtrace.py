"""
GCP Cloud Trace read-only trace store for TraceCraft TUI.

Auth: google.auth.default() ADC chain (Workload Identity → gcloud CLI → GOOGLE_APPLICATION_CREDENTIALS).
Requires: tracecraft[storage-cloudtrace] or tracecraft[gcp]
"""

from __future__ import annotations

import contextlib
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


def _hex_to_uuid(hex_str: str) -> uuid.UUID:
    """Convert a hex trace ID to a UUID (pad or truncate to 32 hex chars)."""
    hex_str = hex_str.replace("-", "").ljust(32, "0")[:32]
    return uuid.UUID(hex_str)


def _proto_timestamp_to_datetime(ts: Any) -> datetime:
    """Convert a Protobuf Timestamp or datetime-like object to datetime."""
    if ts is None:
        return datetime.now(UTC)
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=UTC)
        return ts
    # Protobuf Timestamp has .seconds and .nanos
    try:
        return datetime.fromtimestamp(ts.seconds + ts.nanos / 1e9, tz=UTC)
    except AttributeError:
        return datetime.now(UTC)


def _decode_attribute_value(attr_val: Any) -> Any:
    """Decode a Cloud Trace v2 AttributeValue union to a Python scalar."""
    with contextlib.suppress(Exception):
        # AttributeValue has string_value, int_value, bool_value
        if hasattr(attr_val, "string_value") and attr_val.string_value:
            return attr_val.string_value.value
        if hasattr(attr_val, "int_value"):
            return attr_val.int_value
        if hasattr(attr_val, "bool_value"):
            return attr_val.bool_value
    return str(attr_val)


def _span_kind_to_step_type(span_kind: int) -> str:
    """Map Cloud Trace v2 SpanKind int to TraceCraft StepType string."""
    # SpanKind: 0=UNSPECIFIED, 1=INTERNAL, 2=SERVER, 3=CLIENT, 4=PRODUCER, 5=CONSUMER
    if span_kind in (3, 4):  # CLIENT, PRODUCER
        return "tool"
    if span_kind in (2, 5):  # SERVER, CONSUMER
        return "agent"
    return "workflow"


def _spans_to_agent_run(trace: Any, project_id: str) -> AgentRun | None:  # noqa: ARG001
    """Convert a Cloud Trace v2 Trace proto to an AgentRun."""
    from tracecraft.core.models import AgentRun, Step, StepType

    # trace.name = "projects/{project}/traces/{trace_id}"
    trace_name = trace.name
    trace_id_hex = trace_name.split("/")[-1] if "/" in trace_name else trace_name
    run_id = _hex_to_uuid(trace_id_hex)

    spans = list(trace.spans)
    if not spans:
        return None

    # Find root span: parentSpanId == "" or "0000000000000000"
    root_span = None
    for span in spans:
        psid = getattr(span, "parent_span_id", "") or ""
        if psid in ("", "0", "0000000000000000"):
            root_span = span
            break
    if root_span is None:
        root_span = spans[0]

    start_dt = _proto_timestamp_to_datetime(root_span.start_time)
    end_dt = _proto_timestamp_to_datetime(root_span.end_time)
    duration_ms = (end_dt - start_dt).total_seconds() * 1000

    # Decode root span attributes
    root_attrs: dict[str, Any] = {}
    attr_map = getattr(root_span, "attributes", None)
    if attr_map:
        for k, v in attr_map.attribute_map.items():
            root_attrs[k] = _decode_attribute_value(v)

    # Check for error
    status = getattr(root_span, "status", None)
    error: str | None = None
    if status:
        # StatusCode 0=OK, 1=CANCELLED, 2=UNKNOWN, etc.
        if hasattr(status, "code") and status.code not in (0, 1):  # not OK
            error = getattr(status, "message", None) or f"status_code={status.code}"

    # Build a span-id → Step uuid mapping for parent linking
    span_uuid_map: dict[str, uuid.UUID] = {}
    for span in spans:
        sid = getattr(span, "span_id", "") or ""
        span_uuid_map[sid] = uuid.uuid4()

    # Build Steps for non-root spans
    steps: list[Step] = []
    for span in spans:
        if span is root_span:
            continue
        sid = getattr(span, "span_id", "") or ""
        psid = getattr(span, "parent_span_id", "") or ""

        span_attrs: dict[str, Any] = {}
        attr_map2 = getattr(span, "attributes", None)
        if attr_map2:
            for k, v in attr_map2.attribute_map.items():
                span_attrs[k] = _decode_attribute_value(v)

        # Infer step type
        has_genai = any(k.startswith("gen_ai.") for k in span_attrs)
        if has_genai:
            step_type = StepType.LLM
        else:
            sk = getattr(span, "span_kind", 0)
            step_type = StepType(_span_kind_to_step_type(int(sk) if hasattr(sk, "__int__") else 0))

        span_start = _proto_timestamp_to_datetime(span.start_time)
        span_end = _proto_timestamp_to_datetime(span.end_time)
        span_dur = (span_end - span_start).total_seconds() * 1000

        span_status = getattr(span, "status", None)
        span_error: str | None = None
        if span_status and hasattr(span_status, "code") and span_status.code not in (0, 1):
            span_error = getattr(span_status, "message", None) or f"code={span_status.code}"

        parent_step_id = span_uuid_map.get(psid) if psid else None

        step = Step(
            id=span_uuid_map.get(sid, uuid.uuid4()),
            trace_id=run_id,
            parent_id=parent_step_id,
            type=step_type,
            name=getattr(span.display_name, "value", str(span.display_name)),
            start_time=span_start,
            end_time=span_end,
            duration_ms=span_dur,
            attributes=span_attrs,
            model_name=span_attrs.get("gen_ai.request.model"),
            input_tokens=int(span_attrs["gen_ai.usage.input_tokens"])
            if "gen_ai.usage.input_tokens" in span_attrs
            else None,
            output_tokens=int(span_attrs["gen_ai.usage.output_tokens"])
            if "gen_ai.usage.output_tokens" in span_attrs
            else None,
            error=span_error,
        )
        steps.append(step)

    root_name = getattr(root_span.display_name, "value", str(root_span.display_name))

    return AgentRun(
        id=run_id,
        name=root_name,
        start_time=start_dt,
        end_time=end_dt,
        duration_ms=duration_ms,
        error=error,
        error_count=sum(1 for s in steps if s.error),
        attributes=root_attrs,
        cloud_provider="gcp",
        cloud_trace_id=trace_id_hex,
        steps=steps,
    )


def _apply_query_filters(runs: list[AgentRun], query: TraceQuery) -> list[AgentRun]:
    """Apply TraceQuery filters to a list of AgentRun objects in Python."""
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


class CloudTraceTraceStore(BaseTraceStore):
    """
    Read-only GCP Cloud Trace store for the TraceCraft TUI.

    Reads traces from GCP Cloud Trace v2 API using Application Default Credentials.

    Example:
        store = CloudTraceTraceStore(project_id="my-project", service_name="my-agent")
        traces = store.list_all(limit=20)
    """

    def __init__(
        self,
        project_id: str | None = None,
        service_name: str | None = None,
        lookback_hours: int = 1,
        cache_ttl_seconds: int = 60,
    ) -> None:
        """
        Initialize the Cloud Trace store.

        Args:
            project_id: GCP project ID. Falls back to GOOGLE_CLOUD_PROJECT env var.
            service_name: Optional service name filter.
            lookback_hours: How many hours back list_all() queries.
            cache_ttl_seconds: TTL for the in-memory cache in seconds.

        Raises:
            ImportError: If google-cloud-trace is not installed.
            ValueError: If project_id cannot be determined.
        """
        try:
            from google.cloud import trace_v2
        except ImportError:
            raise ImportError(
                "google-cloud-trace is required for CloudTraceTraceStore. "
                "Install with: pip install tracecraft[storage-cloudtrace]"
            )

        try:
            from google.auth import default as gauth_default

            credentials, detected_project = gauth_default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
        except Exception:
            credentials = None
            detected_project = None

        self._project_id = (
            project_id
            or (detected_project if isinstance(detected_project, str) else None)
            or os.environ.get("GOOGLE_CLOUD_PROJECT")
        )
        if not self._project_id:
            raise ValueError(
                "project_id is required. Set GOOGLE_CLOUD_PROJECT env var or pass project_id."
            )

        self._client = trace_v2.TraceServiceClient(credentials=credentials)
        self._service_name = service_name
        self._lookback_hours = lookback_hours
        self._cache = TTLCache(ttl_seconds=cache_ttl_seconds)

    def save(self, run: AgentRun, project_id: str | None = None) -> None:  # noqa: ARG002
        """Not supported — this store is read-only."""
        raise NotImplementedError("CloudTraceTraceStore is read-only")

    def delete(self, trace_id: str) -> bool:
        """Not supported — this store is read-only."""
        raise NotImplementedError("CloudTraceTraceStore is read-only")

    def list_all(self, limit: int = 100, offset: int = 0) -> list[AgentRun]:
        """
        List traces from Cloud Trace, using the TTL cache.

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
        """Fetch all traces from Cloud Trace for the lookback window."""
        from google.protobuf.timestamp_pb2 import Timestamp

        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(hours=self._lookback_hours)

        start_ts = Timestamp()
        start_ts.FromDatetime(start_time)
        end_ts = Timestamp()
        end_ts.FromDatetime(end_time)

        filter_parts: list[str] = []
        if self._service_name:
            filter_parts.append(f'+labels."service.name":"{self._service_name}"')

        filter_str = " ".join(filter_parts) if filter_parts else ""

        try:
            parent = f"projects/{self._project_id}"
            request: dict[str, Any] = {
                "parent": parent,
                "start_time": start_ts,
                "end_time": end_ts,
                "page_size": 200,
            }
            if filter_str:
                request["filter"] = filter_str

            project_id = self._project_id
            assert project_id is not None  # guaranteed by __init__
            runs: list[AgentRun] = []
            for trace in self._client.list_traces(request=request):
                try:
                    run = _spans_to_agent_run(trace, project_id)
                    if run:
                        runs.append(run)
                except Exception as exc:
                    logger.debug("CloudTraceTraceStore: failed to map trace: %s", exc)
            return runs
        except Exception as exc:
            logger.warning("CloudTraceTraceStore: failed to list traces: %s", exc)
            return []

    def get(self, trace_id: str) -> AgentRun | None:
        """
        Fetch a single trace by its Cloud Trace ID.

        Args:
            trace_id: Hex trace ID.

        Returns:
            AgentRun if found, None otherwise.
        """
        try:
            project_id = self._project_id
            assert project_id is not None  # guaranteed by __init__
            name = f"projects/{project_id}/traces/{trace_id}"
            trace = self._client.get_trace(request={"name": name})
            return _spans_to_agent_run(trace, project_id)
        except Exception as exc:
            logger.warning("CloudTraceTraceStore.get(%s) failed: %s", trace_id, exc)
            return None

    def query(self, query: TraceQuery) -> list[AgentRun]:
        """
        Query traces with filters (applied in Python).

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
