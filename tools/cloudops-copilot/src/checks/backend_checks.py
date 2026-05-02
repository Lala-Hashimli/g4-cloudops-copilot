from __future__ import annotations

from .shared import CheckOutcome, private_vm_requires_vm_mode, skipped_outcome


async def check_backend_health(ssh_client, backend_host: str, service_name: str, settings) -> CheckOutcome:
    if private_vm_requires_vm_mode(settings, backend_host):
        return skipped_outcome("backend-health")
    command = (
        "code=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/api/ingredients); "
        "echo $code; sudo systemctl is-active "
        f"{service_name} || true"
    )
    result = await ssh_client.run_ssh(backend_host, command)
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    status_code = lines[0] if lines else "unknown"
    service_state = lines[1] if len(lines) > 1 else "unknown"
    ok = status_code == "200"
    critical_codes = {"500", "502", "503", "504"}
    return CheckOutcome(
        name="backend-health",
        ok=ok,
        summary=f"Backend API returned {status_code}, service {service_state}",
        details={"stdout": result.stdout, "stderr": result.stderr, "http_code": status_code, "service_state": service_state},
        severity="critical" if status_code in critical_codes else ("warning" if not ok else "info"),
        status="critical" if status_code in critical_codes else ("warning" if not ok else "ok"),
        should_alert=status_code in critical_codes,
    )


async def check_backend_logs(ssh_client, backend_host: str, service_name: str, settings) -> CheckOutcome:
    if private_vm_requires_vm_mode(settings, backend_host):
        return skipped_outcome("backend-logs")
    result = await ssh_client.run_ssh(backend_host, f"sudo journalctl -u {service_name} -n 80 --no-pager")
    lowered = result.stdout.lower()
    patterns = [token for token in ["exception", "error", "failed", "refused", "timeout"] if token in lowered]
    return CheckOutcome(
        name="backend-logs",
        ok=result.return_code == 0 and not patterns,
        summary="Backend log scan completed" if result.return_code == 0 else "Failed to read backend logs",
        details={"stdout": result.stdout, "stderr": result.stderr, "patterns": patterns},
        severity="warning" if patterns else ("warning" if result.return_code != 0 else "info"),
        status="warning" if patterns or result.return_code != 0 else "ok",
        should_alert=False,
    )


async def check_backend_processes(ssh_client, backend_host: str, settings) -> CheckOutcome:
    if private_vm_requires_vm_mode(settings, backend_host):
        return skipped_outcome("backend-processes")
    result = await ssh_client.run_ssh(backend_host, "ps aux --sort=-%cpu | head")
    return CheckOutcome(
        name="backend-processes",
        ok=result.return_code == 0,
        summary="Backend process snapshot collected" if result.return_code == 0 else "Failed to inspect backend processes",
        details={"stdout": result.stdout, "stderr": result.stderr},
        severity="warning" if result.return_code != 0 else "info",
        status="warning" if result.return_code != 0 else "ok",
        should_alert=False,
    )
