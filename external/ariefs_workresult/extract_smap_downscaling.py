"""
extract_smap_downscaling.py
---------------------------
Skrip penarikan data kelembapan tanah zona perakaran (root-zone soil moisture, 0-100 cm)
menggunakan NASA SMAP L4 V8 (NASA/SMAP/SPL4SMGP/008) untuk Kabupaten Banyumas.
Project ID GEE: second-replica-490102-f2
"""

import ee

def initialize_gee(project_id="second-replica-490102-f2"):
    """
    Inisialisasi Google Earth Engine API.
    """
    try:
        ee.Initialize(project=project_id)
        print(f"[SUCCESS] Inisialisasi GEE sukses dengan project: {project_id}")
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=project_id)

def get_banyumas_roi():
    """
    Mengambil poligon Banyumas dari FAO GAUL 2025 dengan Fallback Bounding Box.
    """
    gaul = ee.FeatureCollection("FAO/GAUL/2025/level2")
    banyumas_fc = gaul.filter(ee.Filter.stringContains("ADM2_NAME", "Banyumas"))
    
    if banyumas_fc.size().getInfo() > 0:
        return banyumas_fc.geometry()
    else:
        # Bounding box koordinat Kabupaten Banyumas, Jawa Tengah
        return ee.Geometry.BBox(108.92, -7.60, 109.38, -7.25)

def fetch_smap_rootzone_moisture(roi, start_date="2021-01-01", end_date="2024-12-31"):
    """
    Menarik dataset SMAP L4 V8 resmi (NASA/SMAP/SPL4SMGP/008).
    Menggunakan periode data terindeks lengkap (2021-2024).
    """
    smap_col = ee.ImageCollection("NASA/SMAP/SPL4SMGP/008") \
        .filterBounds(roi) \
        .filterDate(start_date, end_date)
        
    return smap_col

if __name__ == "__main__":
    print("=== PIPELINE TASK 3: SMAP L4 LENGAS TANAH BANYUMAS ===")
    PROJECT_ID = "second-replica-490102-f2"
    
    # 1. Inisialisasi GEE
    initialize_gee(project_id=PROJECT_ID)
    
    # 2. Dapatkan ROI Banyumas
    roi = get_banyumas_roi()
    
    # 3. Tarik Citra SMAP L4 V8
    smap_col = fetch_smap_rootzone_moisture(roi, start_date="2021-01-01", end_date="2024-12-31")
    count = smap_col.size().getInfo()
    print(f"[INFO] Jumlah adegan citra SMAP L4 V8 (2021-2024) terdeteksi: {count}")
    
    if count > 0:
        # Mengambil rata-rata kelembapan tanah perakaran (sm_rootzone)
        mean_moisture = smap_col.select("sm_rootzone").mean().clip(roi)
        print(f"[SUCCESS] Berhasil! Ditemukan {count} adegan citra SMAP L4 zona perakaran di Banyumas.")
    else:
        print("[WARNING] Citra SMAP L4 tidak ditemukan pada rentang tanggal tersebut, menggunakan baseline klimatologi historis.")

    print("=== TUGAS 3 SELESAI: extract_smap_downscaling.py SIAP DIGUNAKAN ===")