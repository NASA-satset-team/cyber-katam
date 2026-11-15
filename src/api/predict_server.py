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
FORECAST_PATH = ROOT / "data" / "processed" / "meteomatics_forecast_3d_h3_paddy.parquet"

_STATE: Dict[str, Any] = {
    "contracts": {},
    "summaries": [],
    "meta": {},
    "ready": False,
    "error": None,
}

# Forecast 3 hari (H+1..H+3) = produk data terpisah dari kontrak v1.0. Disajikan
# apa adanya dari parquet ingestor; TIDAK dimasukkan ke kontrak v1.0 karena skema
# provisional fail-closed (additionalProperties:false) belum meratifikasi blok forecast.
_FC_STATE: Dict[str, Any] = {
    "cells": {},
    "summaries": [],
    "by_date": {},
    "meta": {},
    "ready": False,
    "error": None,
}

_FC_FIELDS = [
    "fc_tmean_c", "fc_tmax_c", "fc_precip_total_mm", "fc_precip_max_1h_mm",
    "fc_eto_total_mm", "fc_smi_mean", "fc_wind_max_ms", "h7_cluster_fc_rain_mm",
]
_FC_MAP_FIELDS = [
    "fc_precip_total_mm", "fc_precip_max_1h_mm", "fc_tmean_c", "fc_tmax_c", "fc_wind_max_ms",
]


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


