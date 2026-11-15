# Agronomic Data Foundation Audit — Crop Parameter Registry

**Status:** audit and design only. No source code, formula, coefficient, engine, or data file was modified. This report is a new file; no commit, push, merge, or branch switch was performed.

**Repository context:** branch `feature/rifaldi-ui`, HEAD `9fc3702`. Audit date: 2026-11-15.

**Target crops:**

1. Padi — Inpari 32
2. Kedelai — Anjasmoro
3. Kacang hijau — Vima-1
4. Sorgum — variety not specified

---

## 1. Executive Summary

The repository does **not** yet contain a crop parameter registry for the four target crops.

It contains related fragments:

- A hand-written three-rotation matrix in `external/ariefs_workresult/crop_rotation_matrix.json`.
- A fixed 90-day water-balance simulator in `external/aryas_workresult/build_water_balance_banyumas.py`.
- A soybean/three-tier nitrogen model in `external/aryas_workresult/fiscal_actuarial.py` and `external/ariefs_workresult/nitrogen_dynamics.py`.
- Scenario-level `RotationCandidate` fields and a Pareto solver in `fiscal_actuarial.py`.
- Static UI rotation labels in `web-app/src/model.js`.
- Rotation-scenario fields in `contracts/grid_cell_contract.schema.json`.

None of these files contains per-cultivar parameters for **Inpari 32, Anjasmoro, Vima-1, or Sorghum**. Inpari 32 does not appear in the repository at all. The other three names appear only as scenario labels or comments.

The audit did find usable **external** sources for:

- Inpari 32 identity, duration, average yield, potential yield, and WBC reaction.
- Anjasmoro identity, duration, and yield range.
- Vima-1 identity, duration, average yield, and potential yield.
- FAO-56 generic crop coefficients, growth-stage lengths, root-depth ranges, and depletion fractions for rice, soybean, green gram/cowpea, and sorghum.

However:

- FAO-56 values are **generic crop values**, not measurements for Inpari 32, Anjasmoro, Vima-1, or a specific sorghum variety.
- The variety descriptions give national/official values, not Banyumas field validation.
- No verified local Banyumas crop parameters, KATAM Banyumas planting calendar, crop-specific N requirement, pH/texture/drainage suitability, crop prices/costs, or pest host-status matrix were found.
- Sorgum has no specified variety, so most variety-specific parameters remain `null`.

**Readiness:**

- **Schema and loader:** can start now.
- **Registry content:** partially seedable with official variety identity/duration/yield and FAO generic water/root parameters; not complete.
- **Agronomy modules:** not ready to run on local Banyumas data until missing parameters are sourced.
- **Minimum viable registry:** use explicit `null` values and evidence statuses; do not silently substitute generic or synthetic values.

---

## 2. Repository Audit

### 2.1 What exists

| Item | File / function | Status | Evidence / limitation |
|---|---|---|---|
| Crop rotation matrix | `external/ariefs_workresult/crop_rotation_matrix.json`; `task7_agronomy_matrix.py::create_rotation_matrix` lines 11–55 | **Assumption-based; scenario-level** | Three scenarios: Padi–Bera, Padi–Kedelai–Sorghum, Padi–Bawang–Legum. Values: water 800/1200/1050 mm/season; expected yield 6.5/9.0/8.5 t/ha; soil moisture threshold 0.6/0.4/0.5. No citations; no economics/Ksat/erosion/non-host fields; not used by an engine. |
| Water balance | `external/aryas_workresult/build_water_balance_banyumas.py` | **Implemented as fixed simulator; synthetic** | 90 daily rows; Kc scenario A/B/C hardcoded at lines 104–122; root depth 1000 mm at line 28; Kc/ETc formula at 129–132; weather from `np.random` + sine at 74–100. No general crop water requirement. |
| Nitrogen dynamics | `external/ariefs_workresult/nitrogen_dynamics.py`; `nitrogen_balance_output.json` | **Assumption-based; soybean only** | `calculate_nitrogen_balance()` lines 11–47: 2.5 t/ha yield, 1.5 residue ratio, 2.5% N, 75–80% fixation, 40% mineralization. Not used by engine; conflicts with Arya’s N ledger. |
| Arya N/fiscal/WBC | `external/aryas_workresult/fiscal_actuarial.py` | **Implemented formulas; assumptions** | `ThreeTierNitrogenParams` lines 16–37; WBC survival lines 115–138; fiscal/AUTP lines 140–195; Pareto lines 197–255; contract builder lines 257–327. No crop registry. |
| Rotation candidate | `fiscal_actuarial.py::RotationCandidate` lines 51–68 | **Data structure only** | Fields include water demand, N displacement, SOC, BPH, revenue, cost, Ksat, erosion, non-host duration. Values in `__main__` are hardcoded demo values. |
| UI rotation comparison | `web-app/src/model.js::strategies` lines 1–32 | **Static UI only** | A: Padi–Bera; B: Padi–Kedelai Anjasmoro; C: Padi–Kacang Hijau; scores `waterScore`, `soilScore`, `pestScore` are arbitrary UI values. |
| Contract rotation fields | `contracts/grid_cell_contract.schema.json:129–181` | **Partial schema only** | Fields: `id`, `crop_sequence`, `water_demand_mm`, `n_fertilizer_displaced_kg`, `soc_change_ton`, `bph_risk_score`, `net_margin_idr`. No crop registry. |
| Crop suitability logic | — | **Not implemented** | Search found no pH, texture, drainage, slope, salinity, or suitability evaluator. |
| Planting calendar logic | — | **Not implemented** | Search found no planting-window, harvest-window, growing-period, or calendar evaluator. |
| Crop parameter registry | — | **Not implemented** | No crop parameter JSON/schema/loader exists. |
| Inpari 32 data | — | **Not found** | No repository record for Inpari 32. |
| Anjasmoro/Vima/Sorghum parameters | Scenario labels only | **Not found as parameters** | Names appear in `fiscal_actuarial.py:350, 363`, `build_water_balance_banyumas.py:48–55`, `crop_rotation_matrix.json`, and UI labels. No per-cultivar parameter records. |
| Local Banyumas parameter data | — | **Not found** | No Banyumas-specific crop parameters; only external statistics/portal links. |
| KATAM Banyumas data | — | **Not found** | No KATAM export, calendar, or recommendation table in the repository. |

