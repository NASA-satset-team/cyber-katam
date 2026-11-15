"""
web-app/scripts/build_grid_4143.py
----------------------------------
Membangun ulang artefak grid sawah dari data FINAL tim data
(D:/data-nasa/banyumas_daily_model_v2/banyumas_daily_model.parquet, 4.143 sel H3 res-9).

Menggantikan build_paddy_grid.py (grid 2.324 sel hasil polyfill mask + nearest-neighbor).
Data baru sudah terobservasi per sel untuk 4.143 sel, sehingga tidak ada interpolasi:
  - grid geojson = 4.143 poligon H3 res-9 langsung dari daftar sel data.
  - wide         = agregat dekad-30 (21-31 Okt) per sel per tahun 2021-2026, OBSERVED.
  - clim         = mu/sd/n_years lintas tahun per sel (7 fitur iklim).

Konvensi dekad-30 = snapshot akhir Oktober (21-31 Okt) per tahun, dikalibrasi terhadap
artefak wide lama (SM ~0.262, RAIN ~jumlah 10 hari). Nilai memakai kolom observasi
MENTAH (bukan gapfill); hari tanpa observasi tetap NaN agar fallback klimatologi
evaluator berlaku jujur.

Agregasi harian -> dekad:
  LST_MODIS_C / SM_ROOTZONE / SM_SURFACE / NDVI / MBSI / N_OBS = mean (skip NaN)
  RAIN_MM = sum; MAX_MMHR = max
  SRTM_ELEV_M / SRTM_SLOPE_DEG = terrain statis (mean, konstan per sel)

Nama file artefak DIPERTAHANKAN (*_paddy) agar path evaluator/ingestor/bridge stabil;
isinya diganti menjadi grid 4.143 sel. Engine tidak diubah.
"""

import argparse
import json
import sys
from pathlib import Path

import h3
import numpy as np
import pandas as pd

root = Path(__file__).resolve().parents[2]

DEFAULT_SRC = Path("D:/data-nasa/banyumas_daily_model_v2/banyumas_daily_model.parquet")
GRID_OUT = root / "data" / "processed" / "banyumas_h3_paddy_grid.geojson"
WIDE_OUT = root / "data" / "processed" / "banyumas_indicators_wide_paddy.parquet"
CLIM_OUT = root / "data" / "processed" / "climatology_baseline_banyumas_paddy.parquet"

YEARS = [2021, 2022, 2023, 2024, 2025, 2026]
DEKAD = 30  # label snapshot akhir Oktober (21-31 Okt)

# Kolom harian yang dibaca dari data final.
SRC_COLS = [
    "h3_index", "date", "lst_modis_c", "max_mmhr", "mbsi", "ndvi", "n_obs",
    "rain_mm", "sm_rootzone", "sm_surface", "elev_m", "slope_deg",
]
# Pemetaan kolom harian -> kolom wide uppercase + fungsi agregasi dekad.
AGG = {
    "LST_MODIS_C": ("lst_modis_c", "mean"),
    "MAX_MMHR": ("max_mmhr", "max"),
    "MBSI": ("mbsi", "mean"),
    "NDVI": ("ndvi", "mean"),
    "N_OBS": ("n_obs", "mean"),
    "RAIN_MM": ("rain_mm", "sum"),
    "SM_ROOTZONE": ("sm_rootzone", "mean"),
    "SM_SURFACE": ("sm_surface", "mean"),
    "SRTM_ELEV_M": ("elev_m", "mean"),
    "SRTM_SLOPE_DEG": ("slope_deg", "mean"),
}
WIDE_ORDER = [
    "h3_index", "year", "dekad", "LST_MODIS_C", "MAX_MMHR", "MBSI", "NDVI",
    "N_OBS", "RAIN_MM", "SM_ROOTZONE", "SM_SURFACE", "SRTM_ELEV_M",
    "SRTM_SLOPE_DEG", "indicator_provenance", "indicator_source_h3",
]
# 7 fitur iklim untuk baseline klimatologi (terrain/N_OBS bukan variabel iklim).
CLIM_FEATURES = [
    "LST_MODIS_C", "MAX_MMHR", "MBSI", "NDVI", "RAIN_MM", "SM_ROOTZONE", "SM_SURFACE",
]


