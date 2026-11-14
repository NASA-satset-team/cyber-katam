"""
task7_h3_final.py
-----------------------------------
Skrip untuk mengekstrak Data Cube GEE di area Banyumas 
dan mengunduhnya sebagai CSV menggunakan FeatureCollection
untuk menghindari batas memori (User memory limit exceeded).
"""

import ee
import pandas as pd
import sys

# Pengecekan library
try:
    import h3
except ImportError:
    print("[ERROR] Library 'h3' belum terpasang. Jalankan: pip install h3")
    sys.exit(1)

def initialize_gee(project_id="second-replica-490102-f2"):
    try:
        ee.Initialize(project=project_id)
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
    lst = ee.ImageCollection("MODIS/061/MOD11A1").filterBounds(roi).filterDate(start_date, end_date).select("LST_Day_1km").mean().rename("MODIS_LST")
    smap = ee.ImageCollection("NASA/SMAP/SPL4SMGP/008").filterBounds(roi).filterDate(start_date, end_date).select("sm_rootzone").mean().rename("SMAP_ROOTZONE")
    gpm = ee.ImageCollection("NASA/GPM_L3/IMERG_V07").filterBounds(roi).filterDate(start_date, end_date).select("precipitation").reduce(ee.Reducer.percentile([95])).rename("GPM_P95")
    
    s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(roi).filterDate(start_date, end_date).filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20)).mean()
    ndvi = s2.normalizedDifference(['B8', 'B4']).rename('NDVI')
    swir1 = s2.select('B11')
    swir2 = s2.select('B12')
    nir = s2.select('B8')
    mbsi = swir1.subtract(swir2).subtract(nir).divide(swir1.add(swir2).add(nir)).rename('MBSI')
    
    # Tambahkan layer longitude dan latitude ke dalam Data Cube
    lonlat = ee.Image.pixelLonLat()
    
    return ee.Image([lst, smap, gpm, ndvi, mbsi, lonlat]).clip(roi)

def get_h3_index(lat, lon, resolution=9):
    try:
        return h3.latlng_to_cell(lat, lon, resolution) # versi h3 baru
    except AttributeError:
        return h3.geo_to_h3(lat, lon, resolution)      # versi h3 lama

if __name__ == "__main__":
    print("=== PIPELINE TASK 7: EKSTRAKSI H3 & CSV (VERSI SUPER FINAL) ===")
    PROJECT_ID = "second-replica-490102-f2"
    
    print("[INFO] 1. Menginisialisasi GEE...")
    initialize_gee(project_id=PROJECT_ID)
    roi = get_banyumas_roi()
    data_cube = build_data_cube(roi)
    
    print("[INFO] 2. Mengubah citra satelit menjadi kumpulan titik (FeatureCollection)...")
    try:
        # PENGATURAN BARU: scale=2000 dan tileScale=16 agar tidak over-memory
        samples_fc = data_cube.sample(
            region=roi,
            scale=2000,           # Diperlebar sedikit agar jumlah titik tidak jutaan
            projection='EPSG:4326',
            geometries=False, 
            dropNulls=True,
            tileScale=16          # KUNCI: Memecah komputasi server Google agar tidak RAM Limit
        )
        
        print("[INFO] 3. Meminta server GEE membuatkan link file CSV...")
        url = samples_fc.getDownloadURL(
            filetype='csv',
            selectors=['MODIS_LST', 'SMAP_ROOTZONE', 'GPM_P95', 'NDVI', 'MBSI', 'latitude', 'longitude']
        )
        print(f"[INFO] 4. Link CSV berhasil didapatkan! Sedang mengunduh via Pandas...")
        
        # Pandas akan otomatis membaca CSV langsung dari URL Google Earth Engine
        df = pd.read_csv(url)
        print(f"[SUCCESS] Berhasil mengunduh {len(df)} titik sampel ruang.")
        
        print("[INFO] 5. Mengonversi koordinat ke H3 Index (Hexagon Uber)...")
        if not df.empty:
            df['h3_index'] = df.apply(lambda row: get_h3_index(row['latitude'], row['longitude'], 9), axis=1)
            
            # Susun dan rapikan kolom sebelum disimpan
            kolom = ['h3_index', 'latitude', 'longitude', 'MODIS_LST', 'SMAP_ROOTZONE', 'GPM_P95', 'NDVI', 'MBSI']
            df = df[[k for k in kolom if k in df.columns]]
            
            # Hapus duplikat h3_index jika ada titik yang jatuh di hexagon yang sama
            df = df.drop_duplicates(subset=['h3_index'])
            
            output_csv = "banyumas_h3_dataset.csv"
            df.to_csv(output_csv, index=False)
            print(f"[SUCCESS] Mantap! File dataset berhasil disimpan: {output_csv} ({len(df)} heksagon unik)")
            print("=== TUGAS 7 SELESAI: DATASET SIAP UNTUK MACHINE LEARNING ===")
            
    except Exception as e:
        print(f"[ERROR] Ekstraksi gagal: {e}")