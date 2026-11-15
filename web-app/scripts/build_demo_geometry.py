"""
Build demo-grid-levels.json from banyumas_h3_indicators_v2.geojson.
Sel H3-9 hasil polyfill mask sawah Sentinel-2, masing-masing dengan
indikator satelit NASA dan provenance per sel (OBSERVED/NEAREST_NEIGHBOR).
"""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]

src_path = root / "public" / "banyumas_h3_indicators_v2.geojson"
source = json.loads(src_path.read_text(encoding="utf-8"))

levels_path = root / "public" / "demo-grid-levels.json"
existing_levels = json.loads(levels_path.read_text(encoding="utf-8"))

# 1. Bangun sel resolusi 9 langsung dari 1.000 fitur banyumas_h3_indicators_v2.geojson
res9_cells = []
for feat in source["features"]:
    props = feat["properties"]
    h3_idx = props["h3_index"]
    phys = props.get("physical_indicators", {})
    flags = props.get("operational_flags", {})
    meta = props.get("meta", {})
    sys_state = props.get("system_state", "ABSTAIN_FIELD_AUDIT_REQUIRED")
    srtm_slope = phys.get("srtm_slope")
    
    # Coordinates ring dari GeoJSON (Polygon -> coordinates[0])
    ring = feat["geometry"]["coordinates"][0]
    
    indicators = {
        "ndvi":           phys.get("hls_ndvi"),
        "bsi":            phys.get("hls_bsi"),
        "smap_wetness":   phys.get("smap_wetness"),
        "gpm_rain_dekad": phys.get("gpm_rain_dekad"),
        "srtm_slope":     round(srtm_slope, 2) if srtm_slope is not None else None,
        "lst_anomaly":    phys.get("lst_anomaly"),
        "erosion_alert":  flags.get("erosion_alert", False),
        "paddy_gate_passed": flags.get("paddy_gate_passed", False),
        "indicator_provenance": flags.get("indicator_provenance"),
        "indicator_source_h3": flags.get("indicator_source_h3"),
        "system_state":   sys_state,
        "dekad_year":     meta.get("current_dekad_year"),
        "dekad":          meta.get("current_dekad"),
    }
    
    res9_cells.append({
        "id": h3_idx,
        "ring": ring,
        "indicators": indicators,
    })

# 2. Pertahankan resolusi 7 dan 8 untuk zoom-out makro
new_levels = {
    "7": existing_levels["levels"].get("7", []),
    "8": existing_levels["levels"].get("8", []),
    "9": res9_cells,
}

artifact = {
    "source": "public/banyumas_h3_indicators_v2.geojson",
    "generator": "web-app/scripts/build_demo_geometry.py",
    "data_type": "REAL_NASA_INDICATORS",
    "contract_version": "grid_cell_contract_v1.2",
    "warning": (
        "Indikator satelit asli: NASA GPM IMERG v7, SMAP SPL4SMGP v8, "
        "HLS v2.0, MODIS LST, SRTM. Sel resolusi 9 terhubung ke indikator "
        "dengan provenance per sel (OBSERVED / NEAREST_NEIGHBOR)."
    ),
    "levels": new_levels,
}

levels_path.write_text(json.dumps(artifact, separators=(",", ":")) + "\n", encoding="utf-8")
print(f"Berhasil! {len(res9_cells)} sel H3-9 memiliki geometri dan indikator NASA lengkap.")
print(f"Ukuran file: {levels_path.stat().st_size / 1024:.1f} KB")
