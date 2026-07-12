# backend/pipeline/verdict_agent.py
"""
VERDICT_AGENT node.

Uses OpenAI's chat completions API. Evidence contract for each verdict value
(implemented as a code check below, not just a prompt instruction):

  - confirmed:     evidence is non-empty, and every domain listed as evidence
                    was classified into a category that does NOT conflict
                    with the claim (e.g. claim says "no ad sharing" and no
                    ad-tech domain appears anywhere in classified_domains).
  - contradicted:   evidence is non-empty, and at least one domain listed as
                    evidence has a classified category that directly
                    conflicts with the claim (e.g. an "ad-tech" domain was
                    contacted despite a "no third-party ad sharing" claim).
  - unverifiable:   used whenever captured/classified traffic contains
                    nothing that speaks to the claim either way — no
                    confirming or contradicting domain was seen. Evidence
                    may be empty.

This node NEVER outputs a verdict without the actual classified_domains list
for this specific scan passed into its prompt context — no verdict is
invented or inferred without evidence attached. If the LLM call fails or
returns an unparsable/ungrounded verdict, that claim's verdict is forced to
"unverifiable" by validate_and_ground() below rather than trusting the raw
model output blindly.
"""

from __future__ import annotations

import json
import os

import httpx

from models.schemas import Claim, ClassifiedDomain, Verdict, VerdictEntry

OPENAI_URL = "https://api.openai.com/v1/chat/completions"

CONFLICT_CATEGORY_HINTS = {
    "advertising": {"ad-tech"},
    "analytics/tracking": {"analytics", "social-tracking"},
    "third-party sharing": {"ad-tech", "analytics", "social-tracking"},
    "location": set(),          # can't infer from domain category alone -> unverifiable unless explicit
    "data retention": set(),    # not observable from traffic -> always unverifiable
    "children's data": set(),   # not observable from traffic -> always unverifiable
}

SYSTEM_PROMPT = """You are the Verdict Agent for Contract Guardian. You are given a list of
privacy-policy CLAIMS and a list of CLASSIFIED DOMAINS actually observed on
the site's network traffic. For each claim, output a verdict grounded ONLY
in the classified domains provided — never invent evidence that isn't in
the list.

Verdict values:
- "confirmed": the traffic evidence is consistent with the claim holding
- "contradicted": a classified domain's category directly conflicts with the claim
- "unverifiable": nothing in the classified domains speaks to this claim either way

For "confirmed" or "contradicted", evidence must cite specific domains from
the CLASSIFIED DOMAINS list, in the form "domain.com (category, classified via source)".
For "unverifiable", evidence may be an empty list.

Respond with ONLY valid JSON: {"verdicts": [{"claim": "...", "verdict": "...", "evidence": ["..."], "explanation": "..."}]}
"""


async def generate_verdicts(
    claims: list[Claim], classified_domains: list[ClassifiedDomain]
) -> list[VerdictEntry]:
    if not claims:
        return []

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        # No LLM available — fall back to a pure rule-based grounding pass
        # rather than skipping verdicts entirely (still 100% evidence-grounded).
        return [_rule_based_verdict(c, classified_domains) for c in claims]

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    domain_context = [
        {"domain": d.domain, "category": d.category, "source": d.source.value}
        for d in classified_domains
    ]
    user_prompt = json.dumps(
        {
            "claims": [{"claim": c.claim, "category": c.category.value} for c in claims],
            "classified_domains": domain_context,
        }
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
            raw_verdicts = parsed.get("verdicts", [])
    except Exception:
        return [_rule_based_verdict(c, classified_domains) for c in claims]

    by_claim = {v.get("claim"): v for v in raw_verdicts if isinstance(v, dict)}
    final: list[VerdictEntry] = []
    valid_domains = {d.domain for d in classified_domains}

    for c in claims:
        candidate = by_claim.get(c.claim)
        entry = _validate_and_ground(c, candidate, valid_domains, classified_domains)
        final.append(entry)
    return final


def _validate_and_ground(
    claim: Claim,
    candidate: dict | None,
    valid_domains: set[str],
    classified_domains: list[ClassifiedDomain],
) -> VerdictEntry:
    """Never trust raw LLM output blindly — verdict must cite only domains
    that actually exist in this scan's classified_domains list. If the
    candidate can't be grounded, force unverifiable."""
    if not candidate:
        return _rule_based_verdict(claim, classified_domains)

    try:
        verdict = Verdict(candidate.get("verdict"))
    except ValueError:
        return _rule_based_verdict(claim, classified_domains)

    evidence = [e for e in candidate.get("evidence", []) if isinstance(e, str)]
    # Strip any evidence line that doesn't actually reference a real domain
    # from this scan — no invented evidence allowed.
    grounded_evidence = [e for e in evidence if any(dom in e for dom in valid_domains)]

    if verdict in (Verdict.CONFIRMED, Verdict.CONTRADICTED) and not grounded_evidence:
        # LLM claimed confirmed/contradicted but cited nothing real — downgrade.
        return _rule_based_verdict(claim, classified_domains)

    explanation = candidate.get("explanation", "").strip() or "No explanation provided."
    return VerdictEntry(
        claim=claim.claim, verdict=verdict, evidence=grounded_evidence, explanation=explanation
    )


def _rule_based_verdict(claim: Claim, classified_domains: list[ClassifiedDomain]) -> VerdictEntry:
    """Deterministic fallback grounding — used when no LLM is available or
    the LLM output can't be validated. Still fully evidence-based."""
    conflict_categories = CONFLICT_CATEGORY_HINTS.get(claim.category.value, set())
    conflicting = [d for d in classified_domains if d.category in conflict_categories]

    if conflicting:
        evidence = [f"{d.domain} ({d.category}, classified via {d.source.value})" for d in conflicting]
        return VerdictEntry(
            claim=claim.claim,
            verdict=Verdict.CONTRADICTED,
            evidence=evidence,
            explanation=(
                f"Traffic includes {len(conflicting)} domain(s) classified in a category "
                f"that conflicts with this claim."
            ),
        )

    return VerdictEntry(
        claim=claim.claim,
        verdict=Verdict.UNVERIFIABLE,
        evidence=[],
        explanation="No captured traffic speaks to this claim either way.",
    )
