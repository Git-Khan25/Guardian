# backend/pipeline/traffic_capturer.py
"""
TRAFFIC_CAPTURER node.

SCOPE BOUNDARY (see project non-negotiables): this node captures which
domains a page contacts, how often, and what kind of resource was requested
(script/xhr/image/etc). It NEVER inspects request or response bodies, never
attempts to decrypt or read TLS payload contents, and never logs headers
beyond the destination host. This is domain-level traffic metadata only —
the same category of information a network admin sees in a router log, not
packet contents.
"""

from __future__ import annotations

from collections import defaultdict
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from models.schemas import CapturedDomain

IDLE_WAIT_MS = 10_000
NAV_TIMEOUT_MS = 20_000


def _domain_of(url: str) -> str:
    try:
        netloc = urlparse(url).netloc
        return netloc.split(":")[0]
    except Exception:
        return ""


async def capture_traffic(url: str) -> list[CapturedDomain]:
    counts: dict[tuple[str, str], int] = defaultdict(int)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()

        def on_request(request):
            # Domain-level only: we read request.url (for host) and
            # request.resource_type. We never touch request.post_data or
            # any response body.
            domain = _domain_of(request.url)
            if not domain:
                return
            counts[(domain, request.resource_type)] += 1

        page.on("request", on_request)

        try:
            await page.goto(url, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
            await page.wait_for_timeout(IDLE_WAIT_MS)
        except Exception:
            pass
        finally:
            await browser.close()

    merged: dict[str, dict] = {}
    for (domain, resource_type), count in counts.items():
        if domain not in merged:
            merged[domain] = {"request_count": 0, "resource_type": resource_type}
        merged[domain]["request_count"] += count

    return [
        CapturedDomain(
            domain=domain,
            request_count=info["request_count"],
            resource_type=info["resource_type"],
        )
        for domain, info in merged.items()
    ]
