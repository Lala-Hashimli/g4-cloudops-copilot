from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from .checks.app_gateway_checks import check_gateway_api_route, check_gateway_availability
from .checks.backend_checks import check_backend_health
from .checks.github_checks import check_latest_github_workflow
from .checks.nginx_checks import check_nginx_errors, check_nginx_status
from .checks.shared import CheckOutcome
from .checks.sql_checks import check_sql_cpu
from .checks.sonarqube_checks import check_sonarqube_health
from .checks.vm_checks import check_vm_cpu_from_azure
from .message_templates import format_alert
from .utils.time_utils import utc_now


logger = logging.getLogger(__name__)


@dataclass
class AlertState:
    last_sent_epoch: float = 0.0
    consecutive_hits: int = 0
    last_value: float = 0.0


class MonitorLoop:
    def __init__(self, settings, bot_notifier, azure_client, ssh_client) -> None:
        self.settings = settings
        self.bot_notifier = bot_notifier
        self.azure_client = azure_client
        self.ssh_client = ssh_client
        self._alert_state: dict[str, AlertState] = {}
        self._running = True

    async def start(self) -> None:
        while self._running:
            try:
                await self.run_once()
            except Exception as exc:  # pragma: no cover - runtime guard
                logger.exception("Monitor loop iteration failed: %s", exc)
            await asyncio.sleep(self.settings.check_interval_seconds)

    def stop(self) -> None:
        self._running = False

    async def run_once(self) -> None:
        results = await asyncio.gather(
            check_vm_cpu_from_azure(self.azure_client, self.settings.backend_vm_name, self.settings.cpu_threshold),
            check_vm_cpu_from_azure(self.azure_client, self.settings.frontend_vm_name, self.settings.cpu_threshold),
            check_sql_cpu(self.azure_client, self.settings.sql_cpu_threshold),
            check_gateway_availability(self.settings.app_gateway_url),
            check_gateway_api_route(self.settings.app_gateway_url),
            check_backend_health(self.ssh_client, self.settings.backend_vm_host, self.settings.backend_service_name, self.settings),
            check_nginx_status(self.ssh_client, self.settings.frontend_vm_host, self.settings),
            check_nginx_errors(self.ssh_client, self.settings.frontend_vm_host, self.settings),
            check_sonarqube_health(self.ssh_client, self.settings.sonarqube_vm_host, self.settings),
            check_latest_github_workflow(self.settings.github_token, self.settings.github_repo),
        )
        for result in results:
            await self._process_result(result)
        await self._process_app_gateway_metrics()

    async def _process_result(self, result: CheckOutcome) -> None:
        severity = result.severity
        metric = result.name
        current_value = result.summary
        threshold = "configured threshold"
        possible_causes = [result.summary]
        recommended_steps = ["Review the related check details and logs."]
        suggested_command = None

        if result.name.endswith("-cpu") and "cpu" in result.details and result.should_alert:
            cpu = float(result.details["cpu"])
            threshold_value = self.settings.sql_cpu_threshold if result.name == "sql-cpu" else self.settings.cpu_threshold
            threshold = f"{threshold_value}%"
            possible_causes = ["High traffic", "A stuck or heavy process", "Recent deployment or scan load"]
            recommended_steps = ["Inspect top processes.", "Review recent logs.", "Check request volume and recent changes."]
            suggested_command = "ps aux --sort=-%cpu | head"

        elif result.name in {"appgw-api", "appgw-frontend", "backend-health", "nginx-status", "nginx-errors", "sonarqube-health"} and result.should_alert:
            possible_causes = [result.summary]
            recommended_steps = ["Check service status.", "Review logs.", "Validate network path and upstream health."]
            suggested_command = "curl -I https://group4b-demo-appgw.southeastasia.cloudapp.azure.com"

        elif result.name == "github-workflows" and result.should_alert and self.settings.github_enabled:
            possible_causes = [result.summary]
            recommended_steps = ["Review the failing workflow logs.", "Verify secrets and runner status."]

        if result.should_alert and self._cooldown_elapsed(result.name):
            self._mark_alert_sent(result.name)
            message = format_alert(
                title=result.name,
                resource=result.details.get("vm_name", self.settings.azure_resource_group),
                component=result.name,
                metric=metric,
                current_value=current_value,
                threshold=threshold,
                severity=severity,
                possible_root_cause=possible_causes,
                recommended_steps=recommended_steps,
                suggested_command=suggested_command,
            )
            await self.bot_notifier.send_message(message)

    async def _process_app_gateway_metrics(self) -> None:
        metrics = self.azure_client.get_app_gateway_metrics()
        unhealthy = metrics.get("unhealthy_host_count")
        healthy = metrics.get("healthy_host_count")
        failed_requests = metrics.get("failed_requests")
        frontend = await check_gateway_availability(self.settings.app_gateway_url)
        api = await check_gateway_api_route(self.settings.app_gateway_url)

        state = self._alert_state.setdefault("appgw-unhealthy-hosts", AlertState())
        if unhealthy is None or unhealthy <= 0:
            state.consecutive_hits = 0
            state.last_value = float(failed_requests or 0)
            return

        live_checks_ok = frontend.ok and api.ok
        state.consecutive_hits += 1

        severity = "warning"
        title = "App Gateway Partial Backend Health Warning"
        possible_root_cause = [
            "Azure metric shows a partial backend health issue.",
            "One backend target may have flapped briefly.",
            "The metric may be stale or recovering while live traffic is healthy.",
        ]
        recommended_steps = [
            "Check Application Gateway backend health in Azure Portal.",
            "Confirm the health probe path and backend pool membership.",
            "Review recent backend restarts or rolling changes.",
        ]

        if frontend.details.get("status", 0) >= 500 or api.details.get("status", 0) >= 500:
            severity = "critical"
            title = "App Gateway Live Traffic Failure"
        elif healthy == 0:
            severity = "critical"
            title = "App Gateway Has No Healthy Backends"
        elif unhealthy >= 1 and state.consecutive_hits >= 2:
            severity = "critical"
            title = "App Gateway Backend Health Issue"
        elif failed_requests and failed_requests > state.last_value:
            severity = "critical"
            title = "App Gateway Failed Requests Increasing"
            possible_root_cause = [
                "Application Gateway is observing increasing failed requests.",
                "A backend or routing issue may be affecting live traffic."
            ]

        if severity == "warning" and live_checks_ok:
            possible_root_cause = [
                "Azure metric shows possible partial unhealthy host count, but live checks are passing."
            ]

        alert_key = f"appgw-{severity}"
        if not self._cooldown_elapsed(alert_key):
            return
        self._mark_alert_sent(alert_key)
        message = format_alert(
            title=title,
            resource=self.settings.app_gateway_name,
            component="Application Gateway",
            metric="Unhealthy host count",
            current_value=str(unhealthy),
            threshold="0",
            severity=severity,
            possible_root_cause=possible_root_cause,
            recommended_steps=recommended_steps,
            suggested_command="curl http://10.20.3.4:8080/api/ingredients",
        )
        state.last_value = float(failed_requests or 0)
        await self.bot_notifier.send_message(message)

    def _cooldown_elapsed(self, key: str) -> bool:
        state = self._alert_state.setdefault(key, AlertState())
        return (utc_now().timestamp() - state.last_sent_epoch) >= self.settings.alert_cooldown_seconds

    def _mark_alert_sent(self, key: str) -> None:
        self._alert_state.setdefault(key, AlertState()).last_sent_epoch = utc_now().timestamp()
