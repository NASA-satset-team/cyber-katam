"""
task7_agronomy_matrix.py
-----------------------------------
Skrip untuk mengompilasi parameter agronomi 3 skenario rotasi tanam
(spesifik wilayah Banyumas) dan menyimpannya ke dalam file JSON.
"""

import json
import os

def create_rotation_matrix():
    # Matriks agronomi untuk 3 skenario rotasi di Banyumas
    rotation_matrix = {
        "metadata": {
            "region": "Banyumas",
            "description": "Parameter agronomi untuk 3 skenario rotasi tanam",
            "version": "1.0"
        },
        "scenarios": {
            "skenario_1": {
                "name": "Padi - Bera",
                "description": "Rotasi tradisional dengan masa bera (kosong) setelah panen padi.",
                "crops": ["Padi", "Bera"],
                "parameters": {
                    "water_requirement_mm_per_season": 800,
                    "soil_moisture_threshold": 0.6,
                    "expected_yield_ton_per_ha": 6.5,
                    "drought_vulnerability": "High"
                }
            },
            "skenario_2": {
                "name": "Padi - Kedelai - Sorghum",
                "description": "Rotasi intensif tahan kering. Sorghum ditanam di musim kemarau.",
                "crops": ["Padi", "Kedelai", "Sorghum"],
                "parameters": {
                    "water_requirement_mm_per_season": 1200,
                    "soil_moisture_threshold": 0.4,
                    "expected_yield_ton_per_ha": 9.0, # Total kombinasi
                    "drought_vulnerability": "Low"
                }
            },
            "skenario_3": {
                "name": "Padi - Bawang - Legum",
                "description": "Rotasi nilai ekonomi tinggi dengan tanaman penutup tanah (legum).",
                "crops": ["Padi", "Bawang Merah", "Legum"],
                "parameters": {
                    "water_requirement_mm_per_season": 1050,
                    "soil_moisture_threshold": 0.5,
                    "expected_yield_ton_per_ha": 8.5, # Total kombinasi
                    "drought_vulnerability": "Medium"
                }
            }
        }
    }
    return rotation_matrix

def save_to_json(data, filename="crop_rotation_matrix.json"):
    # Menyimpan dictionary ke file JSON
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    
    print(f"[SUCCESS] Berkas konfigurasi berhasil dibuat: {filename}")
    print(f"[INFO] Lokasi file: {os.path.abspath(filename)}")

if __name__ == "__main__":
    print("=== PIPELINE TASK 7: MATRIKS AGRONOMI 3 SKENARIO ROTASI ===")
    
    print("[INFO] Mengompilasi parameter agronomi...")
    matrix_data = create_rotation_matrix()
    
    print("[INFO] Menyimpan ke format JSON...")
    save_to_json(matrix_data)
    
    print("=== TUGAS 7 SELESAI ===")