### 2.2 Key repository limitations

1. **Scenario-level values are not crop parameters.**  
   `crop_rotation_matrix.json` stores one combined expected yield and one water requirement per rotation scenario, not per crop. For example, `skenario_2` combines Padi, Kedelai, and Sorghum into 9.0 t/ha and 1200 mm/season. This cannot be decomposed into crop-level values without new data.

2. **Water balance Kc is scenario-specific, not crop-specific.**  
   `build_water_balance_banyumas.py` has one Kc sequence for scenario B (`Padi → Kedelai Anjasmoro → Sorghum`) and one for scenario C (`Padi → Kacang Hijau`). There is no separate sorghum Kc curve, no Vima-1 curve, no Inpari 32 curve, and no Anjasmoro-specific curve.

3. **The root depth is shared.**  
   The simulator uses a single `root_depth_mm = 1000.0` for all scenarios. It is not per crop.

4. **No local validation.**  
   The repository contains no Banyumas field trial, no local crop coefficients, no local yield trial, and no official Banyumas recommendation table.

5. **No crop-level N requirement.**  
   Arya’s N ledger is soybean-oriented and assumption-based; Arief’s model is also soybean-only and uses different coefficients. Neither provides N requirements for Inpari 32, Vima-1, or Sorghum. `docs/project_file_inventory.md:194` (KI-10) records the conflict.

6. **No crop suitability or calendar model.**  
   The codebase has land-cover classes (`src/models/land_cover.py`) but not crop suitability. It has water-balance phase day ranges but not a planting calendar.

7. **No crop registry contract.**  
   `contracts/grid_cell_contract.schema.json` governs rotation scenarios and physical indicators, not crop identities or parameters.

---

## 3. Source and Evidence Registry

Source IDs below are referenced in the parameter matrix. Access date for web sources: **2026-11-15**.

| ID | Type | Source | URL | Location | Evidence status | Notes |
|---|---|---|---|---|---|---|
| S01a | Official extension article (Kementan/BRMP Babel) | “Pengembangan Varietas Padi di Babel melalui Penerapan SNI 6233-2015: Benih Padi Inbrida” | https://babel.brmp.pertanian.go.id/berita/pengembangan-varietas-padi-di-babel-melalui-penerapan-sni6233-2015-benih-padi-inbrida | Section 5, “Varietas Inpari 32 HDB” | **Official national extension source** | Gives 120 days, average 6.3 t/ha, WBC reaction. Not a Banyumas trial. |
| S01b | Official extension article (Kementan/BRMP Riau) | “Dorong Percepatan Tanam, BRMP Riau Salurkan Benih Padi…” | https://riau.brmp.pertanian.go.id/berita/dorong-percepatan-tanam-brmp-riau-salurkan-benih-padi-ke-kabupaten-indragiri-hilir | Article body, paragraph on Inpari 32 HDB | **Official national extension source** | Gives potential yield 8.42 t/ha GKG, HDB resistance, lowland–600 m adaptation. Not a Banyumas trial. |
| S02 | Official repository item (Kementan) | “Vima 1, 2 dan 3” | https://repository.pertanian.go.id/items/1756382c-6ec4-4a9b-94a6-a33a48a5e6f6 | VIMA 1 entry | **Official repository description (search excerpt)** | Gives potential 1.76 t/ha, average 1.38 t/ha, 57 days, 6.3 g/100 seeds. Page fetch had a transport error; values were read from the repository search excerpt. |
| S03 | Official variety description PDF (Kementan/BRMP) | “Varietas Unggul Kedelai 1912–2022” | https://brmp.pertanian.go.id/informasi-publik/download/varietas/varietas-unggul-kedelai-1912-2022 | ANJASMORO entry, p. 57 | **Official description (PDF excerpt)** | Gives 2.03–2.25 t/ha, 82.5–92.5 days, SK 537/Kpts/TP.240/10/2001. PDF is not machine-text-extractable in this environment; values cross-checked with S03b. |
| S03b | University repository reproduction of official description | “Lampiran 1. Deskripsi Kedelai Varietas Anjasmoro” | https://repository.ub.ac.id/129899/10/Lampiran_1._Deskripsi_Kedelai_var._Anjasmoro.pdf | Lampiran 1 | **Reproduction of official description** | Cross-check for Anjasmoro: 2.25–2.03 t/ha, 82.5–92.5 days, SK 537/Kpts/TP.240/10/2001. |
| S04 | FAO-56, Chapter 6, Table 12 | “Crop evapotranspiration — Guidelines for computing crop water requirements” | https://www.fao.org/4/x0490e/x0490e0b.htm | Table 12: Rice; Soybeans; Green Gram and Cowpeas; Sorghum (grain) | **Authoritative generic reference** | Kc ini/mid/end for subhumid climate, RHmin ≈45%, u2 ≈2 m/s. Generic, not cultivar-specific. |
| S05 | FAO-56, Chapter 6, Table 11 | same | https://www.fao.org/4/x0490e/x0490e0b.htm | Table 11: Rice; Soybeans (tropics); Green gram/cowpeas; Sorghum | **Authoritative generic reference** | Stage lengths are general guides; FAO explicitly warns they are approximate and should be locally verified. |
| S06 | FAO-56, Chapter 8, Table 22 | “ETc under soil water stress conditions” | https://www.fao.org/4/x0490e/x0490e0e.htm | Table 22: Rice; Soybeans; Green Gram and Cowpeas; Sorghum (grain) | **Authoritative generic reference** | Maximum effective rooting depth and depletion fraction `p`; ranges, not cultivar/local values. |
| S06b | FAO-56, Chapter 8, Table 23 | same | https://www.fao.org/4/x0490e/x0490e0e.htm | Table 23: Rice; Soybeans; Sorghum; Cowpea | **Authoritative generic reference** | Salinity threshold `ECe` and slope; “Cowpea” is not Vima-1; use only as generic/unsuitable proxy. |
| S07 | Official system description (Kementan/BRMP) | “KATAM Terpadu-SC” | https://tanamanindustri.brmp.pertanian.go.id/layanan/pengaduan-layanan-elektronik-dan-perpustakaan/katam-terpadu-sc | KATAM Terpadu-SC description | **Official system description** | KATAM provides planting time, fertilizer, variety, and climate recommendations for paddy, maize, soybean. No Banyumas-specific export/table is available in the repository. |
| S08 | Official statistics portal | BPS Kabupaten Banyumas — “Jumlah Produksi Tanaman Pangan” | https://banyumaskab.bps.go.id/id/statistics-table/2/NDQjMg==/jumlah-pr | Statistics table portal | **Official local statistics portal** | Provides aggregate production tables, not crop parameters. No local Kc/yield-trial/N/suitability table found. |
| S09 | Taxonomic database (standard nomenclature) | POWO / ITIS / USDA PLANTS | https://powo.science.kew.org/ ; https://www.itis.gov/ | Taxonomic query | **Standard nomenclature; exact record pending** | Scientific names below are standard taxonomy, not measured variety parameters. Exact database record/citation should be recorded before production. |
| S10 | Repository assumptions / synthetic models | `crop_rotation_matrix.json`, `build_water_balance_banyumas.py`, `fiscal_actuarial.py`, `nitrogen_dynamics.py` | local files | See file/line references | **Project assumption / synthetic / hardcoded demo** | Must not be presented as local crop parameters. |

