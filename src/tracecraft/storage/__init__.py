"""
Storage backends for TraceCraft.

Provides pluggable storage for trace persistence:
- JSONL: Simple append-only file storage
- SQLite: Queryable local database storage
- MLflow: Integration with MLflow tracking server
- XRay: Read-only AWS X-Ray trace store (requires tracecraft[storage-xray])
- CloudTrace: Read-only GCP Cloud Trace store (requires tracecraft[storage-cloudtrace])
- AzureMonitor: Read-only Azure Monitor trace store (requires tracecraft[storage-azuremonitor])
- DataDog: Read-only DataDog APM trace store (requires tracecraft[storage-datadog])
"""

from tracecraft.storage.base import BaseTraceStore, TraceQuery
from tracecraft.storage.jsonl import JSONLTraceStore
from tracecraft.storage.sqlite import SQLiteTraceStore

__all__ = [
    "BaseTraceStore",
    "TraceQuery",
    "JSONLTraceStore",
    "SQLiteTraceStore",
]


def get_mlflow_store(
    tracking_uri: str | None = None,
    experiment_name: str | None = None,
) -> BaseTraceStore:
    """
    Get MLflow trace store (lazy import to avoid dependency).

    Args:
        tracking_uri: MLflow tracking server URI.
        experiment_name: Experiment name.

    Returns:
        MLflowTraceStore instance.

    Raises:
        ImportError: If mlflow is not installed.
    """
    from tracecraft.storage.mlflow import MLflowTraceStore

    return MLflowTraceStore(
        tracking_uri=tracking_uri,
        experiment_name=experiment_name,
    )


def get_xray_store(
    region: str = "us-east-1",
    service_name: str | None = None,
    lookback_hours: int = 1,
    cache_ttl_seconds: int = 60,
) -> BaseTraceStore:
    """
    Get read-only AWS X-Ray trace store (lazy import).

    Requires: tracecraft[storage-xray] or tracecraft[aws]
    Auth: boto3 credential chain (env vars, ~/.aws/credentials, instance profile).

    Args:
        region: AWS region name.
        service_name: Optional service name filter.
        lookback_hours: How far back list_all() queries.
        cache_ttl_seconds: TTL for in-memory result cache.

    Returns:
        XRayTraceStore instance.

    Raises:
        ImportError: If boto3 is not installed.
    """
    from tracecraft.storage.xray import XRayTraceStore

    return XRayTraceStore(
        region=region,
        service_name=service_name,
        lookback_hours=lookback_hours,
        cache_ttl_seconds=cache_ttl_seconds,
    )


def get_cloudtrace_store(
    project_id: str | None = None,
    service_name: str | None = None,
    lookback_hours: int = 1,
    cache_ttl_seconds: int = 60,
) -> BaseTraceStore:
    """
    Get read-only GCP Cloud Trace store (lazy import).

    Requires: tracecraft[storage-cloudtrace] or tracecraft[gcp]
    Auth: google.auth.default() ADC chain (Workload Identity → gcloud CLI → GOOGLE_APPLICATION_CREDENTIALS).

    Args:
        project_id: GCP project ID. Falls back to GOOGLE_CLOUD_PROJECT env var.
        service_name: Optional service name filter.
        lookback_hours: How far back list_all() queries.
        cache_ttl_seconds: TTL for in-memory result cache.

    Returns:
        CloudTraceTraceStore instance.

    Raises:
        ImportError: If google-cloud-trace is not installed.
        ValueError: If project_id cannot be determined.
    """
    from tracecraft.storage.cloudtrace import CloudTraceTraceStore

    return CloudTraceTraceStore(
        project_id=project_id,
        service_name=service_name,
        lookback_hours=lookback_hours,
        cache_ttl_seconds=cache_ttl_seconds,
    )


def get_azuremonitor_store(
    workspace_id: str | None = None,
    service_name: str | None = None,
    lookback_hours: int = 1,
    cache_ttl_seconds: int = 60,
) -> BaseTraceStore:
    """
    Get read-only Azure Monitor trace store (lazy import).

    Requires: tracecraft[storage-azuremonitor]
    Auth: DefaultAzureCredential (managed identity → Azure CLI → env vars).
    Workspace ID: from workspace_id arg or AZURE_MONITOR_WORKSPACE_ID env var.

    Args:
        workspace_id: Log Analytics workspace ID. Falls back to AZURE_MONITOR_WORKSPACE_ID.
        service_name: Optional service name filter (cloud_RoleName).
        lookback_hours: How far back list_all() queries.
        cache_ttl_seconds: TTL for in-memory result cache.

    Returns:
        AzureMonitorTraceStore instance.

    Raises:
        ImportError: If azure-monitor-query is not installed.
        ValueError: If workspace_id cannot be determined.
    """
    from tracecraft.storage.azuremonitor import AzureMonitorTraceStore

    return AzureMonitorTraceStore(
        workspace_id=workspace_id,
        service_name=service_name,
        lookback_hours=lookback_hours,
        cache_ttl_seconds=cache_ttl_seconds,
    )


def get_datadog_store(
    site: str = "us1",
    service: str | None = None,
    lookback_hours: int = 1,
    cache_ttl_seconds: int = 60,
) -> BaseTraceStore:
    """
    Get read-only DataDog APM trace store (lazy import).

    Requires: tracecraft[storage-datadog]
    Auth: DD_API_KEY + DD_APP_KEY environment variables (never stored in config).

    Args:
        site: DataDog site (us1, us3, us5, eu1, ap1). Defaults to "us1".
        service: Optional service name filter.
        lookback_hours: How far back list_all() queries.
        cache_ttl_seconds: TTL for in-memory result cache.

    Returns:
        DataDogTraceStore instance.

    Raises:
        ImportError: If httpx is not installed.
        ValueError: If DD_API_KEY or DD_APP_KEY are not set.
    """
    from tracecraft.storage.datadog import DataDogTraceStore

    return DataDogTraceStore(
        site=site,
        service=service,
        lookback_hours=lookback_hours,
        cache_ttl_seconds=cache_ttl_seconds,
    )
