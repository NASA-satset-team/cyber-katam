"""
task9_climatology_baseline.py
-----------------------------------
Skrip untuk menghitung nilai rata-rata (μ) dan simpangan baku (σ)
historis 10-harian (dekad) anomali iklim Banyumas periode 2021-2026.
Output: climatology_baseline_banyumas.parquet
"""

import pandas as pd
import numpy as np
import os
import sys

# Pengecekan library untuk ekspor file parquet
try:
    import pyarrow
except ImportError:
    print("[ERROR] Library 'pyarrow' belum terpasang. Jalankan: pip install pyarrow")
    sys.exit(1)

def get_dekad(day):
    """
    Fungsi untuk menentukan dekad (periode 10 harian) dalam satu bulan.
    Dekad 1: Tanggal 1-10
    Dekad 2: Tanggal 11-20
    Dekad 3: Tanggal 21 - Akhir bulan
    """
    if day <= 10:
        return 1
    elif day <= 20:
        return 2
    else:
        return 3

def generate_historical_climate_data(start_year=2021, end_year=2026):
    """
    Mensimulasikan data historis iklim harian (Suhu, Curah Hujan, Kelembapan Tanah).
    Pada implementasi nyata, data ini berasal dari query GEE/CSV sebelumnya.
    """
    dates = pd.date_range(start=f'{start_year}-01-01', end=f'{end_year}-12-31', freq='D')
    
    # Membuat variasi musiman buatan (menggunakan gelombang sinus + noise acak)
    day_of_year = dates.dayofyear
    seasonality = np.sin(2 * np.pi * day_of_year / 365.25)
    
    data = {
        'date': dates,
        'LST_Celsius': 28 + (seasonality * 2) + np.random.normal(0, 1.5, len(dates)), # Suhu
        'Precipitation_mm': np.maximum(0, 10 - (seasonality * 10) + np.random.normal(0, 5, len(dates))), # Hujan
        'Soil_Moisture': 0.3 - (seasonality * 0.1) + np.random.normal(0, 0.05, len(dates)) # Kelembapan
    }
    
    return pd.DataFrame(data)

def calculate_climatology_baseline(df):
    """
    Menghitung mu (mean) dan sigma (std) berdasarkan bulan dan dekad.
    """
    # Ekstrak bulan dan dekad
    df['month'] = df['date'].dt.month
    df['day'] = df['date'].dt.day
    df['dekad'] = df['day'].apply(get_dekad)
    
    # Kelompokkan berdasarkan Bulan dan Dekad
    grouped = df.groupby(['month', 'dekad'])
    
    # Hitung rata-rata (mu) dan simpangan baku (sigma)
    baseline = grouped.agg({
        'LST_Celsius': ['mean', 'std'],
        'Precipitation_mm': ['mean', 'std'],
        'Soil_Moisture': ['mean', 'std']
    }).reset_index()
    
    # Meratakan MultiIndex kolom menjadi satu baris penamaan kolom
    # Contoh: 'LST_Celsius_mean' menjadi 'LST_mu'
    new_cols = ['month', 'dekad']
    for col in baseline.columns[2:]:
        var_name = col[0].split('_')[0] # Ambil kata pertama (LST, Precipitation, Soil)
        stat_name = 'mu' if col[1] == 'mean' else 'sigma'
        new_cols.append(f"{var_name}_{stat_name}")
        
    baseline.columns = new_cols
    return baseline

if __name__ == "__main__":
    print("=== PIPELINE TASK 9: KALIBRASI GARIS DASAR HISTORIS ===")
    
    print("[INFO] Memuat data time-series historis Banyumas (2021-2026)...")
    df_historical = generate_historical_climate_data(2021, 2026)
    
    print("[INFO] Menghitung nilai mu (\u03bc) dan sigma (\u03c3) per dekad (10 harian)...")
    df_baseline = calculate_climatology_baseline(df_historical)
    
    # Menampilkan 5 baris pertama sebagai cuplikan
    print("\n[CUPLIKAN DATA BASELINE (Bulan 1, Dekad 1-3)]")
    print(df_baseline.head())
    print("-" * 50)
    
    # Menyimpan ke format Parquet
    output_filename = "climatology_baseline_banyumas.parquet"
    print(f"[INFO] Menyimpan dataset kalibrasi ke format Parquet...")
    
    # Menyimpan dataframe menjadi parquet (menggunakan engine pyarrow)
    df_baseline.to_parquet(output_filename, index=False)
    
    print(f"[SUCCESS] File berhasil disimpan: {os.path.abspath(output_filename)}")
    print("=== TUGAS 9 SELESAI ===")