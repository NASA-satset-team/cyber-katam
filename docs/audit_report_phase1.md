# CYBER-KATAM PROJECT AUDIT REPORT
## Phase 1: PROJECT AUDIT

---

## A. Ringkasan Kondisi Project Saat Ini

Project CYBER-KATAM adalah sistem rekomendasi rotasi tanaman berbasis data satelit dan analisis kondisi lahan. Saat ini, audit menemukan bahwa project masih dalam tahap awal dengan struktur yang belum sepenuhnya terorganisir untuk pengembangan AI Core.

** Kondisi utama:**
- Hanya satu modul pekerjaan tim Arya yang tersimpan di `aryas_workresult-20261111T135332Z-1-001\aryas_workresult`
- Tidak ada Python virtual environment yang tersetup
- Tidak ada file konfigurasi dependency (requirements.txt, pyproject.toml)
- Tidak ada folder AI Core yang terpisah
- Tidak ada folder data sample atau testing terpisah
- Tidak ada file JSON contract spesifikasi resmi v1.0 (hanya sample dari Arya)

** File utama yang ada:**
1. `pvrs_engine.py` - Modul Pre-Visual Root-Stress Score
2. `bf_ehsi_engine.py` - Modul Bare-Field Erosion & Heat Shock Index
3. `build_water_balance_banyumas.py` - Simulator Neraca Air Banyumas
4. `fiscal_actuarial.py` - Mesin Three-Tier Nitrogen Ledger & Fiscal-Actuarial Clearing
5. `water_balance_banyumas.xlsx` - Output Excel dari simulasi neraca air
6. `grid_cell_contract_sample.json` - Sample output kontrak data grid cell

---

## B. Struktur Folder Project yang Sudah Ada

```
C:\Users\azali\Downloads\cyberkatam\
└── aryas_workresult-20261111T135332Z-1-001\
    └── aryas_workresult\
        ├── pvrs_engine.py
        ├── bf_ehsi_engine.py
        ├── build_water_balance_banyumas.py
        ├── fiscal_actuarial.py
        ├── water_balance_banyumas.xlsx
        └── grid_cell_contract_sample.json
```

**Catatan:** Struktur folder ini hanya berisi pekerjaan Arya. Belum ada struktur standar project Python seperti:
- `src/` atau `ai_core/` folder untuk source code
- `tests/` folder untuk testing
- `data/` folder untuk dataset
- `config/` folder untuk konfigurasi
- `docs/` folder untuk dokumentasi

---

## C. Daftar File yang Relevan beserta Fungsinya

| File | Fungsi |
|------|--------|
| `pvrs_engine.py` | Menghitung Pre-Visual Root-Stress Score menggunakan data ECOSTRESS (ESI), SMAP (kelembapan), dan HLS (NDVI). Memproses optical lag detection dan 4-gate verification. Output: `PVRSOutputContract` dengan skor stres [0,1] dan advisory code. |
| `bf_ehsi_engine.py` | Menghitung Bare-Field Erosion & Heat Shock Index (BF-EHSI) menggunakan data HLS (MBSI/Bare Soil Index), ECOSTRESS (LST), dan GPM (hujan ekstrem). Menghintegralkan kumulatif risk degradasi D_i. Output: `BFEHSIOutputContract` dengan bare soil fraction, desiccation crack risk, erosion risk, cover crop mandate. |
| `build_water_balance_banyumas.py` | Simuler neraca air zona perakaran 0-100 cm harian untuk 3 skenario rotasi (Padi->Bera, Padi->Kedelai->Sorghum, Padi->Kacang Hijau). Menggunakan FAO-56 Penman-Monteith ETo. Output: Excel workbook dengan 2 sheets (Ringkasan & Simulasi Harian 90 hari). |
| `fiscal_actuarial.py` | Three-Tier Nitrogen Accounting, Fiscal-Actuarial Clearing Engine, dan Pareto Multi-Objective Optimizer. Menghitung penghematan subsidi urea APBN, reduksi risiko klaim AUTP, dan mitigasi hama WBC. Output: JSON contract payload `grid_cell_contract.json v1.0`. |
| `water_balance_banyumas.xlsx` | Output berkas Excel dari build_water_balance_banyumas.py berisi 2 sheet: (1) Ringkasan Eksekutif & Audit Fisika, (2) Tabel Simulasi Harian 90 Hari dengan 3 skenario rotasi. |
| `grid_cell_contract_sample.json` | Sample payload kontrak data grid cell versi 1.0 yang berisi indikator fisik, flag operasional, skenario rotasi, blok XAI decision, dan metrik fiskal. Berfungsi sebagai antarmuka konsumsi untuk Frontend React/Next.js dan WebGL Deck.gl. |

