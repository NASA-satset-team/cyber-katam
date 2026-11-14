# data-pipeline

Owner: **Arief** — satellite acquisition, H3 harmonization, and preprocessing.

## Current status (Task 0)

Arief's received scripts are preserved unchanged in:

`external/ariefs_workresult/`

They have **not** been moved or edited here, per the preservation rules for Task 0.
The received ZIP is stored at
`external/ariefs_workresult/_source_archive/Arief_work-20261114T003733Z-1-001.zip`.

This folder is the intended home for cleaned, integration-ready copies once Arief
confirms the changes in a dedicated PR.

## What does not work yet

- No NASA dataset has been exported and inspected end-to-end.
- `extract_hls_vegetation_bsi.py` uses `COPERNICUS/S2_SR_HARMONIZED`, not HLS.
- `extract_gpm_precipitation.py` uses IMERG V06 first and `precipitationCal`,
  while the documented target is IMERG V07 (`precipitation`, mm/hr).
- `extract_ecostress_banyumas.py` computes a scene mean but applies no QC/cloud
  filtering and no per-observation handling.
- Extraction scripts mostly print counts; several never write a data file.
- `task9_climatology_baseline.py` generates synthetic values, not climatology.
- `task11_benchmark.py` uses `time.sleep()` and is not a pipeline benchmark.

Do not integrate these as production data sources until each is fixed and its
output is verified. Details: `docs/project_file_inventory.md` and
`docs/nasa_data_inventory.md`.
