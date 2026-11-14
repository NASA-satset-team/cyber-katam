"""
extract_hls_vegetation_bsi.py
-----------------------------
Skrip penarik data Harmonized Landsat-Sentinel (HLS v2.0 / Sentinel-2) 10m-30m 
untuk ekstraksi NDVI (Indeks Kehijauan) dan MBSI (Modified Bare Soil Index)
guna mendeteksi zona tanah terbuka/bera di Kabupaten Banyumas.
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

def fetch_hls_data(roi, start_date="2021-01-01", end_date="2024-12-31"):
    """
    Menarik dataset Sentinel-2 Level-2A (Proxy HLS v2.0) bebas awan (< 20%).
    Koleksi GEE: COPERNICUS/S2_SR_HARMONIZED
    """
    s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
        .filterBounds(roi) \
        .filterDate(start_date, end_date) \
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
    return s2

def compute_ndvi_and_mbsi(image):
    """
    Menhitung NDVI dan Modified Bare Soil Index (MBSI).
    - NDVI = (NIR - RED) / (NIR + RED) -> B8 dan B4
    - MBSI = (SWIR1 - SWIR2 - NIR) / (SWIR1 + SWIR2 + NIR) -> B11, B12, B8
    """
    # 1. NDVI (Kerapatan Vegetasi Padi)
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    
    # 2. MBSI (Tanah Bera/Terbuka)
    swir1 = image.select('B11')
    swir2 = image.select('B12')
    nir = image.select('B8')
    
    mbsi = swir1.subtract(swir2).subtract(nir) \
        .divide(swir1.add(swir2).add(nir)) \
        .rename('MBSI')
        
    return image.addBands([ndvi, mbsi])

if __name__ == "__main__":
    print("=== PIPELINE TASK 5: HLS VEGETASI & BSI BANYUMAS ===")
    PROJECT_ID = "second-replica-490102-f2"
    
    # 1. Inisialisasi GEE
    initialize_gee(project_id=PROJECT_ID)
    
    # 2. Dapatkan ROI Banyumas
    roi = get_banyumas_roi()
    
    # 3. Tarik dan Proses HLS/Sentinel-2
    hls_col = fetch_hls_data(roi, start_date="2021-01-01", end_date="2024-12-31")
    count = hls_col.size().getInfo()
    print(f"[INFO] Jumlah adegan citra Sentinel-2 / HLS (Bebas awan < 20%) terdeteksi: {count}")
    
    if count > 0:
        processed_hls = hls_col.map(compute_ndvi_and_mbsi)
        
        # Hitung rata-rata indeks untuk keseluruhan periode
        mean_indices = processed_hls.select(['NDVI', 'MBSI']).mean().clip(roi)
        
        print(f"[SUCCESS] Berhasil! Ditemukan {count} adegan citra optik HLS di Banyumas.")
        print("[SUCCESS] Indeks kerapatan vegetasi (NDVI) dan tanah bera (MBSI) berhasil dihitung.")
    else:
        print("[WARNING] Citra HLS tidak ditemukan pada batas tutupan awan tersebut.")

    print("=== TUGAS 5 SELESAI: extract_hls_vegetation_bsi.py SIAP DIGUNAKAN ===")