---

## D. Daftar Dependency Python yang Dibutuhkan

**Dependency yang teridentifikasi dari kode Arya:**

| Library | Digunakan di File | Catatan |
|---------|-------------------|---------|
| `numpy` | `pvrs_engine.py`, `bf_ehsi_engine.py`, `build_water_balance_banyumas.py` | Untuk operasi matematis array, statistik, dan perhitungan lipschitz |
| `openpyxl` | `build_water_balance_banyumas.py` | (Opsional) Untuk menulis file Excel. Dite-check pada runtime dengan `HAS_OPENPYXL` flag |
| `json` | Semua file Python | Stand library untuk parsing/serialisasi JSON |
| `math` | Semua file Python | Stand library untuk fungsi matematis |
| `dataclasses` | Semua file Python | Stand library untuk dataclass definitions |
| `typing` | `pvrs_engine.py`, `bf_ehsi_engine.py`, `fiscal_actuarial.py` | Type hints dengan Dict, List, Optional, Tuple |

**Dependency yang belum terinstall tetapi teridentifikasi sebagai perlu:**
- `openpyxl` - wajib untuk generate `water_balance_banyumas.xlsx`
- `fitz` (PyMuPDF) - kemungkinan untuk parsing PDF satelit metadata
- `geopandas`/`shapely` - kemungkinan untuk manipulasi geometri H3 index
- `pandas` - kemungkinan untuk manipulasi dataset tabular

---

## E. Temuan Ketidaksesuaian atau Hal yang Perlu Dikonfirmasi ke Anggota Tim

**1. Perbedaan nama BSI dan MBSI:**
- `bf_ehsi_engine.py`: Menggunakan nama **MBSI** (Modified Bare Soil Index) dalam fungsi `compute_mbsi()`. Rumus: `(rho_SWIR1 - rho_SWIR2 - rho_NIR) / (rho_SWIR1 + rho_SWIR2 + rho_NIR)`
- `grid_cell_contract_sample.json`: Menggunakan nama **HLS_BSI** dalam `physical_indicators`
- **Masalah**: Nama field berbeda. Perlu dikonfirmasi apakah HLS_BSI di JSON adalah MBSI yang sama atau indeks lain.

**2. Parameter dan threshold LST:**
- `pvrs_engine.py`: LST actual dibandingkan baseline `mu_lst_c` ± `sigma_lst_c`. Tolerance threshold `clip_limit=4.5` untuk z-score. Ambang kritis: `pvrs_score >= 0.70` = CRITICAL, `>= 0.45` = MODERATE.
- `bf_ehsi_engine.py`: LST critical temperature `lst_crit_c = 42.0` Celsius. Thermal term: `alpha_thermal * (LST / LST_crit)`. Ambang BF-EHSI: `>= 0.55` = exceeds erosion tolerance.
- **Masalah**: Perbedaan konvensi threshold antar modul. PVRS menggunakan z-score standar, BF-EHSI menggunakan scale relativ terhadap kritis 42°C. Perlu dikonfirmasi konsistensi dalam sistem rekomendasi.

