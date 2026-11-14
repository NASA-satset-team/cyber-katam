# CYBER-KATAM

AI-assisted agricultural decision support for paddy-field rotation planning in
Banyumas, Central Java. The system is intended to combine NASA satellite
observations, soil/water physics, agronomic optimisation, and a geospatial
dashboard.

> **Project status: Task 0 — repository setup and audit only.**
> No production pipeline, AI Core module, or web application is complete yet.
> The only datasets currently in the repository are **synthetic fixtures** and
> one **bounding-box** boundary. They are not NASA observations.

**Interactive prototype v0.2:** the React/Vite application in `web-app/src/`
now provides three Indonesian-language experiences: a dark geospatial analyst
dashboard, a light Farmer/PPL mode, and a four-block XAI audit certificate with
sequential simulated verification gates. It includes H3-7–9 geometry, five
visual layer toggles, deterministic UI climate scenarios, three illustrative
rotations, and a real client-rendered PNG discussion card under 150 KB.
All environmental and fiscal values are explicitly simulated; official
planting advice remains withheld. No NASA integration or operational AI is
claimed. See [`docs/mvp.md`](docs/mvp.md); the Task 0 audit below remains a
historical baseline.

## 1. What is true today

| Area | State |
|---|---|
| Git repository | Initialized locally, branch `main`, **no remote yet**, no pushed history |
| Python environment | `.venv` on **Python 3.12.10**; core imports verified |
| Arief's data pipeline | Received and archived unchanged; **no verified NASA export** |
| Arya's physics engines | Received, importable, demo-runnable with synthetic inputs |
| AI Core | Not implemented; readiness assessment in `docs/ai_core_readiness.md` |
| Shared contract | No ratified JSON Schema; only a non-JSON sample log |
| GIS viewer / web app | Not received; placeholder folders |
| H3 dataset | 1,000 synthetic res-9 cells from `grid_disk`; random attributes |

Read the three audit documents before writing code:

1. `docs/project_file_inventory.md` — every received file, what is real vs synthetic.
2. `docs/nasa_data_inventory.md` — target NASA datasets, IDs, DOIs, units, status.
3. `docs/ai_core_readiness.md` — which AI Core modules can start and what is missing.

## 2. Repository structure

```text
cyberkatam/
├── .github/
│   └── pull_request_template.md
├── contracts/                  # ratified JSON Schemas (none yet) + rules
├── data/
│   ├── raw/                    # local only, gitignored
│   ├── processed/              # local only, gitignored
│   ├── mock/                   # synthetic fixtures (points to external artifacts)
│   └── boundaries/             # bbox copy + caveat
├── docs/
│   ├── project_file_inventory.md
│   ├── nasa_data_inventory.md
│   ├── ai_core_readiness.md
│   ├── contract_governance.md
│   ├── environment.md
│   └── audit_report_phase1.md
├── external/
│   ├── aryas_workresult/       # received work, unchanged
│   └── ariefs_workresult/      # received work + original ZIP, unchanged
├── src/
│   ├── contracts/
│   ├── engines/
│   ├── models/
│   └── utils/
├── tests/
│   └── manual/                 # non-pytest exploratory scripts
├── data-pipeline/              # Arief's integration home
├── physics-engines/            # Arya's integration home
├── gis-viewer/                 # Rifaldi
├── web-app/                    # Rafi
├── .gitignore
├── requirements.txt            # core, tested
├── requirements-optional.txt   # geospatial/NASA extras, not installed
├── CONTRIBUTING.md
└── README.md
```

`external/` is **read-only reference material**. Do not edit those files. Create
integration copies in the owning workstream folder and document the change.

## 3. Environment setup (Windows)

Python **3.12** is required for the geospatial stack. This machine also has
Python 3.14, but the newest wheels for `pandas`, `pyarrow`, and `h3` were blocked
by Windows Smart App Control there. Python 3.12.10 with the pinned versions works.

```powershell
# From the repository root
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Verify
python -c "import numpy, pandas, openpyxl, pyarrow, h3, jsonschema, pytest; print('core OK')"
python -m pytest tests/ -v
```

Optional packages (only if your task needs Earth Engine, Earthdata, or raster I/O):

```powershell
python -m pip install -r requirements-optional.txt
```

Exact versions and the Smart App Control finding are recorded in
`docs/environment.md`.

Never commit `.venv/`, `.env`, Earth Engine credentials, service-account JSON,
tokens, or raw satellite granules. `.gitignore` already covers them.

## 4. Data provenance warning

The following files are **synthetic or assumed**, regardless of their names:

- `banyumas_h3_precomputed.geojson` — 1,000 H3 res-9 cells generated with
  `grid_disk` around one centre point. `land_cover` is hardcoded to
  `"Paddy Field"`. MODIS_LST, SMAP_ROOTZONE, GPM_P95, NDVI, and MBSI are
  `random.uniform()` values. The cells are not clipped to a paddy mask.
