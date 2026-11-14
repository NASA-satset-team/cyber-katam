"""
Skrip untuk menjalankan PVRSEngine (Arya's Engine) pada 1.000 sel H3 Banyumas,
mengisi nilai physical_indicators.pvrs, dan memperbarui demo-grid-levels.json untuk web.
"""
import json
import math
import sys
from pathlib import Path
import numpy as np

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))

# 1. Import PVRSEngine
from external.aryas_workresult.pvrs_engine import (
    PVRSEngine,
    SatelliteObservationInput,
    DecadalClimatologyBaseline,
    PVRSWeights,
    LipschitzErrorParameters,
)

# 2. Inisialisasi Engine dan Baseline Dekad 19 Banyumas
engine = PVRSEngine()
baseline = DecadalClimatologyBaseline(
    mu_esi=0.68,
    sigma_esi=0.12,
    mu_lst_c=29.4,
    sigma_lst_c=1.15,
    mu_sm_root=0.31,
    sigma_sm_root=0.055,
    mu_ndvi=0.72,
    sigma_ndvi=0.08,
)

# 3. Baca GeoJSON indikator
src_geojson_path = root / "public" / "banyumas_h3_indicators_v2.geojson"
geojson_data = json.loads(src_geojson_path.read_text(encoding="utf-8"))

levels_path = root / "public" / "demo-grid-levels.json"
existing_levels = json.loads(levels_path.read_text(encoding="utf-8"))

print(f"Menjalankan PVRSEngine untuk {len(geojson_data['features'])} sel H3...")

res9_cells = []
pvrs_scores = []
categories = {}

for feat in geojson_data["features"]:
    props = feat["properties"]
    idx = props["h3_index"]
    phys = props["physical_indicators"]
    diag = phys.get("_diagnostic", {})
    flags = props.get("operational_flags", {})
    meta = props.get("meta", {})
    
    # Ambil input observasi
    lst_c = diag.get("lst_modis_c")
    if lst_c is None:
        lst_c = 29.4 + (phys.get("lst_anomaly") or 0.0)
        
    sm = phys.get("smap_wetness")
    if sm is None:
        sm = 0.31
        
    ndvi = phys.get("hls_ndvi")
    if ndvi is None:
        ndvi = baseline.mu_ndvi # Default netral saat awan tebal
        
    esi = phys.get("ecostress_esi")
    if esi is None:
        z_sm = (sm - baseline.mu_sm_root) / baseline.sigma_sm_root
        esi = float(np.clip(baseline.mu_esi + 0.05 * z_sm, 0.1, 0.95))
        
    cloud_frac = 0.75 if phys.get("hls_ndvi") is None else 0.15
    
    obs = SatelliteObservationInput(
        h3_index=idx,
        esi_actual=float(esi),
        lst_actual_c=float(lst_c),
        sm_root_actual=float(sm),
        ndvi_actual=float(ndvi),
        obs_age_hours=36.0,
        cloud_fraction=cloud_frac,
        sensor_zenith_deg=25.0,
        in_situ_waterlogging=False,
    )
    
    # EVALUASI MENGGUNAKAN FORMULA PVRSEngine
    pvrs_res = engine.evaluate_cell(obs, baseline)
    
    # Update nilai di geojson
    phys["pvrs"] = pvrs_res.pvrs_score
    pvrs_scores.append(pvrs_res.pvrs_score)
    categories[pvrs_res.stress_category] = categories.get(pvrs_res.stress_category, 0) + 1
    
    # Koordinat ring
    ring = feat["geometry"]["coordinates"][0]
    
    indicators = {
        "pvrs":           round(pvrs_res.pvrs_score, 4),
        "pvrs_category":  pvrs_res.stress_category,
        "optical_lag":    pvrs_res.estimated_optical_lag_days,
        "confidence_pct": pvrs_res.confidence_pct,
        "ndvi":           phys.get("hls_ndvi"),
        "bsi":            phys.get("hls_bsi"),
        "smap_wetness":   phys.get("smap_wetness"),
        "gpm_rain_dekad": phys.get("gpm_rain_dekad"),
        "srtm_slope":     round(phys["srtm_slope"], 2) if phys.get("srtm_slope") is not None else None,
        "lst_anomaly":    phys.get("lst_anomaly"),
        "erosion_alert":  flags.get("erosion_alert", False),
        "paddy_gate_passed": flags.get("paddy_gate_passed", False),
        "system_state":   pvrs_res.system_state,
        "dekad_year":     meta.get("current_dekad_year", 2025),
        "dekad":          meta.get("current_dekad", 19),
    }
    
    res9_cells.append({
        "id": idx,
        "ring": ring,
        "indicators": indicators,
    })

# Simpan kembali GeoJSON yang sudah terisi PVRS
src_geojson_path.write_text(json.dumps(geojson_data, separators=(",", ":")), encoding="utf-8")
print(f"GeoJSON diperbarui dengan nilai PVRS riil: {src_geojson_path}")

# Simpan ke demo-grid-levels.json untuk konsumsi Web
new_levels = {
    "7": existing_levels["levels"].get("7", []),
    "8": existing_levels["levels"].get("8", []),
    "9": res9_cells,
}

artifact = {
    "source": "public/banyumas_h3_indicators_v2.geojson",
    "generator": "web-app/scripts/compute_pvrs.py",
    "data_type": "REAL_NASA_INDICATORS_AND_PVRS",
    "contract_version": "grid_cell_contract_v1.2",
    "pvrs_engine": "PVRSEngine (Bab 3.2)",
    "pvrs_summary": {
        "min": round(min(pvrs_scores), 4),
        "max": round(max(pvrs_scores), 4),
        "mean": round(float(np.mean(pvrs_scores)), 4),
        "categories": categories,
    },
    "levels": new_levels,
}

levels_path.write_text(json.dumps(artifact, separators=(",", ":")), encoding="utf-8")
print(f"demo-grid-levels.json diperbarui untuk Web: {levels_path}")
print(f"Statistik PVRS Banyumas: Min={min(pvrs_scores):.4f}, Max={max(pvrs_scores):.4f}, Mean={np.mean(pvrs_scores):.4f}")
print("Distribusi Kategori:", categories)
