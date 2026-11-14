"""
extract_gpm_precipitation.py
----------------------------
Skrip penarik data presipitasi (curah hujan) menggunakan GPM IMERG 
serta perhitungan pemicu erosi monsun (P95) untuk wilayah Kabupaten Banyumas.
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

def fetch_gpm_imerg(roi, start_date="2021-01-01", end_date="2024-12-31"):
    """
    Menarik dataset presipitasi.
    Prioritas 1: NASA GPM IMERG V06 / V07
    Prioritas 2 (Fallback): CHIRPS Daily (presipitasi resolusi tinggi)
    """
    try:
        gpm_col = ee.ImageCollection("NASA/GPM_L3/IMERG_V06") \
            .filterBounds(roi) \
            .filterDate(start_date, end_date) \
            .select("precipitationCal")
            
        if gpm_col.size().getInfo() == 0:
            gpm_col = ee.ImageCollection("NASA/GPM_L3/IMERG_V07") \
                .filterBounds(roi) \
                .filterDate(start_date, end_date) \
                .select("precipitationCal")
        return gpm_col
    except Exception as e:
        print(f"[LOG] Fallback ke CHIRPS karena GPM tidak tersedia/berubah nama: {e}")
        return ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY") \
            .filterBounds(roi) \
            .filterDate(start_date, end_date) \
            .select("precipitation")

if __name__ == "__main__":
    print("=== PIPELINE TASK 4: PRESIPITASI GPM IMERG BANYUMAS ===")
    PROJECT_ID = "second-replica-490102-f2"
    
    # 1. Inisialisasi GEE
    initialize_gee(project_id=PROJECT_ID)
    
    # 2. Dapatkan ROI Banyumas
    roi = get_banyumas_roi()
    
    # 3. Tarik Citra GPM IMERG (Gunakan rentang 2021-2024 agar setara dengan termal/soil moisture)
    gpm_col = fetch_gpm_imerg(roi, start_date="2021-01-01", end_date="2024-12-31")
    count = gpm_col.size().getInfo()
    print(f"[INFO] Jumlah adegan citra Presipitasi (2021-2024) terdeteksi: {count}")
    
    if count > 0:
        # Menghitung persentil ke-95 (P95) untuk deteksi pemicu erosi monsun ekstrim
        p95_precipitation = gpm_col.reduce(ee.Reducer.percentile([95])).clip(roi)
        print(f"[SUCCESS] Berhasil! Ditemukan {count} adegan citra presipitasi di Banyumas.")
        print("[SUCCESS] Kalkulasi Persentil ke-95 (P95) erosi monsun berhasil disiapkan.")
    else:
        print("[WARNING] Citra Presipitasi tidak ditemukan pada rentang tanggal tersebut.")

    print("=== TUGAS 4 SELESAI: extract_gpm_precipitation.py SIAP DIGUNAKAN ===")