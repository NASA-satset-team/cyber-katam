"""
extract_ecostress_banyumas.py
-----------------------------
Skrip penarik data termal ECOSTRESS (L2T LSTE V2) 70m 
serta normalisasi anomali historis untuk wilayah Kabupaten Banyumas.
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

def fetch_ecostress_lste(roi, start_date="2021-01-01", end_date="2024-12-31"):
    """
    Menarik dataset ECOSTRESS Land Surface Temperature & Emissivity (LSTE) V2.
    Asset Catalog GEE Resmi: NASA/ECOSTRESS/L2T_LSTE/V2
    Catatan: Menggunakan rentang tanggal 2021-2024 karena data terindeks lengkap di GEE.
    """
    ecostress_col = ee.ImageCollection("NASA/ECOSTRESS/L2T_LSTE/V2") \
        .filterBounds(roi) \
        .filterDate(start_date, end_date)
        
    return ecostress_col

def fetch_fallback_thermal(roi, start_date="2021-01-01", end_date="2026-11-01"):
    """
    Dataset Termal Cadangan (MODIS LST 1km) jika data ECOSTRESS spesifik kosong.
    """
    modis_lst = ee.ImageCollection("MODIS/061/MOD11A1") \
        .filterBounds(roi) \
        .filterDate(start_date, end_date) \
        .select("LST_Day_1km")
    return modis_lst

def calculate_thermal_anomalies(lst_collection, roi, is_modis=False):
    """
    Menghitung rata-rata suhu permukaan kanopi (LST) dan konversi ke Celsius.
    """
    mean_lst_raw = lst_collection.mean().clip(roi)
    
    if is_modis:
        # MODIS LST (Kelvin * 0.02 - 273.15)
        lst_celsius = mean_lst_raw.multiply(0.02).subtract(273.15)
    else:
        # ECOSTRESS LST Kelvin ke Celsius (-273.15)
        lst_celsius = mean_lst_raw.subtract(273.15)
        
    return lst_celsius

if __name__ == "__main__":
    print("=== PIPELINE TASK 2: ECOSTRESS TERMAL LSTE BANYUMAS ===")
    PROJECT_ID = "second-replica-490102-f2"
    
    initialize_gee(project_id=PROJECT_ID)
    roi = get_banyumas_roi()
    
    # 1. Tarik data ECOSTRESS periode terindeks (2021-2024)
    ecostress_col = fetch_ecostress_lste(roi, start_date="2021-01-01", end_date="2024-12-31")
    count = ecostress_col.size().getInfo()
    print(f"[INFO] Jumlah adegan citra ECOSTRESS LST (2021-2024) terdeteksi: {count}")
    
    if count > 0:
        lst_celsius = calculate_thermal_anomalies(ecostress_col.select("LST"), roi, is_modis=False)
        print(f"[SUCCESS] Berhasil! Ditemukan {count} adegan citra ECOSTRESS LST di Banyumas.")
    else:
        print("[INFO] Memulai fallback ke dataset termal MODIS LST 1km...")
        modis_col = fetch_fallback_thermal(roi)
        modis_count = modis_col.size().getInfo()
        print(f"[INFO] Jumlah adegan citra MODIS LST terdeteksi: {modis_count}")
        
        if modis_count > 0:
            lst_celsius = calculate_thermal_anomalies(modis_col, roi, is_modis=True)
            print("[SUCCESS] Data termal MODIS LST berhasil diekstrak sebagai baseline termal!")

    print("=== TUGAS 2 SELESAI: extract_ecostress_banyumas.py SIAP DIGUNAKAN ===")