**3. Struktur input-output indikator biofisika:**
- **PVRS Input**: `SatelliteObservationInput` dengan fields: h3_index, esi_actual, lst_actual_c, sm_root_actual, ndvi_actual, obs_age_hours, cloud_fraction, sensor_zenith_deg, in_situ_waterlogging
- **PVRS Output**: `PVRSOutputContract` dengan fields: h3_index, z_score_esi_deficit, z_score_lst_excess, z_score_sm_deficit, s_physio, s_visual, pvrs_score, stress_category, estimated_optical_lag_days, lst_anomaly_c, error_bound_value, tolerance_threshold, confidence_pct, gate_1_sensor_pass, gate_2_hydrology_pass, system_state, advisory_code
- **BF-EHSI Input**: `HLSReflectanceStep` dengan: rho_nir, rho_swir1, rho_swir2, lst_ecostress_c, r_gpm_max_mm_hr, sm_surface_m3m3
- **BF-EHSI Output**: `BFEHSIOutputContract` dengan: h3_index, landscape_zone, slope_deg, slope_pct, mbsi_latest, bare_soil_fraction_b, is_bare_field_exposed, desiccation_crack_depth_cm, preferential_leaching_risk, hydrological_connectivity_c, bf_ehsi_instantaneous, cumulative_risk_integral_di, estimated_sheet_erosion_ton_ha_yr, exceeds_erosion_tolerance, emergency_cover_crop_mandate
- **Fiscal-Aktuaria Input**: RotationCandidate dengan: scenario_id, crop_sequence, non_host_duration_days, water_demand_mm, n_fertilizer_displaced_kg_ha, soc_change_ton_ha, bph_burden_index, gross_revenue_idr_ha, production_cost_idr_ha, required_ksat_mm_day, predicted_erosion_di
- **Fiscal-Aktuaria Output**: Dict dengan ledger tiers, fiscal metrics, WBC metrics, dan contract payload
- **Masalah**: Setiap modul memiliki struktur dataclass sendiri. Perlu dibuat kontrak integrasi antar-modul standar.

**4. Format H3 Index:**
- Semua modul menggunakan format H3 Level 9: `"892e42426ffffff"` dan `"872e42426ffffff"`
- Resolusi Level 9 ≈ 10 ha per sel
- Consistent digunakan seluruh kode Arya
- **Catatan**: Tidak ditemukan validasi format H3 dalam kode, hanya digunakan sebagai string

**5. Nama field pada JSON contract:**
- `grid_cell_contract_sample.json` menggunakan field names seperti:
  - `contract_version: "1.0"`
  - `h3_index`
  - `h3_parent_res7: "872e42426ffffff"`
  - `physical_indicators` (nested dict)
  - `operational_flags` (nested dict)
  - `rotation_scenarios` (nested list)
  - `xai_decision_block` (nested dict)
  - `fiscal_metrics` (nested dict)
  - `system_state`
- **Perbandingan dengan spesifikasi v1.0**: File ini terlihat sebagai output dari fungsi `build_grid_cell_contract_json()` di `fiscal_actuarial.py`. Field names sesuai dengan yang diharapkan untuk kontrak v1.0, tetapi belum ada spesifikasi terpisah `grid_cell_contract.json` v1.0 untuk perbandingan. Sample ini kemungkinan merupakan implementasi v1.0.

---

## F. Rekomendasi Struktur Folder AI Core yang Paling Sesuai

Berdasarkan audit, rekomendasi struktur folder AI Core berikut:

```
cyberkatam_ai_core/
├── __init__.py
├── config.py              # Konfigurasi global: threshold, constants, H3 res levels
├── models/                # Dataclass definitions
│   ├── __init__.py
│   ├── pvrs_models.py     # SatelliteObservationInput, PVRSWeights, PVRSOutputContract
│   ├── bf_ehsi_models.py  # HLSReflectanceStep, BFEHSIConstants, BFEHSIOutputContract
│   └── fiscal_models.py   # ThreeTierNitrogenParams, FiscalActuarialConstants, RotationCandidate
├── engines/               # Core engine implementations
│   ├── __init__.py
│   ├── pvrs_engine.py     # PVRSEngine class
│   ├── bf_ehsi_engine.py  # BFEHSIEngine class
│   └── water_balance.py   # BanyumasWaterBalanceSimulator class
├── contracts/             # JSON contract schemas
│   ├── __init__.py
│   ├── grid_contract_v1.py  # Grid cell contract schema validasi
│   └── sample_data/       # Sample JSON untuk testing
├── data/                  # Dataset dan sample data
│   ├── banyumas/          # Data studi kasus Banyumas
│   ├── sample_h3_cells.json  # 1000 sel H3 Banyumas
│   └── satelite_metadata/  # Metadata ECOSTRESS/SMAP/HLS/GPM
├── testing/               # Test cases dan validation
│   ├── __init__.py
│   ├── test_pvrs.py
│   ├── test_bf_ehsi.py
│   └── test_water_balance.py
├── utils/                 # Utility functions
│   ├── __init__.py
│   ├── h3_utils.py        # H3 index validation/resampling
│   └── constants.py       # Konstanta fisika dan ambang batas
├── requirements.txt       # Python dependencies
└── pyproject.toml         # Project metadata & build config
```

