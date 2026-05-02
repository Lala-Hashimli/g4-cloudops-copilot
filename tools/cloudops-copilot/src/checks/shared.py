from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CheckOutcome:
    name: str
    ok: bool
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    severity: str = "info"
    status: str = "ok"
    should_alert: bool = False


PRIVATE_VM_SKIP_MESSAGE = "Private VM SSH checks require running the bot on Ansible VM."


def skipped_outcome(name: str, summary: str = PRIVATE_VM_SKIP_MESSAGE, details: dict[str, Any] | None = None) -> CheckOutcome:
    return CheckOutcome(
        name=name,
        ok=True,
        summary=summary,
        details=details or {},
        severity="info",
        status="skipped",
        should_alert=False,
    )


def private_vm_requires_vm_mode(settings, host: str) -> bool:
    return settings.is_local_mode and host.startswith("10.20.")
