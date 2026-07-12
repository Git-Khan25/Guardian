# backend/api/routes.py
"""
API surface for Contract Guardian.

- POST /scan               kick off a live scan (async, runs the LangGraph pipeline)
- GET  /scan/{id}/status   poll current pipeline stage (powers the frontend's
                            "pipeline lighting up" progress display)
- GET  /scan/{id}/report   full ScanReport once complete
- GET  /demo/{app_name}    instantly return a pre-scanned demo report (the
                            default, primary demo path — no live scanning needed)
- GET  /health             container healthcheck
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException

from models.schemas import ScanRequest, ScanStatusResponse, PipelineStage
from pipeline.graph import run_scan

router = APIRouter()

DEMO_DIR = Path(__file__).resolve().parent.parent / "data" / "demo_scans"

# In-memory scan store — stateless demo tool, no persistent DB per project scope.
_SCANS: dict[str, dict] = {}


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
    scan_id = str(uuid.uuid4())[:8]
    _SCANS[scan_id] = {
        "pipeline_stage": PipelineStage.FETCHING_POLICY.value,
        "errors": [],
        "complete": False,
        "report": None,
    }

    async def _run():
        try:
            final_state = await run_scan(req.url, scan_id)
            _SCANS[scan_id]["report"] = final_state
            _SCANS[scan_id]["pipeline_stage"] = final_state["pipeline_stage"]
            _SCANS[scan_id]["errors"] = final_state["errors"]
            _SCANS[scan_id]["complete"] = True
        except Exception as e:
            _SCANS[scan_id]["errors"].append(
                {"stage": "generating_verdict", "message": f"Pipeline crashed: {e}"}
            )
            _SCANS[scan_id]["complete"] = True

    background_tasks.add_task(lambda: asyncio.create_task(_run()))
    return {"scan_id": scan_id}


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
