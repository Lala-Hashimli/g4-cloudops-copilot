from __future__ import annotations

import aiohttp

from .shared import CheckOutcome


async def check_gateway_availability(app_gateway_url: str, timeout: int = 15) -> CheckOutcome:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            async with session.get(app_gateway_url) as response:
                return CheckOutcome(
                    name="appgw-frontend",
                    ok=200 <= response.status < 400,
                    summary=f"Frontend returned HTTP {response.status}",
                    details={"status": response.status},
                    severity="critical" if response.status >= 500 else ("warning" if response.status >= 400 else "info"),
                    status="critical" if response.status >= 500 else ("warning" if response.status >= 400 else "ok"),
                    should_alert=response.status >= 500,
                )
    except Exception as exc:
        return CheckOutcome(
            name="appgw-frontend",
            ok=False,
            summary="Frontend availability check failed",
            details={"error": str(exc)},
            severity="critical",
            status="critical",
            should_alert=True,
        )


async def check_gateway_api_route(app_gateway_url: str, timeout: int = 15) -> CheckOutcome:
    api_url = f"{app_gateway_url.rstrip('/')}/api/ingredients"
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            async with session.get(api_url) as response:
                ok = 200 <= response.status < 400
                return CheckOutcome(
                    name="appgw-api",
                    ok=ok,
                    summary=f"API route returned HTTP {response.status}",
                    details={"status": response.status, "url": api_url},
                    severity="critical" if response.status >= 500 else ("warning" if not ok else "info"),
                    status="critical" if response.status >= 500 else ("warning" if not ok else "ok"),
                    should_alert=response.status >= 500,
                )
    except Exception as exc:
        return CheckOutcome(
            name="appgw-api",
            ok=False,
            summary="API route check failed",
            details={"error": str(exc), "url": api_url},
            severity="critical",
            status="critical",
            should_alert=True,
        )
