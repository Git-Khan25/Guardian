# backend/api/routes.py
"""
API surface for Contract Guardian.

- POST /scan               kick off a live scan (async, runs the pipeline).
                            Serves instantly from cache if this exact URL was
                            scanned recently — see the caching note below.
- GET  /scan/{id}/status   poll current pipeline stage (powers the frontend's
                            "pipeline lighting up" progress display)
- GET  /scan/{id}/report   full ScanReport once complete
- GET  /demo/{app_name}    instantly return a pre-scanned demo report (the
                            default, primary demo path — no live scanning needed)
- GET  /health             container healthcheck

Caching: a completed live scan is written to disk under
data/scan_cache/<hash>.json, keyed by the normalized URL. Scanning the same
site again within CACHE_TTL_SECONDS returns the cached result immediately —
no re-running Playwright or any LLM calls. Pass {"force": true} in the POST
body to bypass the cache and force a fresh scan.

Timeout: a live scan is capped at SCAN_TIMEOUT_SECONDS end-to-end. If a site
hangs (bot walls, infinite loaders, dead redirects), the scan is marked
complete with a timeout error instead of running forever — the frontend
would otherwise poll indefinitely waiting for a status that never arrives.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, HTTPException

from models.schemas import PipelineStage, ScanRequest, ScanStatusResponse
from pipeline.graph import run_scan

router = APIRouter()

DEMO_DIR = Path(__file__).resolve().parent.parent / "data" / "demo_scans"
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "scan_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CACHE_TTL_SECONDS = 24 * 60 * 60   # a repeat scan within 24h is served from cache
SCAN_TIMEOUT_SECONDS = 90          # hard cap on a single live scan's total runtime

# In-memory scan store — stateless demo tool, no persistent DB per project scope.
# (The disk cache below is separate: it's what makes *repeat* scans instant.)
_SCANS: dict[str, dict] = {}


def _cache_key(url: str) -> str:
    normalized = urlparse(url).netloc.lower().removeprefix("www.")
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _cache_path(url: str) -> Path:
    return CACHE_DIR / f"{_cache_key(url)}.json"


def _read_cache(url: str) -> dict | None:
    path = _cache_path(url)
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            entry = json.load(f)
        if time.time() - entry.get("cached_at", 0) > CACHE_TTL_SECONDS:
            return None  # stale, treat as a miss
        return entry["report"]
    except Exception:
        return None  # corrupt cache entry, treat as a miss rather than error


def _write_cache(url: str, report: dict) -> None:
    path = _cache_path(url)
    try:
        with open(path, "w") as f:
            json.dump({"cached_at": time.time(), "url": url, "report": report}, f)
    except Exception:
        pass  # caching is a nice-to-have, never let it break a scan


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/demo/{app_name}")
async def get_demo(app_name: str):
    path = DEMO_DIR / f"{app_name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No demo scan bundled for '{app_name}'")
    with open(path, "r") as f:
        return json.load(f)


@router.get("/demo")
async def list_demos():
    if not DEMO_DIR.exists():
        return {"apps": []}
    return {"apps": sorted(p.stem for p in DEMO_DIR.glob("*.json"))}


@router.post("/scan")
async def start_scan(req: ScanRequest, background_tasks: BackgroundTasks):
    force = getattr(req, "force", False)

    if not force:
        cached_report = _read_cache(req.url)
        if cached_report is not None:
            scan_id = str(uuid.uuid4())[:8]
            _SCANS[scan_id] = {
                "pipeline_stage": PipelineStage.COMPLETE.value,
                "errors": [],
                "complete": True,
                "report": cached_report,
                "from_cache": True,
            }
            return {"scan_id": scan_id, "from_cache": True}

    scan_id = str(uuid.uuid4())[:8]
    _SCANS[scan_id] = {
        "pipeline_stage": PipelineStage.FETCHING_POLICY.value,
        "errors": [],
        "complete": False,
        "report": None,
        "from_cache": False,
    }

    async def _run():
        try:
            final_state = await asyncio.wait_for(
                run_scan(req.url, scan_id), timeout=SCAN_TIMEOUT_SECONDS
            )
            _SCANS[scan_id]["report"] = final_state
            _SCANS[scan_id]["pipeline_stage"] = final_state["pipeline_stage"]
            _SCANS[scan_id]["errors"] = final_state["errors"]
            _SCANS[scan_id]["complete"] = True
            _write_cache(req.url, final_state)
        except asyncio.TimeoutError:
            _SCANS[scan_id]["errors"].append(
                {
                    "stage": "generating_verdict",
                    "message": (
                        f"Scan exceeded the {SCAN_TIMEOUT_SECONDS}s limit and was stopped — "
                        "this site is likely slow to load, bot-gated, or requires login. "
                        "Try one of the pre-scanned exhibits instead."
                    ),
                }
            )
            _SCANS[scan_id]["pipeline_stage"] = PipelineStage.COMPLETE.value
            _SCANS[scan_id]["complete"] = True
        except Exception as e:
            _SCANS[scan_id]["errors"].append(
                {"stage": "generating_verdict", "message": f"Pipeline crashed: {e}"}
            )
            _SCANS[scan_id]["pipeline_stage"] = PipelineStage.COMPLETE.value
            _SCANS[scan_id]["complete"] = True

    background_tasks.add_task(_run)
    return {"scan_id": scan_id, "from_cache": False}


@router.get("/scan/{scan_id}/status", response_model=ScanStatusResponse)
async def scan_status(scan_id: str):
    scan = _SCANS.get(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Unknown scan_id")
    return ScanStatusResponse(
        scan_id=scan_id,
        pipeline_stage=scan["pipeline_stage"],
        errors=scan["errors"],
        complete=scan["complete"],
    )


@router.get("/scan/{scan_id}/report")
async def scan_report(scan_id: str):
    scan = _SCANS.get(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Unknown scan_id")
    if not scan["complete"]:
        raise HTTPException(status_code=409, detail="Scan still in progress")
    return scan["report"]