### 3.1 Evidence-status vocabulary

| Status | Meaning |
|---|---|
| `verified_official_national` | Official Kementan/BRMP variety or extension source; national/general, not Banyumas field validation. |
| `verified_generic_not_cultivar` | Authoritative generic source (FAO-56); not a measurement of the named cultivar. |
| `reproduced_official` | Official description reproduced in a secondary repository; cross-checked but not primary extraction. |
| `official_system_description` | Official system description; no extracted local data. |
| `standard_nomenclature` | Standard taxonomic name; exact database record/citation pending. |
| `assumption_based` | Repository value with no citation. |
| `synthetic` | Generated by a simulator/random process. |
| `hardcoded_demo` | Fixed demo value. |
| `not_found` | No source/value found. |
| `requires_source` | Parameter is needed; no value/source yet. |
| `requires_local_validation` | National/generic value exists; Banyumas validation is missing. |

---

## 4. Agronomic Parameter Matrix

**Rules used below:**

- `null` means **no verified value found**. It does not mean zero.
- FAO-56 Kc/root/stage values are **generic crop values**, not Inpari 32/Anjasmoro/Vima-1/variety-specific measurements.
- Official variety values are national descriptions, not Banyumas field trials.
- No synthetic or repo assumption value is copied into this matrix as a verified crop parameter.
- Sorgum has no specified variety; variety-specific values are `null`.

### 4.1 Padi — Inpari 32 HDB

| Parameter | Value | Unit | Source | Location | Cultivar | Evidence status | Notes / limitations |
|---|---|---|---|---|---|---|---|
| Scientific name | Oryza sativa L. | taxonomic name | S09 | taxonomic query | Inpari 32 HDB | `standard_nomenclature` | Standard name; exact taxonomic record pending. |
| Variety | Inpari 32 HDB | name | S01a | Section 5 | Inpari 32 HDB | `verified_official_national` | Official extension source; not a Banyumas trial. |
| Growing duration | 120 | day | S01a | Section 5 | Inpari 32 HDB | `verified_official_national` | National description. |
| Growth phases (cultivar-specific) | null | day | — | — | Inpari 32 HDB | `not_found` | No phase split for Inpari 32 found. |
| Growth phases (FAO generic rice) | 30 / 30 / 60 / 30 = 150 | day | S05 | Table 11, Rice | FAO generic rice | `verified_generic_not_cultivar` | Not applicable as Inpari 32 phase split; 150 ≠ 120 days. |
| Kc initial / mid / end | 1.05 / 1.20 / 0.90–0.60 | fraction | S04 | Table 12, Rice | FAO generic rice | `verified_generic_not_cultivar` | Generic, subhumid reference; adjust locally; not Inpari 32-specific. |
| Root depth | 0.5–1.0 | m | S06 | Table 22, Rice | FAO generic rice | `verified_generic_not_cultivar` | Range; local soil/rooting depth unverified. |
| Depletion fraction `p` | 0.20 | fraction | S06 | Table 22, Rice | FAO generic rice | `verified_generic_not_cultivar` | Rice paddy-specific note in FAO; local validation needed. |
| Water requirement | null | mm/season | S04 | ETc = Kc × ETo | Inpari 32 HDB | `requires_local_validation` | No fixed seasonal value; depends on local ETo/rain/irrigation. Repo 800 mm scenario is not a verified parameter. |
| Nitrogen requirement | null | kg N/ha | — | — | Inpari 32 HDB | `requires_source` | No verified N recommendation found; Arya/Arief N constants are not Inpari 32 requirements. |
| Soil pH / texture / drainage / slope suitability | null | pH / class / degree | — | — | Inpari 32 HDB | `requires_source` | No crop suitability table found. |
| Salinity threshold `ECe` | 3.0 | dS/m | S06b | Table 23, Rice | FAO generic rice | `verified_generic_not_cultivar` | Generic salinity threshold; not local/cultivar-specific. |
| Average yield | 6.3 | t/ha GKG | S01a | Section 5 | Inpari 32 HDB | `verified_official_national` | National average description; not Banyumas. |
| Potential yield | 8.42 | t/ha GKG | S01b | Article body | Inpari 32 HDB | `verified_official_national` | National potential; not Banyumas. |
| Pest host status | WBC host; “agak rentan” biotipe 1, 2, 3 | status | S01a | Section 5 | Inpari 32 HDB | `verified_official_national` | Pest reaction, not a full host-status matrix; local WBC pressure unknown. |

