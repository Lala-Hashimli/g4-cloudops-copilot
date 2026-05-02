from __future__ import annotations

from .shared import CheckOutcome, private_vm_requires_vm_mode, skipped_outcome


async def check_nginx_status(ssh_client, frontend_host: str, settings) -> CheckOutcome:
    if private_vm_requires_vm_mode(settings, frontend_host):
        return skipped_outcome("nginx-status")
    result = await ssh_client.run_ssh(frontend_host, "systemctl is-active nginx")
    active = result.stdout.strip() == "active"
    return CheckOutcome(
        name="nginx-status",
        ok=active,
        summary=f"Nginx is {'active' if active else 'not active'}",
        details={"stdout": result.stdout, "stderr": result.stderr},
        severity="critical" if not active else "info",
        status="critical" if not active else "ok",
        should_alert=not active,
    )


async def check_nginx_errors(ssh_client, frontend_host: str, settings) -> CheckOutcome:
    if private_vm_requires_vm_mode(settings, frontend_host):
        return skipped_outcome("nginx-errors")
    result = await ssh_client.run_ssh(frontend_host, "sudo tail -n 80 /var/log/nginx/error.log")
    lowered = f"{result.stdout}\n{result.stderr}".lower()
    bad_patterns = [token for token in ["502", "504", "upstream timed out", "connection refused"] if token in lowered]
    return CheckOutcome(
        name="nginx-errors",
        ok=result.return_code == 0 and not bad_patterns,
        summary="Nginx error log looks clean" if not bad_patterns else "Nginx error patterns detected",
        details={"stdout": result.stdout, "stderr": result.stderr, "patterns": bad_patterns},
        severity="critical" if bad_patterns else ("warning" if result.return_code != 0 else "info"),
        status="critical" if bad_patterns else ("warning" if result.return_code != 0 else "ok"),
        should_alert=bool(bad_patterns),
    )
