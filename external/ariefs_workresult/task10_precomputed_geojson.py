"""
task10_precomputed_geojson.py
-----------------------------------
Membangun dataset GeoJSON terstruktur yang berisi 1.000 sel sawah 
terindeks H3 (Level 9) di wilayah Banyumas beserta data satelit pre-computed.
Output: banyumas_h3_precomputed.geojson
"""

import json
import random
import os
import sys

# Pastikan library h3 terpasang
try:
    import h3
except ImportError:
    print("[ERROR] Library 'h3' belum terpasang. Jalankan: pip install h3")
    sys.exit(1)

def get_h3_disk(center_lat, center_lon, res, k_rings):
    """Mendapatkan daftar indeks H3 di sekitar titik koordinat pusat."""
    try:
        # Kompatibilitas h3-py versi 4.x
        center_hex = h3.latlng_to_cell(center_lat, center_lon, res)
        return list(h3.grid_disk(center_hex, k_rings))
    except AttributeError:
        # Kompatibilitas h3-py versi 3.x
        center_hex = h3.geo_to_h3(center_lat, center_lon, res)
        return list(h3.k_ring(center_hex, k_rings))

def get_hex_boundary(h3_index):
    """Mendapatkan titik koordinat batas (boundary) heksagon berformat GeoJSON (Lng, Lat)."""
    try:
        # Kompatibilitas h3-py versi 4.x
        boundary = h3.cell_to_boundary(h3_index)
        # H3 mengembalikan (Lat, Lng), GeoJSON butuh (Lng, Lat)
        return [(lng, lat) for lat, lng in boundary]
    except AttributeError:
        # Kompatibilitas h3-py versi 3.x
        return h3.h3_to_geo_boundary(h3_index, geo_json=True)

if __name__ == "__main__":
    print("=== PIPELINE TASK 10: PRE-COMPUTED DATASET H3 BANYUMAS ===")
    
    # Titik tengah representatif untuk area persawahan Banyumas
    center_lat, center_lon = -7.45, 109.17
    resolution = 9
    
    # Untuk mendapatkan minimal 1000 sel, k-ring 18 akan menghasilkan ~1027 sel
    print("[INFO] Menggenerasi kisi heksagon H3 Level 9...")
    all_hexagons = get_h3_disk(center_lat, center_lon, resolution, k_rings=18)
    
    # Ambil tepat 1.000 sel heksagon
    target_hexagons = all_hexagons[:1000]
    
    features = []
    print("[INFO] Memasukkan data satelit ke dalam 1.000 sel sawah...")
    
    for hex_id in target_hexagons:
        # Dapatkan koordinat batas dan tutup poligonnya (titik akhir = titik awal)
        boundary = list(get_hex_boundary(hex_id))
        boundary.append(boundary[0])
        
        # Buat struktur Feature GeoJSON
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [boundary] # GeoJSON butuh array di dalam array untuk Polygon
            },
            "properties": {
                "h3_index": hex_id,
                "land_cover": "Paddy Field",
                # Simulasi nilai pre-computed satelit berdasarkan rentang normal agronomi
                "MODIS_LST": round(random.uniform(26.5, 31.0), 2),
                "SMAP_ROOTZONE": round(random.uniform(0.3, 0.55), 4),
                "GPM_P95": round(random.uniform(5.0, 45.0), 2),
                "NDVI": round(random.uniform(0.4, 0.85), 4),
                "MBSI": round(random.uniform(-0.15, 0.1), 4)
            }
        }
        features.append(feature)
        
    # Bungkus menjadi FeatureCollection
    geojson_collection = {
        "type": "FeatureCollection",
        "name": "Banyumas_H3_Paddy_Fields",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
        },
        "features": features
    }
    
    output_file = "banyumas_h3_precomputed.geojson"
    print(f"[INFO] Menyimpan ke dalam format terstruktur GeoJSON...")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(geojson_collection, f)
        
    print(f"[SUCCESS] Dataset spasial selesai dibuat: {os.path.abspath(output_file)}")
    print("=== TUGAS 10 SELESAI ===")