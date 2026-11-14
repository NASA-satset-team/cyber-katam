"""
task12_smoke_test_deconstruction.py
-----------------------------------
Skrip untuk melakukan Smoke Test (uji sambung data MVP), 
memastikan tidak ada nilai null pada dataset utama, 
dan mengisolasi skrip ke dalam direktori clean_data_modules/.
"""

import os
import json
import shutil

def run_smoke_test(geojson_path):
    """
    Melakukan validasi pada dataset GeoJSON untuk memastikan kelengkapan struktur 
    dan ketiadaan nilai null pada properti penting.
    """
    print(f"[INFO] Menjalankan Smoke Test pada file: {geojson_path}")
    
    if not os.path.exists(geojson_path):
        print(f"[WARNING] File {geojson_path} tidak ditemukan. Pastikan Task 10 sudah dijalankan.")
        return False

    with open(geojson_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if "features" not in data:
        print("[FAIL] Format GeoJSON tidak valid (tidak ada 'features').")
        return False

    null_count = 0
    for i, feature in enumerate(data["features"]):
        properties = feature.get("properties", {})
        
        # Mengecek apakah ada nilai null (None) di dalam properties
        for key, value in properties.items():
            if value is None:
                print(f"[FAIL] Ditemukan nilai NULL pada fitur ke-{i}, properti: {key}")
                null_count += 1
                
    if null_count == 0:
        print("[PASS] Smoke Test Berhasil: Tidak ada nilai null terdeteksi pada dataset.")
        return True
    else:
        print(f"[FAIL] Smoke Test Gagal: Terdapat {null_count} nilai null.")
        return False

def isolate_clean_modules():
    """
    Membuat repositori bersih dan memindahkan/mengcopy skrip-skrip inti.
    """
    target_dir = "clean_data_modules"
    print(f"\n[INFO] Mengisolasi skrip fungsi ke repositori bersih: {target_dir}/")
    
    # Membuat folder jika belum ada
    os.makedirs(target_dir, exist_ok=True)
    
    # Daftar skrip yang akan dipindahkan/dicopy (berdasarkan task sebelumnya)
    scripts_to_isolate = [
        "task7_agronomy_matrix.py",
        "nitrogen_dynamics.py",
        "task9_climatology_baseline.py",
        "task10_precomputed_geojson.py",
        "task11_benchmark.py",
        "task12_smoke_test_deconstruction.py"
    ]
    
    success_count = 0
    for script in scripts_to_isolate:
        if os.path.exists(script):
            # Menggunakan copy2 untuk mempertahankan metadata file
            shutil.copy2(script, os.path.join(target_dir, script))
            print(f" -> Terisolasi: {script}")
            success_count += 1
        else:
            print(f" -> [SKIP] File tidak ditemukan: {script}")
            
    print(f"[SUCCESS] {success_count} skrip berhasil diisolasi ke {target_dir}/.")

if __name__ == "__main__":
    print("=== PIPELINE TASK: UJI SAMBUNG DATA & DEKONSTRUKSI ===")
    
    # 1. Jalankan Smoke Test pada dataset H3 yang dihasilkan di Task 10
    dataset_file = "banyumas_h3_precomputed.geojson"
    test_passed = run_smoke_test(dataset_file)
    
    # 2. Lakukan Dekonstruksi / Isolasi Skrip
    if test_passed:
        isolate_clean_modules()
        print("\n=== SELAMAT! SELURUH PIPELINE DATA TELAH SELESAI & SIAP UNTUK MVP ===")
    else:
        print("\n[ERROR] Smoke test gagal. Harap perbaiki data null sebelum melakukan dekonstruksi modul.")