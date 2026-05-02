from __future__ import annotations

import aiohttp

from .shared import CheckOutcome


async def check_latest_github_workflow(github_token: str | None, github_repo: str | None) -> CheckOutcome:
    if not github_token or not github_repo:
        return CheckOutcome(name="github-workflows", ok=False, summary="GitHub workflow checks are not configured", severity="warning", status="skipped", should_alert=False)

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
    }
    url = f"https://api.github.com/repos/{github_repo}/actions/runs?per_page=1"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                data = await response.json()
        run = (data.get("workflow_runs") or [None])[0]
        if not run:
            return CheckOutcome(name="github-workflows", ok=False, summary="No workflow runs found", severity="warning", status="warning", should_alert=False)
        conclusion = run.get("conclusion") or run.get("status")
        ok = conclusion == "success"
        return CheckOutcome(
            name="github-workflows",
            ok=ok,
            summary=f"Latest workflow {run.get('name')} is {conclusion}",
            details={"url": run.get("html_url"), "status": run.get("status"), "conclusion": run.get("conclusion")},
            severity="warning" if not ok else "info",
            status="warning" if not ok else "ok",
            should_alert=not ok,
        )
    except Exception as exc:
        return CheckOutcome(name="github-workflows", ok=False, summary="GitHub API check failed", details={"error": str(exc)}, severity="warning", status="warning", should_alert=False)
