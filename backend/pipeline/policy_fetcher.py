# backend/pipeline/policy_fetcher.py
"""
POLICY_FETCHER node.

Uses Playwright (JS-rendered load, not a bare `requests.get`, since many
privacy-policy pages are rendered client-side) to open the target site,
locate its privacy policy via common URL patterns or a footer-link crawl
fallback, and return the raw text + source URL.

On failure this NEVER raises up into the graph — it returns a
PolicyFetchResult with found=False and an empty policy_text, and the caller
(graph.py) logs the failure into state["errors"]. The pipeline continues
with an empty claims list rather than crashing.
"""

from __future__ import annotations

import re

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

from models.schemas import PolicyFetchResult

COMMON_PRIVACY_PATHS = [
    "/privacy",
    "/privacy-policy",
    "/legal/privacy",
    "/privacy-notice",
    "/policies/privacy",
]

FOOTER_LINK_KEYWORDS = re.compile(r"privacy", re.IGNORECASE)

NAV_TIMEOUT_MS = 15_000


async def fetch_policy(url: str) -> PolicyFetchResult:
    base = url.rstrip("/")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # 1) Try common URL patterns directly — fast path.
            for path in COMMON_PRIVACY_PATHS:
                candidate = base + path
                try:
                    resp = await page.goto(
                        candidate, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded"
                    )
                    if resp is not None and resp.status < 400:
                        text = await _extract_visible_text(page)
                        if _looks_like_policy(text):
                            await browser.close()
                            return PolicyFetchResult(
                                policy_text=text,
                                policy_source_url=candidate,
                                found=True,
                            )
                except PWTimeout:
                    continue
                except Exception:
                    continue

            # 2) Fallback: load the homepage, crawl footer links for anything
            #    mentioning "privacy".
            await page.goto(base, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
            links = await page.eval_on_selector_all(
                "a[href]",
                "els => els.map(e => ({href: e.href, text: e.innerText}))",
            )
            privacy_link = next(
                (
                    l["href"]
                    for l in links
                    if FOOTER_LINK_KEYWORDS.search(l.get("text", "") or "")
                    or FOOTER_LINK_KEYWORDS.search(l.get("href", "") or "")
                ),
                None,
            )
            if privacy_link:
                await page.goto(
                    privacy_link, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded"
                )
                text = await _extract_visible_text(page)
                if _looks_like_policy(text):
                    await browser.close()
                    return PolicyFetchResult(
                        policy_text=text, policy_source_url=privacy_link, found=True
                    )

            await browser.close()
            return PolicyFetchResult(policy_text="", policy_source_url="", found=False)

        except Exception:
            await browser.close()
            return PolicyFetchResult(policy_text="", policy_source_url="", found=False)


async def _extract_visible_text(page) -> str:
    body_text = await page.evaluate(
        "() => document.body ? document.body.innerText : ''"
    )
    return (body_text or "").strip()


def _looks_like_policy(text: str) -> bool:
    """Cheap heuristic gate so we don't hand a 404 page or nav shell to the
    claim extractor as if it were policy text."""
    if len(text) < 300:
        return False
    lowered = text.lower()
    signal_terms = ("privacy", "personal data", "personal information", "collect")
    return any(term in lowered for term in signal_terms)
