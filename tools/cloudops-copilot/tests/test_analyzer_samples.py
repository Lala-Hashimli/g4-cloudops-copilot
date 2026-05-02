from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analyzer import IncidentAnalyzer
from src.message_templates import format_analysis_html


class AnalyzerSampleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = IncidentAnalyzer(ROOT / "rules.yml")

    def _render(self, text: str) -> str:
        result = self.analyzer.analyze_text(text)
        return format_analysis_html(
            title=result.title,
            severity=result.severity,
            root_cause=result.root_cause,
            evidence=result.evidence,
            impact=result.impact,
            steps=result.recommended_steps,
            commands=result.suggested_commands,
            ai_note="• likely cause\n• first check\n• safest fix",
        )

    def test_localhost_frontend_issue(self) -> None:
        rendered = self._render("Request failed: http://localhost:8080/api/ingredients")
        self.assertIn("Frontend API Targeted to Localhost", rendered)
        self.assertIn("localhost:8080", rendered)

    def test_mixed_content_issue(self) -> None:
        rendered = self._render("Mixed Content: The page was loaded over HTTPS but requested http://20.205.212.128/api/ingredients")
        self.assertIn("Mixed Content Detected", rendered)
        self.assertIn("20.205.212.128", rendered)

    def test_app_gateway_502(self) -> None:
        rendered = self._render("502 Bad Gateway from Application Gateway")
        self.assertIn("Application Gateway", rendered)
        self.assertIn("curl -I https://group4b-demo-appgw.southeastasia.cloudapp.azure.com/api/ingredients", rendered)

    def test_apt_update_failed(self) -> None:
        rendered = self._render("fatal: Failed to update apt cache\nping 8.8.8.8: 100% packet loss")
        self.assertIn("Outbound Connectivity Problem", rendered)
        self.assertIn("ping -c 4 8.8.8.8", rendered)

    def test_nginx_502(self) -> None:
        rendered = self._render("nginx upstream timed out and returned 502")
        self.assertIn("Nginx Upstream Error", rendered)
        self.assertIn("/var/log/nginx/error.log", rendered)

    def test_github_actions_failed(self) -> None:
        rendered = self._render("workflow failed: Process completed with exit code 1")
        self.assertIn("GitHub Actions Pipeline Failure", rendered)


if __name__ == "__main__":
    unittest.main()
