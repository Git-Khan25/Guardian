# backend/models/schemas.py
"""
Pydantic schemas for every structured artifact that moves through the
Contract Guardian pipeline. These are the contracts every node must honor —
if a node's output doesn't validate against these, it gets skipped/degraded,
never silently coerced.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared enums
# ---------------------------------------------------------------------------

class ClaimCategory(str, Enum):
    ADVERTISING = "advertising"
    ANALYTICS_TRACKING = "analytics/tracking"
    LOCATION = "location"
    THIRD_PARTY_SHARING = "third-party sharing"
    DATA_RETENTION = "data retention"
    CHILDRENS_DATA = "children's data"


class ClaimConfidence(str, Enum):
    EXPLICIT = "explicit"      # policy states this plainly
    IMPLIED = "implied"        # reasonably inferable but not a direct quote


class ClassificationSource(str, Enum):
    BLOCKLIST = "blocklist"
    MODEL = "model"
    UNKNOWN = "unknown"


class Verdict(str, Enum):
    CONFIRMED = "confirmed"
    CONTRADICTED = "contradicted"
    UNVERIFIABLE = "unverifiable"


class PipelineStage(str, Enum):
    FETCHING_POLICY = "fetching_policy"
    EXTRACTING_CLAIMS = "extracting_claims"
    CAPTURING_TRAFFIC = "capturing_traffic"
    CLASSIFYING_DOMAINS = "classifying_domains"
    GENERATING_VERDICT = "generating_verdict"
    COMPLETE = "complete"


# ---------------------------------------------------------------------------
# Node-level artifacts
# ---------------------------------------------------------------------------

class PolicyFetchResult(BaseModel):
    policy_text: str
    policy_source_url: str
    found: bool = True


class Claim(BaseModel):
    claim: str = Field(..., description="A single concrete, checkable promise.")
    category: ClaimCategory
    confidence: ClaimConfidence


class ClaimExtractionResult(BaseModel):
    claims: list[Claim] = Field(default_factory=list)


class CapturedDomain(BaseModel):
    domain: str
    request_count: int
    resource_type: str  # e.g. "script", "xhr", "image", "document"


class ClassifiedDomain(BaseModel):
    domain: str
    category: str          # e.g. "ad-tech", "analytics", "cdn", "first-party", "unknown"
    source: ClassificationSource
    request_count: int = 0


class VerdictEntry(BaseModel):
    claim: str
    verdict: Verdict
    evidence: list[str] = Field(default_factory=list)
    explanation: str

    # Evidence contract (enforced in code, not just prompt):
    #   confirmed      -> evidence list is non-empty AND every listed domain's
    #                      classified category is consistent with the claim
    #                      holding (i.e. nothing contradicting it was seen).
    #   contradicted   -> evidence list is non-empty AND at least one listed
    #                      domain's classified category directly conflicts
    #                      with the claim (e.g. ad-tech domain contacted when
    #                      claim says "no third-party ad sharing").
    #   unverifiable   -> evidence list may be empty; used whenever captured
    #                      traffic has nothing that speaks to the claim either
    #                      way (no confirming or contradicting domain seen).


class TrustScore(BaseModel):
    confirmed: int = 0
    contradicted: int = 0
    unverifiable: int = 0


class ScanError(BaseModel):
    stage: PipelineStage
    message: str


# ---------------------------------------------------------------------------
# Top-level scan state (mirrors ScanState TypedDict used inside the graph)
# ---------------------------------------------------------------------------

class ScanReport(BaseModel):
    url: str
    scan_id: str
    site_name: Optional[str] = None
    policy_source_url: Optional[str] = None
    claims: list[Claim] = Field(default_factory=list)
    captured_domains: list[CapturedDomain] = Field(default_factory=list)
    classified_domains: list[ClassifiedDomain] = Field(default_factory=list)
    verdicts: list[VerdictEntry] = Field(default_factory=list)
    pipeline_stage: PipelineStage = PipelineStage.FETCHING_POLICY
    errors: list[ScanError] = Field(default_factory=list)
    trust_score: TrustScore = Field(default_factory=TrustScore)


class ScanRequest(BaseModel):
    url: str


class ScanStatusResponse(BaseModel):
    scan_id: str
    pipeline_stage: PipelineStage
    errors: list[ScanError] = Field(default_factory=list)
    complete: bool = False
