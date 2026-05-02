from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AnalysisResult:
    title: str
    severity: str
    root_cause: str
    impact: str = ""
    evidence: list[str] = field(default_factory=list)
    recommended_steps: list[str] = field(default_factory=list)
    suggested_commands: list[str] = field(default_factory=list)
    matched_rule: str | None = None


class IncidentAnalyzer:
    def __init__(self, rules_path: str | Path) -> None:
        self.rules_path = Path(rules_path)
        self.rules = self._load_rules()

    def _load_rules(self) -> dict[str, dict[str, Any]]:
        if not self.rules_path.exists():
            return {}
        with self.rules_path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def list_runbooks(self) -> list[str]:
        return sorted(name.replace("_", "-") for name in self.rules.keys())

    def get_runbook(self, name: str) -> dict[str, Any] | None:
        normalized = name.replace("-", "_").strip()
        return self.rules.get(normalized)

    def analyze_text(self, text: str) -> AnalysisResult:
        lowered = text.lower()
        for rule_name, rule in self.rules.items():
            keywords = [keyword.lower() for keyword in rule.get("keywords", [])]
            matched = [keyword for keyword in keywords if keyword in lowered]
            if matched:
                return AnalysisResult(
                    title=rule.get("title", rule_name.replace("_", " ").title()),
                    severity=rule.get("severity", "warning"),
                    root_cause=rule.get("root_cause", "No root cause description available."),
                    impact=rule.get("impact", "The affected feature may not work correctly for users."),
                    evidence=self._extract_evidence(text, matched),
                    recommended_steps=rule.get("fix_steps", []),
                    suggested_commands=rule.get("suggested_commands", [])[:3],
                    matched_rule=rule_name,
                )

        if any(token in lowered for token in ["502", "bad gateway"]):
            return AnalysisResult(
                title="Backend Reachability Issue",
                severity="critical",
                root_cause="A reverse proxy or gateway cannot successfully reach the backend application.",
                impact="Frontend API requests can fail and users may see missing data or gateway errors.",
                evidence=self._extract_evidence(text, ["502", "bad gateway"]),
                recommended_steps=[
                    "Check the backend health probe and Application Gateway backend health.",
                    "Confirm the backend service is listening on port 8080.",
                    "Verify NSG rules from the App Gateway subnet to the backend subnet.",
                ],
                suggested_commands=[
                    "curl -I https://group4b-demo-appgw.southeastasia.cloudapp.azure.com/api/ingredients",
                    "curl -I http://10.20.3.4:8080/api/ingredients",
                    "sudo systemctl status nginx",
                ],
            )

        if "permission denied" in lowered and "ssh" in lowered:
            return AnalysisResult(
                title="SSH Access Failure",
                severity="warning",
                root_cause="An SSH authentication or authorization problem is preventing remote checks or deployments.",
                impact="VM checks, deployments, or Ansible tasks may fail until SSH access is fixed.",
                evidence=self._extract_evidence(text, ["permission denied", "publickey"]),
                recommended_steps=[
                    "Verify the configured SSH key path.",
                    "Confirm authorized_keys on the target VM.",
                    "Check file permissions on the SSH key and .ssh directory.",
                ],
                suggested_commands=[
                    "ls -l ~/.ssh",
                    "chmod 600 ~/.ssh/id_rsa",
                    "ssh -v azureuser@10.20.3.4",
                ],
            )

        return AnalysisResult(
            title="Unknown Incident",
            severity="info",
            root_cause="No known rule matched the provided context.",
            impact="The issue needs manual triage before a precise fix can be suggested.",
            evidence=self._extract_evidence(text, [text[:200]]),
            recommended_steps=[
                "Review the raw logs or error output.",
                "Check recent infrastructure or deployment changes.",
                "Try /analyze again with more detailed logs.",
            ],
            suggested_commands=[
                "journalctl -n 80 --no-pager",
            ],
        )

    def _extract_evidence(self, text: str, patterns: list[str]) -> list[str]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        evidence: list[str] = []
        for pattern in patterns:
            for line in lines:
                if pattern.lower() in line.lower():
                    evidence.append(line[:220])
                    break
            else:
                evidence.append(pattern[:220])
        deduped: list[str] = []
        for item in evidence:
            if item and item not in deduped:
                deduped.append(item)
        return deduped[:2]
