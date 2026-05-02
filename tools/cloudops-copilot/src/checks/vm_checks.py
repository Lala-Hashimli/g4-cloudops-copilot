from __future__ import annotations

from .shared import CheckOutcome


async def check_vm_cpu_from_azure(azure_client, vm_name: str, threshold: float) -> CheckOutcome:
    value = azure_client.get_vm_cpu(vm_name)
    if value is None:
        return CheckOutcome(
            name=f"{vm_name}-cpu",
            ok=False,
            summary="VM CPU metric unavailable",
            details={"vm_name": vm_name},
            severity="warning",
            status="warning",
            should_alert=False,
        )
    return CheckOutcome(
        name=f"{vm_name}-cpu",
        ok=True,
        summary=f"CPU {value:.2f}%",
        details={"vm_name": vm_name, "cpu": value},
        severity="warning" if value > threshold else "info",
        status="warning" if value > threshold else "ok",
        should_alert=value > threshold,
    )


async def check_top_processes(ssh_client, host: str) -> CheckOutcome:
    result = await ssh_client.run_ssh(host, "ps aux --sort=-%cpu | head")
    return CheckOutcome(
        name=f"{host}-top",
        ok=result.return_code == 0,
        summary="Top CPU processes collected" if result.return_code == 0 else "Failed to collect top CPU processes",
        details={"stdout": result.stdout, "stderr": result.stderr},
        severity="warning" if result.return_code != 0 else "info",
        status="warning" if result.return_code != 0 else "ok",
    )
