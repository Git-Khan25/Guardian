# backend/pipeline/policy_fetcher.py
"""
POLICY_FETCHER node.

Uses Playwright (JS-rendered load, not a bare `requests.get`, since many
privacy-policy pages are rendered client-side) to open the target site,
locate its privacy policy via common URL patterns or a footer-link crawl
fallback, and return the raw text + source URL.

Speed note: the common-path candidates are probed CONCURRENTLY (multiple
tabs in one browser), not one after another. Checking 5 patterns
sequentially at a 15s timeout each could cost up to 75s on a site that
doesn't have any of them (redirects, login walls, bot detection — exactly
what large sites like Instagram or WhatsApp tend to do). Running them in
parallel with a short per-tab timeout bounds this stage to roughly the
single slowest attempt instead of the sum of all of them.

On failure this NEVER raises up into the graph — it returns a
PolicyFetchResult with found=False and an empty policy_text, and the caller
(graph.py) logs the failure into state["errors"]. The pipeline continues
with an empty claims list rather than crashing.
"""

from __future__ import annotations

import asyncio
import re

from playwright.async_api import async_playwright

from models.schemas import PolicyFetchResult

COMMON_PRIVACY_PATHS = [
    "/privacy",
    "/privacy-policy",
    "/legal/privacy",
    "/privacy-notice",
    "/policies/privacy",
]

FOOTER_LINK_KEYWORDS = re.compile(r"privacy", re.IGNORECASE)

# Short per-attempt timeout — these are quick probes, not a single
# do-or-die navigation. A slow/unresponsive candidate should fail fast so
# the other concurrent attempts (or the fallback) get a chance.
PATTERN_TIMEOUT_MS = 7_000
HOMEPAGE_TIMEOUT_MS = 9_000


async def fetch_policy(url: str) -> PolicyFetchResult:
    base = url.rstrip("/")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)

        try:
            # 1) Probe all common URL patterns concurrently, not sequentially.
            results = await asyncio.gather(
                *[_try_candidate(browser, base + path) for path in COMMON_PRIVACY_PATHS],
                return_exceptions=True,
            )
            for path, result in zip(COMMON_PRIVACY_PATHS, results):
                if isinstance(result, PolicyFetchResult) and result.found:
                    await browser.close()
                    return result

            # 2) Fallback: load the homepage once, crawl footer links for
            #    anything mentioning "privacy".
            page = await browser.new_page()
            try:
                await page.goto(base, timeout=HOMEPAGE_TIMEOUT_MS, wait_until="domcontentloaded")
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
                        privacy_link, timeout=HOMEPAGE_TIMEOUT_MS, wait_until="domcontentloaded"
                    )
                    text = await _extract_visible_text(page)
                    if _looks_like_policy(text):
                        await browser.close()
                        return PolicyFetchResult(
                            policy_text=text, policy_source_url=privacy_link, found=True
                        )
            except Exception:
                pass
            finally:
                await page.close()

            await browser.close()
            return PolicyFetchResult(policy_text="", policy_source_url="", found=False)

        except Exception:
            await browser.close()
            return PolicyFetchResult(policy_text="", policy_source_url="", found=False)


async def _try_candidate(browser, candidate_url: str) -> PolicyFetchResult:
    """Probe a single candidate URL in its own tab, bounded by a short
    timeout. Never raises — any failure just means "not this one"."""
    page = None
    try:
        page = await browser.new_page()
        resp = await page.goto(
            candidate_url, timeout=PATTERN_TIMEOUT_MS, wait_until="domcontentloaded"
        )
        if resp is not None and resp.status < 400:
            text = await _extract_visible_text(page)
            if _looks_like_policy(text):
                return PolicyFetchResult(
                    policy_text=text, policy_source_url=candidate_url, found=True
                )
        return PolicyFetchResult(policy_text="", policy_source_url="", found=False)
    except Exception:
        return PolicyFetchResult(policy_text="", policy_source_url="", found=False)
    finally:
        if page is not None:
            await page.close()


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