def build_wide(src: pd.DataFrame) -> pd.DataFrame:
    d = pd.to_datetime(src["date"])
    mask = (d.dt.month == 10) & (d.dt.day >= 21) & (d.dt.year.isin(YEARS))
    sub = src.loc[mask].copy()
    sub["year"] = d[mask].dt.year.astype("int64")
    print(f"   Baris dekad-30 (21-31 Okt, {YEARS[0]}-{YEARS[-1]}): {len(sub)} "
          f"({sub.h3_index.nunique()} sel)")

    agg_spec = {out: (col, fn) for out, (col, fn) in AGG.items()}
    wide = sub.groupby(["h3_index", "year"], sort=True).agg(**agg_spec).reset_index()
    wide["dekad"] = DEKAD
    wide["indicator_provenance"] = "OBSERVED"
    wide["indicator_source_h3"] = wide["h3_index"]
    return wide[WIDE_ORDER]


def build_clim(wide: pd.DataFrame) -> pd.DataFrame:
    g = wide.groupby("h3_index", sort=True)
    clim = pd.DataFrame({"h3_index": g.size().index})
    clim["dekad"] = DEKAD
    for f in CLIM_FEATURES:
        clim[f + "_mu"] = g[f].mean().to_numpy()
    for f in CLIM_FEATURES:
        clim[f + "_n_years"] = g[f].count().to_numpy()
    for f in CLIM_FEATURES:
        clim[f + "_sd"] = g[f].std(ddof=1).to_numpy()
    clim["indicator_provenance"] = "OBSERVED"
    clim["indicator_source_h3"] = clim["h3_index"]
    return clim


def build_grid(cells) -> dict:
    features = []
    for cell in cells:
        ring = [[lng, lat] for lat, lng in h3.cell_to_boundary(cell)]
        ring.append(ring[0])
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"h3_index": cell},
        })
    return {"type": "FeatureCollection", "features": features}


def main() -> int:
    ap = argparse.ArgumentParser(description="Bangun grid+wide+clim 4.143 sel dari data final tim data")
    ap.add_argument("--src", type=str, default=str(DEFAULT_SRC), help="parquet daily final")
    args = ap.parse_args()

    src_path = Path(args.src)
    if not src_path.exists():
        print(f"ERROR: sumber tidak ditemukan: {src_path}")
        return 2

    print(f"1. Membaca data final: {src_path}")
    src = pd.read_parquet(src_path, columns=SRC_COLS)
    cells = sorted(src["h3_index"].unique().tolist())
    print(f"   {len(src)} baris harian, {len(cells)} sel H3 res-9.")

    print("2. Agregasi dekad-30 per sel per tahun (wide, OBSERVED)...")
    wide = build_wide(src)

    print("3. Baseline klimatologi lintas tahun per sel (clim)...")
    clim = build_clim(wide)

    print("4. Geometri grid H3 res-9 langsung dari daftar sel...")
    grid = build_grid(cells)

    GRID_OUT.parent.mkdir(parents=True, exist_ok=True)
    GRID_OUT.write_text(json.dumps(grid, separators=(",", ":")), encoding="utf-8")
    wide.to_parquet(WIDE_OUT, index=False)
    clim.to_parquet(CLIM_OUT, index=False)

    null_frac = {f: round(float(wide[f].isna().mean()), 4) for f in AGG}
    n_years_dist = clim["SM_ROOTZONE_n_years"].value_counts().sort_index().to_dict()
    print(f"\nSelesai. Grid {len(cells)} sel -> {GRID_OUT.name}")
    print(f"   wide: {len(wide)} baris ({len(cells)} sel x {len(YEARS)} tahun) -> {WIDE_OUT.name}")
    print(f"   clim: {len(clim)} baris -> {CLIM_OUT.name}")
    print(f"   provenance: OBSERVED seluruh sel (data per-sel, tanpa interpolasi)")
    print(f"   null fraction wide per fitur: {null_frac}")
    print(f"   distribusi n_years SM_ROOTZONE: {n_years_dist}")
    return 0


if __name__ == "__main__":
    sys.exit(main())