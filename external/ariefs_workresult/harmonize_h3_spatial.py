"""
harmonize_h3_spatial.py (FINAL 2.0)
-----------------------------------
Skrip penggabungan seluruh parameter (LST, Soil Moisture, Presipitasi, NDVI, MBSI)
menjadi satu Data Cube (Multi-band Image) yang siap di-resample ke dalam 
grid heksagonal Uber H3 Level 9 untuk area Banyumas.
Project ID GEE: second-replica-490102-f2
"""

import ee

def initialize_gee(project_id="second-replica-490102-f2"):
    try:
        ee.Initialize(project=project_id)
        print(f"[SUCCESS] Inisialisasi GEE sukses dengan project: {project_id}")
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=project_id)

def get_banyumas_roi():
    gaul = ee.FeatureCollection("FAO/GAUL/2025/level2")
    banyumas_fc = gaul.filter(ee.Filter.stringContains("ADM2_NAME", "Banyumas"))
    if banyumas_fc.size().getInfo() > 0:
        return banyumas_fc.geometry()
    return ee.Geometry.BBox(108.92, -7.60, 109.38, -7.25)

def build_data_cube(roi, start_date="2021-01-01", end_date="2024-12-31"):
    # 1. MODIS LST (Suhu Permukaan) 
    lst = ee.ImageCollection("MODIS/061/MOD11A1") \
        .filterBounds(roi).filterDate(start_date, end_date) \
        .select("LST_Day_1km").mean().rename("MODIS_LST")
        
    # 2. SMAP L4 (Kelembapan Tanah Zona Perakaran)
    smap = ee.ImageCollection("NASA/SMAP/SPL4SMGP/008") \
        .filterBounds(roi).filterDate(start_date, end_date) \
        .select("sm_rootzone").mean().rename("SMAP_ROOTZONE")
        
    # 3. GPM IMERG V07 (Presipitasi P95)
    # FIX: Band di GPM V07 bernama 'precipitation', bukan 'precipitationCal'
    gpm = ee.ImageCollection("NASA/GPM_L3/IMERG_V07") \
        .filterBounds(roi).filterDate(start_date, end_date) \
        .select("precipitation").reduce(ee.Reducer.percentile([95])).rename("GPM_P95")
        
    # 4. HLS / Sentinel-2 (NDVI & MBSI)
    s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
        .filterBounds(roi).filterDate(start_date, end_date) \
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20)).mean()
    
    ndvi = s2.normalizedDifference(['B8', 'B4']).rename('NDVI')
    swir1 = s2.select('B11')
    swir2 = s2.select('B12')
    nir = s2.select('B8')
    mbsi = swir1.subtract(swir2).subtract(nir).divide(swir1.add(swir2).add(nir)).rename('MBSI')
    
    # Gabungkan semua menjadi 1 Image (Data Cube)
    data_cube = ee.Image([lst, smap, gpm, ndvi, mbsi]).clip(roi)
    return data_cube

if __name__ == "__main__":
    print("=== PIPELINE TASK 6: HARMONISASI SPASIAL H3 (DATA CUBE) ===")
    PROJECT_ID = "second-replica-490102-f2"
    
    initialize_gee(project_id=PROJECT_ID)
    roi = get_banyumas_roi()
    
    print("[INFO] Membangun Multi-band Data Cube (LST, SMAP, GPM, NDVI, MBSI)...")
    data_cube = build_data_cube(roi)
    
    # Verifikasi band yang berhasil digabungkan
    bands = data_cube.bandNames().getInfo()
    print(f"[SUCCESS] Data Cube berhasil dibuat dengan {len(bands)} parameter/band:")
    for i, band in enumerate(bands, 1):
        print(f"  {i}. {band}")
        
    print("[SUCCESS] Data komposit siap diekstrak/di-resample ke kisi Heksagonal Uber H3 Level 9.")
    print("=== TUGAS 6 SELESAI: harmonize_h3_spatial.py SIAP DIGUNAKAN ===")