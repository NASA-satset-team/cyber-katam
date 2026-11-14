# Arief's received work — provenance

Received archive:

`_source_archive/Arief_work-20261114T003733Z-1-001.zip`

- Original SHA-256: `165679277C9165225E95B6BF1ED8B70D8474680414D0FA4311801FDD3DB17DA0`
- Extracted on: 2026-11-14
- Published as: `external/ariefs_workresult/`

## Preservation rules applied

- The ZIP is kept unchanged in `_source_archive/`.
- Every extracted file is byte-identical to its ZIP entry (hash comparison: 0
  mismatches).
- No source file was edited, renamed, moved, or deleted.
- `clean_data_modules/` is **not** a second implementation. It is a byte-identical
  copy of six root-level scripts, produced by
  `task12_smoke_test_deconstruction.py`. Both copies are kept.

Verified duplicate pairs (identical SHA-256):

| File | SHA-256 prefix |
|---|---|
| `nitrogen_dynamics.py` | `C162CACAE1599312` |
| `task7_agronomy_matrix.py` | `0A10F34C69FF1660` |
| `task9_climatology_baseline.py` | `39B98B24077D89C0` |
| `task10_precomputed_geojson.py` | `BB44555A126A435A` |
| `task11_benchmark.py` | `DB5505AF1DAABC98` |
| `task12_smoke_test_deconstruction.py` | `A4AA04C728553860` |

The root copy is treated as the canonical received source.

## What is real and what is synthetic

**Nothing in this folder is a verified NASA observation.**

| Artifact | Status |
|---|---|
| `banyumas_h3_precomputed.geojson` | Synthetic: random attribute values, `grid_disk` geometry, hardcoded land cover |
| `climatology_baseline_banyumas.parquet` | Synthetic: sine wave + Gaussian noise |
| `crop_rotation_matrix.json` | Hand-written agronomic assumptions, not measured |
| `nitrogen_balance_output.json` | Output of an assumption-based model |
| `data_pipeline_benchmark.json` | Produced with `time.sleep()`, not a real benchmark |
| `banyumas_paddy_roi.geojson` | A rectangular bbox, not a paddy mask |
| `extract_*.py` | GEE scripts, not verified to have exported anything; HLS script uses Sentinel-2 |

Full details: `docs/project_file_inventory.md`.