### 4.2 Kedelai — Anjasmoro

| Parameter | Value | Unit | Source | Location | Cultivar | Evidence status | Notes / limitations |
|---|---|---|---|---|---|---|---|
| Scientific name | Glycine max (L.) Merr. | taxonomic name | S09 | taxonomic query | Anjasmoro | `standard_nomenclature` | Standard name; exact taxonomic record pending. |
| Variety | Anjasmoro | name | S03 | ANJASMORO entry, p. 57 | Anjasmoro | `verified_official_national` | Official variety description; S03b cross-check. |
| Growing duration | 82.5–92.5 | day | S03 | ANJASMORO entry | Anjasmoro | `verified_official_national` | S03b gives 82.5–92.5; other summaries use 82–92. |
| Growth phases (cultivar-specific) | null | day | — | — | Anjasmoro | `not_found` | No phase split for Anjasmoro found. |
| Growth phases (FAO generic soybean) | 15 / 15 / 40 / 15 = 85 | day | S05 | Table 11, Soybeans (Tropics) | FAO generic soybean | `verified_generic_not_cultivar` | Close to Anjasmoro duration but not a cultivar measurement. |
| Kc initial / mid / end | 0.40 / 1.15 / 0.50 | fraction | S04 | Table 12, Soybeans | FAO generic soybean | `verified_generic_not_cultivar` | Initial value inherited from legume group; not Anjasmoro-specific. |
| Root depth | 0.6–1.3 | m | S06 | Table 22, Soybeans | FAO generic soybean | `verified_generic_not_cultivar` | Range; local soil unverified. |
| Depletion fraction `p` | 0.50 | fraction | S06 | Table 22, Soybeans | FAO generic soybean | `verified_generic_not_cultivar` | Generic. |
| Water requirement | null | mm/season | S04 | ETc = Kc × ETo | Anjasmoro | `requires_local_validation` | No fixed seasonal value; local ETo/rain missing. |
| Nitrogen requirement | null | kg N/ha | — | — | Anjasmoro | `requires_source` | No verified N recommendation; N-fixation potential is not a fertilizer requirement. |
| Soil pH / texture / drainage / slope suitability | null | pH / class / degree | — | — | Anjasmoro | `requires_source` | No crop suitability table found. |
| Salinity threshold `ECe` | 5.0 | dS/m | S06b | Table 23, Soybeans | FAO generic soybean | `verified_generic_not_cultivar` | Generic salinity threshold; not local/cultivar-specific. |
| Yield potential | 2.03–2.25 | t/ha | S03 | ANJASMORO entry | Anjasmoro | `verified_official_national` | Official “daya hasil”; not a Banyumas mean. |
| Pest host status | null | status | — | — | Anjasmoro | `requires_source` | No WBC host-status source found for this variety. |

### 4.3 Kacang hijau — Vima-1

| Parameter | Value | Unit | Source | Location | Cultivar | Evidence status | Notes / limitations |
|---|---|---|---|---|---|---|---|
| Scientific name | Vigna radiata (L.) R. Wilczek | taxonomic name | S09 | taxonomic query | Vima-1 | `standard_nomenclature` | Standard name; exact taxonomic record pending. |
| Variety | Vima-1 | name | S02 | VIMA 1 entry | Vima-1 | `verified_official_national` | Official repository description. |
| Growing duration | 57 | day | S02 | VIMA 1 entry | Vima-1 | `verified_official_national` | Official repository description. |
| Growth phases (cultivar-specific) | null | day | — | — | Vima-1 | `not_found` | No phase split for Vima-1 found. |
| Growth phases (FAO generic green gram) | 20 / 30 / 30 / 20 = 110 | day | S05 | Table 11, Green gram, cowpeas | FAO generic green gram | `verified_generic_not_cultivar` | Not applicable to 57-day Vima-1; do not use as Vima-1 phase split. |
| Kc initial / mid / end | 0.40 / 1.05 / 0.60–0.35 | fraction | S04 | Table 12, Green Gram and Cowpeas | FAO generic green gram | `verified_generic_not_cultivar` | Generic; initial value inherited from legume group. |
| Root depth | 0.6–1.0 | m | S06 | Table 22, Green Gram and Cowpeas | FAO generic green gram | `verified_generic_not_cultivar` | Generic range; not Vima-1. |
| Depletion fraction `p` | 0.45 | fraction | S06 | Table 22, Green Gram and Cowpeas | FAO generic green gram | `verified_generic_not_cultivar` | Generic. |
| Water requirement | null | mm/season | S04 | ETc = Kc × ETo | Vima-1 | `requires_local_validation` | No fixed seasonal value; local ETo/rain missing. |
| Nitrogen requirement | null | kg N/ha | — | — | Vima-1 | `requires_source` | No verified N recommendation; legume N fixation is not the same as N requirement. |
| Soil pH / texture / drainage / slope suitability | null | pH / class / degree | — | — | Vima-1 | `requires_source` | No crop suitability table found. |
| Salinity threshold `ECe` | null | dS/m | S06b | Table 23 has cowpea, not Vima-1 | Vima-1 | `requires_source` | Do not use cowpea 4.9 dS/m as Vima-1 without approval. |
| Average yield | 1.38 | t/ha | S02 | VIMA 1 entry | Vima-1 | `verified_official_national` | Official average. |
| Potential yield | 1.76 | t/ha | S02 | VIMA 1 entry | Vima-1 | `verified_official_national` | Official potential. |
| Pest host status | null | status | — | — | Vima-1 | `requires_source` | No WBC host-status source found. |

