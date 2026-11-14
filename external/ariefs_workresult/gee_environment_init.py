"""
gee_environment_init.py
------------------------
Skrip inisialisasi lingkungan Google Earth Engine (GEE) Python API 
serta ekstraksi & pemodelan batas wilayah sawah Kabupaten Banyumas.
Project ID: second-replica-490102-f2
"""

import ee
import json

def initialize_gee(project_id="second-replica-490102-f2"):
    """
    Menginisialisasi dan memverifikasi koneksi Google Earth Engine API.
    """
    try:
        if project_id:
            ee.Initialize(project=project_id)
        else:
            ee.Initialize()
        print(f"[SUCCESS] Google Earth Engine API berhasil terinisialisasi dengan project: {project_id}")
    except Exception as e:
        print(f"[INFO] Inisialisasi awal gagal ({e}). Memulai otentikasi...")
        ee.Authenticate()
        if project_id:
            ee.Initialize(project=project_id)
        else:
            ee.Initialize()
        print(f"[SUCCESS] Otentikasi dan Inisialisasi GEE Berhasil ({project_id}).")

def get_banyumas_roi():
    """
    Mengambil batas administratif Kabupaten Banyumas dari dataset FAO GAUL di GEE.
    """
    gaul = ee.FeatureCollection("FAO/GAUL/2015/level2")
    banyumas_boundary = gaul.filter(ee.Filter.eq("ADM2_NAME", "Banyumas"))
    return banyumas_boundary

def get_banyumas_paddy_mask(banyumas_roi):
    """
    Mengisolasi tutupan lahan sawah di Banyumas menggunakan ESA WorldCover 10m v200.
    Class 40 = Cropland / Pertanian Sawah.
    """
    worldcover = ee.ImageCollection("ESA/WorldCover/v200").first()
    paddy_mask = worldcover.select("map").eq(40).clip(banyumas_roi)
    return paddy_mask

def export_roi_geojson(filename="banyumas_paddy_roi.geojson"):
    """
    Mengekspor GeoJSON lokal berisi koordinat Bounding Box Kabupaten Banyumas 
    untuk pengujian ekosistem data tanpa ketergantungan koneksi jaringan.
    """
    banyumas_bbox = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": "Kabupaten Banyumas - Sawah Focus Zone",
                    "province": "Jawa Tengah",
                    "regency": "Banyumas",
                    "epsg": 4326
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [108.92, -7.60],
                        [109.38, -7.60],
                        [109.38, -7.25],
                        [108.92, -7.25],
                        [108.92, -7.60]
                    ]]
                }
            }
        ]
    }
    
    with open(filename, "w") as f:
        json.dump(banyumas_bbox, f, indent=2)
    print(f"[SUCCESS] Berkas GeoJSON batas wilayah disimpan sebagai '{filename}'.")

if __name__ == "__main__":
    print("=== TASK 1: SETUP LINGKUNGAN GEE & BATAS WILAYAH BANYUMAS ===")
    PROJECT_ID = "second-replica-490102-f2"
    
    # 1. Inisialisasi GEE dengan Project ID spesifik
    initialize_gee(project_id=PROJECT_ID)
    
    # 2. Ambil ROI & Mask Sawah
    roi = get_banyumas_roi()
    paddy_mask = get_banyumas_paddy_mask(roi)
    
    # 3. Verifikasi jumlah fitur di GEE
    roi_count = roi.size().getInfo()
    print(f"[INFO] Fitur Poligon Banyumas ditemukan di GEE: {roi_count} region")
    
    # 4. Simpan output batas wilayah GeoJSON
    export_roi_geojson()
    
    print("=== TUGAS 1 SELESAI: gee_environment_init.py SIAP DIGUNAKAN ===")
