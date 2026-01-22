"""
Trace context propagation for distributed tracing.

Provides propagators for injecting and extracting trace context
from HTTP headers and other carriers.

Supported formats:
- W3C Trace Context (traceparent/tracestate headers)
- AWS X-Ray (X-Amzn-Trace-Id header)
- GCP Cloud Trace (X-Cloud-Trace-Context header)
"""

from agenttrace.propagation.cloudtrace import (
    CLOUD_TRACE_HEADER,
    CLOUD_TRACE_SESSION_HEADER,
    CloudTraceContextPropagator,
    decimal_to_span_id,
    span_id_to_decimal,
)
from agenttrace.propagation.w3c import (
    W3CTraceContextPropagator,
    format_trace_id,
    generate_span_id,
)
from agenttrace.propagation.xray import (
    AGENTCORE_SESSION_HEADER,
    XRAY_HEADER,
    XRayTraceContextPropagator,
    epoch_to_hex,
    generate_xray_root,
)

__all__ = [
    # W3C Trace Context
    "W3CTraceContextPropagator",
    "format_trace_id",
    "generate_span_id",
    # AWS X-Ray
    "XRayTraceContextPropagator",
    "XRAY_HEADER",
    "AGENTCORE_SESSION_HEADER",
    "generate_xray_root",
    "epoch_to_hex",
    # GCP Cloud Trace
    "CloudTraceContextPropagator",
    "CLOUD_TRACE_HEADER",
    "CLOUD_TRACE_SESSION_HEADER",
    "span_id_to_decimal",
    "decimal_to_span_id",
]
