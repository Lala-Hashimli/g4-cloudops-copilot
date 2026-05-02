from __future__ import annotations

import html
from typing import Iterable


def bullet_list(items: Iterable[str]) -> str:
    values = [item for item in items if item]
    return "\n".join(f"• {item}" for item in values) if values else "• None"


def numbered_list(items: Iterable[str]) -> str:
    values = [item for item in items if item]
    return "\n".join(f"{index}. {item}" for index, item in enumerate(values, start=1)) if values else "1. None"


def format_alert(
    *,
    title: str,
    resource: str,
    component: str,
    metric: str,
    current_value: str,
    threshold: str,
    severity: str,
    possible_root_cause: list[str],
    recommended_steps: list[str],
    suggested_command: str | None = None,
    duration: str = "last check interval",
) -> str:
    message = [
        "🚨 Azure Incident Detected",
        "",
        f"Resource: {resource}",
        f"Component: {component}",
        f"Metric: {metric}",
        f"Current value: {current_value}",
        f"Threshold: {threshold}",
        f"Duration: {duration}",
        f"Severity: {severity.title()}",
        "",
        "Possible root cause:",
        bullet_list(possible_root_cause),
        "",
        "Recommended next steps:",
        numbered_list(recommended_steps),
    ]
    if suggested_command:
        message.extend(["", "Suggested command:", f"`{suggested_command}`"])
    return "\n".join(message)


def format_health_report(title: str, sections: list[tuple[str, str]]) -> str:
    lines = [f"📊 {title}", ""]
    for heading, content in sections:
        lines.extend([f"{heading}", content, ""])
    return "\n".join(lines).strip()


def format_health_line(name: str, status: str, summary: str) -> tuple[str, str]:
    label = status.title()
    return (name, f"{label}: {summary}")


def escape_html(value: str) -> str:
    return html.escape(value or "")


def format_analysis(title: str, severity: str, root_cause: str, evidence: list[str], steps: list[str], commands: list[str] | None = None) -> str:
    lines = [
        f"🛠️ {title}",
        f"Severity: {severity.title()}",
        "",
        "Likely root cause:",
        root_cause,
        "",
        "Evidence:",
        bullet_list(evidence),
        "",
        "Recommended next steps:",
        numbered_list(steps),
    ]
    if commands:
        lines.extend(["", "Suggested commands:", bullet_list([f"`{command}`" for command in commands])])
    return "\n".join(lines)


def format_analysis_html(
    *,
    title: str,
    severity: str,
    root_cause: str,
    evidence: list[str],
    impact: str,
    steps: list[str],
    commands: list[str] | None = None,
    ai_note: str | None = None,
) -> str:
    safe_title = escape_html(title)
    safe_severity = escape_html(severity.title())
    safe_root = escape_html(root_cause)
    safe_impact = escape_html(impact)
    safe_evidence = "\n".join(f"• {escape_html(item)}" for item in evidence[:2]) or "• None"
    safe_steps = "\n".join(f"{idx}. {escape_html(step)}" for idx, step in enumerate(steps[:3], start=1)) or "1. None"
    safe_commands = "\n".join(commands[:3]) if commands else ""

    sections = [
        f"<b>🚨 {safe_title}</b>",
        f"<b>Severity:</b> {safe_severity}",
        "",
        "<b>Root cause:</b>",
        safe_root,
        "",
        "<b>Evidence:</b>",
        safe_evidence,
        "",
        "<b>Impact:</b>",
        safe_impact,
        "",
        "<b>Next steps:</b>",
        safe_steps,
    ]

    if safe_commands:
        sections.extend(
            [
                "",
                "<b>Commands:</b>",
                f"<pre><code>{escape_html(safe_commands)}</code></pre>",
            ]
        )

    if ai_note:
        sections.extend(["", "<b>AI note:</b>", escape_html(ai_note).replace("•", "•")])

    return "\n".join(sections)


def format_runbook(name: str, root_cause: str, fix_steps: list[str], commands: list[str] | None = None) -> str:
    lines = [
        f"📘 Runbook: {name}",
        "",
        "Root cause summary:",
        root_cause,
        "",
        "Fix steps:",
        numbered_list(fix_steps),
    ]
    if commands:
        lines.extend(["", "Useful commands:", bullet_list([f"`{command}`" for command in commands])])
    return "\n".join(lines)