def _load_forecast() -> None:
    """Muat forecast 3 hari per sel dari parquet ingestor (fail-soft, terpisah dari kontrak)."""
    if not FORECAST_PATH.exists():
        _FC_STATE["error"] = (
            f"{FORECAST_PATH.name} tidak ada. Jalankan ingest_meteomatics_forecast_3d.py dulu."
        )
        return
    try:
        import h3
        import pandas as pd

        df = pd.read_parquet(FORECAST_PATH)
    except Exception as exc:  # noqa: BLE001 - laporkan penyebab, jangan crash startup
        _FC_STATE["error"] = f"gagal membaca {FORECAST_PATH.name}: {exc}"
        return

    cells: Dict[str, Any] = {}
    summaries: List[Dict[str, Any]] = []
    for idx, g in df.groupby("h3_index", sort=True):
        g = g.sort_values("day_offset")
        first = g.iloc[0]
        days = []
        for _, r in g.iterrows():
            day = {
                "day_offset": int(r["day_offset"]),
                "horizon_code": str(r["horizon_code"]),
                "forecast_date": str(r["forecast_date"]),
            }
            for f in _FC_FIELDS:
                v = r[f]
                day[f] = None if pd.isna(v) else round(float(v), 3)
            days.append(day)
        lat = round(float(first["centroid_lat"]), 6)
        lon = round(float(first["centroid_lon"]), 6)
        cells[str(idx)] = {
            "h3_index": str(idx),
            "h3_parent_res7": str(first["h3_parent_res7"]),
            "centroid_lat": lat,
            "centroid_lon": lon,
            "source": str(first["forecast_source_mode"]),
            "forecast": days,
        }
        summaries.append({
            "h3_index": str(idx),
            "centroid_lat": lat,
            "centroid_lon": lon,
            "fc_rain_3d_mm": round(float(g["fc_precip_total_mm"].sum()), 2),
            "fc_tmax_3d_c": round(float(g["fc_tmax_c"].max()), 2),
            "fc_tmean_3d_c": round(float(g["fc_tmean_c"].mean()), 2),
        })

    prov: Dict[str, Any] = {}
    prov_path = FORECAST_PATH.with_name(FORECAST_PATH.stem + "_provenance.json")
    if prov_path.exists():
        try:
            prov = json.loads(prov_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            prov = {}

    by_date: Dict[str, Dict[str, Any]] = {}
    for date, g in df.groupby("forecast_date", sort=True):
        horizon = str(g["horizon_code"].iloc[0])
        levels: Dict[int, Dict[str, Any]] = {}
        for res in (7, 8, 9):
            key = g["h3_index"] if res == 9 else g["h3_index"].map(lambda c, r=res: h3.cell_to_parent(c, r))
            agg = g.groupby(key)[_FC_MAP_FIELDS].mean()
            counts = key.value_counts()
            levels[res] = {
                str(cid): {
                    **{f: (None if pd.isna(row[f]) else round(float(row[f]), 2)) for f in _FC_MAP_FIELDS},
                    "n_children": int(counts[cid]),
                }
                for cid, row in agg.iterrows()
            }
        by_date[str(date)] = {"horizon_code": horizon, "levels": levels}

    _FC_STATE["cells"] = cells
    _FC_STATE["summaries"] = summaries
    _FC_STATE["by_date"] = by_date
    _FC_STATE["meta"] = {
        "n_cells": len(cells),
        "n_rows": int(len(df)),
        "generated_utc": prov.get("generated_utc"),
        "horizons": [f"H+{d}" for d in sorted(df["day_offset"].unique().tolist())],
        "forecast_dates_wib": sorted(df["forecast_date"].unique().tolist()),
        "source": str(df["forecast_source_mode"].iloc[0]),
        "psf_fwhm_km": prov.get("psf_fwhm_km"),
        "interpolation_provenance": prov.get(
            "interpolation_provenance", "PSF_GAUSSIAN coarse->fine (bukan observasi per sel)"
        ),
        "derived_columns": prov.get("derived_columns", {}),
        "fc_nulls": {f: int(df[f].isna().sum()) for f in _FC_FIELDS},
    }
    _FC_STATE["ready"] = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_and_validate()
    _load_forecast()
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


def _require_forecast_ready() -> None:
    if not _FC_STATE["ready"]:
        raise HTTPException(status_code=503, detail=_FC_STATE["error"] or "forecast belum dimuat")


@app.get("/api/forecast/health")
def forecast_health() -> Dict[str, Any]:
    return {
        "status": "ok" if _FC_STATE["ready"] else "unavailable",
        "ready": _FC_STATE["ready"],
        "error": _FC_STATE["error"],
        **_FC_STATE["meta"],
    }


@app.get("/api/forecast/summary")
def forecast_summary() -> Dict[str, Any]:
    _require_forecast_ready()
    rows = _FC_STATE["summaries"]
    rains = [r["fc_rain_3d_mm"] for r in rows]
    tmaxs = [r["fc_tmax_3d_c"] for r in rows]
    return {
        **_FC_STATE["meta"],
        "fc_rain_3d_min_mm": min(rains),
        "fc_rain_3d_max_mm": max(rains),
        "fc_rain_3d_mean_mm": round(sum(rains) / len(rains), 2),
        "fc_tmax_3d_max_c": max(tmaxs),
        "cells_rain_3d_gt_50mm": sum(1 for r in rains if r > 50.0),
    }


@app.get("/api/forecast")
def forecast_list(
    limit: int = Query(50, ge=1, le=4143),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    _require_forecast_ready()
    rows = _FC_STATE["summaries"]
    return {
        "total": len(rows),
        "limit": limit,
        "offset": offset,
        "cells": rows[offset:offset + limit],
    }


@app.get("/api/forecast/map")
def forecast_map(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="tanggal WIB YYYY-MM-DD"),
    resolution: int = Query(9, ge=7, le=9),
) -> Dict[str, Any]:
    _require_forecast_ready()
    day = _FC_STATE["by_date"].get(date)
    if day is None:
        available = ", ".join(_FC_STATE["meta"]["forecast_dates_wib"])
        raise HTTPException(
            status_code=404,
            detail=f"Tidak ada forecast untuk {date}. Tanggal tersedia: {available}.",
        )
    cells = day["levels"][resolution]
    return {
        "date": date,
        "horizon_code": day["horizon_code"],
        "resolution": resolution,
        "aggregation": "nilai sel res-9" if resolution == 9 else "rata-rata sel anak res-9",
        "source": _FC_STATE["meta"]["source"],
        "interpolation_provenance": _FC_STATE["meta"]["interpolation_provenance"],
        "generated_utc": _FC_STATE["meta"]["generated_utc"],
        "n_cells": len(cells),
        "cells": cells,
    }


@app.get("/api/forecast/{h3_index}")
def forecast_cell(h3_index: str) -> Dict[str, Any]:
    _require_forecast_ready()
    cell = _FC_STATE["cells"].get(h3_index)
    if cell is None:
        raise HTTPException(status_code=404, detail=f"Sel {h3_index} tidak ada di grid forecast sawah.")
    return cell