"""
src/api/predict_server.py
-------------------------
Backend FastAPI untuk endpoint /predict (Fase 2).

Menyajikan kontrak grid-cell v1.0 per sel sawah (2.324 sel H3 res-9) yang
dirakit PaddyLiveEvaluator + ContractAssembler dari data live Meteomatics.
Kontrak divalidasi terhadap contracts/grid_cell_contract.schema.json saat
startup (fail-closed: server menolak start bila ada kontrak tidak valid).

Jalankan dari root repo:
    uvicorn src.api.predict_server:app --host 127.0.0.1 --port 8000

Vite mem-proxy /api/predict ke server ini (lihat vite.config.js).
Kontrak diperbarui dengan menjalankan ulang ingest_meteomatics_live.py lalu
paddy_live_evaluator.py (logger 3-harian Fase 1 akan menjadwalkannya).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.contracts.contract_validator import ContractValidator  # noqa: E402

CONTRACTS_PATH = ROOT / "data" / "processed" / "paddy_live_contracts.json"

_STATE: Dict[str, Any] = {
    "contracts": {},
    "summaries": [],
    "meta": {},
    "ready": False,
    "error": None,
}


def _load_and_validate() -> None:
    if not CONTRACTS_PATH.exists():
        _STATE["error"] = (
            f"{CONTRACTS_PATH.name} tidak ada. Jalankan ingest_meteomatics_live.py "
            "lalu paddy_live_evaluator.py dulu."
        )
        return
    payload = json.loads(CONTRACTS_PATH.read_text(encoding="utf-8"))
    contracts: Dict[str, Any] = payload.get("contracts", {})
    validator = ContractValidator()
    invalid: List[str] = []
    for idx, contract in contracts.items():
        if not validator.validate(contract).is_valid:
            invalid.append(idx)
    if invalid:
        _STATE["error"] = f"{len(invalid)} kontrak tidak valid, contoh: {invalid[:3]}"
        return

    summaries = []
    for idx, c in contracts.items():
        pi = c["physical_indicators"]
        summaries.append({
            "h3_index": idx,
            "pvrs": pi["PVRS"],
            "bf_ehsi": pi["BF_EHSI"],
            "smap_wetness": pi["SMAP_wetness"],
            "system_state": c["system_state"],
            "missing_observation": c["operational_flags"]["missing_observation"],
            "erosion_alert": c["operational_flags"]["erosion_alert"],
        })
    _STATE["contracts"] = contracts
    _STATE["summaries"] = summaries
    _STATE["meta"] = {
        "contract_version": payload.get("contract_version", "1.0"),
        "n_cells": len(contracts),
        "system_state_counts": dict(Counter(c["system_state"] for c in contracts.values())),
        "source": "paddy_live_evaluator + contract_assembler (live Meteomatics)",
    }
    _STATE["ready"] = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_and_validate()
    yield


app = FastAPI(
    title="CYBER-KATAM /predict",
    description="Kontrak grid-cell v1.0 per sel sawah dari engine fisika live.",
    version="1.0",
    lifespan=lifespan,
)


def _require_ready() -> None:
    if not _STATE["ready"]:
        raise HTTPException(status_code=503, detail=_STATE["error"] or "kontrak belum dimuat")


@app.get("/api/predict/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok" if _STATE["ready"] else "unavailable",
        "ready": _STATE["ready"],
        "error": _STATE["error"],
        **_STATE["meta"],
    }


@app.get("/api/predict/summary")
def summary() -> Dict[str, Any]:
    _require_ready()
    summaries = _STATE["summaries"]
    pvrs_vals = [s["pvrs"] for s in summaries]
    return {
        **_STATE["meta"],
        "pvrs_min": min(pvrs_vals),
        "pvrs_max": max(pvrs_vals),
        "missing_observation_cells": sum(1 for s in summaries if s["missing_observation"]),
        "erosion_alert_cells": sum(1 for s in summaries if s["erosion_alert"]),
    }


@app.get("/api/predict")
def list_cells(
    state: Optional[str] = Query(None, description="filter system_state"),
    limit: int = Query(50, ge=1, le=2324),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    _require_ready()
    rows = _STATE["summaries"]
    if state:
        rows = [r for r in rows if r["system_state"] == state]
    total = len(rows)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "cells": rows[offset:offset + limit],
    }


@app.get("/api/predict/{h3_index}")
def get_cell(h3_index: str) -> Dict[str, Any]:
    _require_ready()
    contract = _STATE["contracts"].get(h3_index)
    if contract is None:
        raise HTTPException(status_code=404, detail=f"Sel {h3_index} tidak ada di grid sawah.")
    return contract