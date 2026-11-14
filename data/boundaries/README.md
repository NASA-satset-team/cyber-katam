# data/boundaries

Administrative and analysis boundaries.

## Current contents

- `banyumas_paddy_roi.geojson` — **copy of the received file** from Arief, kept
  here for stable in-repo access. The original remains untouched at
  `external/ariefs_workresult/banyumas_paddy_roi.geojson`.

## Critical caveat

Despite its name, `banyumas_paddy_roi.geojson` is a **rectangular bounding box**
(108.92–109.38 E, −7.60 to −7.25 S), not a verified paddy-field mask. It was
written by `export_roi_geojson()` in `gee_environment_init.py`.

A real paddy mask requires an ESA WorldCover class-40 or equivalent cropland mask
that has actually been exported, clipped, and inspected. Until then:

- do not clip H3 cells with this bounding box and call them paddy fields;
- do not claim `land_cover = "Paddy Field"`.