### 4.4 Sorgum — variety unspecified

| Parameter | Value | Unit | Source | Location | Cultivar | Evidence status | Notes / limitations |
|---|---|---|---|---|---|---|---|
| Scientific name | Sorghum bicolor (L.) Moench | taxonomic name | S09 | taxonomic query | unspecified | `standard_nomenclature` | Standard name; exact taxonomic record pending. |
| Variety | null | name | — | — | unspecified | `requires_source` | User target says “Sorgum” without a variety. No variety-specific record. |
| Growing duration | null | day | — | — | unspecified | `requires_source` | FAO generic stage lengths exist, but no variety-specific duration. |
| Growth phases (FAO generic sorghum, grain) | 20 / 35 / 40 / 30 (printed total 130; arithmetic 125) | day | S05 | Table 11, Sorghum | FAO generic sorghum | `verified_generic_not_cultivar` | Not variety-specific; extracted table has a total inconsistency; use with caution. |
| Kc initial / mid / end | 0.30 / 1.00–1.10 / 0.55 | fraction | S04 | Table 12, Sorghum – grain | FAO generic sorghum | `verified_generic_not_cultivar` | Initial value inherited from cereal group; not variety-specific. |
| Root depth | 1.0–2.0 | m | S06 | Table 22, Sorghum – grain | FAO generic sorghum | `verified_generic_not_cultivar` | Generic range. |
| Depletion fraction `p` | 0.55 | fraction | S06 | Table 22, Sorghum – grain | FAO generic sorghum | `verified_generic_not_cultivar` | Generic. |
| Water requirement | null | mm/season | S04 | ETc = Kc × ETo | unspecified | `requires_local_validation` | No fixed seasonal value; no local ETo/rain. |
| Nitrogen requirement | null | kg N/ha | — | — | unspecified | `requires_source` | No verified N recommendation. |
| Soil pH / texture / drainage / slope suitability | null | pH / class / degree | — | — | unspecified | `requires_source` | No crop suitability table found. |
| Salinity threshold `ECe` | 6.8 | dS/m | S06b | Table 23, Sorghum | FAO generic sorghum | `verified_generic_not_cultivar` | Generic; not local/variety-specific. |
| Yield potential | null | t/ha | — | — | unspecified | `requires_source` | No variety; no Banyumas yield trial found. |
| Pest host status | null | status | — | — | unspecified | `requires_source` | No WBC host-status source found. |

### 4.5 What the matrix does not prove

- `Kc`, root depth, stage lengths, and salinity thresholds are **FAO generic values**, not measurements of Inpari 32, Anjasmoro, Vima-1, or a specific sorghum variety.
- Official variety duration/yield values are **national descriptions**, not Banyumas field validation.
- `Water requirement = null` means there is no verified fixed seasonal value. It must be calculated with local ETo, rainfall, irrigation, and soil data.
- `Nitrogen requirement = null` means no verified N recommendation was found. Do not use Arya’s soybean ledger or Arief’s soybean balance as N requirements for paddy, mung bean, or sorghum.
- `Suitability = null` means pH/texture/drainage/slope parameters are not available.
- Sorgum cannot be treated as a specific variety.

---

## 5. Missing Parameter List

### 5.1 Cross-crop missing parameters

