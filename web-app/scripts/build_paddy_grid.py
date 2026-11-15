"""
web-app/scripts/build_paddy_grid.py
-----------------------------------
Membangkitkan ulang grid H3 resolusi 9 dari poligon sawah riil Copernicus
Sentinel-2 (public/banyumas_paddy_mask.geojson), menggantikan grid disk
warisan yang memusat di satu titik pusat.

Output:
- data/processed/banyumas_h3_paddy_grid.geojson  (geometri input compute_pvrs.py)
- data/processed/banyumas_indicators_wide_paddy.parquet
- data/processed/climatology_baseline_banyumas_paddy.parquet

Provenance indikator per sel baru:
- OBSERVED         : sel berimpit dengan sel dataset observasi lama (nilai asli).
- NEAREST_NEIGHBOR : sel di luar disk observasi lama mewarisi nilai sel
                     terobservasi terdekat (interpolasi spasial, bukan
                     observasi independen).
"""

import json
import math
from pathlib import Path

import h3
import numpy as np
import polars as pl
from shapely.geometry import shape
from shapely.ops import unary_union

root = Path(__file__).resolve().parents[2]

MASK_PATH = root / "public" / "banyumas_paddy_mask.geojson"
GRID_OUT = root / "data" / "processed" / "banyumas_h3_paddy_grid.geojson"
WIDE_SRC = root / "data" / "processed" / "banyumas_indicators_wide.parquet"
CLIM_SRC = root / "data" / "processed" / "climatology_baseline_banyumas.parquet"
WIDE_OUT = root / "data" / "processed" / "banyumas_indicators_wide_paddy.parquet"
CLIM_OUT = root / "data" / "processed" / "climatology_baseline_banyumas_paddy.parquet"

print("1. Polyfill mask sawah Sentinel-2 ke H3 resolusi 9...")
mask = json.loads(MASK_PATH.read_text(encoding="utf-8"))
polys = [shape(f["geometry"]) for f in mask["features"]]
union = unary_union(polys)
cells = sorted(h3.geo_to_cells(union.__geo_interface__, 9))
print(f"   {len(cells)} sel H3-9 tersebar mengikuti mask sawah.")

features = []
for cell in cells:
    ring = [[lng, lat] for lat, lng in h3.cell_to_boundary(cell)]
    ring.append(ring[0])
    features.append({
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [ring]},
        "properties": {"h3_index": cell},
    })
GRID_OUT.write_text(
    json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")),
    encoding="utf-8",
)
print(f"   Geometri tersimpan: {GRID_OUT.name}")

print("2. Memetakan indikator observasi ke sel baru (provenance eksplisit)...")
wide = pl.read_parquet(WIDE_SRC)
clim = pl.read_parquet(CLIM_SRC)
old_cells = sorted(wide["h3_index"].unique().to_list())
old_set = set(old_cells)

old_centers = np.array([h3.cell_to_latlng(c) for c in old_cells])
new_centers = np.array([h3.cell_to_latlng(c) for c in cells])
cos_lat = np.cos(np.radians(new_centers[:, 0]))[:, None]
dist2 = (new_centers[:, 0, None] - old_centers[None, :, 0]) ** 2 + (
    (new_centers[:, 1, None] - old_centers[None, :, 1]) * cos_lat
) ** 2
nearest_old = [old_cells[i] for i in dist2.argmin(axis=1)]

wide_by_cell = {}
for row in wide.to_dicts():
    wide_by_cell.setdefault(row["h3_index"], []).append(row)
clim_by_cell = {row["h3_index"]: row for row in clim.to_dicts()}

wide_rows = []
clim_rows = []
n_observed = 0
for cell, src in zip(cells, nearest_old):
    if cell in old_set:
        src = cell
        provenance = "OBSERVED"
        n_observed += 1
    else:
        provenance = "NEAREST_NEIGHBOR"
    for row in wide_by_cell[src]:
        wide_rows.append({
            **row,
            "h3_index": cell,
            "indicator_provenance": provenance,
            "indicator_source_h3": src,
        })
    clim_rows.append({
        **clim_by_cell[src],
        "h3_index": cell,
        "indicator_provenance": provenance,
        "indicator_source_h3": src,
    })

pl.DataFrame(wide_rows).write_parquet(WIDE_OUT)
pl.DataFrame(clim_rows).write_parquet(CLIM_OUT)
print(f"   {n_observed} sel OBSERVED, {len(cells) - n_observed} sel NEAREST_NEIGHBOR.")
print(f"   Tersimpan: {WIDE_OUT.name} ({len(wide_rows)} baris), {CLIM_OUT.name} ({len(clim_rows)} baris).")

lats = new_centers[:, 0]
lngs = new_centers[:, 1]
print(
    f"3. Sebaran grid baru: {lngs.min():.3f}..{lngs.max():.3f} BT, "
    f"{lats.min():.3f}..{lats.max():.3f} LS"
)
print("[SUCCESS] Grid paddy siap diproses compute_pvrs.py")