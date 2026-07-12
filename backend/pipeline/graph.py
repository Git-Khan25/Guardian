# backend/pipeline/graph.py
"""
Sequential LangGraph wiring of the five pipeline nodes.

Every node is wrapped so a failure inside it is caught, logged into
state["errors"], and the graph proceeds with partial state — a single
node's failure never crashes the whole scan. Downstream nodes are written
to tolerate empty upstream lists (e.g. verdict_agent with zero claims just
returns zero verdicts).
"""

from __future__ import annotations

from typing import TypedDict
from urllib.parse import urlparse

from langgraph.graph import StateGraph, END

from models.schemas import (
    CapturedDomain,
    Claim,
    ClassifiedDomain,
    PipelineStage,
    ScanError,
    TrustScore,
    Verdict,
    VerdictEntry,
)
from pipeline.claim_extractor import extract_claims
from pipeline.domain_classifier import classify_domains
from pipeline.policy_fetcher import fetch_policy
from pipeline.traffic_capturer import capture_traffic
from pipeline.verdict_agent import generate_verdicts


class ScanState(TypedDict):
    url: str
    scan_id: str
    site_name: str
    policy_text: str
    policy_source_url: str
    claims: list
    captured_domains: list
    classified_domains: list
    verdicts: list
    pipeline_stage: str
    errors: list
    trust_score: dict


def _site_name(url: str) -> str:
    try:
        host = urlparse(url).netloc or urlparse("https://" + url).netloc
        return host.replace("www.", "")
    except Exception:
        return url


async def node_fetch_policy(state: ScanState) -> ScanState:
    state["pipeline_stage"] = PipelineStage.FETCHING_POLICY.value
    try:
        result = await fetch_policy(state["url"])
        state["policy_text"] = result.policy_text
        state["policy_source_url"] = result.policy_source_url
        if not result.found:
            state["errors"].append(
                ScanError(
                    stage=PipelineStage.FETCHING_POLICY,
                    message="Could not locate a privacy policy page; continuing with no claims.",
                ).model_dump()
            )
    except Exception as e:
        state["policy_text"] = ""
        state["policy_source_url"] = ""
        state["errors"].append(
            ScanError(stage=PipelineStage.FETCHING_POLICY, message=str(e)).model_dump()
        )
    return state


async def node_extract_claims(state: ScanState) -> ScanState:
    state["pipeline_stage"] = PipelineStage.EXTRACTING_CLAIMS.value
    try:
        result = await extract_claims(state.get("policy_text", ""))
        state["claims"] = [c.model_dump() for c in result.claims]
    except Exception as e:
        state["claims"] = []
        state["errors"].append(
            ScanError(stage=PipelineStage.EXTRACTING_CLAIMS, message=str(e)).model_dump()
        )
    return state


async def node_capture_traffic(state: ScanState) -> ScanState:
    state["pipeline_stage"] = PipelineStage.CAPTURING_TRAFFIC.value
    try:
        domains = await capture_traffic(state["url"])
        state["captured_domains"] = [d.model_dump() for d in domains]
    except Exception as e:
        state["captured_domains"] = []
        state["errors"].append(
            ScanError(stage=PipelineStage.CAPTURING_TRAFFIC, message=str(e)).model_dump()
        )
    return state


async def node_classify_domains(state: ScanState) -> ScanState:
    state["pipeline_stage"] = PipelineStage.CLASSIFYING_DOMAINS.value
    try:
        captured = [CapturedDomain(**d) for d in state.get("captured_domains", [])]
        classified = await classify_domains(captured)
        state["classified_domains"] = [c.model_dump() for c in classified]
    except Exception as e:
        state["classified_domains"] = []
        state["errors"].append(
            ScanError(stage=PipelineStage.CLASSIFYING_DOMAINS, message=str(e)).model_dump()
        )
    return state


async def node_generate_verdict(state: ScanState) -> ScanState:
    state["pipeline_stage"] = PipelineStage.GENERATING_VERDICT.value
    try:
        claims = [Claim(**c) for c in state.get("claims", [])]
        classified = [ClassifiedDomain(**d) for d in state.get("classified_domains", [])]
        verdicts = await generate_verdicts(claims, classified)
        state["verdicts"] = [v.model_dump() for v in verdicts]

        score = TrustScore()
        for v in verdicts:
            if v.verdict == Verdict.CONFIRMED:
                score.confirmed += 1
            elif v.verdict == Verdict.CONTRADICTED:
                score.contradicted += 1
            else:
                score.unverifiable += 1
        state["trust_score"] = score.model_dump()
    except Exception as e:
        state["verdicts"] = []
        state["trust_score"] = TrustScore().model_dump()
        state["errors"].append(
            ScanError(stage=PipelineStage.GENERATING_VERDICT, message=str(e)).model_dump()
        )
    state["pipeline_stage"] = PipelineStage.COMPLETE.value
    state["site_name"] = _site_name(state["url"])
    return state


def build_graph():
    graph = StateGraph(ScanState)
    graph.add_node("fetch_policy", node_fetch_policy)
    graph.add_node("extract_claims", node_extract_claims)
    graph.add_node("capture_traffic", node_capture_traffic)
    graph.add_node("classify_domains", node_classify_domains)
    graph.add_node("generate_verdict", node_generate_verdict)

    graph.set_entry_point("fetch_policy")
    graph.add_edge("fetch_policy", "extract_claims")
    graph.add_edge("extract_claims", "capture_traffic")
    graph.add_edge("capture_traffic", "classify_domains")
    graph.add_edge("classify_domains", "generate_verdict")
    graph.add_edge("generate_verdict", END)

    return graph.compile()


compiled_graph = build_graph()


async def run_scan(url: str, scan_id: str) -> ScanState:
    initial: ScanState = {
        "url": url,
        "scan_id": scan_id,
        "site_name": _site_name(url),
        "policy_text": "",
        "policy_source_url": "",
        "claims": [],
        "captured_domains": [],
        "classified_domains": [],
        "verdicts": [],
        "pipeline_stage": PipelineStage.FETCHING_POLICY.value,
        "errors": [],
        "trust_score": TrustScore().model_dump(),
    }
    final_state = await compiled_graph.ainvoke(initial)
    return final_state