| Missing parameter | Why needed | Consumer | Expected unit | Existing data | Source needed |
|---|---|---|---|---|---|
| Cultivar-specific Kc by stage | Accurate ETc for each variety | Water requirement calculator | fraction | Only FAO generic crop Kc | Variety trial/agronomic source |
| Cultivar-specific phase lengths | Calendar and water-stage timing | Calendar/water evaluator | day | Only FAO generic stage lengths | Variety trial/agronomic source |
| Cultivar-specific root depth | TAW/RAW and water stress | Water evaluator | m | Only FAO generic ranges | Local soil/root study |
| Seasonal water requirement | Candidate `water_demand_mm` | Water evaluator | mm/season | None verified; repo scenario values are assumptions | Local ETo, rainfall, irrigation, soil data |
| Nitrogen requirement | N budget and fertilizer recommendation | N evaluator | kg N/ha | None verified; Arya/Arief constants are not crop requirements | Agronomic/fertilizer recommendation source |
| Soil pH range | Suitability | Suitability evaluator | pH | None | Soil/crop suitability source |
| Soil texture/drainage class | Suitability | Suitability evaluator | class | None | Soil survey/crop suitability source |
| Slope limit | Suitability/erosion | Suitability evaluator | degree | None | Crop suitability source |
| Salinity threshold per cultivar | Suitability | Suitability evaluator | dS/m | FAO generic for rice/soybean/sorghum; not Vima-1 | Variety/local source |
| Planting window start/end | Calendar | Calendar evaluator | date | None | KATAM Banyumas or local Dinas |
| Harvest window/date | Calendar | Calendar evaluator | date | None | KATAM/local trial |
| Fallow/turnaround duration | Rotation feasibility | Calendar evaluator | day | Only demo non-host values | Local practice/KATAM |
| Pest host status (WBC and others) | Pest-cycle interruption | Pest evaluator | enum | Paddy WBC reaction only | Crop protection source |
| Pest population/migration parameters | Pest model | Pest evaluator | various | Only WBC survival formula | Entomology source |
| Yield under local management | Financial evaluation | Yield/financial evaluator | t/ha | National variety values only | Banyumas trial/BPS/Dinas |
| Crop price and production cost | Financial evaluation | Financial evaluator | IDR/kg; IDR/ha | None crop-specific | Banyumas market/cost data |
| SOC change | `RotationCandidate.soc_change_ton_ha` | Soil evaluator | t/ha | Demo values only | Soil carbon study |
| Crop-level K_sat requirement | `RotationCandidate.required_ksat_mm_day` | Water/suitability evaluator | mm/day | Demo values only | Local soil/crop source |

### 5.2 Per-crop gaps

| Crop | Existing verified data | Still missing |
|---|---|---|
| Padi Inpari 32 | Official duration 120 days; average 6.3 t/ha; potential 8.42 t/ha; WBC reaction; FAO generic rice Kc/root/stage | Inpari 32 phase split; local Kc/root/water/N; pH/texture/drainage/slope suitability; Banyumas yield validation; local pest pressure; crop price/cost |
| Kedelai Anjasmoro | Official duration 82.5–92.5 days; yield 2.03–2.25 t/ha; FAO generic soybean Kc/root/stage | Anjasmoro phase split; local Kc/root/water/N; suitability; local yield; WBC host status; price/cost |
| Kacang hijau Vima-1 | Official duration 57 days; average 1.38 t/ha; potential 1.76 t/ha; FAO generic green gram Kc/root/stage | Vima-1 phase split; local Kc/root/water/N; suitability; local yield; WBC host status; price/cost; salinity |
| Sorgum | FAO generic sorghum Kc/root/stage/salinity | Variety identity; duration; phase split; local Kc/root/water/N; suitability; yield; pest host status; price/cost |

### 5.3 Local/KATAM gaps

- No KATAM Banyumas planting calendar or recommendation table was found in the repository.
- No official Banyumas crop trial parameter table was found.
- BPS Banyumas provides a statistics portal, not crop parameters; aggregate production data cannot substitute for Kc, root depth, N requirement, or suitability.
- Do not use Banyuwangi, national, or other-region values as Banyumas validation without explicit approval.

---

## 6. Proposed Crop Parameter Registry Design

### 6.1 Format recommendation

Use a combination:

1. **JSON Schema Draft 2020-12** for the registry file format and validation.
2. **One JSON file per crop/variety** for reviewability and Git history.
3. **Python frozen dataclasses** for internal use, following `src/models/land_cover.py` style.
4. **`jsonschema`** for validation; already available in the project environment.
5. **No database and no ML model** in the first version.

### 6.2 Proposed folder layout (not created in this task)

```text
contracts/
  crop_parameter_registry.schema.json
data/
  registry/
    sources.json                 # S01a, S01b, S02, ... with citation/URL/location
    units.json                   # day, mm, mm/season, m, fraction, t/ha, kg N/ha, dS/m, ...
    crops/
      padi_inpari_32_hdb.json
      kedelai_anjasmoro.json
      kacang_hijau_vima_1.json
      sorgum_unspecified.json
src/
  registry/
    models.py                    # dataclasses, no formulas
    loader.py                    # schema validation + source/unit resolution
```

### 6.3 Core schema

```text
CropRecord
  ├── schema_version
  ├── registry_version
  ├── crop_id
  ├── common_name
  ├── scientific_name
  ├── variety
  ├── region
  ├── parameters
  │   ├── identity
  │   ├── duration
  │   ├── water
  │   ├── root
  │   ├── nitrogen
  │   ├── calendar
  │   ├── suitability
  │   ├── pest
  │   └── yield_finance
  ├── record_status
  └── notes

ParameterValue
  ├── value
  ├── unit
  ├── source_id
  ├── location
  ├── cultivar
  ├── evidence_status
  ├── notes
  └── required_for[]
```

### 6.4 Field rules

| Field | Rule |
|---|---|
| `crop_id` | Stable slug; unique; e.g. `padi_inpari_32_hdb` |
| `scientific_name` | Required key; value may be `null` until taxonomy is verified |
| `variety` | Required key; `null` for unspecified sorghum |
| `value` | Number/string/array/`null`; `null` only with missing/requires-source status |
| `unit` | Required for every numeric parameter; explicit; reference `units.json` |
| `source_id` | Required for non-null values; `null` only for missing/requires-source |
| `location` | Page/table/section/URL fragment |
| `cultivar` | Named cultivar or explicit `FAO generic`/`unspecified` |
| `evidence_status` | `verified_official_national`, `verified_generic_not_cultivar`, `reproduced_official`, `standard_nomenclature`, `assumption_based`, `synthetic`, `hardcoded_demo`, `not_found`, `requires_source`, `requires_local_validation` |
| `notes` | Limitations and local-validation gaps |
| `record_status` | `complete`, `incomplete`, `conflicting`, `deprecated` |

