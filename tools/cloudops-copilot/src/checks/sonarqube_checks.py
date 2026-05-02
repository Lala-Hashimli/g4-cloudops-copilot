from __future__ import annotations

from .shared import CheckOutcome, skipped_outcome


async def check_sonarqube_health(ssh_client, sonarqube_host: str, settings) -> CheckOutcome:
    if settings.is_local_mode:
        return skipped_outcome("sonarqube-health", "SSH-based SonarQube checks require running the bot on Ansible VM.")
    result = await ssh_client.run_ssh(
        sonarqube_host,
        "curl -s -o /dev/null -w '%{http_code}' http://localhost:9000",
    )
    if result.return_code != 0:
        return CheckOutcome(
            name="sonarqube-health",
            ok=False,
            summary="Could not verify SonarQube over SSH",
            details={"stdout": result.stdout, "stderr": result.stderr},
            severity="warning",
            status="warning",
            should_alert=False,
        )
    code = result.stdout.strip()
    ok = code in {"200", "302"}
    return CheckOutcome(
        name="sonarqube-health",
        ok=ok,
        summary=f"SonarQube HTTP status {code or 'unknown'}",
        details={"stdout": result.stdout, "stderr": result.stderr},
        severity="critical" if not ok else "info",
        status="critical" if not ok else "ok",
        should_alert=not ok,
    )


async def check_sonarqube_container(ssh_client, sonarqube_host: str, settings) -> CheckOutcome:
    if settings.is_local_mode:
        return skipped_outcome("sonarqube-container", "SSH-based SonarQube checks require running the bot on Ansible VM.")
    result = await ssh_client.run_ssh(sonarqube_host, "docker ps || true")
    if result.return_code != 0:
        return CheckOutcome(
            name="sonarqube-container",
            ok=False,
            summary="Could not inspect SonarQube containers over SSH",
            details={"stdout": result.stdout, "stderr": result.stderr},
            severity="warning",
            status="warning",
            should_alert=False,
        )
    return CheckOutcome(
        name="sonarqube-container",
        ok=result.return_code == 0,
        summary="Docker container listing collected",
        details={"stdout": result.stdout, "stderr": result.stderr},
        severity="warning" if result.return_code != 0 else "info",
        status="warning" if result.return_code != 0 else "ok",
        should_alert=False,
    )
