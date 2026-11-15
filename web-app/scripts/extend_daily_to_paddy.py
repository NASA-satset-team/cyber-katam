"""
web-app/scripts/extend_daily_to_paddy.py
----------------------------------------
Ekstraktor harian langsung untuk grid sawah 4.143 sel H3 res-9 dari data FINAL
tim data (D:/data-nasa/banyumas_daily_model_v2/banyumas_daily_model.parquet).

Data baru sudah terobservasi PER SEL untuk seluruh 4.143 sel grid, sehingga jembatan
IDW spasial yang lama (1.000 sel disk -> 2.324 sel) TIDAK lagi diperlukan. Skrip ini
menyalin fitur harian apa adanya per sel, dengan provenance jujur:

- provenance = OBSERVED untuk semua sel (tidak ada interpolasi spasial).
- nearest_source_dist_km = 0 (sel adalah sumbernya sendiri).
- low_confidence = False (tidak ada sel jauh dari sumber).
- ndvi_interp / lst_interp diwarisi dari flag sumber: menandai hari yang nilainya
  di-gapfill secara TEMPORAL (estimasi antar-observasi), bukan interpolasi spasial.
- POWER tetap bersifat regional (~50 km, satu titik) meski disimpan per sel.

Nama file keluaran DIPERTAHANKAN (banyumas_daily_paddy_bridge.parquet + _provenance.json)
agar path evaluator (rain_7d) stabil. Mode jendela: default 30 hari terakhir (backend);
--full-history untuk seluruh riwayat (kebutuhan training tim ML).

Sumber default: D:/data-nasa/banyumas_daily_model_v2/banyumas_daily_model.parquet.
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
OUT_PARQUET = root / "data" / "processed" / "banyumas_daily_paddy_bridge.parquet"

# Fitur harian yang bervariasi spasial (kini observasi langsung per sel).
DAILY_FEATURES = [
    "sm_rootzone_ffill", "sm_surface_ffill", "ndvi_gapfill", "lst_gapfill",
    "rain_mm", "max_mmhr",
]
# POWER regional (satu titik ~50 km); disimpan per sel apa adanya dari sumber.
REGIONAL_FEATURES = [
    "power_t2m", "power_t2m_max", "power_t2m_min", "power_rain_mm",
    "power_rh2m", "power_ws2m", "power_solar_mj",
]
SRC_COLS = (
    ["h3_index", "date", "elev_m", "slope_deg", "ndvi_interp", "lst_interp"]
    + DAILY_FEATURES + REGIONAL_FEATURES
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Ekstrak fitur harian 4.143 sel sawah langsung dari data final (tanpa IDW)")
    ap.add_argument("--src", type=str, default=str(DEFAULT_SRC), help="parquet daily final")
    ap.add_argument("--days", type=int, default=30, help="jendela hari terakhir (default 30)")
    ap.add_argument("--full-history", action="store_true", help="proses seluruh riwayat (tim ML)")
    args = ap.parse_args()

    src_path = Path(args.src)
    if not src_path.exists():
        print(f"ERROR: sumber tidak ditemukan: {src_path}")
        return 2

    src = pd.read_parquet(src_path, columns=SRC_COLS)
    src["date"] = pd.to_datetime(src["date"])
    cells = sorted(src["h3_index"].unique().tolist())
    all_dates = np.sort(src["date"].unique())
    dates = all_dates if args.full_history else all_dates[-args.days:]
    print(f"sumber: {len(cells)} sel | {len(all_dates)} hari total")
    print(f"jendela: {len(dates)} hari ({pd.Timestamp(dates[0]).date()} -> {pd.Timestamp(dates[-1]).date()})")

    out = src[src["date"].isin(dates)].copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")

    # Centroid per sel (statis) dari indeks H3.
    cent = {h: h3.cell_to_latlng(h) for h in cells}
    out["centroid_lat"] = out["h3_index"].map(lambda h: cent[h][0])
    out["centroid_lon"] = out["h3_index"].map(lambda h: cent[h][1])

    out["provenance"] = "OBSERVED"
    out["nearest_source_dist_km"] = 0.0
    out["low_confidence"] = False

    order = (
        ["h3_index", "date", "centroid_lat", "centroid_lon", "elev_m", "slope_deg"]
        + DAILY_FEATURES + REGIONAL_FEATURES
        + ["provenance", "nearest_source_dist_km", "low_confidence", "ndvi_interp", "lst_interp"]
    )
    out = out[order].sort_values(["date", "h3_index"]).reset_index(drop=True)

    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT_PARQUET, index=False)

    null_frac = {f: round(float(out[f].isna().mean()), 4) for f in DAILY_FEATURES + REGIONAL_FEATURES}
    provenance = {
        "source": "DIRECT_OBSERVED_EXTRACT",
        "source_file": str(src_path),
        "generated_utc": pd.Timestamp.utcnow().isoformat(),
        "n_cells": len(cells),
        "n_observed": len(cells),
        "n_idw_interpolated": 0,
        "n_low_confidence": 0,
        "window_days": len(dates),
        "date_start": pd.Timestamp(dates[0]).strftime("%Y-%m-%d"),
        "date_end": pd.Timestamp(dates[-1]).strftime("%Y-%m-%d"),
        "spatial_interpolation": "TIDAK ADA; data final sudah observasi per sel untuk seluruh grid",
        "temporal_gapfill_note": "ndvi_interp/lst_interp=True menandai nilai gapfill temporal (estimasi), diwarisi dari sumber",
        "power_note": "regional satu titik ~50 km, disimpan per sel apa adanya",
        "terrain_source": "SRTM asli per sel (elev_m/slope_deg dari data final)",
        "null_fraction": null_frac,
        "n_rows": len(out),
    }
    prov_path = OUT_PARQUET.with_name(OUT_PARQUET.stem + "_provenance.json")
    prov_path.write_text(json.dumps(provenance, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nSelesai. {len(out)} baris ({len(cells)} sel x {len(dates)} hari) -> {OUT_PARQUET.name}")
    print(f"provenance: OBSERVED seluruh sel (tanpa interpolasi spasial)")
    print(f"null fraction fitur: {null_frac}")
    print(f"provenance -> {prov_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())