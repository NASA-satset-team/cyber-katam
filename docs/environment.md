# Development environment (Task 0 record)

Recorded: 2026-11-14 · Windows · PowerShell

## 1. Machine state

| Item | Value |
|---|---|
| OS | Windows (win32) |
| Python install manager | 26.4 (`py`) |
| Interpreter used | **Python 3.12.10** (installed during Task 0 as `3.12[-64]`) |
| Other interpreter present | Python 3.14.2 (`3.14[-64]`, previously the default) |
| Virtual environment | `.venv/` (recreated with Python 3.12.10, gitignored) |
| pip | 25.x inside `.venv` |
| Git | 2.54.0.windows.1 |
| GitHub CLI | **not installed** |

Python 3.12 is the recommended version for this project because the geospatial
stack (geopandas, rasterio, shapely, pyproj) has reliable cp312 wheels on Windows.

## 2. Why the environment was rebuilt

The original `.venv` used Python 3.14.2 and contained only `numpy` and `openpyxl`.
Installing current wheels for `pandas`, `pyarrow`, and `h3` failed at import with:

```text
ImportError: DLL load failed while importing ...:
An Application Control policy has blocked this file.
```

Cause: Windows **Smart App Control** is enforced
(`VerifiedAndReputablePolicyState = 1`, user-mode code-integrity enforcement = 2).
It blocked unsigned binary extensions from the newest wheels. This is an OS
security setting; it was **not** disabled or bypassed.

Resolution: install Python 3.12.10, recreate `.venv`, and use older, widely
distributed pinned wheels that the policy permits. No security setting was changed.

## 3. Installed core packages (verified)

Command:

```powershell
.venv\Scripts\python.exe -c "import importlib.metadata as md; ..."
```

| Package | Version | Import |
|---|---|---|
| numpy | 2.1.3 | OK |
| pandas | 2.2.3 | OK |
| openpyxl | 3.1.5 | OK |
| pyarrow | 17.0.0 | OK |
| h3 | 4.1.2 | OK |
| jsonschema | 4.23.0 | OK |
| pytest | 8.3.4 | OK |

H3 functional check:

```text
h3.latlng_to_cell(-7.45, 109.17, 9) -> 898d8d654cbffff
len(h3.grid_disk(cell, 2)) -> 19
```

## 4. Optional packages (NOT installed)

Listed in `requirements-optional.txt`:

- `earthengine-api`
- `earthaccess`
- `geopandas`
- `shapely`
- `rasterio`

They were deliberately not installed because no Task 0 work requires live Earth
Engine, Earthdata, or raster I/O. Install only when the task needs them, then pin
the exact versions.

## 5. Reproducibility checks performed

| Check | Result |
|---|---|
| `import numpy, pandas, openpyxl, pyarrow, h3, jsonschema, pytest` | pass |
| Parse Arya's four engines with `ast.parse` | pass |
| Import Arya's four engines | pass |
| Run each Arya `__main__` demo in a scratch directory | pass |
| Run Arief's `task7_agronomy_matrix.py` | pass |
| Run Arief's `nitrogen_dynamics.py` | pass |
| Run Arief's `task10_precomputed_geojson.py` | pass (synthetic; output differs each run) |
| Run Arief's `task12_smoke_test_deconstruction.py` | misleading "success" — see KI-11 |
| Run Arief's `task11_benchmark.py` | pass but meaningless — uses `time.sleep()` |
| Run Arief's `task9_climatology_baseline.py` | **fail** on Windows console (`μ` / cp1252) — see KI-04 |
| `pytest tests/` | no automated tests exist yet |

Arief's scripts were executed from a temporary directory so that the received
artifacts in `external/ariefs_workresult/` were never overwritten.

## 6. Reproduce the environment

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest tests/ -v
```

If a future wheel is blocked by Smart App Control, choose another currently
supported pinned version or ask the user to review the OS policy. Do not disable
security controls automatically.
