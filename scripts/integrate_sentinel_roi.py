"""
scripts/integrate_sentinel_roi.py
---------------------------------
Mengintegrasikan poligon sawah riil Copernicus Sentinel-2 (ESA WorldCover 10m)
ke dalam grid sel H3 CYBER-KATAM:
1. Menghitung intersection dan paddy_fraction spasial presisi per sel H3.
2. Mengelompokkan kelas tutupan lahan: PADDY_FIELD, MIXED, NON_PADDY.
3. Memperbarui flag operasional paddy_gate_passed secara nyata (bukan asumsi).
4. Menghasilkan layer banyumas_paddy_mask.geojson untuk Leaflet.
"""

import json
import shutil
from pathlib import Path
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
ACTUAL_ROI_PATH = ROOT / "data" / "boundaries" / "banyumas_paddy_roi_actual.geojson"
DEMO_GRID_PATH = ROOT / "public" / "demo-grid-levels.json"
INDICATORS_PATH = ROOT / "public" / "banyumas_h3_indicators_v2.geojson"
PROCESSED_INDICATORS_PATH = ROOT / "data" / "processed" / "banyumas_h3_indicators_v2.geojson"
CLEAN_MASK_PATH = ROOT / "public" / "banyumas_paddy_mask.geojson"

print("1. Membaca poligon sawah aktual Copernicus Sentinel-2...")
with open(ACTUAL_ROI_PATH, "r", encoding="utf-8") as f:
    paddy_data = json.load(f)

paddy_features = paddy_data.get("features", [])
print(f"   Ditemukan {len(paddy_features)} fitur poligon sawah Sentinel-2.")

paddy_polys = [shape(f["geometry"]) for f in paddy_features if f["geometry"]["type"] in ("Polygon", "MultiPolygon")]
tree = STRtree(paddy_polys)

# Simpan layer poligon bersih untuk Leaflet (filter slivers < 100 m2)
print("2. Menyiapkan layer visualisasi web public/banyumas_paddy_mask.geojson...")
clean_features = []
for f in paddy_features:
    geom = shape(f["geometry"])
    if geom.area >= 0.000001:  # petak sawah bermakna
        clean_features.append({
            "type": "Feature",
            "properties": {"land_cover": "Paddy Field (Sentinel-2 ESA)"},
            "geometry": mapping(geom)
        })

with open(CLEAN_MASK_PATH, "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": clean_features}, f)
print(f"   Tersimpan {len(clean_features)} poligon sawah utama di {CLEAN_MASK_PATH}.")

# Salin juga file utuh ke public
shutil.copy(ACTUAL_ROI_PATH, ROOT / "public" / "banyumas_paddy_roi_actual.geojson")

print("3. Memproses interseksi spasial pada sel H3 (Resolusi 7, 8, 9)...")
with open(DEMO_GRID_PATH, "r", encoding="utf-8") as f:
    grid_data = json.load(f)

paddy_h3_stats = {}

for res in ["7", "8", "9"]:
    cells = grid_data["levels"][res]
    verified_count = 0
    
    for cell in cells:
        poly = shape({"type": "Polygon", "coordinates": [cell["ring"]]})
        matches = tree.query(poly)
        intersecting = [paddy_polys[i] for i in matches if poly.intersects(paddy_polys[i])]
        
        if intersecting:
            u = unary_union(intersecting)
            inter_area = poly.intersection(u).area
            fraction = min(1.0, round(inter_area / poly.area, 4))
        else:
            fraction = 0.0
            
        # Penentuan kelas tutupan lahan sesuai Task 3 model
        if fraction >= 0.50:
            lc_class = "PADDY_FIELD"
            gate_passed = True
        elif fraction >= 0.05:
            lc_class = "MIXED"
            gate_passed = True
        else:
            lc_class = "NON_PADDY"
            gate_passed = False
            
        if gate_passed:
            verified_count += 1
            
        # Simpan ke indikator sel
        if "indicators" in cell and cell["indicators"] is not None:
            cell["indicators"]["paddy_gate_passed"] = gate_passed
            cell["indicators"]["paddy_fraction"] = fraction
            cell["indicators"]["land_cover_class"] = lc_class
            cell["indicators"]["verification_status"] = "REFERENCE_VALIDATED"
            if not gate_passed:
                cell["indicators"]["system_state"] = "ABSTAIN_NON_PADDY"
        else:
            cell["indicators"] = {
                "paddy_gate_passed": gate_passed,
                "paddy_fraction": fraction,
                "land_cover_class": lc_class,
                "verification_status": "REFERENCE_VALIDATED"
            }
            
        paddy_h3_stats[cell["id"]] = {
            "paddy_gate_passed": gate_passed,
            "paddy_fraction": fraction,
            "land_cover_class": lc_class
        }
        
    print(f"   Resolusi {res}: {verified_count} dari {len(cells)} sel terverifikasi sawah.")

with open(DEMO_GRID_PATH, "w", encoding="utf-8") as f:
    json.dump(grid_data, f)
print(f"   Berhasil memperbarui {DEMO_GRID_PATH}.")

print("4. Memperbarui banyumas_h3_indicators_v2.geojson...")
with open(INDICATORS_PATH, "r", encoding="utf-8") as f:
    indicators_geojson = json.load(f)

for feat in indicators_geojson["features"]:
    h3_id = feat["properties"].get("h3_index") or feat.get("id")
    if h3_id in paddy_h3_stats:
        stat = paddy_h3_stats[h3_id]
        feat["properties"]["operational_flags"]["paddy_gate_passed"] = stat["paddy_gate_passed"]
        feat["properties"]["operational_flags"]["paddy_fraction"] = stat["paddy_fraction"]
        feat["properties"]["operational_flags"]["land_cover_class"] = stat["land_cover_class"]
        
        # Tambahkan flag quality
        flags = feat["properties"]["operational_flags"].get("data_quality_flags", [])
        if "SENTINEL2_WORLDCOVER_VALIDATED" not in flags:
            flags.append("SENTINEL2_WORLDCOVER_VALIDATED")
        feat["properties"]["operational_flags"]["data_quality_flags"] = flags
        
        if not stat["paddy_gate_passed"]:
            feat["properties"]["system_state"] = "ABSTAIN_NON_PADDY"

with open(INDICATORS_PATH, "w", encoding="utf-8") as f:
    json.dump(indicators_geojson, f)

with open(PROCESSED_INDICATORS_PATH, "w", encoding="utf-8") as f:
    json.dump(indicators_geojson, f)

print(f"   Berhasil memperbarui {INDICATORS_PATH} dan {PROCESSED_INDICATORS_PATH}.")
print("\n[SUCCESS] Seluruh data sawah Sentinel-2 telah terintegrasi 100%!")
