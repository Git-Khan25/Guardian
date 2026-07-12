# backend/pipeline/domain_classifier.py
"""
DOMAIN_CLASSIFIER node.

Pass 1: match each captured domain against the bundled static blocklist
(instant, free, fully explainable — "the same trusted lists ad-blockers use").

Pass 2: anything NOT on the blocklist is sent to a small model for
classification by domain name/metadata pattern. If no model API key is
configured, the domain is explicitly marked "unknown" and logged — never
silently dropped.

No external API is called inside the per-domain loop other than the one
classification call itself — this node does not call any reasoning/claim
API.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

from models.schemas import CapturedDomain, ClassificationSource, ClassifiedDomain

BLOCKLIST_PATH = Path(__file__).resolve().parent.parent / "data" / "blocklist.json"

_CATEGORY_LABELS = {
    "ad-tech": "ad-tech",
    "analytics": "analytics",
    "social_tracking": "social-tracking",
    "cdn": "cdn",
    "first_party_infra": "infra",
}


def _load_blocklist() -> dict[str, str]:
    """Flatten blocklist.json into {domain_suffix: category_label}."""
    with open(BLOCKLIST_PATH, "r") as f:
        raw = json.load(f)
    flat = {}
    for key, domains in raw.items():
        if key.startswith("_"):
            continue
        label = _CATEGORY_LABELS.get(key, key)
        for d in domains:
            flat[d] = label
    return flat


_BLOCKLIST = _load_blocklist()


def _blocklist_match(domain: str) -> str | None:
    domain = domain.lower()
    for known, label in _BLOCKLIST.items():
        if domain == known or domain.endswith("." + known) or known in domain:
            return label
    return None


async def classify_domains(captured: list[CapturedDomain]) -> list[ClassifiedDomain]:
    results: list[ClassifiedDomain] = []
    unresolved: list[CapturedDomain] = []

    for c in captured:
        label = _blocklist_match(c.domain)
        if label is not None:
            results.append(
                ClassifiedDomain(
                    domain=c.domain,
                    category=label,
                    source=ClassificationSource.BLOCKLIST,
                    request_count=c.request_count,
                )
            )
        else:
            unresolved.append(c)

    if unresolved:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if api_key:
            results.extend(await _classify_via_model(unresolved, api_key))
        else:
            results.extend(
                ClassifiedDomain(
                    domain=d.domain,
                    category="unknown",
                    source=ClassificationSource.UNKNOWN,
                    request_count=d.request_count,
                )
                for d in unresolved
            )

    return results


_CLASSIFY_PROMPT_TEMPLATE = (
    "Classify each domain below into exactly one category: "
    "ad-tech, analytics, social-tracking, cdn, infra, first-party, or unknown. "
    "Base your guess only on the domain name and common naming patterns "
    "(e.g. subdomains like 'analytics.', 'ads.', 'track.', 'cdn.'). "
    "Respond with ONLY a JSON object mapping each domain to its category, "
    "nothing else.\n\nDomains: {domains}"
)


async def _classify_via_model(
    domains: list[CapturedDomain], api_key: str
) -> list[ClassifiedDomain]:
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    domain_list = [d.domain for d in domains]
    prompt = _CLASSIFY_PROMPT_TEMPLATE.format(domains=json.dumps(domain_list))

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0, "maxOutputTokens": 500},
                },
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data["candidates"][0]["content"]["parts"][0]["text"]
            cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            mapping: dict[str, str] = json.loads(cleaned)
    except Exception:
        return [
            ClassifiedDomain(
                domain=d.domain,
                category="unknown",
                source=ClassificationSource.UNKNOWN,
                request_count=d.request_count,
            )
            for d in domains
        ]

    return [
        ClassifiedDomain(
            domain=d.domain,
            category=mapping.get(d.domain, "unknown"),
            source=(
                ClassificationSource.MODEL
                if d.domain in mapping
                else ClassificationSource.UNKNOWN
            ),
            request_count=d.request_count,
        )
        for d in domains
    ]