### 6.5 Validation rules

1. Reject unknown fields until a new schema version adds them.
2. A `null` value must use `not_found` or `requires_source`; it cannot be `verified_*`.
3. A `verified_*` value must have a `source_id` and a source record with URL/location.
4. A generic FAO value must be marked `verified_generic_not_cultivar`; it cannot be presented as a cultivar measurement.
5. A national variety value must be marked `verified_official_national`; it cannot be presented as Banyumas validation.
6. `unit` must resolve in `units.json`.
7. Duplicate `crop_id` or duplicate parameter keys are rejected.
8. Missing required parameters must cause `insufficient_parameters` in the consuming module; no defaults.
9. `record_status: complete` requires all parameters declared for the supported capability to be non-null and sourced.
10. No source-less or synthetic value may be silently promoted to verified.

### 6.6 How agronomy modules read the registry

```text
CropRegistryLoader.load(crop_id) -> CropRecord
CropRecord.get("kc_mid") -> ParameterValue
ParameterValue.value / unit / source_id / evidence_status
```

Consumers:

- **Suitability evaluator**: reads `suitability.*`; if null → `insufficient_parameters`.
- **Water requirement calculator**: reads `duration`, `water.kc_*`, `root.depth_m`, `root.depletion_fraction`; uses local ETo/rain; never defaults Kc.
- **Planting calendar evaluator**: reads `calendar.*`; if null → no calendar recommendation.
- **Rotation candidate builder**: reads crop sequence/calendar/water/N/yield/finance; fills `RotationCandidate` only when complete.
- **Pareto integration**: passes completed candidates to `solve_pareto_epsilon_constraint`; does not duplicate the solver.

---

## 7. Example Registry Record

The following example uses only values supported by S01a/S01b/S04/S06. Values not found remain `null`. This is a schema example, not a local recommendation.

```json
{
  "schema_version": "0.1.0-proposed",
  "registry_version": "0.1.0-proposed",
  "crop_id": "padi_inpari_32_hdb",
  "common_name": "Padi",
  "scientific_name": "Oryza sativa L.",
  "scientific_name_source": "S09",
  "variety": "Inpari 32 HDB",
  "region": "Banyumas",
  "parameters": {
    "growing_duration_days": {
      "value": 120,
      "unit": "day",
      "source_id": "S01a",
      "location": "Section 5, Inpari 32 HDB",
      "cultivar": "Inpari 32 HDB",
      "evidence_status": "verified_official_national",
      "notes": "National extension description; not a Banyumas field trial.",
      "required_for": ["planting_calendar", "crop_water_requirement"]
    },
    "kc_initial": {
      "value": 1.05,
      "unit": "fraction",
      "source_id": "S04",
      "location": "Table 12, Rice",
      "cultivar": "FAO generic rice",
      "evidence_status": "verified_generic_not_cultivar",
      "notes": "Generic FAO-56 value; not measured for Inpari 32.",
      "required_for": ["crop_water_requirement"]
    },
    "kc_mid": {
      "value": 1.20,
      "unit": "fraction",
      "source_id": "S04",
      "location": "Table 12, Rice",
      "cultivar": "FAO generic rice",
      "evidence_status": "verified_generic_not_cultivar",
      "notes": "Generic FAO-56 value; not measured for Inpari 32.",
      "required_for": ["crop_water_requirement"]
    },
    "kc_end": {
      "value": "0.90-0.60",
      "unit": "fraction",
      "source_id": "S04",
      "location": "Table 12, Rice",
      "cultivar": "FAO generic rice",
      "evidence_status": "verified_generic_not_cultivar",
      "notes": "Range as printed in FAO-56; not Inpari 32-specific.",
      "required_for": ["crop_water_requirement"]
    },
    "root_depth_m": {
      "value": "0.5-1.0",
      "unit": "m",
      "source_id": "S06",
      "location": "Table 22, Rice",
      "cultivar": "FAO generic rice",
      "evidence_status": "verified_generic_not_cultivar",
      "notes": "Range; local soil/rooting depth unverified.",
      "required_for": ["crop_water_requirement"]
    },
    "water_requirement_mm_season": {
      "value": null,
      "unit": "mm/season",
      "source_id": null,
      "location": null,
      "cultivar": "Inpari 32 HDB",
      "evidence_status": "requires_local_validation",
      "notes": "No fixed seasonal value; compute from local ETo, rainfall, irrigation, and Kc. Repo 800 mm scenario is not a verified parameter.",
      "required_for": ["crop_water_requirement", "rotation_candidate"]
    },
    "nitrogen_requirement_kg_ha": {
      "value": null,
      "unit": "kg N/ha",
      "source_id": null,
      "location": null,
      "cultivar": "Inpari 32 HDB",
      "evidence_status": "requires_source",
      "notes": "No verified N recommendation found.",
      "required_for": ["nitrogen_evaluation"]
    },
    "yield_average_t_ha": {
      "value": 6.3,
      "unit": "t/ha GKG",
      "source_id": "S01a",
      "location": "Section 5, Inpari 32 HDB",
      "cultivar": "Inpari 32 HDB",
      "evidence_status": "verified_official_national",
      "notes": "National average description; not Banyumas.",
      "required_for": ["yield_financial_evaluation"]
    },
    "yield_potential_t_ha": {
      "value": 8.42,
      "unit": "t/ha GKG",
      "source_id": "S01b",
      "location": "Article body",
      "cultivar": "Inpari 32 HDB",
      "evidence_status": "verified_official_national",
      "notes": "National potential; not Banyumas.",
      "required_for": ["yield_financial_evaluation"]
    }
  },
  "record_status": "incomplete",
  "notes": "Incomplete: local water/N/suitability/yield validation missing. Generic FAO values are not cultivar measurements."
}
```

