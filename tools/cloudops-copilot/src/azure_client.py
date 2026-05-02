from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Optional

from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.monitor import MonitorManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.sql import SqlManagementClient
from azure.monitor.query import MetricsQueryClient
from azure.monitor.query._models import MetricAggregationType

from .config import Settings
from .utils.time_utils import utc_now


logger = logging.getLogger(__name__)


class AzureClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.azure_enabled
        self.credential: ClientSecretCredential | None = None
        self.compute_client: ComputeManagementClient | None = None
        self.monitor_client: MonitorManagementClient | None = None
        self.metrics_client: MetricsQueryClient | None = None
        self.network_client: NetworkManagementClient | None = None
        self.sql_client: SqlManagementClient | None = None

        if not self.enabled:
            logger.warning("Azure credentials are not fully configured; Azure checks will be skipped.")
            return

        self.credential = ClientSecretCredential(
            tenant_id=settings.azure_tenant_id,
            client_id=settings.azure_client_id,
            client_secret=settings.azure_client_secret,
        )
        self.compute_client = ComputeManagementClient(self.credential, settings.azure_subscription_id)
        self.monitor_client = MonitorManagementClient(self.credential, settings.azure_subscription_id)
        self.metrics_client = MetricsQueryClient(self.credential)
        self.network_client = NetworkManagementClient(self.credential, settings.azure_subscription_id)
        self.sql_client = SqlManagementClient(self.credential, settings.azure_subscription_id)

    def _resource_id(self, provider: str, resource_type: str, name: str, parent: str | None = None) -> str:
        base = (
            f"/subscriptions/{self.settings.azure_subscription_id}"
            f"/resourceGroups/{self.settings.azure_resource_group}"
            f"/providers/{provider}/"
        )
        if parent:
            return f"{base}{parent}/{name}"
        return f"{base}{resource_type}/{name}"

    def vm_resource_id(self, vm_name: str) -> str:
        return self._resource_id("Microsoft.Compute", "virtualMachines", vm_name)

    def app_gateway_resource_id(self) -> str:
        return self._resource_id("Microsoft.Network", "applicationGateways", self.settings.app_gateway_name)

    def sql_database_resource_id(self) -> Optional[str]:
        if not self.sql_client:
            return None
        try:
            servers = list(self.sql_client.servers.list_by_resource_group(self.settings.azure_resource_group))
            for server in servers:
                databases = list(self.sql_client.databases.list_by_server(self.settings.azure_resource_group, server.name))
                for database in databases:
                    if database.name != "master":
                        return (
                            f"/subscriptions/{self.settings.azure_subscription_id}"
                            f"/resourceGroups/{self.settings.azure_resource_group}"
                            f"/providers/Microsoft.Sql/servers/{server.name}/databases/{database.name}"
                        )
        except Exception as exc:  # pragma: no cover - best effort
            logger.exception("Failed to discover SQL database resource ID: %s", exc)
        return None

    def _query_metric(self, resource_id: str, metric_name: str) -> float | None:
        if not self.metrics_client:
            return None
        try:
            response = self.metrics_client.query_resource(
                resource_id,
                metric_names=[metric_name],
                timespan=timedelta(minutes=10),
                aggregations=[MetricAggregationType.AVERAGE],
            )
            for metric in response.metrics:
                for series in metric.timeseries:
                    datapoints = [point.average for point in series.data if point.average is not None]
                    if datapoints:
                        return round(datapoints[-1], 2)
        except Exception as exc:  # pragma: no cover - best effort
            logger.exception("Metric query failed for %s (%s): %s", resource_id, metric_name, exc)
        return None

    def get_vm_cpu(self, vm_name: str) -> float | None:
        if not self.enabled:
            return None
        return self._query_metric(self.vm_resource_id(vm_name), "Percentage CPU")

    def get_sql_cpu(self) -> float | None:
        if not self.enabled:
            return None
        resource_id = self.sql_database_resource_id()
        if not resource_id:
            return None
        # Azure SQL commonly exposes cpu_percent.
        return self._query_metric(resource_id, "cpu_percent")

    def get_app_gateway_metrics(self) -> dict[str, Any]:
        if not self.enabled:
            return {"available": False, "reason": "Azure credentials not configured"}

        resource_id = self.app_gateway_resource_id()
        metrics = {
            "failed_requests": self._query_metric(resource_id, "FailedRequests"),
            "healthy_host_count": self._query_metric(resource_id, "HealthyHostCount"),
            "unhealthy_host_count": self._query_metric(resource_id, "UnhealthyHostCount"),
            "total_requests": self._query_metric(resource_id, "TotalRequests"),
            "timestamp": utc_now().isoformat(),
        }
        metrics["available"] = any(value is not None for key, value in metrics.items() if key != "timestamp")
        return metrics
