from __future__ import annotations

from .shared import CheckOutcome


async def check_sql_cpu(azure_client, threshold: float) -> CheckOutcome:
    value = azure_client.get_sql_cpu()
    if value is None:
        return CheckOutcome(
            name="sql-cpu",
            ok=False,
            summary="SQL metric not configured or unavailable",
            details={},
            severity="warning",
            status="warning",
            should_alert=False,
        )
    return CheckOutcome(
        name="sql-cpu",
        ok=True,
        summary=f"SQL CPU {value:.2f}%",
        details={"cpu": value},
        severity="warning" if value > threshold else "info",
        status="warning" if value > threshold else "ok",
        should_alert=value > threshold,
    )