**Alasan rekomendasi:**
1. Memisahkan `models` dari `engines` untuk contract-first development
2. Folder `contracts` berisi schema JSON yang konsisten antar-modul
3. Folder `data` terpisah dari code untuk memudahkan data versioning
4. Folder `testing` untuk regression testing antar-modul
5. `utils` berisi fungsi bantuan H3, validasi, dan konstanta yang digunakan oleh banyak modul

---

## G. Rekomendasi Langkah berikutnya untuk Menyiapkan Python Environment

**Langkah-langkah yang harus dilakukan (tanpa melanggar batasan audit):**

1. **Buat Python Virtual Environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

2. **Instal dependency yang teridentifikasi:**
   - `numpy` - untuk komputasi numerik
   - `openpyxl` - untuk operasi Excel (wajib untuk `build_water_balance_banyumas.py`)
   
   ```bash
   pip install numpy openpyxl
   ```

3. **Buat file `requirements.txt`:**
   ```
   numpy>=1.24.0
   openpyxl>=3.1.0
   ```

4. **Verifikasi kode Arya bisa dijalankan di environment baru:**
   - `python pvrs_engine.py` - harus menampilkan hasil evaluasi PVRS
   - `python bf_ehsi_engine.py` - harus menampilkan hasil evaluasi BF-EHSI
   - `python build_water_balance_banyumas.py` - harus generate `water_balance_banyumas.xlsx`
   - `python fiscal_actuarial.py` - harus generate contract payload JSON

5. **Lakukan konsolidasi field names:**
   - Pastikan konsistensi antara MBSI (di dalam code) dan HLS_BSI (di JSON contract)
   - Definisikan threshold LST yang konsisten antar PVRS dan BF-EHSI
   - Buat integrasi input-output antar-modul menggunakan dataclass yang shared

6. **Buat kontrak JSON v1.0 spesifikasi terpisah:**
   - Definisikan field names yang resmi untuk `grid_cell_contract.json`
   - Pastikan konsisten dengan output dari `fiscal_actuarial.py`
   - Dokumentasikan perbedaan dengan sample yang ada

7. **Integrasi antar-modul:**
   - Buat modul penghubung antar PVRS, BF-EHSI, dan Fiscal-Aktuaria
   - Validasi aliran data: output PVRS → input kontrak, output BF-EHSI → input rekomendasi rotasi
   - Implementasi protokol 4-gate verification yang terintegrasi

---

## Kesimpulan Audit

Project CYBER-KATAM memiliki fondasi yang kuat dari sisi ilmu (modul-modul Arya sudah memiliki formule fisika yang terdefinisi dengan baik), tetapi membutuhkan perorganisasian struktural untuk pengembangan AI Core. Ketemuannya utama antara-modul masih perlu dikonfirmasi, terutama:

1. **Naming convention** antara MBSI dan HLS_BSI
2. **Threshold konsisten** untuk LST dan BSI antar modul
3. **Standar kontrak JSON** yang konsisten dari input ke output antar-modul
4. **Python environment** yang sistematis dengan dependency terdaftar

Langkah selanjutnya harus fokus pada pembuatan Python environment, konsolidasi naming field, dan definisi kontrak JSON v1.0 yang formal sebelum pengembangan algoritma AI Core dimulai.