- `climatology_baseline_banyumas.parquet` — sine wave + Gaussian noise.
- `data_pipeline_benchmark.json` — generated with `time.sleep()`.
- `banyumas_paddy_roi.geojson` — a rectangular bounding box, not a paddy mask.
- `crop_rotation_matrix.json`, `nitrogen_balance_output.json` — agronomic
  assumptions that still need validation.
- `water_balance_banyumas.xlsx` — simulated series, despite "GPM" and
  "NASA POWER" column labels.

No satellite data, H3 index, or climatology value may be invented to fill gaps.
If a value is missing, the correct output is an explicit missing/abstain state.

## 5. NASA datasets and spatial scale

Target datasets (details, DOIs, GEE IDs, units, QA, status in
`docs/nasa_data_inventory.md`):

1. NASA SMAP L4 `SPL4SMGP` v8 — 3-hourly, ~9 km, surface and root-zone soil moisture.
   GEE: `NASA/SMAP/SPL4SMGP/008`.
2. NASA ECOSTRESS `ECO_L2T_LSTE` v2 — 70 m, irregular ISS overpasses, LST in kelvin.
   GEE: `NASA/ECOSTRESS/L2T_LSTE/V2`.
3. NASA GPM IMERG v7 — 0.1°, half-hourly, precipitation in mm/hr.
   GEE: `NASA/GPM_L3/IMERG_V07`.
4. NASA HLS v2.0 — `HLSL30` and `HLSS30`, 30 m surface reflectance.
   GEE: `NASA/HLS/HLSL30/v002`, `NASA/HLS/HLSS30/v002`.
5. NASA POWER Daily API — optional supplementary meteorology, not a satellite
   substitute.

**Scale rule:** an H3 res-9 cell averages ~0.105 km². A 9 km SMAP pixel is
~81 km² (roughly 770 H3-9 cells) and an IMERG 0.1° cell is ~120 km² at this
latitude (roughly 1,100+ cells). Therefore one SMAP or GPM pixel cannot supply an
independent observation per H3 cell. Preserve native resolution and document the
aggregation or downscaling method.

## 6. GitHub collaboration setup

The local repository is initialized but has **no remote**. Nothing has been
pushed. To publish it:

```powershell
# After the remote exists (created by the owner, or via GitHub CLI)
git remote add origin https://github.com/<OWNER>/cyber-katam.git
git branch -M main
git push -u origin main
```

> Do not run `git push --force` and do not overwrite an existing GitHub
> repository. If the remote already has commits, stop and reconcile first.

### Creating the shared private repository

GitHub CLI is **not installed** on this machine. Either install it
(`winget install --id GitHub.cli`) and authenticate (`gh auth login`), or create
the repository manually in the GitHub web UI.

Only after the user confirms the repository URL and the initial push:

```powershell
gh repo create cyber-katam --private --source . --remote origin --push
```

Then invite collaborators (real usernames only, no placeholders):

```powershell
gh api repos/<OWNER>/cyber-katam/collaborators/<USERNAME> -X PUT -f permission=push
```

### Branch and PR workflow

1. Each member clones the same repository.
2. Each member works on their own branch:
   `feature/arya-...`, `feature/arief-...`, `feature/aqila-...`,
   `feature/rifaldi-...`, `feature/rafi-...`, plus `fix/...` and `docs/...`.
3. Push the branch and open a Pull Request into `main`.
4. Changes to shared contracts require review from all affected workstreams.
5. `main` only receives reviewed, tested changes.

Full rules: `CONTRIBUTING.md`. PR checklist: `.github/pull_request_template.md`.

## 7. Contributors and ownership

| Member | Workstream | Folder |
|---|---|---|
| Arya | Physics, water balance, nitrogen ledger, fiscal-actuarial | `physics-engines/` |
| Arief | Satellite acquisition, H3 harmonization, preprocessing | `data-pipeline/` |
| Aqila | AI Core, contracts, optimisation, XAI, uncertainty, tests | `src/`, `contracts/`, `tests/` |
| Rifaldi | GIS / WebGL / Deck.gl viewer | `gis-viewer/` |
| Rafi | Frontend application | `web-app/` |

## 8. Next steps (not part of Task 0)

1. Ratify `grid_cell_contract.json` v1.0 and add a real JSON Schema.
2. Fix and actually execute the NASA extraction scripts; inspect exported data.
3. Replace synthetic H3 attributes with real observations at documented scale.
4. Build a real paddy mask and clipping step.
5. Implement AI Core modules in the order given in `docs/ai_core_readiness.md`.
6. Replace the `time.sleep()` benchmark with a real pipeline measurement.

Task 0 stops after setup and audit. AI Core implementation starts in the next task.
