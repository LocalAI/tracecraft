"""
DataDog APM read-only trace store for TraceCraft TUI.

Auth: DD_API_KEY + DD_APP_KEY environment variables (never stored in config).
Requires: tracecraft[storage-datadog]
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

DATADOG_SITES: dict[str, str] = {
    "us1": "api.datadoghq.com",
    "us3": "api.us3.datadoghq.com",
    "us5": "api.us5.datadoghq.com",
    "eu1": "api.datadoghq.eu",
    "ap1": "api.ap1.datadoghq.com",
}


def _trace_id_to_uuid(trace_id: str | int) -> uuid.UUID:
    """Convert a DataDog trace ID (uint64 decimal or hex) to a UUID."""
    if isinstance(trace_id, int):
        hex_str = format(trace_id, "032x")
    else:
        trace_id_str = str(trace_id).strip()
        # Try decimal first, then hex, then fall back to hashing the raw string
        try:
            hex_str = format(int(trace_id_str), "032x")
        except ValueError:
            try:
                cleaned = trace_id_str.replace("-", "")
                hex_str = format(int(cleaned, 16), "032x")
            except ValueError:
                # Non-numeric, non-hex ID: derive a deterministic UUID via name hash
                return uuid.uuid5(uuid.NAMESPACE_DNS, trace_id_str)
    hex_str = hex_str[:32]
    return uuid.UUID(hex_str)


def _dd_span_type_to_step_type(span_type: str) -> str:
    """Map DataDog span type string to TraceCraft StepType string."""
    t = (span_type or "").lower()
    if t in ("web", "http"):
        return "tool"
    if t in ("db", "cache", "sql", "redis", "mongodb", "elasticsearch"):
        return "tool"
    if t in ("llm", "ai", "gen_ai"):
        return "llm"
    return "workflow"


def _span_to_step(span: dict[str, Any], trace_id: uuid.UUID) -> Any:
    """Build a TraceCraft Step from a DataDog span dict."""
    from tracecraft.core.models import Step, StepType

    span_type = span.get("type") or ""
    step_type_str = _dd_span_type_to_step_type(span_type)

    meta = span.get("meta") or {}
    metrics = span.get("metrics") or {}

    # Check gen_ai meta for LLM override
    if "gen_ai.request.model" in meta or "model" in meta or "ai.input" in meta:
        step_type_str = "llm"

    try:
        step_type = StepType(step_type_str)
    except ValueError:
        step_type = StepType.WORKFLOW

    # Timing: DataDog uses nanoseconds for start, nanoseconds for duration
    start_ns = span.get("start") or 0
    duration_ns = span.get("duration") or 0
    start_dt = datetime.fromtimestamp(start_ns / 1e9, tz=UTC) if start_ns else datetime.now(UTC)
    duration_ms = duration_ns / 1e6 if duration_ns else None
    end_dt = datetime.fromtimestamp((start_ns + duration_ns) / 1e9, tz=UTC) if start_ns else None

    # I/O
    inputs: dict[str, Any] = {}
    outputs: dict[str, Any] = {}
    if "http.url" in meta:
        inputs["url"] = meta["http.url"]
    if "http.method" in meta:
        inputs["method"] = meta["http.method"]
    if "ai.input" in meta:
        inputs["ai_input"] = meta["ai.input"]
    if "http.status_code" in meta:
        outputs["status_code"] = meta["http.status_code"]
    if "ai.output" in meta:
        outputs["ai_output"] = meta["ai.output"]

    attributes: dict[str, Any] = {**meta, **{str(k): v for k, v in metrics.items()}}

    error: str | None = None
    error_type: str | None = None
    if span.get("error"):
        error = meta.get("error.message") or "error"
        error_type = meta.get("error.type")

    model_name = meta.get("gen_ai.request.model") or meta.get("model")
    input_tokens: int | None = None
    output_tokens: int | None = None
    if "gen_ai.usage.input_tokens" in metrics:
        input_tokens = int(metrics["gen_ai.usage.input_tokens"])
    if "gen_ai.usage.output_tokens" in metrics:
        output_tokens = int(metrics["gen_ai.usage.output_tokens"])

    return Step(
        trace_id=trace_id,
        type=step_type,
        name=span.get("name") or span.get("resource") or "span",
        start_time=start_dt,
        end_time=end_dt,
        duration_ms=duration_ms,
        inputs=inputs,
        outputs=outputs,
        attributes=attributes,
        model_name=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        error=error,
        error_type=error_type,
    )


def _trace_to_agent_run(trace_data: dict[str, Any]) -> AgentRun | None:
    """Convert a DataDog JSONAPI trace object to an AgentRun."""
    from tracecraft.core.models import AgentRun

    attributes = trace_data.get("attributes") or {}
    spans = attributes.get("spans") or []
    if not spans:
        return None

    # Find root span: parent_id == null or "0" or equals trace_id
    raw_trace_id = attributes.get("trace_id") or trace_data.get("id") or "0"
    run_id = _trace_id_to_uuid(raw_trace_id)

    root_span = None
    for span in spans:
        parent_id = span.get("parent_id")
        if not parent_id or str(parent_id) in ("0", "null", ""):
            root_span = span
            break
    if root_span is None:
        root_span = spans[0]

    start_ns = root_span.get("start") or 0
    duration_ns = root_span.get("duration") or 0
    start_dt = datetime.fromtimestamp(start_ns / 1e9, tz=UTC) if start_ns else datetime.now(UTC)
    duration_ms = duration_ns / 1e6 if duration_ns else None

    error: str | None = None
    if root_span.get("error"):
        meta = root_span.get("meta") or {}
        error = meta.get("error.message") or "error"

    total_tokens = 0
    steps = []
    for span in spans:
        if span is root_span:
            continue
        step = _span_to_step(span, run_id)
        steps.append(step)
        if step.input_tokens:
            total_tokens += step.input_tokens
        if step.output_tokens:
            total_tokens += step.output_tokens

    root_metrics = root_span.get("metrics") or {}
    if "gen_ai.usage.input_tokens" in root_metrics:
        total_tokens += int(root_metrics["gen_ai.usage.input_tokens"])
    if "gen_ai.usage.output_tokens" in root_metrics:
        total_tokens += int(root_metrics["gen_ai.usage.output_tokens"])

    service = root_span.get("service") or attributes.get("service") or "datadog-trace"
    name = root_span.get("resource") or root_span.get("name") or service

    return AgentRun(
        id=run_id,
        name=name,
        start_time=start_dt,
        duration_ms=duration_ms,
        error=error,
        error_count=sum(1 for s in steps if s.error),
        total_tokens=total_tokens,
        cloud_provider="datadog",
        cloud_trace_id=str(raw_trace_id),
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


class DataDogTraceStore(BaseTraceStore):
    """
    Read-only DataDog APM trace store for the TraceCraft TUI.

    Fetches traces from DataDog APM API using DD_API_KEY and DD_APP_KEY.

    Example:
        store = DataDogTraceStore(site="us1", service="my-agent")
        traces = store.list_all(limit=20)
    """

    def __init__(
        self,
        site: str = "us1",
        service: str | None = None,
        lookback_hours: int = 1,
        cache_ttl_seconds: int = 60,
    ) -> None:
        """
        Initialize the DataDog trace store.

        Args:
            site: DataDog site key (us1, us3, us5, eu1, ap1).
            service: Optional service name to filter traces. None = all.
            lookback_hours: How many hours back list_all() queries.
            cache_ttl_seconds: TTL for the in-memory cache in seconds.

        Raises:
            ImportError: If httpx is not installed.
            ValueError: If DD_API_KEY or DD_APP_KEY env vars are not set.
        """
        try:
            import httpx
        except ImportError:
            raise ImportError(
                "httpx is required for DataDogTraceStore. "
                "Install with: pip install tracecraft[storage-datadog]"
            )

        api_key = os.environ.get("DD_API_KEY")
        app_key = os.environ.get("DD_APP_KEY")
        if not api_key:
            raise ValueError("DD_API_KEY environment variable is required for DataDogTraceStore.")
        if not app_key:
            raise ValueError("DD_APP_KEY environment variable is required for DataDogTraceStore.")

        host = DATADOG_SITES.get(site, f"api.{site}.datadoghq.com")
        self._base_url = f"https://{host}"
        self._headers = {
            "DD-API-KEY": api_key,
            "DD-APPLICATION-KEY": app_key,
            "Content-Type": "application/json",
        }
        self._http_client = httpx.Client(
            base_url=self._base_url,
            headers=self._headers,
            timeout=30.0,
        )
        self._service = service
        self._lookback_hours = lookback_hours
        self._cache = TTLCache(ttl_seconds=cache_ttl_seconds)

    def save(self, run: AgentRun, project_id: str | None = None) -> None:  # noqa: ARG002
        """Not supported — this store is read-only."""
        raise NotImplementedError("DataDogTraceStore is read-only")

    def delete(self, trace_id: str) -> bool:
        """Not supported — this store is read-only."""
        raise NotImplementedError("DataDogTraceStore is read-only")

    def list_all(self, limit: int = 100, offset: int = 0) -> list[AgentRun]:
        """
        List traces from DataDog APM, using the TTL cache.

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
        """Fetch all traces from DataDog APM for the lookback window."""
        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(hours=self._lookback_hours)

        params: dict[str, Any] = {
            "filter[from]": start_time.isoformat(),
            "filter[to]": end_time.isoformat(),
            "page[limit]": 100,
        }
        if self._service:
            params["filter[service]"] = self._service

        runs: list[AgentRun] = []
        cursor: str | None = None

        try:
            while True:
                if cursor:
                    params["page[cursor]"] = cursor

                response = self._http_client.get("/api/v2/apm/traces", params=params)
                if response.status_code >= 400:
                    logger.warning(
                        "DataDogTraceStore: API returned %d: %s",
                        response.status_code,
                        response.text[:200],
                    )
                    break

                data = response.json()
                trace_list = data.get("data") or []

                for trace_data in trace_list:
                    try:
                        run = _trace_to_agent_run(trace_data)
                        if run:
                            runs.append(run)
                    except Exception as exc:
                        logger.debug("DataDogTraceStore: failed to map trace: %s", exc)

                # Pagination
                meta = data.get("meta") or {}
                page_meta = meta.get("page") or {}
                next_cursor = page_meta.get("after")
                if not next_cursor or not trace_list:
                    break
                cursor = next_cursor

        except Exception as exc:
            logger.warning("DataDogTraceStore: failed to fetch traces: %s", exc)

        return runs

    def get(self, trace_id: str) -> AgentRun | None:
        """
        Fetch a single trace by ID.

        Args:
            trace_id: DataDog trace ID.

        Returns:
            AgentRun if found, None otherwise.
        """
        try:
            response = self._http_client.get(
                "/api/v2/apm/traces",
                params={"filter[query]": f"trace_id:{trace_id}", "page[limit]": 1},
            )
            if response.status_code >= 400:
                return None
            data = response.json()
            trace_list = data.get("data") or []
            if not trace_list:
                return None
            return _trace_to_agent_run(trace_list[0])
        except Exception as exc:
            logger.warning("DataDogTraceStore.get(%s) failed: %s", trace_id, exc)
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

    def close(self) -> None:
        """Close the HTTP client."""
        self._http_client.close()
