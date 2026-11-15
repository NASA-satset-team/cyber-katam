"""
src/engines/paddy_live_evaluator.py
-----------------------------------
Evaluator LIVE per sel untuk grid sawah 2.324 sel H3 res-9.

Menggabungkan kondisi terkini Meteomatics (parquet mm_ hasil ingest_meteomatics_live)
dengan konteks per sel: baseline klimatologi multi-tahun (climatology_baseline_paddy),
terrain SRTM asli, dan vegetasi satelit terkini (indicators_wide_paddy, 2026 dekad 30).

Yang ditingkatkan dibanding cohort bawaan engine (TANPA mengubah bobot terkalibrasi):
  - Baseline klimatologi PER SEL (mu/sigma LST, SM, NDVI), bukan satu nilai regional.
  - Kemiringan SRTM ASLI per sel untuk BF-EHSI, bukan proxy northness berbasis lintang.
  - NDVI satelit per sel untuk MSAVI/TVDI, bukan konstanta 0.73.
  - Kondisi LIVE (suhu, lengas volumetrik, hujan, ET) dari Meteomatics, bukan snapshot statis.
  - BF-EHSI memakai BFEHSIEngine.evaluate_fallow_window penuh (bukan proxy manual),
    termasuk koreksi bias hujan orografis berbasis kemiringan asli.

Engine (PVRSEngine / BFEHSIEngine) dipanggil apa adanya; hanya INPUT yang diperkaya.
TWI diestimasi dari kemiringan SRTM (tanpa data akumulasi aliran D8) -> ditandai proxy.
Fraksi lempung memakai default vertisol 0.52 (belum ada data lempung per sel).

Keluaran: skor per sel (parquet) + GeoJSON kontrak v1.0, serta fungsi evaluate_cell
yang dapat dipakai ulang oleh endpoint /predict.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import h3
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from external.aryas_workresult.pvrs_engine import (  # noqa: E402
    PVRSEngine, SatelliteObservationInput, DecadalClimatologyBaseline,
)
from external.aryas_workresult.bf_ehsi_engine import (  # noqa: E402
    BFEHSIEngine, HLSReflectanceStep,
)
from src.contracts.contract_assembler import (  # noqa: E402
    ContractAssembler, CellPhysicalSignals,
)

CLIM_PATH = ROOT / "data" / "processed" / "climatology_baseline_banyumas_paddy.parquet"
WIDE_PATH = ROOT / "data" / "processed" / "banyumas_indicators_wide_paddy.parquet"
GRID_PATH = ROOT / "data" / "processed" / "banyumas_h3_paddy_grid.geojson"
LIVE_MM_PATH = ROOT / "data" / "processed" / "meteomatics_banyumas_h3_paddy_live.parquet"
BRIDGE_PATH = ROOT / "data" / "processed" / "banyumas_daily_paddy_bridge.parquet"
OUT_SCORES = ROOT / "data" / "processed" / "paddy_live_scores.parquet"
OUT_GEOJSON = ROOT / "data" / "processed" / "banyumas_h3_paddy_live.geojson"
OUT_CONTRACTS = ROOT / "data" / "processed" / "paddy_live_contracts.json"

FALLOW_DAYS = 10
MU_ESI_REGIONAL = 0.68
SIGMA_ESI_REGIONAL = 0.12


def _f(value, default: float) -> float:
    try:
        v = float(value)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def estimate_twi(slope_deg: float) -> float:
    """Proxy TWI dari kemiringan SRTM: ln(a/tan(beta)), a=100 m2 bidang tangkapan khas.

    Bukan TWI akumulasi aliran D8 penuh; ditandai proxy sampai data terrain hidrolis ada.
    """
    beta = math.radians(max(0.5, min(slope_deg, 45.0)))
    return float(np.clip(math.log(100.0 / math.tan(beta)), 3.0, 18.0))


def landscape_zone_from_slope(slope_deg: float) -> str:
    if slope_deg >= 8.0:
        return "Banyumas_Upper_Slamet_Transition_Slope"
    if slope_deg >= 3.0:
        return "Banyumas_Kedungbanteng_Mid_Terrace"
    return "Banyumas_Serayu_Alluvial_Vertisol_Basin"


class PaddyLiveEvaluator:
    """Memuat konteks per sel sekali, lalu mengevaluasi sel dari observasi mm_ live."""

    def __init__(self):
        self.pvrs = PVRSEngine()
        self.bf = BFEHSIEngine()
        self._assembler = ContractAssembler()
        self._ctx: Dict[str, Dict[str, Any]] = {}
        self._mbsi_fallback = 0.0
        self._load_context()

    def _load_context(self) -> None:
        clim = pd.read_parquet(CLIM_PATH).drop_duplicates("h3_index").set_index("h3_index")
        wide = pd.read_parquet(WIDE_PATH)
        curr = wide[(wide["year"] == 2026) & (wide["dekad"] == 30)].set_index("h3_index")
        gj = json.loads(GRID_PATH.read_text(encoding="utf-8"))
        paddy = {ft["properties"]["h3_index"] for ft in gj["features"]}

        # Akumulasi hujan 7 hari terakhir per sel dari bridge harian (sumber GPM_rain_7d).
        rain_7d: Dict[str, float] = {}
        if BRIDGE_PATH.exists():
            bridge = pd.read_parquet(BRIDGE_PATH, columns=["h3_index", "date", "rain_mm"])
            last7 = sorted(bridge["date"].unique())[-7:]
            recent = bridge[bridge["date"].isin(last7)]
            rain_7d = recent.groupby("h3_index")["rain_mm"].sum().to_dict()

        for idx in paddy:
            c = clim.loc[idx] if idx in clim.index else None
            w = curr.loc[idx] if idx in curr.index else None
            self._ctx[idx] = {
                "lst_mu": _f(c.get("LST_MODIS_C_mu") if c is not None else None, 29.4),
                "lst_sd": max(_f(c.get("LST_MODIS_C_sd") if c is not None else None, 1.15), 0.1),
                "sm_mu": _f(c.get("SM_ROOTZONE_mu") if c is not None else None, 0.31),
                "sm_sd": max(_f(c.get("SM_ROOTZONE_sd") if c is not None else None, 0.055), 0.005),
                "ndvi_mu": _f(c.get("NDVI_mu") if c is not None else None, 0.72),
                "ndvi_sd": max(_f(c.get("NDVI_sd") if c is not None else None, 0.08), 0.01),
                "ndvi": _f(w.get("NDVI") if w is not None else None, float("nan")),
                "mbsi": _f(w.get("MBSI") if w is not None else None, float("nan")),
                "n_obs": _f(w.get("N_OBS") if w is not None else None, 0.0),
                "slope": _f(w.get("SRTM_SLOPE_DEG") if w is not None else None, 5.0),
                "elev": _f(w.get("SRTM_ELEV_M") if w is not None else None, 50.0),
                "prov": (w.get("indicator_provenance") if w is not None else None) or "unknown",
                "rain_7d": rain_7d.get(idx),
            }

        # Fallback BSI regional = rata-rata MBSI sel terobservasi (untuk sel abstain).
        observed_mbsi = [
            ctx["mbsi"] for ctx in self._ctx.values() if math.isfinite(ctx["mbsi"])
        ]
        self._mbsi_fallback = (
            float(np.mean(observed_mbsi)) if observed_mbsi else 0.0
        )

    def _baseline(self, ctx: Dict[str, Any]) -> DecadalClimatologyBaseline:
        return DecadalClimatologyBaseline(
            mu_esi=MU_ESI_REGIONAL, sigma_esi=SIGMA_ESI_REGIONAL,
            mu_lst_c=ctx["lst_mu"], sigma_lst_c=ctx["lst_sd"],
            mu_sm_root=ctx["sm_mu"], sigma_sm_root=ctx["sm_sd"],
            mu_ndvi=ctx["ndvi_mu"], sigma_ndvi=ctx["ndvi_sd"],
        )

    def evaluate_cell(self, h3_index: str, mm: Dict[str, Any]) -> Dict[str, Any]:
        ctx = self._ctx.get(h3_index)
        if ctx is None:
            raise KeyError(f"Sel {h3_index} tidak ada di grid sawah.")
        base = self._baseline(ctx)

        lst_live = _f(mm.get("mm_tmax_p95_c"), ctx["lst_mu"])
        t2m_live = _f(mm.get("mm_t2m_mean_c"), lst_live - 5.0)
        sm_live = _f(mm.get("mm_smi_mean"), ctx["sm_mu"])
        et_live = _f(mm.get("mm_et_total_mm"), 4.0)
        precip_live = _f(mm.get("mm_precip_total_mm"), 10.0)
        rmax_live = _f(mm.get("mm_precip_max_1h_mm"), 5.0)
        ndvi = ctx["ndvi"] if math.isfinite(ctx["ndvi"]) else ctx["ndvi_mu"]

        # ESI live dari rasio ET/hujan (pemetaan cohort tim rumus), bukan konstanta.
        esi = float(np.clip(et_live / max(15.0, et_live + 12.0 - 0.1 * precip_live), 0.25, 0.88))
        cloud = 0.15 if ctx["n_obs"] >= 1 else 0.85

        obs = SatelliteObservationInput(
            h3_index=h3_index,
            esi_actual=esi,
            lst_actual_c=lst_live,
            sm_root_actual=sm_live,
            ndvi_actual=ndvi,
            obs_age_hours=24.0,
            cloud_fraction=cloud,
            sensor_zenith_deg=20.0,
            diurnal_temp_range_c=max(4.5, lst_live - t2m_live + 4.0),
        )
        pv = self.pvrs.evaluate_cell(obs, base)

        # BF-EHSI penuh: kemiringan SRTM asli + jendela bera dari kondisi live.
        slope = ctx["slope"]
        twi = estimate_twi(slope)
        zone = landscape_zone_from_slope(slope)
        sm_surf = float(np.clip(sm_live * 0.45, 0.08, 0.32))
        r_extreme = max(38.0, min(68.0, rmax_live * 11.5))
        steps = [
            HLSReflectanceStep(
                day_index=d,
                rho_nir=0.16, rho_swir1=0.34, rho_swir2=0.11,
                lst_ecostress_c=lst_live + 6.5 + 0.25 * d,
                r_gpm_max_mm_hr=rmax_live if d < 8 else r_extreme,
                sm_surface_m3m3=max(0.08, sm_surf - 0.008 * d),
                delta_t_days=1.0,
                eto_mm_day=max(3.5, et_live),
                precip_bias_correction_factor=1.0,
            )
            for d in range(FALLOW_DAYS)
        ]
        bf = self.bf.evaluate_fallow_window(h3_index, zone, slope, twi, steps, clay_fraction=0.52)
        bf_norm = float(np.clip(bf.bf_ehsi_instantaneous / 2.5, 0.0, 1.0))

        erosion_alert = bool(slope > 15.0 or (precip_live > 150.0 and slope > 8.0))
        system_state = pv.system_state

        return {
            "h3_index": h3_index,
            "pvrs_score": round(float(pv.pvrs_score), 4),
            "stress_category": pv.stress_category,
            "confidence_pct": round(float(pv.confidence_pct), 2),
            "system_state": system_state,
            "optical_lag_days": int(pv.estimated_optical_lag_days),
            "bf_ehsi_instantaneous": round(float(bf.bf_ehsi_instantaneous), 4),
            "bf_ehsi_norm": round(bf_norm, 4),
            "cumulative_risk_di": round(float(bf.cumulative_risk_integral_di), 4),
            "sheet_erosion_ton_ha_yr": round(float(bf.estimated_sheet_erosion_ton_ha_yr), 3),
            "exceeds_erosion_tolerance": bool(bf.exceeds_erosion_tolerance),
            "crack_depth_cm": round(float(bf.desiccation_crack_depth_cm), 2),
            "slope_deg": round(slope, 2),
            "twi_proxy": round(twi, 2),
            "landscape_zone": zone,
            "erosion_alert": erosion_alert,
            "lst_anomaly_c": round(float(pv.lst_anomaly_c), 3),
            "msavi_effective": round(float(pv.msavi_effective), 4),
            "tvdi_dryness_index": round(float(pv.tvdi_dryness_index), 4),
            "esi_live": round(esi, 3),
            "sm_root_live_m3m3": round(sm_live, 4),
            "ndvi_satellite": round(ndvi, 4),
            "indicator_provenance": ctx["prov"],
            "_contract": self._contract(h3_index, ctx, pv, bf, esi, sm_live, ndvi,
                                        precip_live, erosion_alert, system_state, mm),
        }

    def _contract(self, idx, ctx, pv, bf, esi, sm_live, ndvi, precip_live,
                  erosion_alert, system_state, mm) -> Dict[str, Any]:
        """Kontrak v1.0 conform skema (dirakit ContractAssembler) dari nilai live + engine penuh."""
        slope = ctx["slope"]
        ndvi_is_fallback = not math.isfinite(ctx["ndvi"])
        bsi_is_fallback = not math.isfinite(ctx["mbsi"])
        hls_bsi = ctx["mbsi"] if not bsi_is_fallback else self._mbsi_fallback

        rain_7d = ctx.get("rain_7d")
        if rain_7d is not None and math.isfinite(rain_7d):
            gpm_rain_7d = float(rain_7d)
            rain_7d_source = "bridge_observed_7d"
        else:
            gpm_rain_7d = float(precip_live)
            rain_7d_source = "live_24h_fallback"

        signals = CellPhysicalSignals(
            pvrs=float(pv.pvrs_score),
            bf_ehsi_raw=float(bf.bf_ehsi_instantaneous),
            smap_wetness=float(sm_live),
            ecostress_esi=float(esi),
            lst_anomaly_c=float(pv.lst_anomaly_c),
            hls_bsi=float(hls_bsi),
            hls_ndvi=float(ndvi),
            gpm_rain_7d_mm=gpm_rain_7d,
            srtm_slope_deg=float(slope),
        )
        return self._assembler.assemble(
            h3_index=idx,
            signals=signals,
            missing_observation=bool(ctx["n_obs"] < 1),
            optical_lag_days=int(pv.estimated_optical_lag_days),
            erosion_alert=erosion_alert,
            system_state=system_state,
            stress_category=pv.stress_category,
            confidence_pct=float(pv.confidence_pct),
            h3_parent_res7=mm.get("h3_parent_res7"),
            indicator_provenance=ctx["prov"],
            ndvi_is_fallback=ndvi_is_fallback,
            bsi_is_fallback=bsi_is_fallback,
            rain_7d_source=rain_7d_source,
        )

    def evaluate_batch(self, mm_df: pd.DataFrame) -> pd.DataFrame:
        rows = [self.evaluate_cell(str(r["h3_index"]), r) for r in mm_df.to_dict(orient="records")]
        return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluasi live per sel 2.324 sawah (PVRS + BF-EHSI penuh)")
    ap.add_argument("--mm", type=str, default=str(LIVE_MM_PATH), help="parquet mm_ live")
    ap.add_argument("--limit", type=int, default=0, help="batasi jumlah sel (uji)")
    args = ap.parse_args()

    mm_path = Path(args.mm)
    if not mm_path.exists():
        print(f"ERROR: {mm_path} tidak ada. Jalankan ingest_meteomatics_live.py dulu.")
        return 2
    mm = pd.read_parquet(mm_path)
    if args.limit > 0:
        mm = mm.head(args.limit)

    ev = PaddyLiveEvaluator()
    print(f"Konteks per sel dimuat: {len(ev._ctx)} sel. Evaluasi {len(mm)} sel...")
    scores = ev.evaluate_batch(mm)

    OUT_SCORES.parent.mkdir(parents=True, exist_ok=True)
    flat = scores.drop(columns=["_contract"])
    flat.to_parquet(OUT_SCORES, index=False)

    gj = json.loads(GRID_PATH.read_text(encoding="utf-8"))
    geom = {ft["properties"]["h3_index"]: ft["geometry"] for ft in gj["features"]}
    features = []
    for rec in scores.to_dict(orient="records"):
        idx = rec["h3_index"]
        if idx not in geom:
            continue
        props = rec["_contract"]
        props["h3_index"] = idx
        features.append({"type": "Feature", "geometry": geom[idx], "properties": props})
    OUT_GEOJSON.write_text(json.dumps({"type": "FeatureCollection", "features": features},
                                      ensure_ascii=False), encoding="utf-8")

    # Kontrak v1.0 per sel (sumber endpoint /predict), divalidasi fail-closed.
    from src.contracts.contract_validator import ContractValidator
    validator = ContractValidator()
    contracts = {rec["h3_index"]: rec["_contract"] for rec in scores.to_dict(orient="records")}
    invalid = []
    for idx, contract in contracts.items():
        result = validator.validate(contract)
        if not result.is_valid:
            invalid.append((idx, result.errors[0].message if result.errors else "?"))
    if invalid:
        print(f"ERROR: {len(invalid)} kontrak tidak valid. Contoh: {invalid[:3]}")
        return 1
    OUT_CONTRACTS.write_text(json.dumps({
        "contract_version": "1.0",
        "n_cells": len(contracts),
        "contracts": contracts,
    }, ensure_ascii=False), encoding="utf-8")

    print(f"\nSelesai. {len(flat)} sel -> {OUT_SCORES.name} + {OUT_GEOJSON.name} + {OUT_CONTRACTS.name}")
    print(f"Kontrak v1.0 valid: {len(contracts)}/{len(contracts)} (ContractValidator).")
    print("Distribusi stress_category:", flat.stress_category.value_counts().to_dict())
    print("system_state:", flat.system_state.value_counts().to_dict())
    print(f"PVRS: {flat.pvrs_score.min():.3f}..{flat.pvrs_score.max():.3f} | "
          f"BF-EHSI(norm): {flat.bf_ehsi_norm.min():.3f}..{flat.bf_ehsi_norm.max():.3f}")
    print(f"erosion_alert: {int(flat.erosion_alert.sum())} sel | "
          f"exceeds_tolerance: {int(flat.exceeds_erosion_tolerance.sum())} sel")
    return 0


if __name__ == "__main__":
    sys.exit(main())