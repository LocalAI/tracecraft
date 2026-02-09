"""Backend URL parsing and configuration for OTel export targets.

This module handles parsing endpoint URLs and extracting backend-specific
configuration for various observability platforms.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class BackendConfig:
    """Configuration extracted from a backend URL.

    Attributes:
        scheme: The URL scheme (http, https, tracecraft, datadog, etc.)
        host: The host portion of the URL.
        port: The port number (default varies by scheme).
        path: The path portion of the URL.
        endpoint_url: The full HTTP(S) endpoint URL for OTLP export.
        backend_type: Identified backend type (tracecraft, datadog, azure, aws, generic).
    """

    scheme: str
    host: str
    port: int
    path: str
    endpoint_url: str
    backend_type: str


# Default ports for different schemes
DEFAULT_PORTS = {
    "http": 4318,
    "https": 4318,
    "tracecraft": 4318,
    "datadog": 4318,
    "azure": 443,
    "aws": 443,
    "xray": 443,
}

# Map custom schemes to their actual HTTP scheme
SCHEME_TO_HTTP = {
    "tracecraft": "http",
    "datadog": "https",
    "azure": "https",
    "aws": "https",
    "xray": "https",
}

# Map schemes to backend types
SCHEME_TO_BACKEND = {
    "tracecraft": "tracecraft",
    "datadog": "datadog",
    "azure": "azure",
    "aws": "aws",
    "xray": "aws",
    "http": "generic",
    "https": "generic",
}


def parse_endpoint(endpoint: str | None = None) -> BackendConfig:
    """Parse an endpoint URL into a BackendConfig.

    Supports various URL formats:
    - Standard HTTP(S): http://localhost:4318, https://otel.example.com
    - TraceCraft: tracecraft://localhost:4318 (alias for http://)
    - DataDog: datadog://intake.datadoghq.com
    - Azure: azure://appinsights.azure.com
    - AWS X-Ray: aws://xray.us-east-1.amazonaws.com

    Environment variable fallbacks (in order):
    - TRACECRAFT_ENDPOINT
    - OTEL_EXPORTER_OTLP_ENDPOINT
    - Default: http://localhost:4318

    Args:
        endpoint: The endpoint URL to parse. If None, uses environment variables.

    Returns:
        BackendConfig with parsed URL components and the resolved HTTP endpoint.

    Example:
        >>> config = parse_endpoint("tracecraft://localhost:4318")
        >>> config.endpoint_url
        'http://localhost:4318/v1/traces'
        >>> config.backend_type
        'tracecraft'
    """
    # Resolve endpoint from environment if not provided
    if endpoint is None:
        endpoint = os.environ.get(
            "TRACECRAFT_ENDPOINT",
            os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"),
        )

    # Parse the URL
    parsed = urlparse(endpoint)

    # Extract scheme (default to http if none)
    scheme = parsed.scheme.lower() if parsed.scheme else "http"

    # Extract host
    host = parsed.hostname or "localhost"

    # Extract port (use default for scheme if not specified)
    port = parsed.port or DEFAULT_PORTS.get(scheme, 4318)

    # Extract path (default to /v1/traces for OTLP)
    path = parsed.path if parsed.path and parsed.path != "/" else "/v1/traces"

    # Determine the actual HTTP scheme
    http_scheme = SCHEME_TO_HTTP.get(scheme, scheme)

    # Build the final endpoint URL
    endpoint_url = f"{http_scheme}://{host}:{port}{path}"

    # Determine backend type
    backend_type = SCHEME_TO_BACKEND.get(scheme, "generic")

    return BackendConfig(
        scheme=scheme,
        host=host,
        port=port,
        path=path,
        endpoint_url=endpoint_url,
        backend_type=backend_type,
    )


def get_service_name(service_name: str | None = None) -> str:
    """Get the service name from parameter or environment.

    Args:
        service_name: Explicit service name. If None, uses environment variables.

    Returns:
        The service name to use.

    Environment variable fallbacks (in order):
    - TRACECRAFT_SERVICE_NAME
    - OTEL_SERVICE_NAME
    - Default: "tracecraft-agent"
    """
    if service_name:
        return service_name

    return os.environ.get(
        "TRACECRAFT_SERVICE_NAME",
        os.environ.get("OTEL_SERVICE_NAME", "tracecraft-agent"),
    )
