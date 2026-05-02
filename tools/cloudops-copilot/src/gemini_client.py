from __future__ import annotations

import logging
from textwrap import dedent
from typing import Any

import aiohttp

from .config import Settings
from .utils.safe_format import sanitize_text


logger = logging.getLogger(__name__)


class GeminiClient:
    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_model
        self.enabled = settings.gemini_enabled
        self._secrets = settings.known_secrets

    async def explain_incident(self, context: dict[str, Any]) -> str | None:
        if not self.enabled or not self.api_key:
            return None

        safe_context = sanitize_text(str(context), self._secrets)
        prompt = dedent(
            f"""
            You are a DevOps/SRE assistant for a specific Azure 3-tier VM-based architecture.
            The system uses Application Gateway WAF v2, Frontend VM with Nginx, Backend VM with Java/Maven API,
            Azure SQL Database, Ansible VM, Terraform, GitHub Actions, Application Insights and Log Analytics.
            Do not suggest Azure App Service commands unless the incident explicitly mentions App Service.
            Keep the answer short, practical, and specific.
            Return only 3 short bullets:
            - likely cause
            - first check
            - safest fix

            Incident context:
            {safe_context}
            """
        ).strip()

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            f"?key={self.api_key}"
        )
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                    ]
                }
            ]
        }
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
                async with session.post(url, json=payload) as response:
                    if response.status >= 400:
                        logger.warning("Gemini API returned HTTP %s", response.status)
                        return None
                    data = await response.json()
            candidates = data.get("candidates") or []
            if not candidates:
                return None
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "\n".join(part.get("text", "") for part in parts if part.get("text"))
            return self._normalize_ai_note(text.strip()) or None
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Gemini explanation failed: %s", exc)
            return None

    def _normalize_ai_note(self, text: str) -> str:
        lines = [line.strip("•-* \t") for line in text.splitlines() if line.strip()]
        bullets: list[str] = []
        for line in lines:
            if line and line not in bullets:
                bullets.append(line[:180])
            if len(bullets) == 3:
                break
        return "\n".join(f"• {line}" for line in bullets)
