# backend/pipeline/claim_extractor.py
"""
CLAIM_EXTRACTOR node.

Uses OpenAI's chat completions API for strict, schema-constrained
extraction: only concrete, checkable promises against the fixed category
list make it out of this node. Vague statements like "we take your privacy
seriously" are filtered at the prompt level AND re-checked in code
(see _is_vague) — never left in just because the model included them.

On any failure (missing key, network error, invalid JSON) this degrades
gracefully: retries once with a stricter reminder, then returns an empty
claims list rather than crashing the run.
"""

from __future__ import annotations

import json
import os
import re

import httpx

from models.schemas import Claim, ClaimCategory, ClaimConfidence, ClaimExtractionResult

OPENAI_URL = "https://api.openai.com/v1/chat/completions"

CATEGORIES = [c.value for c in ClaimCategory]

SYSTEM_PROMPT = f"""You extract CONCRETE, CHECKABLE promises from a website's privacy policy.

Only extract a claim if it is specific enough that someone could verify it by
watching the site's actual network traffic (e.g. "does not share data with
third-party advertisers", "does not use tracking cookies for children under 13").

DO NOT extract vague, unverifiable marketing language such as "we take your
privacy seriously", "we care about your data", "your trust matters to us".
If the policy contains only vague language on a topic, skip it entirely.

Each claim must be assigned exactly one category from this fixed list:
{json.dumps(CATEGORIES)}

Each claim must be assigned a confidence:
- "explicit": the policy states this plainly
- "implied": reasonably inferable but not a direct quote

Respond with ONLY valid JSON, no prose, no markdown fences, matching this shape:
{{"claims": [{{"claim": "...", "category": "...", "confidence": "explicit"}}]}}

If there are no checkable claims, respond with {{"claims": []}}.
"""

VAGUE_PATTERNS = [
    r"take.{0,15}privacy seriously",
    r"care about your (data|privacy)",
    r"your trust matters",
    r"committed to (protecting|your privacy)",
    r"privacy is important to us",
]
_VAGUE_RE = re.compile("|".join(VAGUE_PATTERNS), re.IGNORECASE)


def _is_vague(claim_text: str) -> bool:
    return bool(_VAGUE_RE.search(claim_text)) or len(claim_text.strip()) < 12


async def extract_claims(policy_text: str) -> ClaimExtractionResult:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or not policy_text.strip():
        return ClaimExtractionResult(claims=[])

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    result = await _call_and_parse(policy_text, api_key, model, strict_retry=False)
    if result is None:
        result = await _call_and_parse(policy_text, api_key, model, strict_retry=True)
    if result is None:
        return ClaimExtractionResult(claims=[])

    # Code-level filter — never trust the prompt alone to keep vague claims out.
    clean_claims = [c for c in result.claims if not _is_vague(c.claim)]
    return ClaimExtractionResult(claims=clean_claims)


async def _call_and_parse(
    policy_text: str, api_key: str, model: str, strict_retry: bool
) -> ClaimExtractionResult | None:
    user_prompt = policy_text[:12000]  # keep prompt bounded
    if strict_retry:
        user_prompt = (
            "REMINDER: respond with ONLY the raw JSON object, no markdown fences, "
            "no commentary. Every claim MUST use one of the exact category strings "
            f"given. Categories: {json.dumps(CATEGORIES)}\n\nPOLICY TEXT:\n" + user_prompt
        )

    payload = {
        "model": model,
        "max_tokens": 2000,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(OPENAI_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            raw = data["choices"][0]["message"]["content"]
            cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(cleaned)

            claims = []
            for item in parsed.get("claims", []):
                try:
                    claims.append(
                        Claim(
                            claim=item["claim"],
                            category=ClaimCategory(item["category"]),
                            confidence=ClaimConfidence(item.get("confidence", "implied")),
                        )
                    )
                except (KeyError, ValueError):
                    # skip individual malformed claim, don't fail the whole batch
                    continue
            return ClaimExtractionResult(claims=claims)
    except Exception:
        return None
