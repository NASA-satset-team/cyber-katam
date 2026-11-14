"""
nitrogen_dynamics.py
-----------------------------------
Skrip perhitungan Neraca Nitrogen & Brangkasan Legum.
Memodelkan fiksasi N oleh bintil akar kedelai (Bradyrhizobium)
serta fraksi N yang tersedia untuk musim tanam berikutnya.
"""

import json

def calculate_nitrogen_balance(soybean_yield_ton_ha=2.5, nodule_efficiency=0.75):
    """
    Menghitung neraca nitrogen berdasarkan hasil panen kedelai.
    """
    # 1. Estimasi Brangkasan (Residu Daun, Batang, Akar)
    # Asumsi umum: 1 ton biji kedelai menghasilkan ~1.5 ton brangkasan kering
    biomass_residue_ton_ha = soybean_yield_ton_ha * 1.5
    
    # 2. Total Nitrogen dalam Brangkasan
    # Asumsi: brangkasan legum mengandung sekitar 2.5% N dari total berat kering
    n_content_percent = 0.025
    total_n_in_residue_kg_ha = biomass_residue_ton_ha * 1000 * n_content_percent
    
    # 3. Fiksasi N oleh Bradyrhizobium (Efisiensi Bintil Akar)
    # Menghitung berapa banyak N yang benar-benar difiksasi dari udara (bukan serapan dari tanah)
    n_fixed_kg_ha = total_n_in_residue_kg_ha * nodule_efficiency
    
    # 4. Mineralisasi (Ketersediaan untuk musim berikutnya)
    # Fraksi N organik yang terurai dan bisa diserap tanaman rotasi berikutnya (misal Padi/Bawang)
    # Asumsi tingkat mineralisasi di tahun pertama adalah 40%
    mineralization_rate = 0.40
    n_available_next_season_kg_ha = n_fixed_kg_ha * mineralization_rate
    
    return {
        "metadata": {
            "model": "Bradyrhizobium N-Fixation Model",
            "region": "Banyumas",
            "description": "Neraca ketersediaan N untuk rotasi tanam pasca-kedelai"
        },
        "parameters": {
            "soybean_yield_ton_ha": soybean_yield_ton_ha,
            "biomass_residue_ton_ha": biomass_residue_ton_ha,
            "total_n_in_residue_kg_ha": total_n_in_residue_kg_ha,
            "n_fixed_by_bradyrhizobium_kg_ha": n_fixed_kg_ha,
            "n_available_next_season_kg_ha": n_available_next_season_kg_ha
        }
    }

if __name__ == "__main__":
    print("=== PIPELINE TASK 8: NERACA NITROGEN & BRANGKASAN LEGUM ===")
    
    # Simulasi perhitungan dengan hasil panen 2.5 ton/ha dan efisiensi bintil akar optimal (80%)
    print("[INFO] Memodelkan fiksasi N bintil akar kedelai (Bradyrhizobium)...")
    result = calculate_nitrogen_balance(soybean_yield_ton_ha=2.5, nodule_efficiency=0.80)
    
    params = result["parameters"]
    print(f" - Estimasi Panen Kedelai      : {params['soybean_yield_ton_ha']} Ton/Ha")
    print(f" - Estimasi Brangkasan (Residu): {params['biomass_residue_ton_ha']} Ton/Ha")
    print(f" - Total N dalam Brangkasan    : {params['total_n_in_residue_kg_ha']:.2f} Kg/Ha")
    print(f" - N Terfiksasi (Bintil Akar)  : {params['n_fixed_by_bradyrhizobium_kg_ha']:.2f} Kg/Ha")
    print(f" - N Tersedia Musim Berikutnya : {params['n_available_next_season_kg_ha']:.2f} Kg/Ha")
    
    # Simpan hasil untuk dibaca oleh pipeline model berikutnya
    output_file = "nitrogen_balance_output.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4)
        
    print(f"\n[SUCCESS] Hasil perhitungan neraca N disimpan di: {output_file}")
    print("=== TUGAS 8 SELESAI: nitrogen_dynamics.py SIAP DIGUNAKAN ===")