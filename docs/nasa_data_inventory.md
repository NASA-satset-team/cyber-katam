# NASA data inventory and integration plan

Last verified: 2026-11-14
Purpose: define the NASA datasets CYBER-KATAM intends to use, their official
identity, units, scale, quality handling, and **honest extraction status**.

> **Status rule:** no dataset is "integrated" until a real export exists, has been
> opened, its units/schema checked, and its provenance recorded. Code that queries
> a collection is not an extraction.

## 0. Executive status

| Dataset | Code exists | Real export verified | Ready for AI Core |
|---|---|---|---|
| SMAP L4 SPL4SMGP v8 | Yes (query only) | **No** | No |
| ECOSTRESS L2T LSTE v2 | Yes (query only) | **No** | No |
| GPM IMERG v7 | Yes, but wrong version/band | **No** | No |
| HLS HLSL30/HLSS30 v2 | No (uses Sentinel-2 instead) | **No** | No |
| NASA POWER Daily | No | **No** | No |

---

## 1. NASA SMAP L4 SPL4SMGP Version 8

| Field | Value |
|---|---|
| Official name | SMAP L4 Global 3-hourly 9 km EASE-Grid Surface and Root Zone Soil Moisture Geophysical Data, Version 8 |
| Short name | `SPL4SMGP` |
| Version | 8 (V008) |
| DOI | [10.5067/T5RUATAQREF8](https://doi.org/10.5067/T5RUATAQREF8) |
| Provider | NASA NSIDC DAAC |
| Product page | https://nsidc.org/data/spl4smgp/versions/8 |
| GEE collection | `NASA/SMAP/SPL4SMGP/008` |
| Variables used | `sm_surface` (0–5 cm), `sm_rootzone` (0–100 cm); optional `surface_temp`, `soil_temp_layer1` |
| Units | Soil moisture: **m³/m³** volumetric; temperature: K in the source product |
| Spatial resolution | **~9 km** EASE-Grid 2.0 (EPSG:6933) |
| Temporal resolution | **3-hourly** time-average fields |
| Date range | 2015-03-31 to present |
| Quality flags | No dedicated per-pixel QC band in the GEE asset. Use physical range checks (0–0.6 m³/m³), mask fill, and compare against `SPL4SMAU` assimilation diagnostics when needed |
| Native projection | EASE-Grid 2.0; do not treat it as EPSG:4326 pixels |
| Extraction status | **Not extracted.** `extract_smap_downscaling.py` only counts scenes and computes a mean image in memory. No GeoTIFF/CSV/Parquet exists |
| AI Core consumers | PVRS root-zone deficit, BF-EHSI surface moisture, uncertainty engine, water balance, scenario stress |

### Required fixes before integration

- The script name says "downscaling", but no downscaling exists. Either rename it
  or implement the native-support inversion from Arya's `pvrs_engine.py`.
- Add an actual export (`Export.image.toDrive` / `toCloudStorage`, or Earthdata
  download) and inspect the result.
- Preserve 3-hourly timestamps or explicitly aggregate to daily/dekadal with a
  documented statistic.
- Do not average 2015–2024 in one step for a "current" indicator.

---

## 2. NASA ECOSTRESS L2T LSTE Version 2

| Field | Value |
|---|---|
| Official name | ECOSTRESS Tiled Land Surface Temperature and Emissivity Instantaneous L2 Global 70 m, Version 2 |
| Short name | `ECO_L2T_LSTE` |
| Version | 002 |
| DOI | [10.5067/ECOSTRESS/ECO_L2T_LSTE.002](https://doi.org/10.5067/ECOSTRESS/ECO_L2T_LSTE.002) |
| Provider | NASA LP DAAC |
| Product page | https://www.earthdata.nasa.gov/data/catalog/lpcloud-eco-l2t-lste-002 |
| GEE collection | `NASA/ECOSTRESS/L2T_LSTE/V2` |
| Variables used | `LST` (kelvin), `QC`, `cloud`, `water`, `LST_err`, `EmisWB`, `view_zenith` |
| Units | LST: **kelvin**; must subtract 273.15 for °C. `LST_err`: K. Emissivity: dimensionless |
| Spatial resolution | **70 m** |
| Temporal resolution | **Irregular**: ISS/ECOSTRESS target acquisitions, not a fixed daily overpass |
| Date range | 2018-07-09 to present |
| Quality flags | `QC` bitmask (LST quality, error, temporal interpolation, sky, outlier, slope, snow/ice, land/water). **QC does not account for clouds** — use the `cloud` mask |
| Extraction status | **Not extracted.** `extract_ecostress_banyumas.py` averages all scenes and applies no QC or cloud filtering |
| AI Core consumers | PVRS LST anomaly, BF-EHSI thermal term, uncertainty engine, XAI evidence |

### Critical gap: ESI is not in L2T LSTE

Arya's PVRS requires `esi_actual` (evaporative stress index). The L2T LSTE
product provides **land surface temperature and emissivity only**. ESI must come
from a separate ECOSTRESS L4 ESI product or from an ET/PET calculation. That
source has **not** been selected or downloaded. Until it is, PVRS cannot be
computed with real data — LST alone is not ESI.

### Required fixes before integration

- Convert K → °C explicitly and record the conversion.
- Apply cloud mask and QC filters; report the retained-pixel fraction.
- Keep acquisition timestamps; do not collapse irregular overpasses into a
  single scene mean without a stated temporal rule.
- Handle no-observation days as missing, not as zero or as a climatological value.
- Select and document the ESI source separately.

---

## 3. NASA GPM IMERG Version 7

| Field | Value |
|---|---|
| Official name | GPM IMERG Final Precipitation L3 Half Hourly 0.1° × 0.1°, V07 (`GPM_3IMERGHH`) |
| Version | 07 (V07B current) |
| DOI | [10.5067/GPM/IMERG/3B-HH/07](https://doi.org/10.5067/GPM/IMERG/3B-HH/07) |
| Provider | NASA GES DISC |
| Product page | https://disc.gsfc.nasa.gov/datasets/GPM_3IMERGHH_07/summary |
| GEE collection | `NASA/GPM_L3/IMERG_V07` |
| Variables used | `precipitation` (mm/hr); optional `randomError`, quality index |
| Units | **mm/hr** (a rate, not mm per image) |
| Spatial resolution | **0.1° × 0.1°** (≈10 × 10 km near the equator) |
| Temporal resolution | **30 minutes** |
| Date range | 1998-01-01 to present in GEE; Final Run is delayed by roughly 3.5–4 months |
| Quality flags | IMERG quality index and random error fields; mask fill. GEE may blend Final and Late granules — record which product a workflow uses |
| Extraction status | **Not extracted.** `extract_gpm_precipitation.py` uses IMERG **V06** first and the band `precipitationCal`; V07 uses `precipitation`. It also silently falls back to CHIRPS |
| AI Core consumers | BF-EHSI rainfall erosivity, P95 trigger, water balance forcing, scenario stress |

### Required fixes before integration

- Use `NASA/GPM_L3/IMERG_V07` and band `precipitation`.
- Remove the silent CHIRPS fallback or make it an explicit, separately labelled
  dataset (CHIRPS is not NASA GPM).
- State the aggregation: daily total (mm/day) = Σ(half-hourly rate × 0.5 h).
- Define P95 on a stated series: daily totals, event maxima, or half-hourly rates.
  The current code takes P95 of half-hourly rates and calls it a rainfall trigger.
- Do not compare a P95 rate (mm/hr) with a threshold defined in mm/day.
- Export and inspect at least one season.

---

## 4. NASA HLS (HLSL30 + HLSS30) Version 2.0

| Field | Value |
|---|---|
| Official names | HLS Operational Land Imager Surface Reflectance and TOA Brightness Daily Global 30 m v2.0; HLS Sentinel-2 MSI Surface Reflectance Daily Global 30 m v2.0 |
| Short names | `HLSL30` v002, `HLSS30` v002 |
| DOIs | [10.5067/HLS/HLSL30.002](https://doi.org/10.5067/HLS/HLSL30.002), [10.5067/HLS/HLSS30.002](https://doi.org/10.5067/HLS/HLSS30.002) |
| Provider | NASA LP DAAC |
| Product page | https://hls.gsfc.nasa.gov/ |
| GEE collections | `NASA/HLS/HLSL30/v002`, `NASA/HLS/HLSS30/v002` |
| Variables used | Surface reflectance: red, NIR, SWIR1, SWIR2; `Fmask` QA |
| Units | Surface reflectance, dimensionless (scaled integers in the source; check the GEE catalog scale). Fill: `-9999` |
| Spatial resolution | **30 m** |
| Temporal resolution | Daily acquisition; combined L30+S30 revisit ~2–3 days |
| Date range | 2013-04-11 to present |
| Quality flags | `Fmask` cloud/shadow/cirrus/snow bits and aerosol bits; apply before compositing |
| Extraction status | **Not extracted.** `extract_hls_vegetation_bsi.py` uses `COPERNICUS/S2_SR_HARMONIZED`, which is **not NASA HLS** |
| AI Core consumers | BF-EHSI MBSI/bare soil, PVRS NDVI, bare-soil detector, XAI evidence |

### Band mapping (do not copy Sentinel-2 names)

| Index | HLSL30 (Landsat 8/9) | HLSS30 (Sentinel-2) |
|---|---|---|
| Red | `B4` | `B4` |
| NIR | `B5` | `B8A` (preferred) or `B8` |
| SWIR1 | `B6` | `B11` |
| SWIR2 | `B7` | `B12` |
| QA | `Fmask` | `Fmask` |

The current script uses Sentinel-2 `B8`, `B4`, `B11`, `B12` directly, which is
wrong for HLSL30 and bypasses HLS harmonization.

### Required fixes before integration

- Switch collections to `NASA/HLS/HLSL30/v002` + `NASA/HLS/HLSS30/v002`.
- Implement sensor-specific band mapping and normalize reflectance scale.
- Apply `Fmask` to remove cloud/shadow/cirrus and mask `-9999`.
- Composite L30 and S30 consistently (same period, same statistic).
- Compute NDVI and MBSI from reflectance; state the exact formula used.
  Arya's MBSI is `(SWIR1 − SWIR2 − NIR) / (SWIR1 + SWIR2 + NIR)`.
- Export a real time series for at least one H3 cell and inspect it.

---

## 5. NASA POWER Daily API (supplementary)

| Field | Value |
|---|---|
| Official name | NASA Prediction of Worldwide Energy Resources (POWER) Daily API |
| Version | API v2 (temporal/daily/point) |
| DOI | No dataset DOI; cite the NASA POWER project and API |
| Provider | NASA Langley Research Center |
| Product page | https://power.larc.nasa.gov/ |
| API | https://power.larc.nasa.gov/api/temporal/daily/point |
| GEE collection | Not a GEE collection |
| Variables used | `T2M` (°C), `T2M_MAX`/`T2M_MIN` (°C), `RH2M` (%), `PRECTOTCORR` (mm/day), `WS2M` (m/s), `ALLSKY_SFC_SW_DWN` (kWh/m²/day) |
| Spatial resolution | 0.5° × 0.625° meteorology (MERRA-2 based) |
| Temporal resolution | Daily |
| Date range | 1981-01-01 to near-present |
| Quality flags | API fill values and metadata; not a satellite retrieval with pixel QA |
| Extraction status | **Not implemented** |
| AI Core consumers | Water-balance ETo/forcing, scenario stress testing, gap filling for meteorological context |

### Rules

- Identify it explicitly as **NASA POWER meteorological data**. It is not a
  substitute for SMAP soil moisture, ECOSTRESS LST, GPM precipitation, or HLS
  reflectance.
- If POWER precipitation is used, do not present it as GPM IMERG.
- ETo must be computed with a documented method (e.g. FAO-56) from POWER
  variables; do not label a simulated ETo series as "NASA POWER".

---

## 6. Spatial scale and aggregation rule

H3 resolution 9 cells in the received dataset average **~0.102 km²** (102.03 km²
for 1,000 cells).

| Source | Native pixel area (approx.) | Relationship to one H3-9 cell | Correct operation |
|---|---:|---|---|
| SMAP L4, 9 km | ~81 km² | ~1 pixel covers **~790 H3 cells** | Aggregate H3 cells to the pixel, or perform documented downscaling. Never assign an independent SMAP observation to every cell |
| GPM IMERG, 0.1° at 7.45°S | ~122 km² | ~1 pixel covers **~1,200 H3 cells** | Same as SMAP: pixel-level value shared across cells |
| ECOSTRESS, 70 m | ~0.0049 km² | **~21 pixels per H3 cell** | Spatially average valid pixels into the cell |
| HLS, 30 m | ~0.0009 km² | **~113 pixels per H3 cell** | Spatially average/composite valid pixels into the cell |

Consequences:

- SMAP and GPM provide **one observation shared by many H3 cells**. Any apparent
  per-cell variation is interpolation or a model, not independent measurement.
- HLS and ECOSTRESS provide sub-cell detail; aggregation must report the valid
  pixel count and the statistic used.
- Record in every output whether a value is native, aggregated, interpolated, or
  downscaled. The PVRS `delta_support` error term exists precisely because this
  scale mismatch is real.

---

## 7. Cross-dataset consistency rules

- Never mix V06 and V07 IMERG in one time series.
- Never mix Sentinel-2 SR and HLS SR in one NDVI/MBSI series.
- Record units at the column level: `lst_celsius`, `sm_rootzone_m3m3`,
  `precip_mm_hr`, `precip_mm_day`, `reflectance_unitless`.
- Store timestamps in UTC and keep acquisition time for ECOSTRESS/HLS.
- QA filtering must be reproducible: record thresholds and retained fraction.
- A missing observation is `null`/masked, never zero, never climatology, never a
  random draw.
- Extraction scripts must write a manifest with collection ID, version, date
  range, ROI, band names, units, scale, QA rule, row/pixel count, and checksum.

## 8. What still needs extraction

1. SMAP: export 3-hourly/daily `sm_surface` and `sm_rootzone` for Banyumas;
   inspect units and plausible range.
2. ECOSTRESS: export LSTE with QC/cloud filtering and timestamps; separately
   source an ESI product.
3. GPM: export V07 `precipitation`; build daily totals and a documented P95.
4. HLS: export L30 and S30 reflectance with `Fmask`; compute NDVI/MBSI with the
   correct band mapping.
5. POWER: optional daily point series for the water-balance module.

No AI Core module should be marked "tested with real data" until at least one of
these exports exists and is inspected.