---

## 8. Recommended Next Implementation Steps

1. **Approve the source/evidence policy.**
   - Decide whether FAO-56 generic values may be stored as provisional values with `verified_generic_not_cultivar`.
   - Decide whether national variety descriptions may be used as provisional `verified_official_national` values.
   - Require `null` for missing local parameters.

2. **Create the registry schema and loader only.**
   - Add the proposed JSON Schema, `sources.json`, `units.json`, and loader tests.
   - Do not add synthetic defaults.
   - Reject a verified value without source/location.

3. **Seed the four crop records with sourced values.**
   - Inpari 32: duration, average/potential yield, WBC reaction, FAO generic rice Kc/root/stage.
   - Anjasmoro: duration, yield range, FAO generic soybean Kc/root/stage.
   - Vima-1: duration, average/potential yield, FAO generic green gram Kc/root/stage.
   - Sorgum: scientific name and FAO generic sorghum Kc/root/stage; leave variety/duration/yield null.
   - Keep all local/N/suitability/price fields null.

4. **Obtain missing local and KATAM data.**
   - Export KATAM Banyumas planting calendar/recommendation for padi, kedelai, and kacang hijau (and sorghum if available).
   - Request Banyumas Dinas Pertanian/BPS crop trial/local yield data.
   - Do not use Banyuwangi or other regions as Banyumas validation.

5. **Resolve agronomic data gaps with sources.**
   - Cultivar-specific Kc/phase/root depth/water requirement.
   - N requirement and N fixation assumptions.
   - pH/texture/drainage/slope suitability.
   - Pest host status beyond WBC.
   - Crop prices, costs, and local yield response.
   - Sorghum variety identity.

6. **Implement agronomy modules only after the registry is populated.**
   - Suitability → calendar → water requirement → candidate builder.
   - Reuse `BanyumasWaterBalanceSimulator` by parameterization, not a second water-balance engine.
   - Reuse `RotationCandidate` and `solve_pareto_epsilon_constraint` unchanged.
   - If parameters are missing, return `insufficient_parameters`.

7. **Add tests.**
   - Schema/source/unit validation.
   - Null/missing handling.
   - Generic vs cultivar vs local status cannot be mislabeled.
   - Candidate builder fails closed.
   - Pareto wrapper tests.

8. **Integrate API/UI only after data validation.**
   - No static “verified” labels.
   - Show evidence status and missing-data warnings.
   - Do not display national/generic values as Banyumas measurements.

---

## 9. Open Questions

1. Is FAO-56 generic Kc/root depth acceptable as a provisional value, or must every value be cultivar-specific before storage?
2. Should Inpari 32/Anjasmoro/Vima-1 values from national descriptions be labeled `verified_official_national` or `provisional_national`?
3. Which sorghum variety is intended? Without a variety, most sorghum parameters must remain `null`.
4. Does KATAM provide downloadable Banyumas data, or only an interactive portal? Who owns access/export?
5. Which Banyumas Dinas Pertanian/BPS dataset is authoritative for local yield, water, and crop management?
6. Is “nitrogen requirement” intended as fertilizer N recommendation or N fixation/balance? Both are different and currently missing.
7. Which pH/texture/drainage/slope thresholds are approved for crop suitability?
8. Should local Banyumas validation override national variety descriptions, or be stored as a separate evidence layer?
9. Which crop prices/costs are acceptable for financial evaluation?
10. Who approves registry records and evidence statuses?

---

## 10. Bottom Line

**What already exists:**

- Official national variety descriptions for Inpari 32, Anjasmoro, and Vima-1 (duration/yield/pest reaction where available).
- FAO-56 generic Kc, stage lengths, root-depth ranges, depletion fractions, and salinity thresholds for rice, soybean, green gram/cowpea, and sorghum.
- Repository fragments: crop matrix, fixed water balance, N/fiscal/Pareto models, static UI scenarios.
- Contract fields for rotation scenarios, but no crop registry.

**What is missing:**

- Crop parameter registry and schema.
- Inpari 32 data in the repository.
- Cultivar-specific Kc, phase lengths, root depth, water requirement, N requirement, and suitability.
- Banyumas local validation and KATAM Banyumas calendar.
- Crop-level yield/finance data.
- Pest host-status matrix beyond paddy WBC reaction.
- Sorghum variety identity and variety-specific parameters.
- Tests for the registry and agronomy modules.

**What needs verification from the team:**

- Whether generic FAO values are acceptable provisionally.
- Whether national variety descriptions are acceptable as `verified_official_national`.
- Sorghum variety.
- KATAM/Banyumas data access and ownership.
- N requirement vs N fixation definition.
- Suitability thresholds and local validation data.
- Registry evidence-status policy.

**Is the repository ready for registry implementation?**

- **Schema/loader skeleton:** yes.
- **Seed values:** partially; identity/duration/yield and generic FAO water/root values can be stored with explicit evidence status.
- **Production agronomy:** no; local and cultivar-specific parameters are missing.
- **Full crop rotation integration:** no; suitability, calendar, water requirement, candidate generation, and local validation are not ready.

The correct next step is to implement the registry structure with `null` and evidence statuses, seed only sourced values, and collect the missing local/KATAM data before any agronomy calculation treats these values as Banyumas-specific.
