# data/mock (synthetic fixtures)

This folder is for **explicitly synthetic** fixtures used by unit tests and
AI Core development.

## Important

The synthetic H3 dataset received from Arief is intentionally kept in
`external/ariefs_workresult/` as the immutable received artifact. It is not copied
here to avoid two diverging copies. Read it from there and treat every value as
fake:

`external/ariefs_workresult/banyumas_h3_precomputed.geojson`

- 1,000 resolution-9 H3 cells generated with `grid_disk` around one center point.
- `land_cover` hardcoded to `"Paddy Field"`.
- MODIS_LST, SMAP_ROOTZONE, GPM_P95, NDVI, and MBSI are `random.uniform()` values.
- No paddy-field mask clipping and no real NASA observation.

The synthetic climatology baseline is:

`external/ariefs_workresult/climatology_baseline_banyumas.parquet`
(36 month×dekad rows generated from a sine wave plus Gaussian noise).

When you need a canonical mock dataset for tests, copy these files into a
timestamped fixture folder and record the provenance in the test docstring.
Never rename them to sound like observations.
